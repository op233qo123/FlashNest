// WebAudio observer mocks only. No browser, WASM, SWF, audio device or network.
import assert from 'node:assert/strict';
import {installAudioObserver} from './observer.mjs';

function environment() {
  const calls={factory:[],start:[],resume:[],suspend:[],close:[],dispatch:[],setter:[]};
  class Scheduled {
    constructor(){this.handler=null;this.startResult=Symbol('start-result');this.dispatchResult=true}
    get onended(){return this.handler}
    set onended(value){if(this.setterError)throw this.setterError;calls.setter.push({receiver:this,value});this.handler=value==null?null:value}
    dispatchEvent(event){calls.dispatch.push({receiver:this,event});if(typeof this.handler==='function')Reflect.apply(this.handler,this,[event]);return this.dispatchResult}
  }
  class Source extends Scheduled {
    start(...args){calls.start.push({receiver:this,args});if(this.startError)throw this.startError;return this.startResult}
  }
  class BaseContext {
    createBufferSource(...args){calls.factory.push({receiver:this,args});if(this.factoryError)throw this.factoryError;return new Source()}
  }
  class Context extends BaseContext {
    constructor(){super();this.state='suspended';this.resumePromise=Promise.resolve('resumed');this.suspendPromise=Promise.resolve('suspended');this.closePromise=Promise.resolve('closed')}
    resume(...args){calls.resume.push({receiver:this,args});if(this.resumeError)throw this.resumeError;this.state='running';return this.resumePromise}
    suspend(...args){calls.suspend.push({receiver:this,args});if(this.suspendError)throw this.suspendError;this.state='suspended';return this.suspendPromise}
    close(...args){calls.close.push({receiver:this,args});if(this.closeError)throw this.closeError;this.state='closed';return this.closePromise}
  }
  const g={AudioContext:Context,AudioScheduledSourceNode:Scheduled,AudioBufferSourceNode:Source,Event,DOMException};
  const slots=[[BaseContext.prototype,'createBufferSource'],[Scheduled.prototype,'onended'],[Source.prototype,'start'],[Context.prototype,'resume'],[Context.prototype,'suspend'],[Context.prototype,'close']];
  const originals=slots.map(([owner,key])=>({owner,key,descriptor:Object.getOwnPropertyDescriptor(owner,key)}));
  function restored(){for(const {owner,key,descriptor}of originals)assert.deepEqual(Object.getOwnPropertyDescriptor(owner,key),descriptor,key+' descriptor restored exactly')}
  return {g,calls,Context,Source,Scheduled,originals,restored};
}
const flush=async()=>{await Promise.resolve();await Promise.resolve()};
let cases=0;
async function check(name,fn){await fn();cases++;console.log('PASS '+name)}

await check('original onended callback/getter identity, receiver and Event are unchanged',async()=>{
  const e=environment(),o=installAudioObserver(e.g);o.setCycle(0);
  try {
    const ctx=new e.Context(),node=ctx.createBufferSource('factory-arg');
    let received;
    function handler(event){received={receiver:this,event};return 'handler-result'}
    node.onended=handler;
    assert.strictEqual(node.onended,handler);
    const event=new Event('ended');assert.equal(node.dispatchEvent(event),true);
    assert.strictEqual(received.receiver,node);assert.strictEqual(received.event,event);
    const value=node.start(0.125,4,8);assert.strictEqual(value,node.startResult);
    assert.deepEqual(e.calls.start[0].args,[0.125,4,8]);assert.strictEqual(e.calls.start[0].receiver,node);
    assert.strictEqual(e.calls.factory[0].receiver,ctx);assert.deepEqual(e.calls.factory[0].args,['factory-arg']);
    const s=o.snapshot();assert.equal(s.contexts[0].cycle,0);assert.equal(s.contexts[0].nodes,1);
    assert(s.events.filter(x=>x.kind==='attach').every(x=>x.identityPreserved===true));
    assert.throws(()=>o.dispatchSyntheticEnded(),/Synthetic arm/);
    // Returned evidence is a clone: consumers cannot mutate the live accounting.
    s.contexts[0].nodes=999;assert.equal(o.snapshot().contexts[0].nodes,1);
  }finally{o.restore();e.restored();o.restore()}
});

