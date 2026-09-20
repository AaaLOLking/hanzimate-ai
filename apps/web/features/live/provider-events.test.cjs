/* eslint-disable @typescript-eslint/no-require-imports -- Node test runner executes this file as CommonJS. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

function setup() {
  const source = fs.readFileSync(require.resolve("./provider-events.ts"), "utf8");
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const sandbox = { exports: {}, require: () => ({}), process };
  vm.runInNewContext(js, sandbox);
  return sandbox.exports;
}

test("error event exposes message, code and error type", () => {
  const { parseProviderEvent } = setup();
  const event = parseProviderEvent(JSON.stringify({
    type: "error",
    error: {
      type: "invalid_request_error",
      code: "conversation_already_has_active_response",
      message: "Conversation already has an active response",
    },
  }));
  assert.equal(event.kind, "provider_error");
  assert.equal(event.message, "Conversation already has an active response");
  assert.equal(event.code, "conversation_already_has_active_response");
  assert.equal(event.errorType, "invalid_request_error");
});

test("error event without code still parses", () => {
  const { parseProviderEvent } = setup();
  const event = parseProviderEvent(JSON.stringify({ type: "error", error: { message: "boom" } }));
  assert.equal(event.kind, "provider_error");
  assert.equal(event.message, "boom");
  assert.equal(event.code, null);
  assert.equal(event.errorType, null);
});

test("active-response conflict is recoverable, never fatal", () => {
  const { isFatalProviderError } = setup();
  assert.equal(isFatalProviderError({
    code: "conversation_already_has_active_response",
    errorType: "invalid_request_error",
    message: "Conversation already has an active response",
  }), false);
  assert.equal(isFatalProviderError({ code: null, errorType: null, message: "Conversation already has an active response" }), false);
});

test("auth, permission, key and quota errors are fatal", () => {
  const { isFatalProviderError } = setup();
  assert.equal(isFatalProviderError({ code: "invalid_api_key", errorType: "authentication_error", message: "Incorrect API key provided" }), true);
  assert.equal(isFatalProviderError({ code: null, errorType: "permission_error", message: "You don't have access" }), true);
  assert.equal(isFatalProviderError({ code: "AllocationQuota.FreeTierOnly", errorType: null, message: "Free tier quota exhausted" }), true);
  assert.equal(isFatalProviderError({ code: null, errorType: null, message: "Unauthorized: token expired" }), true);
  assert.equal(isFatalProviderError({ code: "insufficient_quota", errorType: null, message: "billing required" }), true);
});

test("unknown or transient errors default to recoverable", () => {
  const { isFatalProviderError } = setup();
  assert.equal(isFatalProviderError({ code: "rate_limit_exceeded", errorType: "rate_limit_error", message: "Too many requests" }), false);
  assert.equal(isFatalProviderError({ code: null, errorType: null, message: "" }), false);
});
