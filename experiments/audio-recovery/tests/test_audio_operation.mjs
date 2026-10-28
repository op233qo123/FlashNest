import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {stripTypeScriptTypes} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const helperURL=process.env.RUFFLE_SOURCE_DIR ? pathToFileURL(resolve(process.env.RUFFLE_SOURCE_DIR,'web/packages/core/src/internal/audio-operation.ts')) : new URL('../upstream/web/packages/core/src/internal/audio-operation.ts',import.meta.url);
const {bindAudioContext,requestAudioOperation}=await import(helperURL);

const unhandled=[];const onUnhandled=error=>unhandled.push(error);
process.on('unhandledRejection',onUnhandled);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function flush(){await tick();await tick();await tick()}
const device=()=>new DOMException('Failed to start the audio device','InvalidStateError');
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
class Context {
 state='suspended';calls=[];plans={resume:[],suspend:[]};
 resume(...args){assert(this instanceof Context);this.calls.push(['resume',...args]);return this.take('resume')}
 suspend(...args){assert(this instanceof Context);this.calls.push(['suspend',...args]);return this.take('suspend')}
 take(name){const x=this.plans[name].shift();if(x?.throws)throw x.error;return x?.promise??Promise.resolve()}
}
function owned(){const context=new Context(),events=[];const release=bindAudioContext(context,x=>events.push(x));return {context,events,release}}
let count=0;
async function test(name,fn){const before=unhandled.length;await fn();await flush();assert.equal(unhandled.length,before,`${name}: unexpected unhandled rejection`);count++;console.log('PASS '+name)}
async function fatal(error,fn){const before=unhandled.length;await fn();await flush();assert.equal(unhandled.length,before+1);assert.equal(unhandled.pop(),error)}