await check('baseline missing-detach and candidate explicit-detach close snapshots remain distinct',async()=>{
  for(const detach of [false,true]){
    const e=environment(),o=installAudioObserver(e.g);o.setCycle(0);
    try {
      const ctx=new e.Context(),first=ctx.createBufferSource(),second=ctx.createBufferSource();
      first.onended=()=>{};second.onended=()=>{};
      if(detach){first.onended=null;second.onended=null}
      const actual=ctx.close('close-arg');assert.strictEqual(actual,ctx.closePromise);
      const row=o.snapshot().contexts[0];assert.equal(row.closeCalls,1);
      assert.deepEqual(row.closeSnapshots[0].attachedIds,detach?[]:[1,2]);
      assert.equal(row.closeSnapshots[0].explicitlyDetached,detach?2:0);
      assert.equal(row.closeSnapshots[0].state,'suspended');
      assert.strictEqual(e.calls.close[0].receiver,ctx);assert.deepEqual(e.calls.close[0].args,['close-arg']);
      await actual;await flush();assert.equal(o.snapshot().contexts[0].closeFulfilled,1);assert.equal(o.snapshot().contexts[0].closeRejected,0);
    }finally{o.restore();e.restored()}
  }
});

await check('close rejection/throw preserve original Promise/error and are recorded',async()=>{
  const e=environment(),o=installAudioObserver(e.g);o.setCycle(1);
  try {
    const ctx=new e.Context(),failure=new Error('native close rejection');ctx.closePromise=Promise.reject(failure);
    const actual=ctx.close();assert.strictEqual(actual,ctx.closePromise);await assert.rejects(actual,x=>x===failure);await flush();
    assert.equal(o.snapshot().contexts[0].closeRejected,1);assert.equal(o.snapshot().contexts[0].closeFulfilled,0);
    const second=new e.Context(),thrown=new Error('native close throw');second.closeError=thrown;
    assert.throws(()=>second.close(),x=>x===thrown);
    assert.equal(o.snapshot().contexts[1].closeRejected,1);assert.equal(o.snapshot().events.filter(x=>x.kind==='close-throw').length,1);
  }finally{o.restore();e.restored()}
});

await check('resume/suspend passthrough preserves receiver, arguments, Promise and native errors',async()=>{
  const e=environment(),o=installAudioObserver(e.g);o.setCycle(0);
  try {
    const ctx=new e.Context();
    assert.strictEqual(ctx.resume('r'),ctx.resumePromise);assert.strictEqual(ctx.suspend('s'),ctx.suspendPromise);
    assert.strictEqual(e.calls.resume[0].receiver,ctx);assert.deepEqual(e.calls.resume[0].args,['r']);
    assert.strictEqual(e.calls.suspend[0].receiver,ctx);assert.deepEqual(e.calls.suspend[0].args,['s']);
    await flush();const row=o.snapshot().contexts[0];assert.equal(row.resumes,1);assert.equal(row.suspends,1);
    assert.equal(row.resumeFulfilled,1);assert.equal(row.suspendFulfilled,1);assert.equal(row.resumeRejected,0);assert.equal(row.suspendRejected,0);
    const rejectedResume=new Error('native resume rejection');ctx.resumePromise=Promise.reject(rejectedResume);
    const resumeResult=ctx.resume();assert.strictEqual(resumeResult,ctx.resumePromise);await assert.rejects(resumeResult,x=>x===rejectedResume);
    const rejectedSuspend=new Error('native suspend rejection');ctx.suspendPromise=Promise.reject(rejectedSuspend);
    const suspendResult=ctx.suspend();assert.strictEqual(suspendResult,ctx.suspendPromise);await assert.rejects(suspendResult,x=>x===rejectedSuspend);
    await flush();assert.equal(o.snapshot().contexts[0].resumeRejected,1);assert.equal(o.snapshot().contexts[0].suspendRejected,1);
    const error=new Error('native resume throw');ctx.resumeError=error;assert.throws(()=>ctx.resume(),x=>x===error);
    const error2=new Error('native suspend throw');ctx.suspendError=error2;assert.throws(()=>ctx.suspend(),x=>x===error2);
  }finally{o.restore();e.restored()}
});

