import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('./audio-recovery-injection.js',import.meta.url),'utf8');
function setup() {
 class Target { dispatchEvent(event){ return true; } }
 class Audio { state='suspended'; calls=0; resume(){this.calls++;this.state='running';return Promise.resolve();} }
 const player=new Target(), listeners={};
 const storage=new Map([['synthetic','original']]);
 const c={AudioContext:Audio,EventTarget:Target,DOMException,Error,Proxy,Reflect,Promise,Math,Date,queueMicrotask,
 localStorage:{get length(){return storage.size},key:i=>[...storage.keys()][i],getItem:k=>storage.get(k)},
 document:{querySelector:()=>player,querySelectorAll:()=>[player],addEventListener:(name,fn)=>listeners[name]=fn,removeEventListener:(name)=>delete listeners[name]}};
 c.window=c;vm.createContext(c);vm.runInContext(source,c);
 const context=new c.AudioContext();
 const event=(status,operationId,extra={})=>player.dispatchEvent({type:'ruffle-audio-status',detail:{schema:1,contextId:1,operationId,intentId:operationId,phase:'core-play',operation:'resume',status,state:context.state,current:true,retryEligible:false,...extra}});
 return {c,context,event,listeners,storage,probe:c.FlashNestAudioProbe};
}
{
 const {context,event,probe,listeners}=setup();event('bound',0);probe.arm('known');event('pending',1);
 await assert.rejects(context.resume(),e=>e.name==='InvalidStateError'&&e.message==='Failed to start the audio device');
 event('rejected',1,{retryEligible:true});assert.equal(probe.status().injections,1);
 assert.equal(probe.status().nativeResumeRestored,true);
 listeners.click({isTrusted:true,target:{closest:()=>true}});event('pending',2);await context.resume();event('fulfilled',2);
 const s=probe.status();assert.equal(s.fulfilledOperation,2);assert.equal(s.trustedRetries,1);assert.equal(s.sameSave,true);assert.equal(context.calls,1);probe.dispose();
}
{
 const {context,event,probe}=setup();event('bound',0);probe.arm('unknown');event('pending',1);
 await assert.rejects(context.resume(),/Original synthetic unknown audio failure/);assert.equal(probe.status().injections,1);probe.dispose();
}
{
 const {c,event,probe}=setup();new c.AudioContext();assert.throws(()=>event('bound',0),/Ambiguous/);assert.throws(()=>probe.arm('known'),/Invalid/);probe.dispose();
}
{
 const {context,probe}=setup();probe.arm('known',true);await assert.rejects(context.resume(),/Failed to start/);assert.equal(probe.status().injections,1);probe.dispose();
}
{
 const {event,probe,listeners}=setup();event('bound',0);assert.throws(()=>listeners.click({isTrusted:false,target:{closest:()=>true}}),/not trusted/);probe.dispose();
}
{
 const {context,event,probe}=setup();event('bound',0);event('pending',1);probe.arm('known');
 assert.throws(()=>context.resume(),/lacks source-owned/);probe.dispose();
}
{
 const {context,event,probe,listeners}=setup();event('bound',0);probe.arm('known');event('pending',1);
 await assert.rejects(context.resume());event('rejected',2,{retryEligible:true});assert.equal(probe.status().rejectedOperation,0);
 event('rejected',1,{retryEligible:true});listeners.click({isTrusted:true,target:{closest:()=>true}});
 event('pending',2,{phase:'visibility'});context.state='running';event('fulfilled',2,{phase:'visibility'});
 assert.equal(probe.status().fulfilledOperation,0);
 event('pending',3);event('fulfilled',3,{intentId:99});assert.equal(probe.status().fulfilledOperation,0);
 event('fulfilled',3);assert.equal(probe.status().fulfilledOperation,3);probe.dispose();
}
{
 const {context,event,probe,listeners}=setup();event('bound',0);probe.arm('known');event('pending',1);
 await assert.rejects(context.resume());event('rejected',1,{retryEligible:true});
 listeners.click({isTrusted:true,target:{closest:()=>true}});await Promise.resolve();
 event('pending',2);await context.resume();event('fulfilled',2);
 assert.equal(probe.status().fulfilledOperation,0);assert.match(probe.status().failure,/synchronously/);probe.dispose();
}
console.log('PASS 8 injection mock groups; not native or hardware recovery evidence');
