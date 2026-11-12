/* One AudioContext clock for a fictional caller fixture and rendered bot PCM.
 * The worklet retains timing metadata, never transcripts or microphone input.
 */
class VoiceClock extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = []; this.offset = 0; this.queued = 0;
    this.written = 0; this.consumed = 0; this.markers = [];
    this.fixture = null; this.fixtureOffset = 0; this.lastVoiced = -1;
    this.turn = null; this.speechEnded = false; this.firstPlayed = false; this.speechEndFrame = Infinity;
    this.port.onmessage = ({data: m}) => {
      if (m.type === 'audio') {
        if (m.samples.length + this.queued > sampleRate * 60) {
          this.port.postMessage({type: 'error', reason: 'audio_queue_limit'}); return;
        }
        this.queue.push(m.samples); this.queued += m.samples.length;
        this.written += m.samples.length;
      } else if (m.type === 'marker') {
        this.markers.push({id: m.id, position: this.written});
      } else if (m.type === 'clear') {
        this.queue = []; this.offset = 0; this.queued = 0;
        this.consumed = this.written; this.markers = [];
      } else if (m.type === 'fixture') {
        if (this.queued || this.fixture || (this.turn && !this.firstPlayed)) {
          this.port.postMessage({type: 'error', reason: 'previous_audio_or_turn_pending'}); return;
        }
        this.fixture = m.samples; this.fixtureOffset = 0;
        this.lastVoiced = m.lastVoiced; this.turn = m.turn;
        this.speechEnded = false; this.firstPlayed = false; this.speechEndFrame = Infinity;
      }
    };
  }
  stamp(event, frame) {
    this.port.postMessage({type: 'timing', event, turn: this.turn,
      at_ms: frame / sampleRate * 1000, resolution_ms: 1000 / sampleRate});
  }
  process(_, outputs) {
    const out = outputs[0][0]; out.fill(0);
    const mic = new Float32Array(out.length);
    for (let i = 0; i < out.length; i++) {
      if (this.fixture) {
        mic[i] = this.fixture[this.fixtureOffset];
        if (this.fixtureOffset === this.lastVoiced) {
          this.speechEnded = true; this.speechEndFrame = currentFrame + i + 1;
          this.stamp('speech.end', currentFrame + i + 1);
        }
        this.fixtureOffset++;
        if (this.fixtureOffset >= this.fixture.length) this.fixture = null;
      }
      if (this.queue.length) {
        out[i] = this.queue[0][this.offset++]; this.queued--; this.consumed++;
        if (this.offset === this.queue[0].length) { this.queue.shift(); this.offset = 0; }
        if (this.turn && !this.speechEnded && Math.abs(out[i]) >= 0.01) {
          this.port.postMessage({type:'error',reason:'audio_overlaps_caller'}); this.turn = null;
        }
        if (this.speechEnded && currentFrame + i >= this.speechEndFrame && !this.firstPlayed && Math.abs(out[i]) >= 0.01) {
          this.firstPlayed = true;
          this.stamp('audio.first_played', currentFrame + i);
        }
      }
    }
    while (this.markers.length && this.markers[0].position <= this.consumed) {
      this.port.postMessage({type: 'ack', id: this.markers.shift().id});
    }
    this.port.postMessage({type: 'mic', samples: mic, queued: this.queued});
    return true;
  }
}
registerProcessor('voice-clock', VoiceClock);