await check('first/second-start injection occurs exactly once, without calling the native start at that site',async()=>{
  for(const [mode,index]of [['start-first',1],['start-second',2]]){
    const e=environment(),o=installAudioObserver(e.g,{mode});o.setCycle(0);
    try {
      const ctx=new e.Context(),nodes=[ctx.createBufferSource(),ctx.createBufferSource(),ctx.createBufferSource()];
      for(let i=0;i<nodes.length;i++){
        if(i+1===index)assert.throws(()=>nodes[i].start(10+i),x=>x instanceof DOMException&&x.name==='InvalidStateError'&&x.message.includes('Original audio lifecycle diagnostic'));
        else assert.strictEqual(nodes[i].start(10+i),nodes[i].startResult);
      }
      assert.equal(e.calls.start.length,2);assert(!e.calls.start.some(x=>x.receiver===nodes[index-1]));
      // One observer arm injects once, not once per recreated context.
      const later=new e.Context(),laterNode=later.createBufferSource();assert.strictEqual(laterNode.start(),laterNode.startResult);
      const s=o.snapshot();assert.equal(s.injected,true);assert.equal(s.events.filter(x=>x.kind==='injected-start-error').length,1);
      assert.equal(s.contexts[0].starts,3);assert.equal(s.contexts[1].starts,1);
    }finally{o.restore();e.restored()}
  }
});

await check('unmodified start/factory/setter native exceptions propagate unchanged',async()=>{
  const e=environment(),o=installAudioObserver(e.g);o.setCycle(0);
  try {
    const ctx=new e.Context(),node=ctx.createBufferSource(),startError=new Error('start-native');node.startError=startError;
    assert.throws(()=>node.start(),x=>x===startError);
    const setterError=new Error('setter-native');node.setterError=setterError;
    assert.throws(()=>{node.onended=()=>{}},x=>x===setterError);assert.equal(o.snapshot().nodes[0].attaches,0);
    const factoryError=new Error('factory-native');ctx.factoryError=factoryError;
    assert.throws(()=>ctx.createBufferSource(),x=>x===factoryError);assert.equal(o.snapshot().contexts[0].nodes,1);
  }finally{o.restore();e.restored()}
});

await check('synthetic arm dispatches an ended Event on the retained latest node; detachment prevents refill',async()=>{
  for(const detached of [false,true]){
    const e=environment(),o=installAudioObserver(e.g,{mode:'synthetic-ended'});o.setCycle(0);
    try {
      const ctx=new e.Context(),old=ctx.createBufferSource(),latest=ctx.createBufferSource();let seen;
      old.onended=()=>{throw new Error('Not the latest node')};
      latest.onended=function(event){seen={receiver:this,event};ctx.createBufferSource()};
      if(detached)latest.onended=null;
      await ctx.close();await flush();
      const result=o.dispatchSyntheticEnded();assert.equal(result.node,2);assert.equal(result.hadHandler,!detached);
      assert.equal(e.calls.dispatch.length,1);assert.strictEqual(e.calls.dispatch[0].receiver,latest);assert.equal(e.calls.dispatch[0].event.type,'ended');
      assert.equal(result.afterNodes-result.beforeNodes,detached?0:1);
      assert.equal(result.afterAttempts-result.beforeAttempts,detached?0:1);assert.equal(result.beforeThrows,0);assert.equal(result.afterThrows,0);
      if(detached)assert.equal(seen,undefined);else{assert.strictEqual(seen.receiver,latest);assert.strictEqual(seen.event,e.calls.dispatch[0].event)}
      o.releaseRetained();assert.throws(()=>o.dispatchSyntheticEnded(),/requires its explicitly retained node/);
    }finally{o.restore();e.restored()}
  }
});

