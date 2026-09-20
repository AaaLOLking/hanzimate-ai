"use client";

import { ToolActivityPanel } from "@/features/live/tool-activity";
import type { ToolActivity } from "@/features/live/tool-client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  type CSSProperties,
  type FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { AppShell } from "@/components/app-shell";
import { createAudioMeter, type AudioMeterStop } from "@/features/live/audio-meter";
import {
  isFatalProviderError,
  parseProviderEvent,
} from "@/features/live/provider-events";
import {
  connectQwenWebRtc,
  type QwenWebRtcConnection,
} from "@/features/live/qwen-webrtc";
import {
  initialLiveRuntime,
  projectLiveView,
  type LiveRuntimeState,
} from "@/features/live/state";
import { buildPracticeSessionPayload } from "@/lib/practice";
import {
  ApiError,
  apiRequest,
  downloadConversation,
  type ConversationScenario,
  type ErrorEvent,
  type RealtimeConnection,
  type SessionEvent,
  type SessionEventType,
  type SessionSummary,
  type Utterance,
  type VoiceSession,
  type VoiceSessionCreated,
  type VoiceSessionPreferences,
  type Workspace,
} from "@/lib/api";

type TransportMode = "webrtc" | "mock" | "text_fallback";
type CorrectionMode = "immersion" | "coach" | "exam";
type SpeechSpeed = "slow" | "normal";
type Patience = "normal" | "patient";

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}

