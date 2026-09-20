export type ProviderEvent =
  | { kind: "config_ack"; rawType: string }
  | { kind: "user_speech_started"; rawType: string; audioStartMs: number | null }
  | { kind: "user_speech_stopped"; rawType: string; audioEndMs: number | null }
  | {
      kind: "user_caption_preview";
      rawType: string;
      transcript: string;
      itemId: string | null;
      contentIndex: number;
    }
  | {
      kind: "user_caption_final";
      rawType: string;
      transcript: string;
      itemId: string | null;
      contentIndex: number;
    }
  | {
      kind: "user_caption_failed";
      rawType: string;
      itemId: string | null;
      message: string;
    }
  | { kind: "response_started"; rawType: string; responseId: string | null }
  | {
      kind: "assistant_caption_delta";
      rawType: string;
      delta: string;
      itemId: string | null;
      responseId: string | null;
      contentIndex: number;
    }
  | {
      kind: "assistant_caption_final";
      rawType: string;
      transcript: string;
      itemId: string | null;
      responseId: string | null;
      contentIndex: number;
    }
  | {
      kind: "response_terminal";
      rawType: string;
      responseId: string | null;
      status: "completed" | "cancelled" | "failed" | "unknown";
    }
  | {
      kind: "provider_error";
      rawType: string;
      message: string;
      code: string | null;
      errorType: string | null;
    }
  | { kind: "unknown"; rawType: string };

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object"
    ? (value as Record<string, unknown>)
    : null;
}

function firstString(...values: unknown[]) {
  return values.find((value): value is string => typeof value === "string") ?? null;
}

function firstNumber(...values: unknown[]) {
  return values.find((value): value is number => typeof value === "number") ?? null;
}

function contentIndex(event: Record<string, unknown>) {
  const value = firstNumber(event.content_index, event.output_index);
  return value === null ? 0 : Math.max(0, value);
}

export function parseProviderEvent(rawEvent: string): ProviderEvent | null {
  let event: Record<string, unknown>;
  try {
    event = JSON.parse(rawEvent) as Record<string, unknown>;
  } catch {
    return null;
  }

  const rawType = firstString(event.type) ?? "";
  const item = record(event.item);
  const response = record(event.response);
  const error = record(event.error);
  const itemId = firstString(event.item_id, item?.id);
  const responseId = firstString(event.response_id, response?.id);

  if (rawType === "session.updated") {
    return { kind: "config_ack", rawType };
  }
  if (rawType.endsWith("speech_started")) {
    return {
      kind: "user_speech_started",
      rawType,
      audioStartMs: firstNumber(event.audio_start_ms, event.audio_start),
    };
  }
  if (rawType.endsWith("speech_stopped")) {
    return {
      kind: "user_speech_stopped",
      rawType,
      audioEndMs: firstNumber(event.audio_end_ms, event.audio_end),
    };
  }
  if (rawType.endsWith("input_audio_transcription.delta")) {
    return {
      kind: "user_caption_preview",
      rawType,
      transcript: firstString(event.delta, event.transcript) ?? "",
      itemId,
      contentIndex: contentIndex(event),
    };
  }
  if (rawType.endsWith("input_audio_transcription.completed")) {
    return {
      kind: "user_caption_final",
      rawType,
      transcript: firstString(event.transcript, event.text) ?? "",
      itemId,
      contentIndex: contentIndex(event),
    };
  }
  if (rawType.endsWith("input_audio_transcription.failed")) {
    return {
      kind: "user_caption_failed",
      rawType,
      itemId,
      message: firstString(error?.message, event.message) ?? "学习者语音转写失败",
    };
  }
  if (rawType === "response.created") {
    return { kind: "response_started", rawType, responseId };
  }
  if (rawType === "response.audio_transcript.delta") {
    return {
      kind: "assistant_caption_delta",
      rawType,
      delta: firstString(event.delta, event.transcript) ?? "",
      itemId,
      responseId,
      contentIndex: contentIndex(event),
    };
  }
  if (rawType === "response.audio_transcript.done") {
    return {
      kind: "assistant_caption_final",
      rawType,
      transcript: firstString(event.transcript, event.text) ?? "",
      itemId,
      responseId,
      contentIndex: contentIndex(event),
    };
  }
  if (
    rawType === "response.done" ||
    rawType === "response.cancelled" ||
    rawType === "response.failed"
  ) {
    const providerStatus = firstString(response?.status, event.status);
    const status = rawType === "response.cancelled"
      ? "cancelled"
      : rawType === "response.failed"
        ? "failed"
        : providerStatus === "completed" || providerStatus === "cancelled" || providerStatus === "failed"
          ? providerStatus
          : "unknown";
    return { kind: "response_terminal", rawType, responseId, status };
  }
  if (rawType === "error") {
    return {
      kind: "provider_error",
      rawType,
      message: firstString(error?.message, event.message) ?? "实时模型返回错误",
      code: firstString(error?.code, event.code),
      errorType: firstString(error?.type, event.error_type),
    };
  }
  return { kind: "unknown", rawType };
}

/** Fatal errors kill every follow-up request on this connection (auth/quota/session
 * level), so the session degrades to text mode. Request-scoped, recoverable errors —
 * e.g. "Conversation already has an active response" — must NOT degrade the session. */
export function isFatalProviderError(error: { code: string | null; errorType: string | null; message: string }): boolean {
  const haystack = `${error.errorType ?? ""} ${error.code ?? ""} ${error.message}`.toLowerCase();
  return /auth|permission|forbidden|unauthori|api[_-]?key|access[_-]?token|quota|billing|insufficient/.test(haystack);
}
