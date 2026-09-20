/* eslint-disable @typescript-eslint/no-require-imports -- Node test runner executes this file as CommonJS. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

class FakeChannel {
  constructor() {
    this.readyState = "open";
    this.listeners = new Map();
    this.sent = [];
  }
  send(data) {
    this.sent.push(JSON.parse(data));
  }
  addEventListener(type, listener) {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }
  dispatch(type, event) {
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
  close() {
    this.readyState = "closed";
  }
}

class FakePeer {
  constructor() {
    this.channel = new FakeChannel();
    FakePeer.latest = this;
    this.connectionState = "connected";
    this.iceGatheringState = "complete";
    this.listeners = new Map();
  }
  createDataChannel() {
    return this.channel;
  }
  async createOffer() {
    return { type: "offer", sdp: "offer-sdp" };
  }
  async setLocalDescription() {}
  async setRemoteDescription() {}
  get localDescription() {
    return { type: "offer", sdp: "offer-sdp" };
  }
  addTrack() {}
  addEventListener(type, listener) {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }
  close() {}
}

function loadModule() {
  const source = fs.readFileSync(require.resolve("./qwen-webrtc.ts"), "utf8");
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const sandbox = {
    exports: {},
    require: (path) => (path.includes("tool-client") ? { createToolBridge: () => null } : {}),
    process,
    console,
    setTimeout,
    clearTimeout,
    window: { setTimeout, clearTimeout },
    RTCPeerConnection: FakePeer,
  };
  vm.runInNewContext(js, sandbox);
  return sandbox.exports;
}

const flush = () => new Promise((resolve) => setImmediate(resolve));

async function connect() {
  const promise = loadModule().connectQwenWebRtc({
    connectionEpoch: 1,
    exchangeOffer: async () => "answer-sdp",
    mediaStream: { getTracks: () => [] },
    onConnectionLoss: () => {},
    onEvent: () => {},
    onRemoteStream: () => {},
    sessionUpdate: { type: "session.update" },
  });
  const channel = FakePeer.latest.channel;
  await flush();
  await flush();
  channel.dispatch("message", { data: JSON.stringify({ type: "session.updated" }) });
  const conn = await promise;
  channel.sent.length = 0;
  return { conn, channel };
}

const types = (channel) => channel.sent.map((event) => event.type);

test("interject with no active response sends the message immediately", async () => {
  const { conn, channel } = await connect();
  await conn.sendTextInterject("你好");
  assert.deepEqual(types(channel), ["conversation.item.create", "response.create"]);
  assert.equal(channel.sent[0].item.content[0].text, "你好");
});

test("interject cancels the active response, waits for terminal, then sends", async () => {
  const { conn, channel } = await connect();
  channel.dispatch("message", { data: JSON.stringify({ type: "response.created", response: { id: "r1" } }) });
  const pending = conn.sendTextInterject("先不用查，直接告诉我");
  await flush();
  assert.deepEqual(types(channel), ["response.cancel"]);
  channel.dispatch("message", { data: JSON.stringify({ type: "response.done", response: { id: "r1", status: "cancelled" } }) });
  await pending;
  assert.deepEqual(types(channel), ["response.cancel", "conversation.item.create", "response.create"]);
  assert.equal(channel.sent[1].item.content[0].text, "先不用查，直接告诉我");
});

test("interject is also released by a response.cancelled event", async () => {
  const { conn, channel } = await connect();
  channel.dispatch("message", { data: JSON.stringify({ type: "response.created", response: { id: "r2" } }) });
  const pending = conn.sendTextInterject("换一个话题");
  await flush();
  channel.dispatch("message", { data: JSON.stringify({ type: "response.cancelled", response: { id: "r2" } }) });
  await pending;
  assert.deepEqual(types(channel), ["response.cancel", "conversation.item.create", "response.create"]);
});

test("interject proceeds after the terminal wait timeout", async () => {
  const { conn, channel } = await connect();
  channel.dispatch("message", { data: JSON.stringify({ type: "response.created", response: { id: "r3" } }) });
  await conn.sendTextInterject("兜底发送", 25);
  assert.deepEqual(types(channel), ["response.cancel", "conversation.item.create", "response.create"]);
});

test("closing the connection rejects a pending interject instead of hanging", async () => {
  const { conn, channel } = await connect();
  channel.dispatch("message", { data: JSON.stringify({ type: "response.created", response: { id: "r4" } }) });
  const pending = conn.sendTextInterject("连接已断开");
  await flush();
  conn.close();
  await assert.rejects(pending, /实时事件通道当前不可用/);
});

test("plain sendText keeps its existing immediate semantics", async () => {
  const { conn, channel } = await connect();
  channel.dispatch("message", { data: JSON.stringify({ type: "response.created", response: { id: "r5" } }) });
  conn.sendText("普通文字");
  assert.deepEqual(types(channel), ["conversation.item.create"]);
  assert.equal(conn.connectionEpoch, 1);
});
