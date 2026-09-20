// Shared practice-mode selection → session-create payload mapping.
// Used by /practice (new entry) and the conversation page start card so both
// paths produce identical VoiceSessionCreate bodies (backend contract unchanged).

export type PracticeMode = "scenario" | "free" | "custom";
export type CorrectionMode = "immersion" | "coach" | "exam";
export type SpeechSpeed = "slow" | "normal";
export type Patience = "normal" | "patient";

export interface PracticeSessionOptions {
  practiceMode: PracticeMode;
  customObjective: string;
  scenarioId: string | undefined;
  scenarioTitle: string | undefined;
  correctionMode: CorrectionMode;
  speechSpeed: SpeechSpeed;
  patience: Patience;
}

/**
 * Build the POST /api/v1/voice/sessions body. `undefined` fields are dropped by
 * JSON.stringify, matching the backend rule that custom_objective is only valid
 * for custom practice and scenario_id only for scenario practice.
 */
export function buildPracticeSessionPayload(options: PracticeSessionOptions): Record<string, unknown> {
  return {
    client_session_id: crypto.randomUUID(),
    protocol_version: "live-v1",
    continuous: true,
    practice_mode: options.practiceMode,
    custom_objective: options.practiceMode === "custom" ? options.customObjective.trim() : undefined,
    scenario_id: options.practiceMode === "scenario" ? options.scenarioId : undefined,
    scenario: options.scenarioTitle ?? "中文场景对话",
    correction_mode: options.correctionMode,
    speech_speed: options.speechSpeed,
    patience: options.patience,
  };
}

/** Custom practice requires a non-empty objective; mirrors backend validation client-side. */
export function isPracticeStartable(options: Pick<PracticeSessionOptions, "practiceMode" | "customObjective">): boolean {
  return options.practiceMode !== "custom" || Boolean(options.customObjective.trim());
}
