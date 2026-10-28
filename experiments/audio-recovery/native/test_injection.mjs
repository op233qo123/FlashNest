import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('./audio-recovery-injection.js',import.meta.url),'utf8');
function setup() {
 class Target {
  callbacks=[];
  dispatchEvent(event){return true;}
  addEventListener(type,fn,options){this.callbacks.push({type,fn,options});}
  removeEventListener(type,fn){this.callbacks=this.callbacks.filter(x=>x.type!==type||x.fn!==fn);}
 }
 class Audio {state='suspended';calls=0;resume(){this.calls++;this.state='running';return Promise.resolve();}}
 const player=new Target(),button=new Target(),listeners={};button.closest=()=>button;
 const storage=new Map([['synthetic','original']]);
 const c={AudioContext:Audio,EventTarget:Target,DOMException,Error,Proxy,Reflect,Promise,Math,Date,queueMicrotask,
 localStorage:{get length(){return storage.size},key:i=>[...storage.keys()][i],getItem:k=>storage.get(k)},
 document:{querySelector:s=>s==='#audio-retry'?button:player,querySelectorAll:()=>[player],addEventListener:(name,fn,capture)=>listeners[capture?'capture':'bubble']=fn,removeEventListener:(name,fn,capture)=>delete listeners[capture?'capture':'bubble']}};
 c.window=c;vm.createContext(c);vm.runInContext(source,c);
 let body=()=>{};const listener=function(e){return body.call(this,e);};button.addEventListener('click',listener);
 const context=new c.AudioContext();
 const event=(status,operationId,extra={})=>player.dispatchEvent({type:'ruffle-audio-status',detail:{schema:1,contextId:1,operationId,intentId:operationId,phase:'core-play',operation:'resume',status,state:context.state,current:true,retryEligible:false,...extra}});
 const click=()=>({isTrusted:true,eventPhase:1,currentTarget:c.document,target:button});
 function target(e,fn){e.eventPhase=2;e.currentTarget=button;body=fn;return button.callbacks[0].fn.call(button,e);}
 function end(e,bubble=true){if(bubble){e.eventPhase=3;e.currentTarget=c.document;listeners.bubble(e);}e.eventPhase=0;e.currentTarget=null;}
 return {c,context,event,listeners,storage,button,listener,click,target,end,probe:c.FlashNestAudioProbe};
}
async function rejected(s){s.event('bound',0);s.probe.arm('known');s.event('pending',1);await assert.rejects(s.context.resume(),e=>e.name==='InvalidStateError');s.event('rejected',1,{retryEligible:true});}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);await Promise.resolve();
 let promise;s.target(e,()=>{s.event('pending',2);promise=s.context.resume();});s.end(e);await promise;s.event('fulfilled',2);
 const p=s.probe.status();assert.equal(p.fulfilledOperation,2);assert.equal(p.failure,null);assert.equal(p.sameSave,true);assert.equal(s.context.calls,1);s.probe.dispose();
}
{
 const s=setup();s.event('bound',0);s.probe.arm('unknown');s.event('pending',1);await assert.rejects(s.context.resume(),/Original synthetic/);s.probe.dispose();
}
{
 const s=setup();new s.c.AudioContext();assert.throws(()=>s.event('bound',0),/Ambiguous/);s.probe.dispose();
}
{
 const s=setup();s.probe.arm('known',true);await assert.rejects(s.context.resume(),/Failed to start/);assert.equal(s.probe.status().nativeResumeRestored,true);s.probe.dispose();
}
{
 const s=setup();const e=s.click();e.isTrusted=false;assert.throws(()=>s.listeners.capture(e),/not trusted/);s.probe.dispose();
}
{
 const s=setup();s.event('bound',0);s.event('pending',1);s.probe.arm('known');assert.throws(()=>s.context.resume(),/lacks source-owned/);s.probe.dispose();
}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);
 s.target(e,()=>{s.event('pending',2,{phase:'visibility'});s.event('fulfilled',2,{phase:'visibility'});s.event('pending',3);});
 s.end(e);s.context.state='running';s.event('fulfilled',3,{intentId:99});assert.equal(s.probe.status().fulfilledOperation,0);s.event('fulfilled',3);assert.equal(s.probe.status().fulfilledOperation,3);s.probe.dispose();
}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);s.target(e,()=>{});s.end(e);
 await Promise.resolve();s.event('pending',2);await s.context.resume();s.event('fulfilled',2);
 assert.equal(s.probe.status().fulfilledOperation,0);assert.match(s.probe.status().failure,/synchronously/);s.probe.dispose();
}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);assert.throws(()=>s.listeners.capture(e),/Repeated/);s.probe.dispose();
}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);await Promise.resolve();s.event('pending',2);s.event('fulfilled',2);assert.equal(s.probe.status().fulfilledOperation,0);
 s.target(e,()=>s.event('pending',3));s.context.state='running';s.end(e);s.event('fulfilled',3);assert.equal(s.probe.status().fulfilledOperation,3);s.probe.dispose();
}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);s.target(e,()=>{});s.end(e,false);
 s.event('pending',2);s.context.state='running';s.event('fulfilled',2);assert.equal(s.probe.status().fulfilledOperation,0);assert.match(s.probe.status().failure,/without bubble/);s.probe.dispose();
}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);assert.throws(()=>s.target(e,()=>{s.event('pending',2);s.event('pending',3);}),/Duplicate/);s.probe.dispose();
}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);
 s.target(e,()=>{queueMicrotask(()=>s.event('pending',2));});
 // phase/currentTarget still identify button during callback-cleanup checkpoint.
 await Promise.resolve();s.context.state='running';s.event('fulfilled',2);s.end(e);
 assert.equal(s.probe.status().fulfilledOperation,0);assert.match(s.probe.status().failure,/synchronously/);s.probe.dispose();
}
{
 const s=setup();await rejected(s);const e=s.click();s.listeners.capture(e);
 assert.throws(()=>s.target(e,()=>{throw new Error('callback throws');}),/callback throws/);
 s.event('pending',2);s.context.state='running';s.event('fulfilled',2);s.end(e);assert.equal(s.probe.status().fulfilledOperation,0);s.probe.dispose();
}
{
 const s=setup();assert.throws(()=>s.button.addEventListener('click',()=>{}),/Duplicate/);s.probe.dispose();
}
{
 const s=setup();const e=s.click();e.target={closest:()=>s.button};assert.throws(()=>s.listeners.capture(e),/exact registered/);s.probe.dispose();
}
{
 const s=setup();const e=s.click();const result=s.target(e,function(arg){assert.equal(this,s.button);assert.equal(arg,e);return 42;});assert.equal(result,42);
 s.button.removeEventListener('click',s.listener,{capture:false});assert.equal(s.button.callbacks.length,0);s.probe.dispose();assert.equal(s.button.callbacks.length,0);
}
console.log('PASS 17 injection mock groups; not native or hardware recovery evidence');
