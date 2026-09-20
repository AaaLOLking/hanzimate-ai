/* eslint-disable @typescript-eslint/no-unused-expressions -- Playwright CLI function input. */
async (page) => {
  // CLI probe: real UI and API, synthetic peer/audio, isolated temporary SQLite port 8001.
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('http://localhost:8000/**', async route => {
    const response = await route.fetch({maxRetries:2,url: route.request().url().replace(':8000', ':8001')});
    await route.fulfill({response});
  });
  await page.addInitScript(() => {
    window.__probe = {peers: [], configs: [], tracks: []};
    navigator.mediaDevices.getUserMedia = async () => {
      const context = new AudioContext();
      const stream = context.createMediaStreamDestination().stream;
      window.__probe.tracks.push(...stream.getTracks());
      return stream;
    };
    class Channel extends EventTarget {
      readyState = 'open';
      emit(event) { this.dispatchEvent(new MessageEvent('message', {data: JSON.stringify(event)})); }
      send(raw) {
        const event = JSON.parse(raw);
        if (event.type === 'session.update') {
          window.__probe.configs.push(event.session.instructions);
          setTimeout(() => this.emit({type:'session.updated'}), 1);
        }
        if (event.type === 'response.create') {
          const id = crypto.randomUUID();
          setTimeout(() => {
            this.emit({type:'response.created',response:{id}});
            this.emit({type:'response.audio_transcript.done',response_id:id,item_id:id,transcript:'好的，我们继续讨论租房。'});
            this.emit({type:'response.done',response:{id,status:'completed'}});
          }, 20);
        }
      }
      close() { this.readyState = 'closed'; }
    }
    window.RTCPeerConnection = class extends EventTarget {
      connectionState = 'connected'; iceGatheringState = 'complete';
      channel = new Channel();
      constructor() { super(); window.__probe.peers.push(this); }
      createDataChannel() { return this.channel; }
      addTrack() {}
      async createOffer() { return {type:'offer',sdp:'synthetic-browser-offer-for-probe'}; }
      async setLocalDescription(value) { this.localDescription = value; }
      async setRemoteDescription() {}
      close() { this.connectionState = 'closed'; }
    };
  });
  const workspace = await (await page.request.post('http://localhost:8001/api/v1/workspaces', {data:{kind:'conversation',title:'隔离续接验收',state:{practice_mode:'custom',custom_objective:'练习租房'}}})).json();
  await page.goto('http://localhost:3000/conversation/'+workspace.id);
  await page.getByRole('button',{name:'使用麦克风开始',exact:true}).click();
  await page.getByRole('heading',{name:'正在听你说',exact:true}).waitFor();
  await page.evaluate(() => {
    window.__probe.peers.at(-1).channel.emit({type:'conversation.item.input_audio_transcription.completed',item_id:'early-budget',transcript:'我的租房预算是三千元。'});
  });
  // Stop/mute should not prevent quiet handoff, and muted tracks stay muted.
  await page.getByRole('button',{name:'● 静音',exact:true}).click();
  await page.waitForFunction(() => window.__probe.configs.length >= 3 && document.body.innerText.includes('连续对话 · 第 3 段'), {timeout:25000});
  const segmentLabel = await page.getByText('连续对话 · 第', {exact:false}).first().textContent();
  const state = await page.evaluate(() => ({connections:window.__probe.peers.length, configs:window.__probe.configs, muted:window.__probe.tracks.every(t=>!t.enabled)}));
  if (!state.muted || !state.configs[2].includes('三千元')) throw Error('Memory or mute state not preserved');
  if (!/连续对话 · 第 3 段/.test(segmentLabel)) throw Error('Segment label not advanced to 第 3 段: ' + segmentLabel);
  await page.getByRole('button',{name:'结束并保存',exact:true}).click();
  await page.getByRole('heading',{name:'本次对话已保存',exact:true}).waitFor();
  const sessionId = (await (await page.request.get('http://localhost:8001/api/v1/workspaces/'+workspace.id)).json()).state.last_session_id;
  const session = await (await page.request.get('http://localhost:8001/api/v1/voice/sessions/'+sessionId)).json();
  if (session.connection_epoch < 3 || session.status !== 'completed' || session.duration_seconds <= 4) throw Error('Session not continued/saved');
  const exported = await page.request.get('http://localhost:8001/api/v1/voice/sessions/'+sessionId+'/transcript.md');
  if (!(await exported.text()).includes('三千元')) throw Error('Export missing early transcript');
  if (errors.length) throw Error(errors.join(';'));
  await page.unrouteAll({behavior:"wait"});
  return {synthetic:true,epoch:session.connection_epoch,duration:session.duration_seconds,earlyMemory:true,mutedAcrossRollover:true,segmentLabel,status:session.status,export:exported.status(),pageErrors:errors};
}
