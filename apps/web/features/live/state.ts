export type SessionLifecycle =
  | "idle"
  | "starting"
  | "live"
  | "ending"
  | "ended"
  | "failed";

export type TransportState =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "fallback"
  | "closed"
  | "error";

export type InputState = "unavailable" | "requesting" | "ready" | "speech" | "muted";
export type OutputState = "idle" | "thinking" | "playing" | "stopped";
export type PersistenceState = "idle" | "saving" | "saved" | "error";

export interface LiveRuntimeState {
  lifecycle: SessionLifecycle;
  transport: TransportState;
  input: InputState;
  output: OutputState;
  persistence: PersistenceState;
}

export type LiveViewState =
  | "idle"
  | "connecting"
  | "reconnecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "ending"
  | "ended"
  | "error";

export const initialLiveRuntime: LiveRuntimeState = {
  lifecycle: "idle",
  transport: "idle",
  input: "unavailable",
  output: "idle",
  persistence: "idle",
};

export function projectLiveView(state: LiveRuntimeState): LiveViewState {
  if (state.lifecycle === "idle") return "idle";
  if (state.lifecycle === "ending") return "ending";
  if (state.lifecycle === "ended") return "ended";
  if (state.lifecycle === "failed" || state.transport === "error" || state.persistence === "error") {
    return "error";
  }
  if (state.transport === "connecting") return "connecting";
  if (state.transport === "reconnecting") return "reconnecting";
  if (state.output === "playing") return "speaking";
  if (state.output === "thinking") return "thinking";
  return "listening";
}