await test('known owned native resume rejection is retry eligible',async()=>{
 const {context,events}=owned(),d=deferred();context.plans.resume.push(d);
 requestAudioOperation(context,'resume','core-play');assert.equal(events.at(-1).status,'pending');
 d.reject(device());await flush();const e=events.at(-1);assert.equal(e.status,'rejected');assert.equal(e.retryEligible,true);assert.equal(e.current,true);assert.equal(e.state,'suspended');assert.equal(context.calls.length,1);assert.deepEqual(context.calls[0],['resume']);assert(Object.isFrozen(e));
});
for(const [label,error] of [
 ['uninitialized',new DOMException('AudioDestinationNode is not initialized','InvalidStateError')],
 ['wrong name',new DOMException('Failed to start the audio device','NotAllowedError')],
 ['plain Error',new Error('Failed to start the audio device')],
 ['closed error',new DOMException('Context is closed','InvalidStateError')],
 ['non-audio Error',new Error('Original AVM2 failure')],
 ['undefined rejection',undefined],['null rejection',null],
])await test('fatal original identity: '+label,async()=>{
 const {context,events}=owned(),d=deferred();context.plans.resume.push(d);requestAudioOperation(context,'resume','core-play');
 await fatal(error,()=>d.reject(error));assert.equal(events.at(-1).retryEligible,false);
});
await test('same message with active closed context stays fatal',async()=>{
 const {context,events}=owned(),d=deferred(),error=device();context.state='closed';context.plans.resume.push(d);requestAudioOperation(context,'resume','core-play');await fatal(error,()=>d.reject(error));assert.equal(events.at(-1).retryEligible,false);
});
await test('unowned context cannot claim retry eligibility',async()=>{
 const context=new Context(),d=deferred(),error=device();context.plans.resume.push(d);requestAudioOperation(context,'resume','core-play');await fatal(error,()=>d.reject(error));
});
await test('binding after request cannot retroactively own it',async()=>{
 const context=new Context(),events=[],d=deferred(),error=device();context.plans.resume.push(d);requestAudioOperation(context,'resume','core-play');bindAudioContext(context,x=>events.push(x));await fatal(error,()=>d.reject(error));assert.equal(events.at(-1).current,false);
});
await test('suspend same message stays fatal',async()=>{
 const {context,events}=owned(),d=deferred(),error=device();context.plans.suspend.push(d);requestAudioOperation(context,'suspend','core-pause');await fatal(error,()=>d.reject(error));assert.equal(events.at(-1).retryEligible,false);
});
await test('synchronous throw is not a rejected native resume Promise',async()=>{
 const {context,events}=owned(),error=device();context.plans.resume.push({throws:true,error});await fatal(error,()=>requestAudioOperation(context,'resume','core-play'));assert.equal(events.filter(x=>x.retryEligible).length,0);
});
await test('fresh resume success is current only after actual fulfillment',async()=>{
 const {context,events}=owned(),first=deferred(),retry=deferred();context.plans.resume.push(first,retry);requestAudioOperation(context,'resume','core-play');first.reject(device());await flush();const failed=events.at(-1);requestAudioOperation(context,'resume','core-play');const pending=events.at(-1);assert.equal(pending.status,'pending');assert(pending.operationId>failed.operationId);assert.equal(pending.contextId,failed.contextId);context.state='running';retry.resolve();await flush();const completed=events.at(-1);assert.equal(completed.status,'fulfilled');assert.equal(completed.operationId,pending.operationId);assert.equal(completed.intentId,pending.intentId);assert.equal(completed.state,'running');assert.equal(completed.current,true);
});
await test('fulfilled but interrupted is not reported running',async()=>{
 const {context,events}=owned(),d=deferred();context.plans.resume.push(d);requestAudioOperation(context,'resume','visibility');context.state='interrupted';d.resolve();await flush();assert.equal(events.at(-1).state,'interrupted');
});
await test('pause invalidates prior resume completion without invoking another resume',async()=>{
 const {context,events}=owned(),r=deferred(),s=deferred();context.plans.resume.push(r);context.plans.suspend.push(s);requestAudioOperation(context,'resume','core-play');const id=events.at(-1).operationId;requestAudioOperation(context,'suspend','core-pause');s.resolve();r.resolve();await flush();const old=events.find(x=>x.operationId===id&&x.status==='fulfilled');assert.equal(old.current,false);assert.deepEqual(context.calls,[['resume'],['suspend']]);
});
await test('superseded known failure cannot replace newer current success',async()=>{
 const {context,events}=owned(),one=deferred(),two=deferred();context.plans.resume.push(one,two);requestAudioOperation(context,'resume','core-play');const old=events.at(-1).operationId;requestAudioOperation(context,'resume','visibility');context.state='running';two.resolve();one.reject(device());await flush();const rejected=events.find(x=>x.operationId===old&&x.status==='rejected');assert.equal(rejected.current,false);assert.equal(rejected.retryEligible,false);assert.equal(context.calls.length,2);
});
await test('release detaches listener and known old failure cannot touch new context',async()=>{
 const old=owned(),d=deferred();old.context.plans.resume.push(d);requestAudioOperation(old.context,'resume','unmute');old.release();old.release();const size=old.events.length;assert.equal(old.events.at(-1).status,'released');const next=owned();assert(next.events[0].contextId>old.events[0].contextId);d.reject(device());await flush();assert.equal(old.events.length,size);assert.equal(next.events.length,1);assert.equal(old.context.calls.length,1);
});
await test('unknown retired failure remains fatal exactly once',async()=>{
 const {context,events,release}=owned(),d=deferred(),error=new Error('retired unknown');context.plans.resume.push(d);requestAudioOperation(context,'resume','core-play');release();const n=events.length;await fatal(error,()=>d.reject(error));assert.equal(events.length,n);
});
await test('closed cancellation is not silently generalized',async()=>{
 const {context,release}=owned(),d=deferred(),error=new DOMException('Context is closed','InvalidStateError');context.plans.resume.push(d);requestAudioOperation(context,'resume','core-play');release();await fatal(error,()=>d.reject(error));
});
await test('unknown hostile diagnostic getter preserves original exception',async()=>{
 const {context}=owned(),d=deferred(),error=new Error('x');Object.defineProperty(error,'name',{get(){throw new Error('do not replace original')}});context.plans.resume.push(d);requestAudioOperation(context,'resume','core-play');await fatal(error,()=>d.reject(error));
});
await test('same context cannot acquire two subscriptions',async()=>{
 const {context,release}=owned();assert.throws(()=>bindAudioContext(context,()=>{}),/rebound/);release();assert.throws(()=>bindAudioContext(context,()=>{}),/rebound/);
});
await test('counter exhaustion fails closed before native call',async()=>{
 const src=await readFile(helperURL,'utf8');
 const js=stripTypeScriptTypes(src.replace('let nextContextId = 0;','let nextContextId = Number.MAX_SAFE_INTEGER;'));
 const mod=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
 const c=new Context();assert.throws(()=>mod.bindAudioContext(c,()=>{}),/counter exhausted/);assert.equal(c.calls.length,0);
});
process.removeListener('unhandledRejection',onUnhandled);
console.log(`PASS ${count} source-bound audio operation groups`);
