/* Exercise the actual page controller's failed-run export and stop lifecycle. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
 const {audioMetadata,runArtifact}=await import('./artifact.mjs');
 const source=fs.readFileSync(__dirname+'/probe.js','utf8').replace(/^import .*\n/,'');
 function controller(){
  const elements=new Map();let socket,node,closes=0,connections=0,saved;
  class Socket{static OPEN=1;constructor(){socket=this;connections++;this.readyState=1;}close(){this.readyState=3;this.onclose?.();}send(){}}
  class Audio{constructor(){this.state='suspended';this.sampleRate=16000;this.baseLatency=.01;this.outputLatency=.032;this.audioWorklet={addModule:async()=>{}};}async resume(){this.state='running';}async close(){closes++;this.state='closed';this.baseLatency=0;this.outputLatency=0;}}
  class AudioNode{constructor(){node=this;this.port={postMessage(){}};}connect(){}disconnect(){}}
  class BlobURL extends URL{static createObjectURL(blob){saved=blob;return 'blob:control';}static revokeObjectURL(){}}
  const sandbox={audioMetadata,runArtifact,window:{},crypto:{randomUUID:()=> 'authored-clock'},
   document:{querySelector(id){if(!elements.has(id))elements.set(id,{textContent:'',value:'ws://127.0.0.1:5005/websocket'});return elements.get(id);},createElement:()=>({click(){}})},
   WebSocket:Socket,AudioContext:Audio,AudioWorkletNode:AudioNode,URL:BlobURL,Blob,performance,
   setTimeout:()=>1,clearTimeout(){},Uint8Array,Float32Array,DataView,btoa:()=>''};
  vm.createContext(sandbox);vm.runInContext(source,sandbox);
  return {elements,sandbox,getSocket:()=>socket,getNode:()=>node,closes:()=>closes,connections:()=>connections,saved:()=>saved};
 }
 const c=controller();await c.elements.get('#connect').onclick();
 c.getSocket().onmessage({data:JSON.stringify({type:'handshake',sample_rate:16000})});
 await new Promise(setImmediate);
 c.getNode().port.onmessage({data:{type:'timing',event:'speech.end',turn:'turn-1',at_ms:100,resolution_ms:.0625}});
 c.getNode().port.onmessage({data:{type:'error',reason:'previous_audio_or_turn_pending'}});
 await new Promise(setImmediate);
 await c.elements.get('#stop').onclick();await c.elements.get('#stop').onclick();
 assert.equal(c.closes(),1);
 c.elements.get('#save-run').onclick();const report=JSON.parse(await c.saved().text());
 assert.equal(report.failure,'previous_audio_or_turn_pending');assert.equal(report.events.length,1);
 assert.equal(report.stopped,true);assert.equal(report.state,'closed');
 assert.equal(report.audio.output_latency_s,.032);assert.equal(report.audio.base_latency_s,.01);
 assert.equal(JSON.stringify(report).includes('127.0.0.1'),false);
 await c.elements.get('#connect').onclick();assert.equal(c.connections(),1);
 const before=controller();await before.elements.get('#stop').onclick();
 await before.elements.get('#connect').onclick();assert.equal(before.connections(),0);
 console.log('page controls PASS: partial failure export, pre-close audio metadata, idempotent stop, no connect after stop');
})().catch(error=>{console.error(error);process.exitCode=1;});
