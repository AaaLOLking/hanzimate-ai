import { createToolBridge, type ToolActivity } from "./tool-client";

export interface QwenWebRtcConnection {
  connectionEpoch: number;
  close(): void;
  interrupt(): void;
  requestResponse(): void;
  sendText(text: string): void;
  sendTextInterject(text: string, terminalTimeoutMs?: number): Promise<void>;
  updateSession(sessionUpdate: Record<string, unknown>): void;
  toolsBusy(): boolean;
}

interface ConnectOptions {
  connectionEpoch: number;
  exchangeOffer(sdp: string, connectionEpoch: number): Promise<string>;
  mediaStream: MediaStream;
  onConnectionLoss(): void;
  onEvent(rawEvent: string): void;
  onRemoteStream(stream: MediaStream): void;
  sessionUpdate: Record<string, unknown>;
  toolSessionId?: string;
  onToolActivity?(activity: ToolActivity): void;
}

function waitForIceGathering(peer: RTCPeerConnection) {
  if (peer.iceGatheringState === "complete") return Promise.resolve();
  return new Promise<void>((resolve) => {
    const timeout = window.setTimeout(resolve, 1800);
    const listener = () => {
      if (peer.iceGatheringState !== "complete") return;
      window.clearTimeout(timeout);
      peer.removeEventListener("icegatheringstatechange", listener);
      resolve();
    };
    peer.addEventListener("icegatheringstatechange", listener);
  });
}

function waitForPeerConnection(peer: RTCPeerConnection) {
  if (peer.connectionState === "connected") return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      peer.removeEventListener("connectionstatechange", listener);
      reject(new Error("实时语音通道连接超时"));
    }, 8000);
    const listener = () => {
      if (peer.connectionState === "connected") {
        window.clearTimeout(timeout);
        peer.removeEventListener("connectionstatechange", listener);
        resolve();
      } else if (peer.connectionState === "failed") {
        window.clearTimeout(timeout);
        peer.removeEventListener("connectionstatechange", listener);
        reject(new Error("实时语音通道建立失败"));
      }
    };
    peer.addEventListener("connectionstatechange", listener);
  });
}

function waitForDataChannel(channel: RTCDataChannel) {
  if (channel.readyState === "open") return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error("实时事件通道连接超时")), 5000);
    channel.addEventListener("open", () => {
      window.clearTimeout(timeout);
      resolve();
    }, { once: true });
    channel.addEventListener("error", () => {
      window.clearTimeout(timeout);
      reject(new Error("实时事件通道建立失败"));
    }, { once: true });
  });
}

function waitForConfigAck(register: (resolve: () => void) => void) {
  return new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error("实时模型没有确认会话配置")), 5000);
    register(() => {
      window.clearTimeout(timeout);
      resolve();
    });
  });
}

