export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export async function downloadConversation(sessionId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/v1/voice/sessions/${sessionId}/transcript.md`, {
    headers: { "X-Learner-ID": DEMO_USER_ID },
  });
  if (!response.ok) throw new Error("导出失败，请稍后重试。");
  return response.blob();
}

const DEMO_USER_ID =
  process.env.NEXT_PUBLIC_DEMO_USER_ID ?? "00000000-0000-4000-8000-000000000001";

export interface Workspace {
  id: string;
  kind: "conversation" | "lesson" | "review";
  title: string;
  status: "active" | "processing" | "review_due" | "completed" | "archived";
  state: Record<string, unknown>;
  updated_at: string;
  last_opened_at: string;
}

export interface OnboardingState {
  complete: boolean;
  user: {
    id: string;
    email: string;
    display_name: string;
    locale: string;
  };
  mission: null | {
    id: string;
    why: string;
    success_looks_like: string[];
    priorities: string[];
    weekly_minutes: number;
    deadline: string | null;
  };
  profile: null | {
    estimated_hsk_band: string;
    skill_estimates: Record<string, number>;
    preferences: Record<string, unknown>;
  };
  recommended_workspace: Workspace | null;
}

export interface ModelOption {
  id: string;
  provider: string;
  model: string;
  display_name: string;
  capabilities: string[];
}

export interface ModelRun {
  id: string;
  task: "conversation_summary" | "lesson_tutor";
  provider: string;
  model: string;
  status: "succeeded" | "failed" | "blocked";
  latency_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_yuan: number;
  error_code: string | null;
  fallback_from: string | null;
  created_at: string;
}

export interface ModelUsage {
  date: string;
  total_calls: number;
  external_calls: number;
  failed_calls: number;
  blocked_calls: number;
  estimated_cost_yuan: number;
  daily_external_call_limit: number;
  remaining_external_calls: number;
  pricing_configured: boolean;
  recent_runs: ModelRun[];
}

export interface AccountOverview {
  user: OnboardingState["user"];
  consent: null | {
    policy_version: string;
    privacy_acknowledged: boolean;
    learning_memory: boolean;
    audio_retention: boolean;
    granted_at: string;
  };
  mission: OnboardingState["mission"];
  profile: null | OnboardingState["profile"] & {
    user_id: string;
    native_language: string;
    support_language: string;
    projection_version: number;
    updated_at: string;
  };
  stats: {
    workspaces: number;
    conversations: number;
    lessons_started: number;
    lessons_completed: number;
    active_memories: number;
    review_attempts: number;
  };
  model_usage: ModelUsage;
}

export interface AccountDeletionReceipt {
  receipt_id: string;
  deleted_at: string;
  deleted_records: Record<string, number>;
}

export interface BetaFeedback {
  id: string;
  area: "conversation" | "course" | "review" | "overall";
  issue_type: "praise" | "wrong_correction" | "confusing" | "slow" | "bug" | "idea" | "other";
  rating: number;
  is_blocking: boolean;
  message: string;
  page_path: string | null;
  created_at: string;
}

export interface BetaDashboard {
  progress: Record<"conversations" | "lessons" | "reviews" | "feedback", {
    current: number;
    target: number;
    complete: boolean;
  }>;
  ready_for_exit: boolean;
  feedback: BetaFeedback[];
}

export interface Utterance {
  id: string;
  client_event_id: string;
  sequence_no: number;
  connection_epoch: number;
  provider_item_id: string | null;
  provider_response_id: string | null;
  content_index: number;
  speaker: "user" | "assistant";
  transcript: string;
  source: "provider" | "browser_speech" | "browser_text" | "mock";
  is_final: boolean;
  transcript_status: "partial" | "final" | "incomplete";
  playback_status: "not_applicable" | "unknown" | "completed" | "interrupted";
  started_ms: number | null;
  ended_ms: number | null;
  created_at: string;
}

export interface VoiceSession {
  id: string;
  workspace_id: string;
  status:
    | "created"
    | "connecting"
    | "reconnecting"
    | "active"
    | "ending"
    | "completed"
    | "failed";
  correction_mode: "immersion" | "coach" | "exam";
  speech_speed: "slow" | "normal";
  patience: "normal" | "patient";
  provider: string;
  model: string;
  voice: string;
  connection_mode: "webrtc" | "mock";
  client_session_id: string | null;
  protocol_version: "legacy" | "live-v1";
  skill_version: string;
  context_pack: Record<string, unknown>;
  requested_config: Record<string, unknown>;
  config_revision: number;
  applied_config_revision: number | null;
  connection_epoch: number;
  transport_status:
    | "idle"
    | "connecting"
    | "connected"
    | "reconnecting"
    | "text_fallback"
    | "closed"
    | "error";
  deadline_at: string | null;
  max_duration_seconds: number;
  duration_seconds: number;
  reconnect_count: number;
  interruption_count: number;
  first_response_latency_ms: number | null;
  last_event_at: string | null;
  failure_reason: string | null;
  created_at: string;
  started_at: string | null;
  ending_at: string | null;
  ended_at: string | null;
  end_reason:
    | "user_ended"
    | "cancelled_start"
    | "practice_limit"
    | "connection_failed"
    | "client_abandoned"
    | "save_incomplete"
    | null;
  closing_manifest: Record<string, unknown> | null;
  utterances: Utterance[];
}

export interface RealtimeConnection {
  mode: "webrtc" | "mock";
  provider: string;
  model: string;
  voice: string;
  max_duration_seconds: number;
  fallback_reason: string | null;
  session_update: Record<string, unknown>;
  capabilities: Record<
    string,
    "verified" | "unsupported" | "unverified"
  >;
}

export interface VoiceSessionPreferences {
  config_revision: number;
  applied_config_revision: number | null;
  requested_config: Record<string, unknown>;
  session_update: Record<string, unknown>;
}

export interface VoiceSessionCreated {
  session: VoiceSession;
  connection: RealtimeConnection;
}

export interface ConversationScenario {
  id: string;
  title: string;
  category: string;
  level: string;
  objective: string;
  opening_line: string;
  prompt_starters: string[];
  safety_note: string | null;
}

export type SessionEventType =
  | "connection_attempt"
  | "connection_established"
  | "connection_lost"
  | "reconnect_attempt"
  | "segment_continued"
  | "reconnect_succeeded"
  | "reconnect_failed"
  | "interruption"
  | "provider_first_response"
  | "budget_warning"
  | "fallback_activated"
  | "provider_error"
  | "config_applied"
  | "user_speech_started"
  | "user_speech_stopped"
  | "output_started"
  | "output_stopped"
  | "transcript_save_failed"
  | "session_heartbeat"
  | "session_timeout"
  | "save_incomplete";

export interface SessionEvent {
  id: string;
  client_event_id: string;
  event_type: SessionEventType;
  elapsed_ms: number | null;
  event_payload: Record<string, unknown>;
  created_at: string;
}

export interface ErrorEvent {
  id: string;
  session_id: string;
  cluster_id: string | null;
  learner_text: string;
  corrected_text: string;
  explanation: string;
  error_type: string;
  subtype: string;
  severity: "blocking" | "major" | "minor" | "optional";
  confidence: number;
  status: "candidate" | "confirmed" | "rejected";
  evidence_span: string;
  canonical_key: string;
  hsk_tags: string[];
  model_version: string;
  skill_version: string;
  observed_at: string;
  created_at: string;
}

export interface SessionSummary {
  id: string;
  session_id: string;
  task_status: "completed" | "partially-completed" | "not-completed";
  task_explanation: string;
  highlights: string[];
  next_step: string;
  provider: string;
  model: string;
  skill_version: string;
  generated_at: string;
  candidate_errors: ErrorEvent[];
}

export interface ErrorCluster {
  id: string;
  canonical_key: string;
  error_type: string;
  subtype: string;
  explanation: string;
  corrected_example: string;
  status: "active" | "archived";
  occurrence_count: number;
  first_seen_at: string;
  last_seen_at: string;
  updated_at: string;
  next_review_at: string | null;
}

export interface LessonProgress {
  id: string;
  workspace_id: string;
  status: "in_progress" | "completed";
  current_step: number;
  attempt_count: number;
  best_score: number;
  started_at: string;
  completed_at: string | null;
  updated_at: string;
}

export interface CourseLesson {
  id: string;
  slug: string;
  position: number;
  title: string;
  track: "daily-life" | "hsk";
  level: string;
  objective: string;
  estimated_minutes: number;
  targets: string[];
  progress: LessonProgress | null;
}

export interface Course {
  id: string;
  slug: string;
  version: number;
  title: string;
  description: string;
  framework: string;
  level: string;
  lessons: CourseLesson[];
}

export interface LessonActivity {
  prompt: string;
  feedback_rule: string;
}

export interface LessonExample {
  chinese: string;
  pinyin?: string;
  support_text?: string;
  note: string;
}

export interface LessonContent {
  prerequisites: string[];
  explanation: string;
  examples: LessonExample[];
  guided_practice: LessonActivity;
  retrieval_practice: LessonActivity;
  transfer_task: LessonActivity;
  completion_evidence: string;
  next_review?: string;
}

export interface LessonMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  provider: string;
  model: string;
  citations: Array<{ id: string; title: string; publisher: string; url: string }>;
  created_at: string;
}

export interface LessonDetail {
  id: string;
  course_id: string;
  course_title: string;
  course_version: number;
  slug: string;
  version: number;
  position: number;
  title: string;
  framework: string;
  level: string;
  objective: string;
  estimated_minutes: number;
  targets: string[];
  sources: Array<{ id: string; title: string; publisher: string; url: string }>;
  content: LessonContent;
  context_pack: Record<string, unknown>;
  skill_version: string;
  progress: LessonProgress | null;
  messages: LessonMessage[];
}

export interface LessonAttemptResult {
  passed: boolean;
  score: number;
  feedback: string;
  missing_targets: string[];
  next_activity: "guided" | "retrieval" | "transfer" | "completed";
  progress: LessonProgress;
  evidence: {
    id: string;
    evidence_type: string;
    response: string;
    passed: boolean;
    score: number;
    feedback: string;
    skill_version: string;
    observed_at: string;
  };
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Learner-ID", DEMO_USER_ID);
  if (init.body) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const errorDetail = detail?.detail;
    const message = typeof errorDetail === "string"
      ? errorDetail
      : typeof errorDetail?.message === "string"
        ? errorDetail.message
        : "请求失败，请稍后重试";
    throw new ApiError(message, response.status, errorDetail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function downloadAccountArchive(): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/account/export`, {
    headers: { "X-Learner-ID": DEMO_USER_ID },
  });
  if (!response.ok) throw new Error("数据导出失败，请稍后重试");
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "hanzimate-data.json";
  return { blob: await response.blob(), filename };
}