await check('bounded event/node overflow is explicit, not silently successful',async()=>{
  const e=environment(),o=installAudioObserver(e.g,{maxEvents:2,maxNodes:1});o.setCycle(0);
  try {
    const ctx=new e.Context(),a=ctx.createBufferSource();a.onended=()=>{};ctx.createBufferSource();
    const s=o.snapshot();assert.equal(s.overflow,true);assert.equal(s.nodes.length,1);assert.equal(s.events.length,2);
  }finally{o.restore();e.restored()}
});

await check('unsupported install rolls back already-installed hooks; restore detects overwritten hook',async()=>{
  const e=environment();Object.defineProperty(e.Source.prototype,'start',{...Object.getOwnPropertyDescriptor(e.Source.prototype,'start'),configurable:false});
  const factory=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e.Context.prototype),'createBufferSource');
  const setter=Object.getOwnPropertyDescriptor(e.Scheduled.prototype,'onended');
  assert.throws(()=>installAudioObserver(e.g),/Nonconfigurable Audio API start/);
  assert.deepEqual(Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e.Context.prototype),'createBufferSource'),factory);
  assert.deepEqual(Object.getOwnPropertyDescriptor(e.Scheduled.prototype,'onended'),setter);
  const other=environment(),o=installAudioObserver(other.g);other.Context.prototype.close=()=>Promise.resolve();
  assert.throws(()=>o.restore(),/Audio hook overwritten: close/);
  // This isolated environment is discarded; no shared globals were patched.
});

await check('source attempt is recorded before a throwing native factory',async()=>{
 const e=environment(),o=installAudioObserver(e.g);o.setCycle(0);
 try{const ctx=new e.Context(),failure=new Error('Closed context diagnostic');ctx.factoryError=failure;assert.throws(()=>ctx.createBufferSource(),x=>x===failure);const c=o.snapshot().contexts[0];assert.equal(c.sourceAttempts,1);assert.equal(c.sourceThrows,1);assert.equal(c.nodes,0)}finally{o.restore();e.restored()}
});

await check('undefined and null detach normalize to actual null with unchanged callback identity',async()=>{
 const e=environment(),o=installAudioObserver(e.g);o.setCycle(0);
 try{const ctx=new e.Context(),node=ctx.createBufferSource();function handler(){};for(const clear of [undefined,null]){node.onended=handler;assert.strictEqual(node.onended,handler);node.onended=clear;assert.strictEqual(node.onended,null)}const events=o.snapshot().events.filter(x=>x.kind==='detach');assert.deepEqual(events.map(x=>x.setterCategory),['undefined','null']);assert(events.every(x=>x.getterCategory==='null'&&x.cleared===true&&x.identityPreserved===null));assert.equal(o.snapshot().nodes[0].attached,false)}finally{o.restore();e.restored()}
});
await check('non-null native getter remains attached and unsupported setter categories stay visible',async()=>{
 const e=environment(),o=installAudioObserver(e.g);o.setCycle(0);
 try{const ctx=new e.Context(),node=ctx.createBufferSource();node.onended=42;const event=o.snapshot().events.at(-1);assert.equal(event.kind,'unsupported-onended');assert.equal(event.setterCategory,'number');assert.equal(o.snapshot().nodes[0].attached,true)}finally{o.restore();e.restored()}
});

await check('wrong native getter or replacement callback fails semantics and stays conservatively attached',async()=>{
 for(const replace of [false,true]){const e=environment();const original=Object.getOwnPropertyDescriptor(e.Scheduled.prototype,'onended');Object.defineProperty(e.Scheduled.prototype,'onended',{...original,set(value){this.handler=replace&&typeof value==='function'?function replacement(){}:value}});const o=installAudioObserver(e.g);o.setCycle(0);try{const node=new e.Context().createBufferSource();node.onended=replace?function actual(){}:undefined;const event=o.snapshot().events.at(-1);assert.equal(event.kind,replace?'attach':'detach');assert.equal(replace?event.identityPreserved:event.cleared,false);assert.equal(o.snapshot().nodes[0].attached,true)}finally{o.restore()}}
});

console.log(`PASS ${cases} WebAudio observer mock groups; no real browser, audio, SWF or WASM execution`);