export async function connectQwenWebRtc(
  options: ConnectOptions,
): Promise<QwenWebRtcConnection> {
  const peer = new RTCPeerConnection({ iceServers: [] });
  const outgoing = peer.createDataChannel("oai-events");
  let configAck: (() => void) | null = null;
  let closed = false;
  // The provider rejects conversation.item.create while a response is active, so text
  // sent as a barge-in must wait for the cancelled response's terminal event first.
  let activeResponse: string | null = null;
  const terminalWaiters = new Map<string, Array<() => void>>();
  const send = (event: Record<string, unknown>) => {
    if (closed || outgoing.readyState !== "open") throw new Error("实时事件通道当前不可用");
    outgoing.send(JSON.stringify(event));
  };
  const toolBridge = options.toolSessionId ? createToolBridge({
    sessionId: options.toolSessionId, epoch: options.connectionEpoch, send,
    onActivity: options.onToolActivity,
  }) : null;

  const handleRawEvent = (rawEvent: string) => {
    try {
      const parsed = JSON.parse(rawEvent) as Record<string, unknown>;
      toolBridge?.onEvent(parsed);
      if (parsed.type === "session.updated") {
        configAck?.();
        configAck = null;
      }
      if (parsed.type === "response.created") {
        const id = (parsed.response as { id?: string } | undefined)?.id;
        activeResponse = typeof id === "string" && id ? id : "active";
      }
      if (parsed.type === "response.done" || parsed.type === "response.cancelled" || parsed.type === "response.failed") {
        const finished = activeResponse;
        activeResponse = null;
        for (const key of [finished, "active"]) {
          if (!key) continue;
          const waiters = terminalWaiters.get(key);
          if (!waiters) continue;
          terminalWaiters.delete(key);
          waiters.forEach((notify) => notify());
        }
      }
    } catch {
      // The page-level parser deliberately ignores malformed provider events.
    }
    options.onEvent(rawEvent);
  };
  const attachMessages = (channel: RTCDataChannel) => {
    channel.addEventListener("message", (event) => {
      if (typeof event.data === "string") handleRawEvent(event.data);
    });
  };

  options.mediaStream.getTracks().forEach((track) => peer.addTrack(track, options.mediaStream));
  peer.addEventListener("track", (event) => {
    const remoteStream = event.streams[0];
    if (remoteStream) options.onRemoteStream(remoteStream);
  });
  peer.addEventListener("datachannel", (event) => attachMessages(event.channel));
  peer.addEventListener("connectionstatechange", () => {
    if (!closed && (peer.connectionState === "disconnected" || peer.connectionState === "failed")) {
      toolBridge?.cancel();
      options.onConnectionLoss();
    }
  });
  attachMessages(outgoing);

  try {
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    await waitForIceGathering(peer);
    if (!peer.localDescription?.sdp) throw new Error("浏览器未生成有效的 WebRTC Offer");
    const answerSdp = await options.exchangeOffer(
      peer.localDescription.sdp,
      options.connectionEpoch,
    );
    await peer.setRemoteDescription({ type: "answer", sdp: answerSdp });
    await Promise.all([waitForPeerConnection(peer), waitForDataChannel(outgoing)]);
    const acknowledgement = waitForConfigAck((resolve) => {
      configAck = resolve;
    });
    outgoing.send(JSON.stringify(options.sessionUpdate));
    await acknowledgement;
  } catch (error) {
    toolBridge?.cancel();
    closed = true;
    outgoing.close();
    peer.close();
    throw error;
  }

  const releaseTerminalWaiters = () => {
    for (const waiters of terminalWaiters.values()) waiters.forEach((notify) => notify());
    terminalWaiters.clear();
  };

  return {
    connectionEpoch: options.connectionEpoch,
    toolsBusy: () => toolBridge?.isBusy() ?? false,
    close() {
      toolBridge?.cancel();
      closed = true;
      releaseTerminalWaiters();
      outgoing.close();
      peer.close();
    },
    interrupt() {
      toolBridge?.cancel();
      send({ type: "response.cancel" });
    },
    requestResponse() {
      send({ type: "response.create" });
    },
    sendText(text: string) {
      toolBridge?.cancel();
      send({
        type: "conversation.item.create",
        item: {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text }],
        },
      });
    },
    async sendTextInterject(text: string, terminalTimeoutMs = 3000) {
      toolBridge?.cancel();
      const target = activeResponse;
      if (target) {
        send({ type: "response.cancel" });
        await new Promise<void>((resolve) => {
          const timer = window.setTimeout(() => {
            terminalWaiters.delete(target);
            resolve();
          }, terminalTimeoutMs);
          const notify = () => {
            window.clearTimeout(timer);
            resolve();
          };
          const waiters = terminalWaiters.get(target) ?? [];
          waiters.push(notify);
          terminalWaiters.set(target, waiters);
        });
      }
      send({
        type: "conversation.item.create",
        item: {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text }],
        },
      });
      send({ type: "response.create" });
    },
    updateSession(sessionUpdate: Record<string, unknown>) {
      send(sessionUpdate);
    },
  };
}
