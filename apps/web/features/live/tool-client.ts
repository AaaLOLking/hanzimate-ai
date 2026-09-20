import { API_BASE_URL } from "../../lib/api";

export interface ToolSource {
  title: string;
  url?: string;
  level?: string;
  explanation?: string;
  excerpt?: string;
}
export interface ToolActivity {
  name: string;
  status: string;
  message: string;
  sources: ToolSource[];
}
interface Call {
  name: string;
  call_id: string;
  response_id: string;
  arguments: string;
}
interface Options {
  sessionId: string;
  epoch: number;
  send(event: Record<string, unknown>): void;
  onActivity?(activity: ToolActivity): void;
}

export function createToolBridge(options: Options) {
  const headers = {
    "Content-Type": "application/json",
    "X-Learner-ID": process.env.NEXT_PUBLIC_DEMO_USER_ID ?? "00000000-0000-4000-8000-000000000001",
  };
  const pending = new Map<string, Call>();
  const seen = new Set<string>();
  const cancelled = new Set<string>();
  let generation = 0;
  let responseId = "";
  let running = false;
  let controller: AbortController | null = null;
  let watchdog: ReturnType<typeof setTimeout> | null = null;
  const report = (activity: ToolActivity) => options.onActivity?.(activity);
  const scope = (id: string) => ({ connection_epoch: options.epoch, response_id: id });
  const url = `${API_BASE_URL}/api/v1/voice/sessions/${options.sessionId}/tools`;
  const cancel = () => {
    generation += 1;
    if (watchdog) clearTimeout(watchdog);
    watchdog = null;
    const hadWork = running || pending.size > 0;
    if (responseId) cancelled.add(responseId);
    if (hadWork && responseId) {
      void fetch(`${url}/cancel`, {
        method: "POST", headers, body: JSON.stringify(scope(responseId)), keepalive: true,
      }).catch(() => { /* Local generation fencing still discards late results. */ });
      report({ name: "工具查询", status: "cancelled", message: "查询已取消，旧结果不会继续播报。", sources: [] });
    }
    controller?.abort();
    controller = null;
    pending.clear();
    running = false;
  };
  const run = async () => {
    if (running || !pending.size) return;
    running = true;
    if (watchdog) clearTimeout(watchdog);
    const ticket = generation;
    const calls = [...pending.values()];
    pending.clear();
    const outputs: { call: Call; output: ToolActivity }[] = [];
    for (const call of calls) {
      if (ticket !== generation) return;
      controller = new AbortController();
      const activeController = controller;
      report({ name: call.name, status: "running", message: "正在查询资料…", sources: [] });
      const timeout = setTimeout(() => activeController.abort(), 35000);
      let output: ToolActivity;
      try {
        const response = await fetch(`${url}/execute`, {
          method: "POST", headers, signal: activeController.signal,
          body: JSON.stringify({ ...call, connection_epoch: options.epoch }),
        });
        if (!response.ok) throw new Error("工具请求失败");
        output = { ...(await response.json()), name: call.name } as ToolActivity;
        if (output.status === "running") {
          output = { name: call.name, status: "failed", message: "重复请求仍在处理，没有可用结果。", sources: [] };
        }
      } catch {
        output = { name: call.name, status: "failed", message: "查询失败或超时，没有获得可靠结果。", sources: [] };
      } finally {
        clearTimeout(timeout);
      }
      if (ticket !== generation) return;
      report(output);
      outputs.push({ call, output });
    }
    if (ticket !== generation) return;
    try {
      for (const { call, output } of outputs) {
        if (output.status === "cancelled") continue;
        options.send({ type: "conversation.item.create", item: {
          type: "function_call_output", call_id: call.call_id, output: JSON.stringify(output),
        } });
      }
      if (outputs.some(({ output }) => output.status !== "cancelled")) {
        options.send({ type: "response.create" });
      }
    } catch {
      report({ name: "工具查询", status: "failed", message: "语音连接已断开，结果未交给模型。", sources: [] });
    } finally {
      running = false;
      controller = null;
    }
  };
  return {
    isBusy: () => running || pending.size > 0,
    cancel,
    onEvent(event: Record<string, unknown>) {
      if (event.type === "input_audio_buffer.speech_started") cancel();
      if (event.type === "response.created") {
        const id = (event.response as { id?: string } | undefined)?.id;
        if (id && id !== responseId && (running || pending.size > 0)) cancel();
        if (id) responseId = id;
      }
      if (event.type === "response.function_call_arguments.done") {
        const call = event as unknown as Call;
        if (![call.name, call.call_id, call.response_id, call.arguments].every((value) => typeof value === "string")) return;
        if (cancelled.has(call.response_id) || (responseId && call.response_id !== responseId)) return;
        if (seen.has(call.call_id)) return;
        seen.add(call.call_id);
        responseId = call.response_id;
        pending.set(call.call_id, { name: call.name, call_id: call.call_id,
          response_id: call.response_id, arguments: call.arguments });
        report({ name: call.name, status: "running", message: "准备查询资料…", sources: [] });
        if (watchdog) clearTimeout(watchdog);
        watchdog = setTimeout(cancel, 20000);
      }
      if (event.type === "response.done") {
        const response = event.response as { id?: string; status?: string } | undefined;
        if (response?.id !== responseId) return;
        if (response.status === "completed") void run();
        else cancel();
      }
    },
  };
}
