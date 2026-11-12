const status = document.querySelector('#status');
const rows = []; let socket, context, node, timeout, turn = 0, stopped = false, queued = 0, lastAudio = null, failure = null;
const clock = `browser.audio.${crypto.randomUUID()}`;
const session = 'session-1';
function show(text) { status.textContent += `\n${text}`; }
function pcm(samples) {
  const bytes = new Uint8Array(samples.length * 2), view = new DataView(bytes.buffer);
  samples.forEach((x, i) => view.setInt16(i * 2, Math.round(Math.max(-1, Math.min(1, x)) * 32767), true));
  return btoa(String.fromCharCode(...bytes));
}
async function stop() {
  stopped = true; clearTimeout(timeout);
  socket?.close(); node?.disconnect(); if (context) await context.close();
  show('Stopped. No automatic reconnect or retry.');
}
async function connect() {
  if (socket || context) throw Error('One connection per page; reload explicitly for another run.');
  const url = new URL(document.querySelector('#endpoint').value);
  if (!['ws:', 'wss:'].includes(url.protocol) || url.username || url.password || url.search || url.hash)
    throw Error('Expected a WebSocket URL without credentials/query/fragment.');
  socket = new WebSocket(url);
  timeout = setTimeout(stop, 180000);
  socket.onclose = () => { if (!stopped) stop(); };
  socket.onerror = () => show('WebSocket error; no retry.');
  let incoming = Promise.resolve();
  socket.onmessage = ({data}) => {
    incoming = incoming.then(async () => {
    if (stopped) return;
    try {
      const message = JSON.parse(data);
      if (message.type === 'handshake') {
        if (context || ![8000,16000,24000,48000].includes(message.sample_rate)) throw Error('Invalid handshake.');
        context = new AudioContext({sampleRate: message.sample_rate});
        await context.audioWorklet.addModule('clock-worklet.js');
        node = new AudioWorkletNode(context, 'voice-clock', {numberOfInputs:0, numberOfOutputs:1, outputChannelCount:[1]});
        node.port.onmessage = ({data: m}) => {
          if (m.type === 'mic') { queued=m.queued; if(socket.readyState === WebSocket.OPEN)socket.send(JSON.stringify({audio:pcm(m.samples)})); }
          else if (m.type === 'ack' && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({marker:m.id}));
          else if (m.type === 'error') { failure=m.reason; show(`Refused: ${m.reason}`); stop(); }
          else if (m.type === 'timing') {
            const row = {schema:'rasa.voice-latency-event/v1', event:m.event, session, turn:m.turn,
              clock, at_ms:m.at_ms, resolution_ms:m.resolution_ms};
            rows.push(row); show(JSON.stringify(row));
          }
        };
        node.connect(context.destination); await context.resume();
        show(JSON.stringify({sample_rate:context.sampleRate, base_latency_s:context.baseLatency,
          output_latency_s:context.outputLatency ?? null, method:'synthetic_fixture_worklet_render_not_acoustic'}));
      } else if (!node) throw Error('Audio arrived before ready handshake.');
      else if (message.audio) {
        lastAudio = performance.now();
        const binary = atob(message.audio); if (binary.length > 2097152 || binary.length % 2) throw Error('Invalid PCM frame.');
        const view = new DataView(Uint8Array.from(binary, c => c.charCodeAt(0)).buffer);
        const samples = Float32Array.from({length:binary.length/2}, (_,i) => view.getInt16(i*2,true)/32768);
        node.port.postMessage({type:'audio',samples});
      } else if (message.marker) node.port.postMessage({type:'marker',id:message.marker});
      else if (message.interruptPlayback) node.port.postMessage({type:'clear'});
    } catch (error) { failure=error.name; show(`Probe error: ${error.name}`); await stop(); }
    });
  };
}
document.querySelector('#connect').onclick = () => connect().catch(e => show(e.message));
document.querySelector('#stop').onclick = stop;
document.querySelector('#speak').onclick = async () => {
  try {
    if (!node || stopped) throw Error('Connect and wait for the greeting first.');
    const file = document.querySelector('#fixture').files[0];
    if (!file || file.size > 10485760) throw Error('Choose a fictional WAV under 10 MiB.');
    const audio = await context.decodeAudioData(await file.arrayBuffer());
    if (audio.numberOfChannels !== 1 || audio.duration > 30) throw Error('Expected mono caller fixture under 30 seconds.');
    const samples = audio.getChannelData(0); let lastVoiced = -1;
    samples.forEach((x,i) => {if(Math.abs(x)>=0.01)lastVoiced=i;});
    if (lastVoiced < 0) throw Error('Fixture contains no signal above the documented threshold.');
    node.port.postMessage({type:'fixture', samples, lastVoiced, turn:`turn-${++turn}`});
  } catch(e) {show(e.message);}
};
document.querySelector('#save').onclick = () => {
  const url = URL.createObjectURL(new Blob([rows.map(x=>JSON.stringify(x)).join('\n')+'\n'], {type:'application/x-ndjson'}));
  const a = document.createElement('a'); a.href=url; a.download='voice-timing.jsonl'; a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
};
// Timing-only inspection for an automated receiving control. No console/audio capture.
window.voiceTiming = () => ({events:rows.slice(), failure, state:context?.state ?? 'not_started', queued_samples:queued, received_audio:lastAudio!==null, quiet_ms:lastAudio===null?null:performance.now()-lastAudio});
