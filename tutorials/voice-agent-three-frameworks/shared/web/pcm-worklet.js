// Microphone capture for the browser_audio protocol.
//
// Runs on the audio thread. Takes the context's float samples (whatever rate
// the browser picked, usually 44.1 or 48 kHz), resamples them to the rate the
// server announced in its handshake with a linear interpolator that keeps its
// position between blocks, and posts 20 ms frames of 16-bit little-endian PCM
// to the page, which base64-encodes each one into an {"audio": ...} frame.

class PcmCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.target = options.processorOptions.targetRate;
    this.ratio = sampleRate / this.target; // input samples per output sample
    this.frame = Math.round(this.target / 50); // 20 ms
    this.out = new Int16Array(this.frame);
    this.filled = 0;
    this.pos = 0; // fractional read position into the carried + new input
    this.carry = new Float32Array(0);
    this.muted = false;
    this.port.onmessage = (e) => {
      if (e.data && typeof e.data.muted === "boolean") this.muted = e.data.muted;
    };
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;
    const input = new Float32Array(this.carry.length + channel.length);
    input.set(this.carry, 0);
    input.set(channel, this.carry.length);
    let level = 0;
    while (this.pos + 1 < input.length) {
      const i = Math.floor(this.pos);
      const f = this.pos - i;
      let s = input[i] * (1 - f) + input[i + 1] * f;
      if (this.muted) s = 0;
      level = Math.max(level, Math.abs(s));
      s = Math.max(-1, Math.min(1, s));
      this.out[this.filled++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      if (this.filled === this.frame) {
        this.port.postMessage({ pcm: this.out.buffer.slice(0), level });
        this.filled = 0;
        level = 0;
      }
      this.pos += this.ratio;
    }
    const keep = Math.floor(this.pos);
    this.carry = input.slice(keep);
    this.pos -= keep;
    return true;
  }
}

registerProcessor("pcm-capture", PcmCapture);
