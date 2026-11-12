/* Actual artifact serialization controls; no DOM, SDK or provider required. */
const assert = require('node:assert/strict');
(async () => {
 const {audioMetadata,runArtifact}=await import('./artifact.mjs');
 const empty=runArtifact();
 assert.equal(empty.events.length,0);assert.equal(empty.audio,null);assert.equal(empty.state,'not_started');
 assert.equal(empty.method.acoustic_measurement,false);
 const row={schema:'rasa.voice-latency-event/v1',event:'speech.end',session:'s1',turn:'t1',clock:'browser.audio.1',at_ms:123,resolution_ms:.0625,transcript:'PRIVATE'};
 const failed=runArtifact({events:[row],failure:'previous_audio_or_turn_pending',state:'closed',stopped:true,
   audio:{sample_rate:16000,base_latency_s:.01,output_latency_s:.032,secret:'PRIVATE'},endpoint:'PRIVATE'});
 assert.equal(failed.failure,'previous_audio_or_turn_pending');assert.equal(failed.stopped,true);
 assert.deepEqual(failed.audio,{sample_rate:16000,base_latency_s:.01,output_latency_s:.032});
 assert.equal(JSON.stringify(failed).includes('PRIVATE'),false);
 assert.equal(failed.events.length,1);assert.equal(failed.method.output_latency_added_to_interval,false);
 assert.equal(audioMetadata({sampleRate:16000,baseLatency:NaN,outputLatency:undefined}).base_latency_s,null);
 assert.equal(audioMetadata({sampleRate:16000,baseLatency:0,outputLatency:undefined}).base_latency_s,0);
 assert.throws(()=>runArtifact({events:[{...row,at_ms:NaN}]}));
 assert.throws(()=>runArtifact({events:[{...row,clock:'PRIVATE space'}]}));
 console.log('artifact controls PASS: failed partial runs, output-device limits, private field exclusion, invalid timings');
})().catch(error=>{console.error(error);process.exitCode=1;});
