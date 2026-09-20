/* eslint-disable @typescript-eslint/no-unused-expressions -- Playwright CLI function input. */
async (page) => {
  // CLI probe scenario: user ends the call while a segment rollover is still connecting.
  // The finish flow must wait for the in-flight connection to settle its epoch, then save.
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('http://localhost:8000/**', async route => {
    const response = await route.fetch({maxRetries:2,url: route.request().url().replace(':8000', ':8001')});
    await route.fulfill({response});
  });
  await page.addInitScript(() => {
    window.__probe = {peers: [], configs: [], tracks: [], offerDelayMs: 0};
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
      async createOffer() {
        if (window.__probe.offerDelayMs) await new Promise(resolve => setTimeout(resolve, window.__probe.offerDelayMs));
        return {type:'offer',sdp:'synthetic-browser-offer-for-probe'};
      }
      async setLocalDescription(value) { this.localDescription = value; }
      async setRemoteDescription() {}
      close() { this.connectionState = 'closed'; }
    };
  });
  const workspace = await (await page.request.post('http://localhost:8001/api/v1/workspaces', {data:{kind:'conversation',title:'隔离切换中结束验收',state:{practice_mode:'custom',custom_objective:'练习租房'}}})).json();
  await page.goto('http://localhost:3000/conversation/'+workspace.id);
  await page.getByRole('button',{name:'使用麦克风开始',exact:true}).click();
  await page.getByRole('heading',{name:'正在听你说',exact:true}).waitFor();
  await page.evaluate(() => {
    window.__probe.peers.at(-1).channel.emit({type:'conversation.item.input_audio_transcription.completed',item_id:'early-budget',transcript:'我的租房预算是三千元。'});
  });
  await page.waitForFunction(() => window.__probe.configs.length >= 1 && document.body.innerText.includes('三千元'), {timeout:25000});
  // Slow down the next (rollover) offer so the finish click lands mid-handoff.
  await page.evaluate(() => { window.__probe.offerDelayMs = 3000; });
  await page.waitForFunction(() => document.body.innerText.includes('正在载入历史摘录并续接下一段'), {timeout:25000});
  await page.getByRole('button',{name:'结束并保存',exact:true}).click();
  await page.getByRole('heading',{name:'本次对话已保存',exact:true}).waitFor();
  const sessionId = (await (await page.request.get('http://localhost:8001/api/v1/workspaces/'+workspace.id)).json()).state.last_session_id;
  const session = await (await page.request.get('http://localhost:8001/api/v1/voice/sessions/'+sessionId)).json();
  if (session.connection_epoch !== 2 || session.status !== 'completed') throw Error('End during rollover not settled: epoch='+session.connection_epoch+' status='+session.status);
  const exported = await page.request.get('http://localhost:8001/api/v1/voice/sessions/'+sessionId+'/transcript.md');
  if (!(await exported.text()).includes('三千元')) throw Error('Export missing early transcript');
  if (errors.length) throw Error(errors.join(';'));
  await page.unrouteAll({behavior:"wait"});
  return {synthetic:true,endDuringRollover:true,epoch:session.connection_epoch,status:session.status,export:exported.status(),pageErrors:errors};
}