interface SpeechRecognitionEventLike {
  results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start(): void;
  stop(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface ExpectedUtterance {
  client_event_id: string;
  transcript_status: "final" | "incomplete";
  playback_status: "not_applicable" | "unknown" | "completed" | "interrupted";
}

interface PersistUtteranceOptions {
  clientEventId?: string;
  connectionEpoch?: number;
  contentIndex?: number;
  endedMs?: number | null;
  playbackStatus?: "not_applicable" | "unknown" | "completed" | "interrupted";
  providerItemId?: string | null;
  providerResponseId?: string | null;
  source: "provider" | "browser_speech" | "browser_text" | "mock";
  speaker: "user" | "assistant";
  startedMs?: number | null;
  transcript: string;
  transcriptStatus?: "final" | "incomplete";
}

const MAX_RECONNECT_ATTEMPTS = 2;
const RECONNECT_DELAYS = [800, 1800];

const stateCopy = {
  idle: { label: "准备开始", note: "选择场景和模式后，开始一次可连续交流的中文对话。" },
  connecting: { label: "正在连接", note: "正在准备麦克风、教学上下文和实时通道…" },
  reconnecting: { label: "正在恢复连接", note: "已保存的转写不会丢失，正在续接本次对话…" },
  listening: { label: "正在听你说", note: "自然说话即可；停顿时，小文会耐心等待。" },
  thinking: { label: "正在理解", note: "正在结合本次任务生成回应。" },
  speaking: { label: "小文正在说", note: "你可以直接开口打断，或点停止回答。" },
  ending: { label: "正在保存", note: "正在排空最后的转写与播放状态…" },
  ended: { label: "本次对话已保存", note: "可靠转写、时长和连接质量已写入当前工作区。" },
  error: { label: "需要处理", note: "学习记录仍保留在当前会话中。" },
} as const;

const mockReplies: Record<string, string[]> = {
  "campus-canteen": [
    "好的，你还需要米饭或者饮料吗？",
    "明白了。一共二十八元。你可以再确认一下价格吗？",
    "很好，你已经完成了点餐。最后试着说明你要打包还是在这里吃。",
  ],
  "convenience-store": [
    "矿泉水在右边第二排。你想要多大一瓶的？",
    "可以，我们支持手机支付。你还需要购物袋吗？",
    "表达得很清楚。结账前再确认一次数量吧。",
  ],
  "campus-directions": [
    "你先往前走，到第二个路口以后向右转。你能重复一下路线吗？",
    "表达得很清楚。说“请问，教学楼怎么走？”会更自然。",
    "很好，最后试着用“所以”总结一次完整路线吧。",
  ],
  "dorm-repair": [
    "我记下来了。请问是完全不能开，还是不制冷？",
    "维修师傅今天下午三点可以来，你那个时间在宿舍吗？",
    "好的，请再说一次你的房间号，方便我们确认。",
  ],
  "hospital-registration": [
    "我可以帮你说明挂号流程。你想表达的主要不舒服是什么？",
    "你可以先到自助机登记，再去对应窗口确认科室。",
    "很好。这个练习只帮助你表达就诊需求，不代替医生判断。",
  ],
  "classroom-question": [
    "当然可以。请告诉我，是哪个词还是哪个步骤没有听明白？",
    "这个问题问得很清楚。你还可以说“您能再举一个例子吗？”",
    "很好，最后用自己的话复述一下老师的解释吧。",
  ],
};

function formatTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function wait(delayMs: number) {
  return new Promise((resolve) => window.setTimeout(resolve, delayMs));
}

function serverTimeMs(value: string) {
  const includesTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(includesTimezone ? value : `${value}Z`).getTime();
}

export default function ConversationPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [scenarios, setScenarios] = useState<ConversationScenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("campus-directions");
  const [practiceMode, setPracticeMode] = useState<"scenario" | "free" | "custom">("scenario");
  const [customObjective, setCustomObjective] = useState("");
  const [voiceSession, setVoiceSession] = useState<VoiceSession | null>(null);
  const [connection, setConnection] = useState<RealtimeConnection | null>(null);
  const [transportMode, setTransportMode] = useState<TransportMode>("mock");
  const [runtime, setRuntime] = useState<LiveRuntimeState>(initialLiveRuntime);
  const [utterances, setUtterances] = useState<Utterance[]>([]);
  const [partialAssistant, setPartialAssistant] = useState("");
  const [partialUser, setPartialUser] = useState("");
  const [textInput, setTextInput] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [budgetWarning, setBudgetWarning] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [correctionMode, setCorrectionMode] = useState<CorrectionMode>("coach");
  const [speechSpeed, setSpeechSpeed] = useState<SpeechSpeed>("slow");
  const [patience, setPatience] = useState<Patience>("patient");
  const [recognizing, setRecognizing] = useState(false);
  const [microphoneMuted, setMicrophoneMuted] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [showTextInput, setShowTextInput] = useState(false);
  const [inputLevel, setInputLevel] = useState(0);
  const [outputLevel, setOutputLevel] = useState(0);
  const [canAbandonSave, setCanAbandonSave] = useState(false);
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [reviewSelections, setReviewSelections] = useState<Record<string, boolean>>({});
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  const sequenceRef = useRef(0);
  const sequenceByEventIdRef = useRef(new Map<string, number>());
  const startedAtRef = useRef<number | null>(null);
  const elapsedRef = useRef(0);
  const streamRef = useRef<MediaStream | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const inputMeterRef = useRef<AudioMeterStop | null>(null);
  const outputMeterRef = useRef<AudioMeterStop | null>(null);
  const qwenRef = useRef<QwenWebRtcConnection | null>(null);
  const runtimeRef = useRef(initialLiveRuntime);
  const utterancesRef = useRef<Utterance[]>([]);
  const savedIdsRef = useRef(new Set<string>());
  const expectedRef = useRef(new Map<string, ExpectedUtterance>());
  const pendingWritesRef = useRef(new Set<Promise<Utterance>>());
  const providerEventIdsRef = useRef(new Map<string, string>());
  const voiceSessionRef = useRef<VoiceSession | null>(null);
  const connectionEpochRef = useRef(0);
  const recoveringRef = useRef(false);
  const finishingRef = useRef(false);
  const acceptProviderEventsRef = useRef(true);
  const budgetWarningSentRef = useRef(false);
  const turnEndedAtRef = useRef<number | null>(null);
  const firstLatencyRecordedRef = useRef(false);
  const pendingConfigRevisionRef = useRef<number | null>(null);
  const assistantBufferRef = useRef("");
  const activeResponseIdRef = useRef<string | null>(null);
  const providerResponseActiveRef = useRef(false);
  const activeAssistantRef = useRef<Utterance | null>(null);
  const assistantEventIdsRef = useRef(new Map<string, string>());
  const activeUserEventIdRef = useRef<string | null>(null);
  const interruptedResponsesRef = useRef(new Set<string>());
  const outputStartedResponsesRef = useRef(new Set<string>());
  const suppressOutputRef = useRef(false);
  const eventChainRef = useRef(Promise.resolve());
  const finishSessionRef = useRef<(allowIncomplete?: boolean) => void>(() => undefined);
  const continueSegmentRef = useRef<() => void>(() => undefined);
  const joinFreshSessionRef = useRef<(join: "voice" | "text") => void>(() => undefined);
  const joinedSessionRef = useRef(false);
  const segmentStartedRef = useRef(Date.now());
  const quietSinceRef = useRef(Date.now());
  const providerActivityRef = useRef(0);
  const connectingRef = useRef<Promise<void> | null>(null);
  const microphoneMutedRef = useRef(microphoneMuted);
  microphoneMutedRef.current = microphoneMuted;
  const [continuingSegment, setContinuingSegment] = useState(false);
  const [toolActivity, setToolActivity] = useState<ToolActivity | null>(null);

  const liveState = projectLiveView(runtime);
  const selectedScenario: ConversationScenario | undefined = practiceMode === "scenario"
    ? scenarios.find((scenario) => scenario.id === selectedScenarioId) ?? scenarios[0]
    : {
        id: practiceMode,
        title: practiceMode === "free" ? "自由对话" : "自定义练习",
        category: "中文交流",
        level: "不限",
        objective: practiceMode === "free" ? "围绕你感兴趣的话题自然交流，可以随时换话题" : customObjective.trim() || "填写你想练习的目标",
        opening_line: practiceMode === "free" ? "你好！今天想聊些什么？" : "你好！我们按你的目标来练习，你想先从哪里开始？",
        prompt_starters: practiceMode === "free" ? ["我想聊聊今天发生的事。", "你可以帮我找一个话题吗？"] : ["我们开始练习吧。", "请先给我一个示例。"],
        safety_note: null,
      };

  function updateRuntime(patch: Partial<LiveRuntimeState>) {
    const next = { ...runtimeRef.current, ...patch };
    runtimeRef.current = next;
    setRuntime(next);
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiRequest<Workspace>(`/api/v1/workspaces/${workspaceId}`),
      apiRequest<ConversationScenario[]>("/api/v1/voice/scenarios"),
    ])
      .then(async ([restoredWorkspace, catalog]) => {
        if (cancelled) return;
        setWorkspace(restoredWorkspace);
        const savedMode = restoredWorkspace.state.practice_mode;
        setPracticeMode(savedMode === "free" || savedMode === "custom" ? savedMode : "scenario");
        setCustomObjective(String(restoredWorkspace.state.custom_objective ?? ""));
        setScenarios(catalog);
        const savedScenario = restoredWorkspace.state.scenario_id;
        const matchingScenario = catalog.find(
          (scenario) => scenario.id === savedScenario || scenario.title === restoredWorkspace.title,
        );
        if (matchingScenario) setSelectedScenarioId(matchingScenario.id);

        const activeSessionId = restoredWorkspace.state.active_session_id;
        const previousSessionId = restoredWorkspace.state.last_session_id;
        const sessionId = typeof activeSessionId === "string"
          ? activeSessionId
          : typeof previousSessionId === "string" ? previousSessionId : null;
        if (!sessionId) return;
        const previous = await apiRequest<VoiceSession>(`/api/v1/voice/sessions/${sessionId}`);
        if (cancelled) return;
        setVoiceSession(previous);
        voiceSessionRef.current = previous;
        setTransportMode(previous.connection_mode === "webrtc" ? "webrtc" : "mock");
        setUtterances(previous.utterances);
        utterancesRef.current = previous.utterances;
        savedIdsRef.current = new Set(previous.utterances.map((item) => item.client_event_id));
        expectedRef.current = new Map(
          previous.utterances.map((item) => [
            item.client_event_id,
            {
              client_event_id: item.client_event_id,
              transcript_status: item.transcript_status === "incomplete" ? "incomplete" : "final",
              playback_status: item.playback_status,
            },
          ]),
        );
        sequenceByEventIdRef.current = new Map(
          previous.utterances.map((item) => [item.client_event_id, item.sequence_no]),
        );
        sequenceRef.current = Math.max(0, ...previous.utterances.map((item) => item.sequence_no));
        connectionEpochRef.current = previous.connection_epoch;
        setSpeechSpeed(previous.speech_speed);
        setPatience(previous.patience);
        setCorrectionMode(previous.correction_mode);
        if (typeof activeSessionId === "string" && previous.status !== "completed" && previous.status !== "failed") {
          const stoppedAt = previous.ending_at ?? new Date().toISOString();
          const restoredElapsed = previous.started_at
            ? Math.min(
                previous.context_pack.continuous ? Infinity : previous.max_duration_seconds,
                Math.max(
                  0,
                  Math.floor(
                    (serverTimeMs(stoppedAt) - serverTimeMs(previous.started_at)) / 1000,
                  ),
                ),
              )
            : 0;
          elapsedRef.current = restoredElapsed;
          setElapsed(restoredElapsed);
          return;
        }
        if (previous.status === "completed") {
          elapsedRef.current = previous.duration_seconds;
          setElapsed(previous.duration_seconds);
          updateRuntime({ lifecycle: "ended", transport: "closed", persistence: "saved" });
          const savedSummary = await apiRequest<SessionSummary | null>(`/api/v1/voice/sessions/${previous.id}/summary`);
          if (!cancelled) applySessionSummary(savedSummary);
        }
      })
      .catch((requestError) => {
        if (cancelled) return;
        setError(requestError instanceof Error ? requestError.message : "无法恢复工作区");
        updateRuntime({ lifecycle: "failed", transport: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  useEffect(() => {
    utterancesRef.current = utterances;
  }, [utterances]);

  useEffect(() => {
    voiceSessionRef.current = voiceSession;
  }, [voiceSession]);

  useEffect(() => {
    if (!startedAtRef.current || !["live", "ending"].includes(runtime.lifecycle)) return;
    const timer = window.setInterval(() => {
      const seconds = Math.floor((Date.now() - (startedAtRef.current ?? Date.now())) / 1000);
      elapsedRef.current = seconds;
      setElapsed(seconds);
      const maximum = connection?.max_duration_seconds ?? 480;
      if (voiceSessionRef.current?.context_pack.continuous) {
        if (Date.now() - segmentStartedRef.current >= maximum * 1000) {
          continueSegmentRef.current();
        }
        return;
      }
      if (seconds >= maximum) {
        finishSessionRef.current(false);
      } else if (maximum - seconds <= 60 && !budgetWarningSentRef.current) {
        budgetWarningSentRef.current = true;
        setBudgetWarning(true);
        const currentSession = voiceSessionRef.current;
        if (currentSession) {
          void recordSessionEvent(currentSession.id, "budget_warning", { remaining_seconds: maximum - seconds });
        }
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [connection, runtime.lifecycle]);

  useEffect(() => {
    const recoveryPromptOpen = runtime.lifecycle === "idle" && voiceSession?.status === "active";
    if (runtime.lifecycle !== "live" && !recoveryPromptOpen) return;

    const sendHeartbeat = () => {
      const currentSession = voiceSessionRef.current;
      if (!currentSession || currentSession.status !== "active") return;
      void recordSessionEvent(currentSession.id, "session_heartbeat", {
        phase: recoveryPromptOpen ? "recovery_prompt" : projectLiveView(runtimeRef.current),
        connection_epoch: connectionEpochRef.current,
        transport: runtimeRef.current.transport,
        input: runtimeRef.current.input,
        output: runtimeRef.current.output,
      });
    };

    sendHeartbeat();
    const heartbeat = window.setInterval(sendHeartbeat, 15_000);
    return () => window.clearInterval(heartbeat);
  }, [runtime.lifecycle, voiceSession?.id, voiceSession?.status]);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    qwenRef.current?.close();
    outputMeterRef.current?.();
    inputMeterRef.current?.();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    window.speechSynthesis?.cancel();
  }, []);

  function disposeConnection() {
    qwenRef.current?.close();
    qwenRef.current = null;
    outputMeterRef.current?.();
    outputMeterRef.current = null;
    if (audioRef.current) audioRef.current.srcObject = null;
  }

  function releaseMedia() {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    disposeConnection();
    inputMeterRef.current?.();
    inputMeterRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    window.speechSynthesis?.cancel();
  }

  async function recordSessionEvent(
    sessionId: string,
    eventType: SessionEventType,
    eventPayload: Record<string, unknown> = {},
  ) {
    try {
      await apiRequest<SessionEvent>(`/api/v1/voice/sessions/${sessionId}/events`, {
        method: "POST",
        body: JSON.stringify({
          client_event_id: `${eventType}-${crypto.randomUUID()}`,
          event_type: eventType,
          elapsed_ms: elapsedRef.current * 1000,
          event_payload: eventPayload,
        }),
      });
      setVoiceSession((current) => {
        if (!current || current.id !== sessionId) return current;
        if (eventType === "reconnect_attempt") return { ...current, reconnect_count: current.reconnect_count + 1 };
        if (eventType === "interruption") return { ...current, interruption_count: current.interruption_count + 1 };
        if (eventType === "provider_first_response" && current.first_response_latency_ms === null && typeof eventPayload.latency_ms === "number") {
          return { ...current, first_response_latency_ms: eventPayload.latency_ms };
        }
        if (eventType === "config_applied" && typeof eventPayload.config_revision === "number") {
          return { ...current, applied_config_revision: eventPayload.config_revision };
        }
        return current;
      });
    } catch {
      // Telemetry must never break the media or transcript path.
    }
  }

  function providerClientEventId(key: string) {
    const existing = providerEventIdsRef.current.get(key);
    if (existing) return existing;
    const created = `p-${connectionEpochRef.current}-${crypto.randomUUID()}`;
    providerEventIdsRef.current.set(key, created);
    return created;
  }

  async function persistUtterance(options: PersistUtteranceOptions) {
    const currentSession = voiceSessionRef.current;
    if (!currentSession) throw new Error("当前没有可写入的语音会话");
    const existingSequence = options.clientEventId
      ? sequenceByEventIdRef.current.get(options.clientEventId)
      : undefined;
    const sequence = existingSequence ?? sequenceRef.current + 1;
    const clientEventId = options.clientEventId ??
      `${options.speaker}-${sequence}-${crypto.randomUUID()}`;
    if (existingSequence === undefined) {
      sequenceRef.current = sequence;
      sequenceByEventIdRef.current.set(clientEventId, sequence);
    }
    const playbackStatus = options.playbackStatus ?? (options.speaker === "assistant" ? "unknown" : "not_applicable");
    const transcriptStatus = options.transcriptStatus ?? "final";
    expectedRef.current.set(clientEventId, {
      client_event_id: clientEventId,
      transcript_status: transcriptStatus,
      playback_status: playbackStatus,
    });
    updateRuntime({ persistence: "saving" });

    const request = apiRequest<Utterance>(`/api/v1/voice/sessions/${currentSession.id}/utterances`, {
      method: "POST",
      body: JSON.stringify({
        client_event_id: clientEventId,
        sequence_no: sequence,
        connection_epoch: options.connectionEpoch ?? connectionEpochRef.current,
        provider_item_id: options.providerItemId ?? null,
        provider_response_id: options.providerResponseId ?? null,
        content_index: options.contentIndex ?? 0,
        speaker: options.speaker,
        transcript: options.transcript,
        source: options.source,
        is_final: transcriptStatus === "final",
        transcript_status: transcriptStatus,
        playback_status: playbackStatus,
        started_ms: options.startedMs ?? null,
        ended_ms: options.endedMs ?? null,
      }),
    });
    pendingWritesRef.current.add(request);
    try {
      const saved = await request;
      savedIdsRef.current.add(saved.client_event_id);
      expectedRef.current.set(saved.client_event_id, {
        client_event_id: saved.client_event_id,
        transcript_status: saved.transcript_status === "incomplete" ? "incomplete" : "final",
        playback_status: saved.playback_status,
      });
      setUtterances((current) => {
        if (!current.some((item) => item.id === saved.id)) return [...current, saved];
        return current.map((item) => (item.id === saved.id ? saved : item));
      });
      updateRuntime({
        persistence: pendingWritesRef.current.size === 1 ? "saved" : "saving",
      });
      return saved;
    } catch (requestError) {
      updateRuntime({ persistence: "error" });
      setError(requestError instanceof Error ? requestError.message : "转写保存失败");
      void recordSessionEvent(currentSession.id, "transcript_save_failed", { client_event_id: clientEventId });
      throw requestError;
    } finally {
      pendingWritesRef.current.delete(request);
    }
  }

  async function updatePlayback(utterance: Utterance, playbackStatus: "completed" | "interrupted") {
    if (utterance.playback_status !== "unknown") return utterance;
    const currentSession = voiceSessionRef.current;
    if (!currentSession) return utterance;
    const updated = await apiRequest<Utterance>(
      `/api/v1/voice/sessions/${currentSession.id}/utterances/${utterance.id}/playback`,
      {
        method: "PATCH",
        body: JSON.stringify({ connection_epoch: utterance.connection_epoch, playback_status: playbackStatus }),
      },
    );
    expectedRef.current.set(updated.client_event_id, {
      client_event_id: updated.client_event_id,
      transcript_status: updated.transcript_status === "incomplete" ? "incomplete" : "final",
      playback_status: updated.playback_status,
    });
    setUtterances((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    if (activeAssistantRef.current?.id === updated.id) activeAssistantRef.current = updated;
    return updated;
  }

  function speakLocally(text: string, saved: Utterance) {
    if (!("speechSynthesis" in window)) {
      updateRuntime({ output: "idle" });
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = speechSpeed === "slow" ? 0.82 : 1;
    utterance.onstart = () => updateRuntime({ output: "playing" });
    utterance.onend = () => {
      updateRuntime({ output: "idle" });
      const current = activeAssistantRef.current;
      if (current?.id === saved.id && current.playback_status === "unknown") {
        void updatePlayback(current, "completed").catch(() => undefined);
      }
    };
    window.speechSynthesis.speak(utterance);
  }

  async function activateTextFallback(sessionId: string, reason: string) {
    disposeConnection();
    inputMeterRef.current?.();
    inputMeterRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    const activated = await apiRequest<VoiceSession>(`/api/v1/voice/sessions/${sessionId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: "active", connection_epoch: connectionEpochRef.current, failure_reason: reason }),
    });
    setVoiceSession(activated);
    voiceSessionRef.current = activated;
    setTransportMode("text_fallback");
    setReconnectAttempt(0);
    updateRuntime({ lifecycle: "live", transport: "fallback", input: "unavailable", output: "idle" });
    setShowTextInput(true);
    setError("实时语音暂时不可用，已切换到文字与本地朗读；本次学习记录会继续保存。");
    void recordSessionEvent(sessionId, "fallback_activated", { reason });
  }

  async function resumeSession(useMicrophone: boolean) {
    const currentSession = voiceSessionRef.current;
    if (!currentSession || currentSession.status === "ending") return;
    setError("");
    setShowTextInput(!useMicrophone);
    setMicrophoneMuted(false);
    finishingRef.current = false;
    recoveringRef.current = false;
    acceptProviderEventsRef.current = true;
    updateRuntime({
      lifecycle: "starting",
      transport: "connecting",
      input: useMicrophone ? "requesting" : "unavailable",
      output: "idle",
      persistence: "saved",
    });
    try {
      const resumed = await apiRequest<VoiceSessionCreated>(
        `/api/v1/voice/sessions/${currentSession.id}/resume`,
        { method: "POST" },
      );
      setVoiceSession(resumed.session);
      voiceSessionRef.current = resumed.session;
      setConnection(resumed.connection);
      connectionEpochRef.current = resumed.session.connection_epoch;
      const restoredElapsed = resumed.session.started_at
        ? Math.min(
            resumed.session.context_pack.continuous ? Infinity : resumed.session.max_duration_seconds,
            Math.max(
              0,
              Math.floor(
                (Date.now() - serverTimeMs(resumed.session.started_at)) / 1000,
              ),
            ),
          )
        : elapsedRef.current;
      elapsedRef.current = restoredElapsed;
      setElapsed(restoredElapsed);
      startedAtRef.current = Date.now() - restoredElapsed * 1000;

      if (useMicrophone && resumed.connection.mode === "webrtc") {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("当前浏览器不支持麦克风访问");
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        streamRef.current = stream;
        inputMeterRef.current = createAudioMeter(stream, setInputLevel);
        await recordSessionEvent(currentSession.id, "reconnect_attempt", {
          reason: "page_restore",
        });
        await connectWebRtc(currentSession.id, resumed.connection, stream, true);
        setTransportMode("webrtc");
        updateRuntime({
          lifecycle: "live",
          transport: "connected",
          input: "ready",
        });
        await recordSessionEvent(currentSession.id, "reconnect_succeeded", {
          reason: "page_restore",
        });
        return;
      }

      const activated = await apiRequest<VoiceSession>(
        `/api/v1/voice/sessions/${currentSession.id}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: "active",
            connection_epoch: resumed.session.connection_epoch,
          }),
        },
      );
      setVoiceSession(activated);
      voiceSessionRef.current = activated;
      const nextMode = resumed.connection.mode === "mock" ? "mock" : "text_fallback";
      setTransportMode(nextMode);
      setShowTextInput(true);
      updateRuntime({
        lifecycle: "live",
        transport: "fallback",
        input: "unavailable",
      });
      await recordSessionEvent(currentSession.id, "connection_established", {
        mode: nextMode,
        reason: "page_restore",
      });
    } catch (requestError) {
      releaseMedia();
      setError(requestError instanceof Error ? requestError.message : "恢复会话失败");
      updateRuntime({
        lifecycle: "idle",
        transport: "idle",
        input: "unavailable",
      });
    }
  }

  async function startSession(useMicrophone: boolean) {
    if (practiceMode === "custom" && !customObjective.trim()) {
      setError("请先填写你想练习的目标。");
      return;
    }
    setError("");
    setCanAbandonSave(false);
    setSessionSummary(null);
    setSummaryError("");
    setBudgetWarning(false);
    setReconnectAttempt(0);
    setShowTranscript(false);
    setShowTextInput(!useMicrophone);
    setMicrophoneMuted(false);
    budgetWarningSentRef.current = false;
    firstLatencyRecordedRef.current = false;
    finishingRef.current = false;
    recoveringRef.current = false;
    acceptProviderEventsRef.current = true;
    expectedRef.current.clear();
    savedIdsRef.current.clear();
    providerEventIdsRef.current.clear();
    sequenceByEventIdRef.current.clear();
    interruptedResponsesRef.current.clear();
    outputStartedResponsesRef.current.clear();
    assistantEventIdsRef.current.clear();
    activeUserEventIdRef.current = null;
    activeAssistantRef.current = null;
    activeResponseIdRef.current = null;
    sequenceRef.current = 0;
    updateRuntime({
      lifecycle: "starting",
      transport: "connecting",
      input: useMicrophone ? "requesting" : "unavailable",
      output: "idle",
      persistence: "idle",
    });

    try {
      let stream: MediaStream | null = null;
      if (useMicrophone) {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("当前浏览器不支持麦克风访问");
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        streamRef.current = stream;
        inputMeterRef.current = createAudioMeter(stream, setInputLevel);
        updateRuntime({ input: "ready" });
      }

      const created = await apiRequest<VoiceSessionCreated>("/api/v1/voice/sessions", {
        method: "POST",
        body: JSON.stringify({
          ...buildPracticeSessionPayload({
            practiceMode,
            customObjective,
            scenarioId: selectedScenario?.id,
            scenarioTitle: selectedScenario?.title ?? workspace?.title,
            correctionMode,
            speechSpeed,
            patience,
          }),
          workspace_id: workspaceId,
        }),
      });
      setVoiceSession(created.session);
      voiceSessionRef.current = created.session;
      connectionEpochRef.current = created.session.connection_epoch;
      setConnection(created.connection);
      setTransportMode(created.connection.mode);
      setUtterances([]);
      utterancesRef.current = [];
      await recordSessionEvent(created.session.id, "connection_attempt", { mode: created.connection.mode });

      if (selectedScenario) {
        setWorkspace((current) => current ? {
          ...current,
          title: selectedScenario.title,
          status: "active",
          state: {
            ...current.state,
            practice_mode: practiceMode,
            custom_objective: practiceMode === "custom" ? customObjective.trim() : null,
            scenario_id: practiceMode === "scenario" ? selectedScenario.id : null,
            objective: selectedScenario.objective,
            opening_line: selectedScenario.opening_line,
            prompt_starters: selectedScenario.prompt_starters,
            safety_note: selectedScenario.safety_note,
          },
        } : current);
      }

      startedAtRef.current = Date.now();
      elapsedRef.current = 0;
      setElapsed(0);

      if (created.connection.mode === "webrtc" && stream) {
        try {
          await connectWebRtc(created.session.id, created.connection, stream, false);
          setTransportMode("webrtc");
          updateRuntime({ lifecycle: "live", transport: "connected", input: "ready" });
          void recordSessionEvent(created.session.id, "connection_established", { mode: "webrtc" });
          turnEndedAtRef.current = performance.now();
          qwenRef.current?.requestResponse();
        } catch (connectionError) {
          await activateTextFallback(
            created.session.id,
            connectionError instanceof Error ? connectionError.message : "实时连接失败",
          );
          await playMockGreeting();
        }
      } else {
        stream?.getTracks().forEach((track) => track.stop());
        inputMeterRef.current?.();
        inputMeterRef.current = null;
        streamRef.current = null;
        const reason = created.connection.mode === "mock"
          ? created.connection.fallback_reason ?? "服务端未配置实时模型"
          : "用户选择文字模式";
        const activated = await apiRequest<VoiceSession>(`/api/v1/voice/sessions/${created.session.id}/status`, {
          method: "PATCH",
          body: JSON.stringify({
            status: "active",
            connection_epoch: created.session.connection_epoch,
            failure_reason: created.connection.mode === "mock" ? reason : null,
          }),
        });
        setVoiceSession(activated);
        voiceSessionRef.current = activated;
        setTransportMode(created.connection.mode === "mock" ? "mock" : "text_fallback");
        setShowTextInput(true);
        updateRuntime({ lifecycle: "live", transport: "fallback", input: "unavailable" });
        void recordSessionEvent(created.session.id, "connection_established", { mode: created.connection.mode });
        await playMockGreeting();
      }
    } catch (requestError) {
      releaseMedia();
      setError(requestError instanceof Error ? requestError.message : "实时连接失败");
      updateRuntime({ lifecycle: "failed", transport: "error" });
    }
  }

  async function playMockGreeting() {
    const greeting = selectedScenario?.opening_line ?? `你好！今天我们练习“${workspace?.title ?? "中文对话"}”。你可以先开始。`;
    updateRuntime({ output: "playing" });
    const saved = await persistUtterance({ speaker: "assistant", transcript: greeting, source: "mock" });
    activeAssistantRef.current = saved;
    speakLocally(greeting, saved);
  }

  function connectWebRtc(
    sessionId: string,
    realtimeConnection: RealtimeConnection,
    stream: MediaStream,
    isReconnect: boolean,
    safeHandoff = false,
  ) {
    const operation = connectWebRtcInternal(sessionId, realtimeConnection, stream, isReconnect, safeHandoff);
    // Ending waits for activation too, preventing a late active PATCH.
    connectingRef.current = operation;
    return operation;
  }

  async function connectWebRtcInternal(
    sessionId: string,
    realtimeConnection: RealtimeConnection,
    stream: MediaStream,
    isReconnect: boolean,
    safeHandoff: boolean,
  ) {
    const activityBeforeRestore = providerActivityRef.current;
    if (isReconnect) {
      const restored = await apiRequest<VoiceSessionCreated>(`/api/v1/voice/sessions/${sessionId}/resume`, { method: "POST" });
      realtimeConnection = restored.connection;
    }
    if (finishingRef.current) throw new Error("会话正在结束");
    if (safeHandoff && (qwenRef.current?.toolsBusy() || runtimeRef.current.input === "speech" || !["idle", "stopped"].includes(runtimeRef.current.output) || pendingWritesRef.current.size || activityBeforeRestore !== providerActivityRef.current || Date.now() - quietSinceRef.current < 3000)) return;
    if (safeHandoff) stream.getAudioTracks().forEach((track) => { track.enabled = false; });
    disposeConnection();
    const nextEpoch = connectionEpochRef.current + 1;
    connectionEpochRef.current = nextEpoch;
    pendingConfigRevisionRef.current = voiceSessionRef.current?.config_revision ?? 1;
    const connecting = connectQwenWebRtc({
      toolSessionId: sessionId,
      onToolActivity: setToolActivity,
      connectionEpoch: nextEpoch,
      mediaStream: stream,
      sessionUpdate: realtimeConnection.session_update,
      exchangeOffer: async (sdp, connectionEpoch) => {
        const answer = await apiRequest<{ sdp: string; connection_epoch: number }>(`/api/v1/voice/sessions/${sessionId}/offer`, {
          method: "POST",
          body: JSON.stringify({ sdp, connection_epoch: connectionEpoch }),
        });
        connectionEpochRef.current = answer.connection_epoch;
        return answer.sdp;
      },
      onEvent: (rawEvent) => {
        providerActivityRef.current += 1;
        quietSinceRef.current = Date.now();
        eventChainRef.current = eventChainRef.current
          .then(() => handleProviderEvent(sessionId, nextEpoch, rawEvent))
          .catch(() => undefined);
      },
      onRemoteStream: (remoteStream) => {
        if (audioRef.current) {
          audioRef.current.srcObject = remoteStream;
          audioRef.current.muted = suppressOutputRef.current;
          void audioRef.current.play().catch(() => undefined);
        }
        outputMeterRef.current?.();
        outputMeterRef.current = createAudioMeter(remoteStream, setOutputLevel);
      },
      onConnectionLoss: () => void handleConnectionLoss(sessionId, realtimeConnection),
    });
    const qwen = await connecting;
    if (finishingRef.current) {
      qwen.close();
      throw new Error("会话正在结束");
    }
    qwenRef.current = qwen;
    segmentStartedRef.current = Date.now();
    const activated = await apiRequest<VoiceSession>(`/api/v1/voice/sessions/${sessionId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: "active", connection_epoch: nextEpoch }),
    });
    if (finishingRef.current) { qwen.close(); return; }
    setVoiceSession(activated);
    voiceSessionRef.current = activated;
    stream.getAudioTracks().forEach((track) => { track.enabled = !microphoneMutedRef.current; });
    if (safeHandoff) await recordSessionEvent(sessionId, "segment_continued", { connection_epoch: nextEpoch });
  }

  async function handleConnectionLoss(sessionId: string, realtimeConnection: RealtimeConnection) {
    if (
      recoveringRef.current ||
      finishingRef.current ||
      voiceSessionRef.current?.status !== "active" ||
      runtimeRef.current.lifecycle !== "live"
    ) return;
    recoveringRef.current = true;
    updateRuntime({ transport: "reconnecting", output: "idle" });
    await recordSessionEvent(sessionId, "connection_lost", {
      browser_online: navigator.onLine,
      connection_epoch: connectionEpochRef.current,
    });

    for (let attempt = 1; attempt <= MAX_RECONNECT_ATTEMPTS; attempt += 1) {
      setReconnectAttempt(attempt);
      await recordSessionEvent(sessionId, "reconnect_attempt", { attempt });
      await wait(RECONNECT_DELAYS[attempt - 1]);
      if (finishingRef.current || runtimeRef.current.lifecycle !== "live") return;
      const stream = streamRef.current;
      if (!stream || !navigator.onLine) {
        await recordSessionEvent(sessionId, "reconnect_failed", {
          attempt,
          reason: stream ? "browser_offline" : "microphone_stream_closed",
        });
        continue;
      }
      try {
        await connectWebRtc(sessionId, realtimeConnection, stream, true);
        if (finishingRef.current) return;
        setTransportMode("webrtc");
        setReconnectAttempt(0);
        setError("");
        updateRuntime({ transport: "connected", input: microphoneMuted ? "muted" : "ready" });
        recoveringRef.current = false;
        await recordSessionEvent(sessionId, "reconnect_succeeded", { attempt });
        return;
      } catch (connectionError) {
        if (finishingRef.current) return;
        await recordSessionEvent(sessionId, "reconnect_failed", {
          attempt,
          reason: connectionError instanceof Error ? connectionError.message : "unknown_error",
        });
      }
    }

    recoveringRef.current = false;
    await activateTextFallback(sessionId, "两次自动重连均未成功");
  }

  useEffect(() => {
    if (runtime.input === "speech" || !["idle", "stopped"].includes(runtime.output) || outputLevel > 0.01 || partialUser) {
      quietSinceRef.current = Date.now();
    }
  }, [runtime.input, runtime.output, outputLevel, partialUser]);

  useEffect(() => {
    continueSegmentRef.current = () => {
      const current = voiceSessionRef.current;
      const state = runtimeRef.current;
      if (!current || !connection || !qwenRef.current || recoveringRef.current || finishingRef.current || state.lifecycle !== "live") return;
      if (qwenRef.current?.toolsBusy() || state.input === "speech" || !["idle", "stopped"].includes(state.output) || state.persistence === "error" || pendingWritesRef.current.size || Date.now() - quietSinceRef.current < 3000) return;
      void (async () => {
        recoveringRef.current = true;
        setContinuingSegment(true);
        try {
          await eventChainRef.current;
          await Promise.all([...pendingWritesRef.current]);
          if (finishingRef.current || runtimeRef.current.input === "speech" || !["idle", "stopped"].includes(runtimeRef.current.output)) return;
          const stream = streamRef.current;
          if (!stream) return;
          updateRuntime({ transport: "reconnecting" });
          await connectWebRtc(current.id, connection, stream, true, true);
          if (!finishingRef.current) updateRuntime({ transport: "connected" });
        } catch {
          if (!finishingRef.current) await activateTextFallback(current.id, "自动续接失败，已保留对话记录，可继续文字练习。");
        } finally {
          recoveringRef.current = false;
          // Restore the latest mute choice even when fresh activity aborted handoff.
          if (!finishingRef.current && qwenRef.current) {
            streamRef.current?.getAudioTracks().forEach((track) => { track.enabled = !microphoneMutedRef.current; });
          }
          setContinuingSegment(false);
        }
      })();
    };
  });

  async function handleProviderEvent(sessionId: string, eventEpoch: number, rawEvent: string) {
    if (!acceptProviderEventsRef.current || eventEpoch !== connectionEpochRef.current) return;
    const event = parseProviderEvent(rawEvent);
    if (!event) return;

    if (event.kind === "config_ack") {
      const revision = pendingConfigRevisionRef.current;
      if (revision !== null) {
        pendingConfigRevisionRef.current = null;
        await recordSessionEvent(sessionId, "config_applied", {
          config_revision: revision,
          connection_epoch: connectionEpochRef.current,
        });
      }
      return;
    }
    if (event.kind === "user_speech_started") {
      setPartialUser("");
      activeUserEventIdRef.current = null;
      updateRuntime({ input: "speech" });
      await recordSessionEvent(sessionId, "user_speech_started", { connection_epoch: connectionEpochRef.current });
      if (["playing", "thinking"].includes(runtimeRef.current.output)) await stopCurrentAnswer("voice_barge_in");
      return;
    }
    if (event.kind === "user_speech_stopped") {
      updateRuntime({ input: microphoneMuted ? "muted" : "ready", output: "thinking" });
      turnEndedAtRef.current = performance.now();
      await recordSessionEvent(sessionId, "user_speech_stopped", { connection_epoch: connectionEpochRef.current });
      return;
    }
    if (event.kind === "user_caption_preview") {
      setPartialUser(event.transcript);
      const clientEventId = activeUserEventIdRef.current ??
        providerClientEventId(`user:${event.itemId ?? "active"}:${event.contentIndex}`);
      activeUserEventIdRef.current = clientEventId;
      expectedRef.current.set(clientEventId, {
        client_event_id: clientEventId,
        transcript_status: "incomplete",
        playback_status: "not_applicable",
      });
      return;
    }
    if (event.kind === "user_caption_final") {
      const text = event.transcript.trim();
      setPartialUser("");
      if (!text) return;
      const key = `user:${event.itemId ?? "active"}:${event.contentIndex}`;
      await persistUtterance({
        clientEventId: activeUserEventIdRef.current ?? providerClientEventId(key),
        speaker: "user",
        transcript: text,
        source: "provider",
        providerItemId: event.itemId,
        contentIndex: event.contentIndex,
      });
      activeUserEventIdRef.current = null;
      return;
    }
    if (event.kind === "user_caption_failed") {
      setPartialUser("");
      setError("这句话没有可靠转写，请再说一次或使用文字输入。");
      await recordSessionEvent(sessionId, "transcript_save_failed", {
        provider_item_id: event.itemId,
        reason: event.message,
      });
      return;
    }
    if (event.kind === "response_started") {
      activeResponseIdRef.current = event.responseId;
      providerResponseActiveRef.current = true;
      activeAssistantRef.current = null;
      assistantBufferRef.current = "";
      setPartialAssistant("");
      suppressOutputRef.current = false;
      if (audioRef.current) audioRef.current.muted = false;
      updateRuntime({ output: "thinking" });
      return;
    }
    if (event.kind === "assistant_caption_delta") {
      if (!firstLatencyRecordedRef.current && turnEndedAtRef.current !== null) {
        firstLatencyRecordedRef.current = true;
        const latencyMs = Math.round(performance.now() - turnEndedAtRef.current);
        await recordSessionEvent(sessionId, "provider_first_response", { latency_ms: latencyMs });
      }
      assistantBufferRef.current += event.delta;
      setPartialAssistant(assistantBufferRef.current);
      updateRuntime({ output: "playing" });
      const responseKey = event.responseId ?? activeResponseIdRef.current ?? "active";
      const eventKey = `${responseKey}:${event.contentIndex}`;
      const clientEventId = assistantEventIdsRef.current.get(eventKey) ??
        providerClientEventId(`assistant:${event.itemId ?? responseKey}:${event.contentIndex}`);
      assistantEventIdsRef.current.set(eventKey, clientEventId);
      expectedRef.current.set(clientEventId, {
        client_event_id: clientEventId,
        transcript_status: "incomplete",
        playback_status: "unknown",
      });
      const outputKey = event.responseId ?? "active";
      if (!outputStartedResponsesRef.current.has(outputKey)) {
        outputStartedResponsesRef.current.add(outputKey);
        await recordSessionEvent(sessionId, "output_started", { response_id: event.responseId });
      }
      return;
    }
    if (event.kind === "assistant_caption_final") {
      const text = (event.transcript || assistantBufferRef.current).trim();
      assistantBufferRef.current = "";
      setPartialAssistant("");
      if (!text) return;
      const responseId = event.responseId ?? activeResponseIdRef.current;
      const interrupted = responseId ? interruptedResponsesRef.current.has(responseId) : false;
      const key = `assistant:${event.itemId ?? responseId ?? "active"}:${event.contentIndex}`;
      const eventKey = `${responseId ?? "active"}:${event.contentIndex}`;
      const saved = await persistUtterance({
        clientEventId: assistantEventIdsRef.current.get(eventKey) ?? providerClientEventId(key),
        speaker: "assistant",
        transcript: text,
        source: "provider",
        providerItemId: event.itemId,
        providerResponseId: responseId,
        contentIndex: event.contentIndex,
        playbackStatus: interrupted ? "interrupted" : "unknown",
      });
      activeAssistantRef.current = saved;
      return;
    }
    if (event.kind === "response_terminal") {
      providerResponseActiveRef.current = false;
      const interrupted = event.status === "cancelled" || (event.responseId ? interruptedResponsesRef.current.has(event.responseId) : false);
      const activeAssistant = activeAssistantRef.current;
      if (activeAssistant && (!event.responseId || activeAssistant.provider_response_id === event.responseId)) {
        try {
          await updatePlayback(activeAssistant, interrupted ? "interrupted" : "completed");
        } catch {
          setError("回答已结束，但播放状态暂未写入；结束会话时会再次核对。");
        }
      }
      updateRuntime({ output: "idle" });
      await recordSessionEvent(sessionId, "output_stopped", {
        response_id: event.responseId,
        status: interrupted ? "interrupted" : "completed",
      });
      return;
    }
    if (event.kind === "provider_error") {
      const fatal = isFatalProviderError(event);
      await recordSessionEvent(sessionId, "provider_error", {
        message: event.message,
        code: event.code,
        error_type: event.errorType,
        classification: fatal ? "fatal" : "recoverable",
      });
      if (fatal) {
        await activateTextFallback(sessionId, event.message);
      } else {
        setError(`${event.message}（实时语音仍保持连接，可继续对话。）`);
      }
    }
  }

  async function stopCurrentAnswer(reason: "button" | "voice_barge_in") {
    const currentSession = voiceSessionRef.current;
    if (!currentSession) return;
    const responseId = activeResponseIdRef.current;
    if (responseId) interruptedResponsesRef.current.add(responseId);
    suppressOutputRef.current = true;
    if (audioRef.current) audioRef.current.muted = true;
    window.speechSynthesis?.cancel();
    try {
      qwenRef.current?.interrupt();
    } catch {
      // Muting the local sink still makes the stop control immediate.
    }
    const activeAssistant = activeAssistantRef.current;
    if (activeAssistant?.playback_status === "unknown") {
      try {
        await updatePlayback(activeAssistant, "interrupted");
      } catch {
        // The final transcript event can still persist the interrupted status.
      }
    }
    updateRuntime({ output: "stopped" });
    await recordSessionEvent(currentSession.id, "interruption", { reason, response_id: responseId });
    await recordSessionEvent(currentSession.id, "output_stopped", { reason, response_id: responseId, status: "interrupted" });
  }

  function toggleMicrophone() {
    const nextMuted = !microphoneMuted;
    streamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = !nextMuted && !recoveringRef.current;
    });
    microphoneMutedRef.current = nextMuted;
    setMicrophoneMuted(nextMuted);
    updateRuntime({ input: nextMuted ? "muted" : "ready" });
  }

  async function changeLivePreference(change: { speech_speed?: SpeechSpeed; patience?: Patience }) {
    if (change.speech_speed) setSpeechSpeed(change.speech_speed);
    if (change.patience) setPatience(change.patience);
    const currentSession = voiceSessionRef.current;
    if (!currentSession || currentSession.status !== "active" || currentSession.protocol_version !== "live-v1") return;
    try {
      const updated = await apiRequest<VoiceSessionPreferences>(`/api/v1/voice/sessions/${currentSession.id}/preferences`, {
        method: "PATCH",
        body: JSON.stringify({ expected_config_revision: currentSession.config_revision, ...change }),
      });
      pendingConfigRevisionRef.current = updated.config_revision;
      const nextSession = {
        ...currentSession,
        config_revision: updated.config_revision,
        requested_config: updated.requested_config,
        speech_speed: change.speech_speed ?? currentSession.speech_speed,
        patience: change.patience ?? currentSession.patience,
      };
      setVoiceSession(nextSession);
      voiceSessionRef.current = nextSession;
      qwenRef.current?.updateSession(updated.session_update);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "实时设置更新失败");
    }
  }

  async function sendText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = textInput.trim();
    const currentSession = voiceSessionRef.current;
    if (!text || !currentSession || currentSession.status !== "active" || finishingRef.current || recoveringRef.current) return;
    setTextInput("");
    updateRuntime({ output: "thinking" });
    turnEndedAtRef.current = performance.now();
    try {
      await persistUtterance({ speaker: "user", transcript: text, source: "browser_text" });
      if (transportMode === "webrtc" && qwenRef.current) {
        if (providerResponseActiveRef.current) {
          // Text sent while an answer is streaming counts as a barge-in: cancel the
          // in-flight response first, then send the new message once the provider
          // confirms the terminal state (otherwise item.create is rejected).
          const responseId = activeResponseIdRef.current;
          if (responseId) interruptedResponsesRef.current.add(responseId);
          suppressOutputRef.current = true;
          if (audioRef.current) audioRef.current.muted = true;
          window.speechSynthesis?.cancel();
          const activeAssistant = activeAssistantRef.current;
          if (activeAssistant?.playback_status === "unknown") {
            try {
              await updatePlayback(activeAssistant, "interrupted");
            } catch {
              // The final transcript event can still persist the interrupted status.
            }
          }
          await recordSessionEvent(currentSession.id, "interruption", { reason: "text_barge_in", response_id: responseId });
          await qwenRef.current.sendTextInterject(text);
        } else {
          qwenRef.current.sendText(text);
          qwenRef.current.requestResponse();
        }
        return;
      }
      await wait(350);
      const replies = practiceMode === "scenario"
        ? mockReplies[selectedScenarioId] ?? mockReplies["campus-directions"]
        : ["这里是本地演练，你可以继续输入练习。使用麦克风连接实时模型后，我会围绕你的话题和目标回应。"];
      const replyIndex = Math.max(0, Math.floor((sequenceRef.current - 2) / 2));
      const reply = replies[Math.min(replyIndex, replies.length - 1)];
      const saved = await persistUtterance({ speaker: "assistant", transcript: reply, source: "mock" });
      activeAssistantRef.current = saved;
      speakLocally(reply, saved);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "转写保存失败");
    }
  }

  function toggleSpeechRecognition() {
    if (recognizing) {
      recognitionRef.current?.stop();
      setRecognizing(false);
      return;
    }
    const speechWindow = window as Window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setError("当前浏览器不支持本地语音转写，请直接使用文字输入。");
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "zh-CN";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      setTextInput(result[0].transcript);
      if (result.isFinal) setRecognizing(false);
    };
    recognition.onend = () => setRecognizing(false);
    recognition.onerror = () => {
      setRecognizing(false);
      setError("本地语音识别没有成功，请使用文字输入。");
    };
    recognitionRef.current = recognition;
    setRecognizing(true);
    recognition.start();
  }

  async function finishSession(allowIncomplete = false) {
    const currentSession = voiceSessionRef.current;
    if (!currentSession || currentSession.status === "completed" || finishingRef.current) return;
    finishingRef.current = true;
    recoveringRef.current = false;
    setCanAbandonSave(false);
    const wasOutputActive = ["playing", "thinking"].includes(runtimeRef.current.output);
    updateRuntime({ lifecycle: "ending", output: "stopped", persistence: "saving" });
    acceptProviderEventsRef.current = false;
    streamRef.current?.getAudioTracks().forEach((track) => { track.enabled = false; });
    if (audioRef.current) audioRef.current.muted = true;
    try { qwenRef.current?.interrupt(); } catch { /* Disconnected transports still need saving. */ }
    window.speechSynthesis?.cancel();

    try {
      // Let an in-flight offer settle its epoch before closing the logical session.
      await connectingRef.current?.catch(() => undefined);
      const activeAssistant = activeAssistantRef.current;
      if (activeAssistant?.playback_status === "unknown") {
        try {
          await updatePlayback(
            activeAssistant,
            wasOutputActive ? "interrupted" : "completed",
          );
        } catch {
          // The manifest keeps the unresolved playback state visible to finalize.
        }
      }
      // Only unresolved entries need a closing handshake; saved history is already durable.
      const unresolvedExpected = () => {
        const savedById = new Map(utterancesRef.current.map((item) => [item.client_event_id, item]));
        return [...expectedRef.current.values()].filter((expected) => {
          const saved = savedById.get(expected.client_event_id);
          return !saved || saved.transcript_status !== expected.transcript_status || saved.playback_status !== expected.playback_status;
        });
      };
      const knownClientEventIds = unresolvedExpected().map((item) => item.client_event_id);
      if (currentSession.status !== "ending") {
        const endingSession = await apiRequest<VoiceSession>(`/api/v1/voice/sessions/${currentSession.id}/status`, {
          method: "PATCH",
          body: JSON.stringify({
            status: "ending",
            connection_epoch: connectionEpochRef.current,
            end_reason: !currentSession.context_pack.continuous && elapsedRef.current >= currentSession.max_duration_seconds ? "practice_limit" : "user_ended",
            closing_manifest: {
              known_client_event_ids: knownClientEventIds,
              connection_epoch: connectionEpochRef.current,
              config_revision: currentSession.config_revision,
            },
          }),
        });
        setVoiceSession(endingSession);
        voiceSessionRef.current = endingSession;
      }

      disposeConnection();
      inputMeterRef.current?.();
      inputMeterRef.current = null;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      window.speechSynthesis?.cancel();
      await eventChainRef.current;
      await Promise.allSettled([...pendingWritesRef.current]);

      const expectedUtterances = unresolvedExpected();
      const missingClientEventIds = expectedUtterances
        .filter((item) => !savedIdsRef.current.has(item.client_event_id))
        .map((item) => item.client_event_id);
      if (allowIncomplete) {
        await recordSessionEvent(currentSession.id, "save_incomplete", { missing_client_event_ids: missingClientEventIds });
      }
      const finished = await apiRequest<VoiceSession>(`/api/v1/voice/sessions/${currentSession.id}/finalize`, {
        method: "POST",
        body: JSON.stringify({
          duration_seconds: elapsedRef.current,
          allow_incomplete: allowIncomplete,
          expected_utterances: expectedUtterances,
          missing_client_event_ids: missingClientEventIds,
        }),
      });
      setVoiceSession(finished);
      voiceSessionRef.current = finished;
      setUtterances(finished.utterances);
      utterancesRef.current = finished.utterances;
      setBudgetWarning(false);
      startedAtRef.current = null;
      updateRuntime({
        lifecycle: "ended",
        transport: "closed",
        input: "unavailable",
        output: "idle",
        persistence: "saved",
      });
      setSummaryLoading(true);
      setSummaryError("");
      try {
        const hasReliableUserTranscript = finished.utterances.some(
          (item) => item.speaker === "user" && item.transcript_status === "final",
        );
        if (!hasReliableUserTranscript) {
          setSummaryError("完成至少一句可靠的学习者表达后，才会生成学习报告。");
          return;
        }
        const summary = await apiRequest<SessionSummary>(`/api/v1/voice/sessions/${finished.id}/summary`, { method: "POST" });
        applySessionSummary(summary);
      } catch (summaryRequestError) {
        setSummaryError(summaryRequestError instanceof Error ? summaryRequestError.message : "本次学习报告生成失败");
      } finally {
        setSummaryLoading(false);
      }
    } catch (requestError) {
      finishingRef.current = false;
      const detail = requestError instanceof ApiError && requestError.detail && typeof requestError.detail === "object"
        ? requestError.detail as Record<string, unknown>
        : null;
      if (detail?.code === "transcript_pending") {
        setCanAbandonSave(true);
        setError("还有转写没有可靠保存。你可以稍后重试，或明确选择“仍然结束”。");
        updateRuntime({ lifecycle: "ending", persistence: "error" });
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "结束会话失败");
      updateRuntime({ lifecycle: "failed", persistence: "error" });
    }
  }

  function applySessionSummary(summary: SessionSummary | null) {
    setSessionSummary(summary);
    // Review starts from an explicit opt-in: nothing is pre-checked, so saving
    // without changes rejects every candidate (evidence discipline).
    const selections: Record<string, boolean> = {};
    summary?.candidate_errors.forEach((candidate) => {
      if (candidate.status === "candidate") selections[candidate.id] = false;
    });
    setReviewSelections(selections);
  }

  async function submitReview() {
    if (!sessionSummary || reviewSubmitting) return;
    setReviewSubmitting(true);
    setSummaryError("");
    for (const candidate of sessionSummary.candidate_errors) {
      if (candidate.status !== "candidate") continue;
      await decideError(candidate, reviewSelections[candidate.id] ? "confirmed" : "rejected");
    }
    setReviewSubmitting(false);
  }

  async function decideError(candidate: ErrorEvent, status: "confirmed" | "rejected") {
    setSummaryError("");
    try {
      const updated = await apiRequest<ErrorEvent>(`/api/v1/errors/${candidate.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setSessionSummary((current) => current ? {
        ...current,
        candidate_errors: current.candidate_errors.map((item) => item.id === updated.id ? updated : item),
      } : current);
    } catch (decisionError) {
      setSummaryError(decisionError instanceof Error ? decisionError.message : "保存判断失败");
    }
  }

  function resetForPractice() {
    setRuntime(initialLiveRuntime);
    runtimeRef.current = initialLiveRuntime;
    setVoiceSession(null);
    voiceSessionRef.current = null;
    setConnection(null);
    setUtterances([]);
    utterancesRef.current = [];
    setPartialAssistant("");
    setPartialUser("");
    setElapsed(0);
    elapsedRef.current = 0;
    setError("");
    setCanAbandonSave(false);
    setBudgetWarning(false);
  }

  useEffect(() => {
    finishSessionRef.current = (allowIncomplete = false) => void finishSession(allowIncomplete);
    joinFreshSessionRef.current = (join) => void resumeSession(join === "voice");
  });

  // Auto-join a session created on /practice: the page lands with ?join=voice|text
  // and the fresh session is continued through the same resume path as the
  // recovery card. Without the param this effect never fires, so direct
  // workspace restores keep their existing behavior.
  useEffect(() => {
    if (joinedSessionRef.current) return;
    if (runtime.lifecycle !== "idle" || !voiceSession) return;
    if (voiceSession.utterances.length > 0) return;
    if (!["created", "connecting"].includes(voiceSession.status)) return;
    const join = new URLSearchParams(window.location.search).get("join");
    if (join !== "voice" && join !== "text") return;
    joinedSessionRef.current = true;
    window.history.replaceState(null, "", `/conversation/${workspaceId}`);
    joinFreshSessionRef.current(join);
  }, [voiceSession, runtime.lifecycle, workspaceId]);

  const recoverableSession = runtime.lifecycle === "idle" && voiceSession &&
    ["created", "connecting", "reconnecting", "active", "ending"].includes(voiceSession.status);
  const canSend = voiceSession?.status === "active" && runtime.lifecycle === "live" && runtime.transport !== "reconnecting";
  const objective = selectedScenario?.objective ?? String(workspace?.state.objective ?? "完成一次自然、可理解的中文交流");
  const maximumSeconds = connection?.max_duration_seconds ?? 480;
  const remainingSeconds = Math.max(0, maximumSeconds - elapsed);
  const promptStarters = selectedScenario?.prompt_starters ?? (
    Array.isArray(workspace?.state.prompt_starters)
      ? workspace.state.prompt_starters as string[]
      : ["请问，你可以帮我吗？", "你可以说慢一点吗？"]
  );
  const connectionLabel = transportMode === "webrtc" ? "Qwen WebRTC" : transportMode === "text_fallback" ? "文字降级" : "本地模拟";
  const latestTurn = utterances[utterances.length - 1];
  const captionText = partialAssistant || partialUser || latestTurn?.transcript || "可以开始说话了";
  const captionSpeaker = partialAssistant ? "小文" : partialUser ? "你" : latestTurn?.speaker === "assistant" ? "小文" : "你";
  const orbLevel = liveState === "speaking" ? outputLevel : inputLevel;
  const orbStyle = { "--live-level": String(Math.max(0.08, orbLevel)) } as CSSProperties;

  const pendingReviewCount = sessionSummary?.candidate_errors.filter((candidate) => candidate.status === "candidate").length ?? 0;
  const checkedReviewCount = sessionSummary?.candidate_errors.filter(
    (candidate) => candidate.status === "candidate" && reviewSelections[candidate.id],
  ).length ?? 0;

  const railSidebar = ["starting", "live", "ending"].includes(runtime.lifecycle);

  return (
    <AppShell
      active="conversation"
      panel={(
        <div className="liveCoachPanel">
          <div className="coachIdentity"><span>文</span><div><strong>小文老师</strong><small>实时口语教练</small></div></div>
          <section><span className="sectionLabel">本次唯一目标</span><p>{objective}</p></section>
          <section><span className="sectionLabel">会话设置</span><dl><div><dt>估计水平</dt><dd>{String(voiceSession?.context_pack.estimated_hsk_band ?? selectedScenario?.level ?? "待确认")}</dd></div><div><dt>纠错</dt><dd>{correctionMode === "coach" ? "每轮 1 个重点" : correctionMode === "exam" ? "结束后反馈" : "最少干预"}</dd></div><div><dt>语速</dt><dd><button className="inlineSetting" onClick={() => void changeLivePreference({ speech_speed: speechSpeed === "slow" ? "normal" : "slow" })}>{speechSpeed === "slow" ? "慢速" : "正常"}</button></dd></div><div><dt>等待停顿</dt><dd><button className="inlineSetting" onClick={() => void changeLivePreference({ patience: patience === "patient" ? "normal" : "patient" })}>{patience === "patient" ? "耐心" : "普通"}</button></dd></div></dl></section>
          <section><span className="sectionLabel">连接质量</span><dl><div><dt>通道</dt><dd>{connectionLabel}</dd></div><div><dt>配置</dt><dd>{voiceSession?.applied_config_revision === voiceSession?.config_revision ? `v${voiceSession?.config_revision} 已应用` : "等待确认"}</dd></div><div><dt>自动重连</dt><dd>{voiceSession?.reconnect_count ?? 0} 次</dd></div><div><dt>有效打断</dt><dd>{voiceSession?.interruption_count ?? 0} 次</dd></div><div><dt>首段响应</dt><dd>{voiceSession?.first_response_latency_ms ? `${voiceSession.first_response_latency_ms} ms` : "待采样"}</dd></div></dl></section>
          <section className="liveTips"><span className="sectionLabel">可以这样开始</span>{promptStarters.map((starter) => <button key={starter} onClick={() => { setTextInput(starter); setShowTextInput(true); }}>{starter}</button>)}</section>
          {selectedScenario?.safety_note ? <div className="safetyNotice"><strong>场景边界</strong><p>{selectedScenario.safety_note}</p></div> : null}
          {transportMode !== "webrtc" && connection ? <div className="fallbackNotice"><strong>本地演练</strong><p>{connection.fallback_reason ?? "当前没有实时语音通道，回答由本地演练流程生成。"}</p></div> : null}
        </div>
      )}
      panelLabel="实时口语教练"
      rail={railSidebar}
      sidebar={(
        <>
          <Link className="backLink" href="/">← 返回今日计划</Link>
          <div className="scenarioBlock">
            <span className="sectionLabel lightLabel">SCENARIO</span>
            <h1>{selectedScenario?.title ?? workspace?.title ?? "正在加载…"}</h1>
            <p>{objective}</p>
          </div>
          <div className="modeBlock">
            <span>纠错模式</span>
            {(["immersion", "coach", "exam"] as const).map((mode) => (
              <button
                className={correctionMode === mode ? "modeOption active" : "modeOption"}
                disabled={Boolean(recoverableSession) || (runtime.lifecycle !== "idle" && runtime.lifecycle !== "ended")}
                key={mode}
                onClick={() => setCorrectionMode(mode)}
              >
                <strong>{mode === "immersion" ? "沉浸" : mode === "coach" ? "教练" : "考试"}</strong>
                <small>{mode === "immersion" ? "只在影响理解时纠正" : mode === "coach" ? "每轮最多一个重点" : "结束后统一反馈"}</small>
              </button>
            ))}
          </div>
          <div className="livePrivacy"><strong>音频不落盘</strong><span>只保存可靠文字转写和必要会话事件。</span></div>
        </>
      )}
    >
      <div className="stackColumn">
        <header className="liveHeader">
          <div><span className={`connectionDot ${liveState}`} />{stateCopy[liveState].label}</div>
          <strong>{formatTime(elapsed)} <small>{voiceSession?.context_pack.continuous ? `连续对话 · 第 ${Math.max(1, voiceSession.connection_epoch)} 段` : `/ ${formatTime(maximumSeconds)}`}</small></strong>
          {voiceSession && runtime.lifecycle === "live" ? <button onClick={() => void finishSession(false)}>结束并保存</button> : <span />}
        </header>
        {voiceSession ? <button className="inlineSetting" onClick={() => {
          void downloadConversation(voiceSession.id).then((blob) => {
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `conversation-${voiceSession.id}.md`;
            link.click();
            window.setTimeout(() => URL.revokeObjectURL(url), 1000);
          }).catch(() => setError("对话记录导出失败，请重试。"));
        }}>导出 Markdown 记录</button> : null}

        {budgetWarning ? (
          <div className="liveBudgetWarning" role="status"><strong>还剩 {formatTime(remainingSeconds)}</strong><span>到时会自动进入保存阶段。</span></div>
        ) : null}

        <div className="liveCanvas">
          {runtime.lifecycle === "idle" ? (
            <section className="startSessionCard">
              <div className="liveOrb idleOrb"><span /><span /><span /></div>
              <span className="sectionLabel">LIVE CHINESE</span>
              {recoverableSession ? (
                <div className="sessionRecoveryCard">
                  <h2>{voiceSession.status === "ending" ? "上次对话正在等待保存" : "发现一段未结束的对话"}</h2>
                  <p>
                    已恢复 {voiceSession.utterances.length} 条可靠记录。页面不会自动打开麦克风，
                    由你决定继续或结束。
                  </p>
                  <div className="sessionRecoveryMeta">
                    <span>连接代次 {voiceSession.connection_epoch}</span>
                    <span>{formatTime(elapsed)} 已记录</span>
                  </div>
                  <div className="startActions">
                    {voiceSession.status !== "ending" ? (
                      <>
                        <button className="primaryButton" onClick={() => void resumeSession(true)}>继续语音练习</button>
                        <button className="secondaryButton" onClick={() => void resumeSession(false)}>用文字继续</button>
                      </>
                    ) : null}
                    <button className="secondaryButton" onClick={() => void finishSession(false)}>
                      {voiceSession.status === "ending" ? "完成保存" : "结束并查看记录"}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <h2>今天想怎么练中文？</h2>
                  <p>真实模式使用 WebRTC 连续交流；未配置实时模型时会清楚标注本地演练。</p>
                  <div className="scenarioPicker" aria-label="选择练习方式">
                    {(["scenario", "free", "custom"] as const).map((mode) => (
                      <button key={mode} aria-pressed={practiceMode === mode} className={practiceMode === mode ? "active" : ""} onClick={() => setPracticeMode(mode)}>
                        <strong>{mode === "scenario" ? "场景练习" : mode === "free" ? "自由对话" : "自定义目标"}</strong>
                        <small>{mode === "scenario" ? "选择生活场景" : mode === "free" ? "聊任何感兴趣的话题" : "按你的需求练习"}</small>
                      </button>
                    ))}
                  </div>
                  {practiceMode === "custom" ? (
                    <label className="customPracticeGoal">
                      <span>你想练习什么？</span>
                      <textarea value={customObjective} onChange={(event) => setCustomObjective(event.target.value)} maxLength={500} rows={3} placeholder="例如：明天我要面试，请扮演面试官，帮我练习中文自我介绍。" />
                      <small>{customObjective.length}/500 字 · 开始后本次目标固定，下次练习可修改。</small>
                    </label>
                  ) : null}
                  {practiceMode === "free" ? <p>从今天的经历、兴趣或任何想聊的话题开始，也可以让小文帮你找话题。</p> : null}
                  {practiceMode === "scenario" ? (
                  <div className="scenarioPicker" aria-label="选择对话场景">
                    {scenarios.map((scenario) => (
                      <button className={selectedScenarioId === scenario.id ? "active" : ""} key={scenario.id} onClick={() => setSelectedScenarioId(scenario.id)}>
                        <strong>{scenario.title}</strong><small>{scenario.level} · {scenario.category}</small>
                      </button>
                    ))}
                  </div>
                  ) : null}
                  <div className="startActions">
                    <button disabled={practiceMode === "custom" && !customObjective.trim()} className="primaryButton" onClick={() => void startSession(true)}>使用麦克风开始</button>
                    <button disabled={practiceMode === "custom" && !customObjective.trim()} className="secondaryButton" onClick={() => void startSession(false)}>先用文字演练</button>
                  </div>
                  <div className="startPreferences">
                    <div className="speedToggle"><span>AI 语速</span><button className={speechSpeed === "slow" ? "active" : ""} onClick={() => setSpeechSpeed("slow")}>慢速</button><button className={speechSpeed === "normal" ? "active" : ""} onClick={() => setSpeechSpeed("normal")}>正常</button></div>
                    <div className="speedToggle"><span>等待停顿</span><button className={patience === "patient" ? "active" : ""} onClick={() => setPatience("patient")}>耐心</button><button className={patience === "normal" ? "active" : ""} onClick={() => setPatience("normal")}>普通</button></div>
                  </div>
                </>
              )}
            </section>
          ) : (
            <>
              <section className="liveStatusHero liveCallStage">
                <div className={`liveOrb ${liveState}`} style={orbStyle}><span /><span /><span /><span /><span /></div>
                <h2>{stateCopy[liveState].label}</h2>
                <ToolActivityPanel activity={toolActivity} />
                <p>{continuingSegment ? "正在载入历史摘录并续接下一段，请稍候再说话。" : liveState === "reconnecting" ? `正在进行第 ${reconnectAttempt}/${MAX_RECONNECT_ATTEMPTS} 次自动重连。` : stateCopy[liveState].note}</p>
                {connection ? <span className={`providerBadge ${transportMode !== "webrtc" ? "mock" : ""}`}>{connectionLabel} · {connection.model}</span> : null}
                {runtime.lifecycle !== "ended" ? <div className="liveCaptionPreview" aria-live="polite"><span>{captionSpeaker}</span><p>{captionText}</p></div> : null}
                {runtime.lifecycle === "live" ? (
                  <div className="liveControls" aria-label="通话控制">
                    <button className={microphoneMuted ? "active" : ""} disabled={!streamRef.current} onClick={toggleMicrophone}><span>{microphoneMuted ? "◌" : "●"}</span>{microphoneMuted ? "取消静音" : "静音"}</button>
                    <button disabled={!["playing", "thinking"].includes(runtime.output)} onClick={() => void stopCurrentAnswer("button")}><span>■</span>停止回答</button>
                    <button className={showTranscript ? "active" : ""} onClick={() => setShowTranscript((current) => !current)}><span>字幕</span>{showTranscript ? "收起记录" : "查看记录"}</button>
                    <button className={showTextInput ? "active" : ""} onClick={() => setShowTextInput((current) => !current)}><span>键盘</span>文字输入</button>
                  </div>
                ) : null}
                {canAbandonSave ? <div className="saveRecovery"><p>仍有转写未保存，继续结束会把本次标记为记录不完整。</p><button onClick={() => void finishSession(true)}>仍然结束</button></div> : null}
                {runtime.lifecycle === "ended" ? <button className="secondaryButton practiceAgain" onClick={resetForPractice}>再练一次</button> : null}
              </section>

              {runtime.lifecycle === "ended" ? (
                <section className="sessionReport reveal" aria-label="本次学习报告">
                  <div className="reportHeading">
                    <div><span className="sectionLabel">SESSION REPORT</span><h3>{summaryLoading ? "正在提炼本次对话…" : "本次学习报告"}</h3></div>
                    {sessionSummary ? <span className={`taskResult ${sessionSummary.task_status}`}>{sessionSummary.task_status === "completed" ? "任务完成" : sessionSummary.task_status === "partially-completed" ? "部分完成" : "未完成"}</span> : null}
                  </div>
                  {summaryError ? <p className="reportError">{summaryError}</p> : null}
                  {sessionSummary ? (
                    <>
                      <p className="reportExplanation">{sessionSummary.task_explanation}</p>
                      <ul className="reportHighlights">{sessionSummary.highlights.map((highlight) => <li key={highlight}>{highlight}</li>)}</ul>
                      {sessionSummary.candidate_errors.length ? (
                        <div className="candidateErrors">
                          <div className="candidateIntro"><strong>本次回顾：这些候选错误要收入错误本吗？</strong><span>逐条勾选想记住的候选；保存后勾选项进入错误本，其余被忽略且不再提示。</span></div>
                          {pendingReviewCount ? (
                            <>
                              {sessionSummary.candidate_errors.filter((candidate) => candidate.status === "candidate").map((candidate) => (
                                <label className={`candidateError reviewItem ${reviewSelections[candidate.id] ? "selected" : ""}`} key={candidate.id}>
                                  <input
                                    aria-label={`把“${candidate.corrected_text}”收入错误本`}
                                    checked={reviewSelections[candidate.id] ?? false}
                                    disabled={reviewSubmitting}
                                    onChange={(event) => setReviewSelections((current) => ({ ...current, [candidate.id]: event.target.checked }))}
                                    type="checkbox"
                                  />
                                  <div className="reviewItemBody">
                                    <div className="errorRewrite"><span>{candidate.learner_text}</span><strong>→ {candidate.corrected_text}</strong></div>
                                    <p>{candidate.explanation}</p>
                                    <div className="errorMeta"><span>{candidate.hsk_tags.join(" · ") || candidate.subtype}</span><span>置信度 {Math.round(candidate.confidence * 100)}%</span></div>
                                  </div>
                                </label>
                              ))}
                              <div className="reviewSubmitBar">
                                <span>将收入 {checkedReviewCount} 条 · 忽略 {pendingReviewCount - checkedReviewCount} 条</span>
                                <button className="primaryButton" disabled={reviewSubmitting} onClick={() => void submitReview()} type="button">{reviewSubmitting ? "正在保存…" : "保存回顾"}</button>
                              </div>
                            </>
                          ) : (
                            <>
                              {sessionSummary.candidate_errors.map((candidate) => (
                                <article className={`candidateError ${candidate.status}`} key={candidate.id}>
                                  <div className="errorRewrite"><span>{candidate.learner_text}</span><strong>→ {candidate.corrected_text}</strong></div>
                                  <p>{candidate.explanation}</p>
                                  <div className="errorMeta"><span>{candidate.hsk_tags.join(" · ") || candidate.subtype}</span><span>置信度 {Math.round(candidate.confidence * 100)}%</span></div>
                                  <span className="decisionState">{candidate.status === "confirmed" ? "✓ 已加入错误记忆" : "已忽略"}</span>
                                </article>
                              ))}
                              <div className="reviewSubmitBar">
                                <span>回顾已保存：收入 {sessionSummary.candidate_errors.filter((candidate) => candidate.status === "confirmed").length} 条 · 忽略 {sessionSummary.candidate_errors.filter((candidate) => candidate.status === "rejected").length} 条</span>
                              </div>
                            </>
                          )}
                        </div>
                      ) : <p className="noCandidateError">本次没有发现可可靠确认的典型错误。</p>}
                      <div className="nextStep"><span>下一步</span><strong>{sessionSummary.next_step}</strong><Link href="/errors">打开错误本 →</Link></div>
                      <small className="reportProvenance">{sessionSummary.provider} / {sessionSummary.model} · 教学 Skill {sessionSummary.skill_version}</small>
                    </>
                  ) : null}
                </section>
              ) : null}

              {(showTranscript || runtime.lifecycle === "ended") ? (
                <section className="transcriptStream liveTranscriptDrawer reveal" aria-live="polite">
                  <div className="transcriptDrawerHeading"><strong>本次对话</strong><span>{utterances.length} 条可靠记录</span></div>
                  {utterances.map((utterance) => (
                    <article className={`transcriptTurn ${utterance.speaker}`} key={utterance.id}>
                      <span>{utterance.speaker === "assistant" ? "小文" : "你"}</span>
                      <div><p>{utterance.transcript}</p><small>{utterance.source === "provider" ? "实时转写" : utterance.source === "mock" ? "本地演练" : "文字输入"}{utterance.playback_status === "interrupted" ? " · 已打断" : ""}</small></div>
                    </article>
                  ))}
                  {partialUser ? <article className="transcriptTurn user partial"><span>你</span><div><p>{partialUser}</p><small>识别中，不会写入学习记录</small></div></article> : null}
                  {partialAssistant ? <article className="transcriptTurn assistant partial"><span>小文</span><div><p>{partialAssistant}</p><small>正在生成，不会写入学习记录</small></div></article> : null}
                  {utterances.length === 0 && !partialUser && !partialAssistant ? <p className="emptyTranscript">可靠转写会出现在这里。</p> : null}
                </section>
              ) : null}
            </>
          )}
        </div>

        {error ? <div className="liveError" role="alert">{error}</div> : null}
        {canSend && showTextInput ? <form className="liveComposer" onSubmit={sendText}><button aria-label="使用浏览器语音识别" className={recognizing ? "speechButton active" : "speechButton"} onClick={toggleSpeechRecognition} type="button">◉</button><input aria-label="输入一句中文" onChange={(event) => setTextInput(event.target.value)} placeholder="输入一句中文…" value={textInput} /><button aria-label="发送" className="sendButton" type="submit">↑</button></form> : null}
        <audio autoPlay playsInline ref={audioRef} />
      </div>
    </AppShell>
  );
}
