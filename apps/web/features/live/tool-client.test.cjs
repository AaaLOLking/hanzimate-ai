/* eslint-disable @typescript-eslint/no-require-imports -- Node test runner executes this file as CommonJS. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

function setup(fetchImpl = async () => ({ ok: true, json: async () => ({ status: "succeeded", message: "已找到", sources: [] }) })) {
  const source = fs.readFileSync(require.resolve("./tool-client.ts"), "utf8");
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const sandbox = { exports: {}, require: () => ({ API_BASE_URL: "http://test" }),
    process, fetch: fetchImpl, AbortController, setTimeout, clearTimeout };
  vm.runInNewContext(js, sandbox);
  const sent = [], activity = [];
  const bridge = sandbox.exports.createToolBridge({ sessionId: "session-1", epoch: 4,
    send: (event) => sent.push(event), onActivity: (event) => activity.push(event) });
  return { bridge, sent, activity };
}
const created = (id = "resp-1") => ({ type: "response.created", response: { id } });
const call = (id = "resp-1") => ({ type: "response.function_call_arguments.done", name: "hsk_lookup",
  call_id: "call-1", response_id: id, arguments: '{"query":"把字句"}' });
const done = (id = "resp-1") => ({ type: "response.done", response: { id, status: "completed" } });
const settle = () => new Promise((resolve) => setImmediate(resolve));

test("waits for response completion, deduplicates, returns native tool output before response.create", async () => {
  const { bridge, sent } = setup();
  bridge.onEvent(created()); bridge.onEvent(call()); bridge.onEvent(call());
  assert.equal(bridge.isBusy(), true);
  assert.equal(sent.length, 0);
  bridge.onEvent(done()); await settle();
  assert.equal(sent.length, 2);
  assert.equal(sent[0].item.type, "function_call_output");
  assert.equal(sent[0].item.call_id, "call-1");
  assert.equal(sent[1].type, "response.create");
  bridge.onEvent(call()); bridge.onEvent(done()); await settle();
  assert.equal(sent.length, 2);
  assert.equal(bridge.isBusy(), false);
});

for (const cause of ["speech", "new-response", "close"]) {
  test(`late result cannot speak after ${cause}`, async () => {
    let release;
    const { bridge, sent, activity } = setup((url) => url.endsWith("/cancel")
      ? Promise.resolve({ ok: true }) : new Promise((resolve) => { release = resolve; }));
    bridge.onEvent(created()); bridge.onEvent(call()); bridge.onEvent(done());
    if (cause === "speech") bridge.onEvent({ type: "input_audio_buffer.speech_started" });
    else if (cause === "new-response") bridge.onEvent(created("resp-2"));
    else bridge.cancel();
    release({ ok: true, json: async () => ({ status: "succeeded", message: "旧结果", sources: [] }) });
    await settle();
    assert.equal(sent.length, 0);
    assert.equal(activity.at(-1).status, "cancelled");
    bridge.onEvent(call()); bridge.onEvent(done()); await settle();
    assert.equal(sent.length, 0);
    assert.equal(bridge.isBusy(), false);
  });
}

test("unavailable is returned as an error result, never a fabricated search", async () => {
  const { bridge, sent } = setup(async () => ({ ok: true,
    json: async () => ({ status: "unavailable", message: "尚未配置", sources: [] }) }));
  bridge.onEvent(created()); bridge.onEvent(call()); bridge.onEvent(done()); await settle();
  const output = JSON.parse(sent[0].item.output);
  assert.equal(output.status, "unavailable");
  assert.equal(output.sources.length, 0);
});

test("malformed and unrelated response events do not execute tools", async () => {
  let calls = 0;
  const { bridge } = setup(async () => { calls++; throw new Error("should not execute"); });
  bridge.onEvent(created("resp-2")); bridge.onEvent(call());
  bridge.onEvent({ ...call("resp-2"), arguments: {} }); bridge.onEvent(done("resp-2"));
  await settle();
  assert.equal(calls, 0);
  assert.equal(bridge.isBusy(), false);
});

test("incomplete response cannot execute a partially generated tool plan", async () => {
  let calls = 0;
  const { bridge, sent } = setup(async (url) => {
    if (url.endsWith("/execute")) calls++;
    return { ok: true };
  });
  bridge.onEvent(created()); bridge.onEvent(call());
  bridge.onEvent({ type: "response.done", response: { id: "resp-1", status: "incomplete" } });
  await settle();
  assert.equal(calls, 0);
  assert.equal(sent.length, 0);
  assert.equal(bridge.isBusy(), false);
});

test("multiple calls return all outputs before a single response request", async () => {
  const { bridge, sent } = setup();
  bridge.onEvent(created()); bridge.onEvent(call());
  bridge.onEvent({ ...call(), call_id: "call-2", name: "expert_answer" });
  bridge.onEvent(done()); await settle();
  assert.equal(sent.length, 3);
  assert.equal(sent[0].item.call_id, "call-1");
  assert.equal(sent[1].item.call_id, "call-2");
  assert.equal(sent[2].type, "response.create");
});
