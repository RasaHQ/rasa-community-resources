/* Deterministic audio-quantum controls; no browser, provider or SDK session. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/clock-worklet.js', 'utf8');
function create() {
  let Type; const messages = [];
  const sandbox = {sampleRate:16000, currentFrame:0, Float32Array,
    AudioWorkletProcessor:class {constructor(){this.port={postMessage:m=>messages.push(m)};}},
    registerProcessor:(_, t)=>{Type=t;}};
  vm.createContext(sandbox); vm.runInContext(source, sandbox);
  const node=new Type();
  return {node,messages,send:m=>node.port.onmessage({data:m}), render:frame=>{
    sandbox.currentFrame=frame; const out=new Float32Array(4);node.process([],[[out]]);return out;
  }};
}
{
 const c=create();
 c.send({type:'fixture',samples:new Float32Array([.1,.1]),lastVoiced:1,turn:'turn-1'});
 c.render(0);
 assert.equal(c.messages.find(x=>x.event==='speech.end').at_ms,2/16000*1000);
 c.send({type:'audio',samples:new Float32Array([0,0,0,0,0,0,0,0,.2])});
 c.send({type:'marker',id:'end'});
 assert.equal(c.messages.filter(x=>x.event==='audio.first_played').length,0);
 c.render(4);c.render(8);
 assert.equal(c.messages.filter(x=>x.event==='audio.first_played').length,0);
 c.render(12);
 assert.equal(c.messages.find(x=>x.event==='audio.first_played').at_ms,12/16000*1000);
 assert.equal(c.messages.filter(x=>x.type==='ack').length,1);
 c.render(16);assert.equal(c.messages.filter(x=>x.event==='audio.first_played').length,1);
}
{
 const c=create();c.send({type:'audio',samples:new Float32Array([.2])});
 c.send({type:'fixture',samples:new Float32Array([.1]),lastVoiced:0,turn:'turn-1'});
 assert.equal(c.messages.find(x=>x.type==='error').reason,'previous_audio_or_turn_pending');
 assert.equal(c.messages.filter(x=>x.type==='timing').length,0);
}
{
 const c=create();c.send({type:'fixture',samples:new Float32Array(20).fill(.1),lastVoiced:19,turn:'turn-1'});
 c.send({type:'audio',samples:new Float32Array([.2])});c.render(0);
 assert.equal(c.messages.find(x=>x.type==='error').reason,'audio_overlaps_caller');
 assert.equal(c.messages.filter(x=>x.event==='audio.first_played').length,0);
}
console.log('worklet controls PASS: rendered queue boundary, marker, duplicate, pending and overlap');
