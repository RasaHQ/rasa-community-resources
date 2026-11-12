/* Timing-only run artifacts. No endpoint, filename, transcript, audio or key. */
const finite = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
const label = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,100}$/.test(value) ? value : null;
export function audioMetadata(context) {
  if (!context) return null;
  return {sample_rate:finite(context.sampleRate), base_latency_s:finite(context.baseLatency),
    output_latency_s:finite(context.outputLatency)};
}
export function runArtifact({events = [], failure = null, state = 'not_started', stopped = false,
  queued = 0, receivedAudio = false, quietMs = null, audio = null} = {}) {
  const timings = events.map(row => {
    if (row.schema !== 'rasa.voice-latency-event/v1' ||
        !['speech.end','audio.first_played'].includes(row.event) ||
        !label(row.session) || !label(row.turn) || !label(row.clock) ||
        finite(row.at_ms) === null || finite(row.resolution_ms) === null)
      throw Error('Invalid browser timing event');
    return Object.fromEntries(['schema','event','session','turn','clock','at_ms','resolution_ms'].map(key=>[key,row[key]]));
  });
  return {schema:'rasa.voice-latency-browser-run/v1', events:timings,
    failure:label(failure), state:['not_started','suspended','running','closed'].includes(state)?state:'unknown',
    stopped:Boolean(stopped), queued_samples:finite(queued), received_audio:Boolean(receivedAudio), quiet_ms:finite(quietMs),
    audio:audio ? {sample_rate:finite(audio.sample_rate),base_latency_s:finite(audio.base_latency_s),
      output_latency_s:finite(audio.output_latency_s)} : null,
    method:{boundary:'synthetic_fixture_to_first_rendered_non_silent_sample',threshold_dbfs:-40,
      clock:'shared_AudioContext_sample_clock',acoustic_measurement:false,
      output_latency_added_to_interval:false},
    result_claim:'Observations only; no typical-latency target or vendor acceptance implied'};
}
