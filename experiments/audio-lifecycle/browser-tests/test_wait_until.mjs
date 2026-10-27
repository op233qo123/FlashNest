// Pure polling mocks: no browser, WebdriverIO, runtime, audio or network execution.
import assert from 'node:assert/strict';
import {waitUntilFailFast} from './wait-until.mjs';
let groups=0;
async function check(name,fn){await fn();groups++;console.log('PASS '+name)}
async function thrownValue(promise,expected){let rejected=false,actual;try{await promise}catch(error){rejected=true;actual=error}assert.equal(rejected,true,'A predicate failure must not become success');assert.strictEqual(actual,expected,'Exact thrown identity/value must survive')}
function polling({max=5,timeout=new Error('mock timeout'),receiver={mockReceiver:true},args=['poll-argument'],completion=true}={}){
 const state={polls:0,options:null};
 const wait=async(condition,options)=>{state.options=options;for(let i=0;i<max;i++){state.polls++;try{if(await Reflect.apply(condition,receiver,args))return completion}catch{/* Model WebdriverIO retrying predicate exceptions. */}}throw timeout};
 return {wait,state,receiver,args};
}

await check('ordinary false readiness polls until true with identical options/receiver/arguments',async()=>{
 const p=polling({completion:'native success'}),options=Object.freeze({timeout:123,interval:7,timeoutMsg:'ready'});let calls=0;
 const result=await waitUntilFailFast(p.wait,function(...args){calls++;assert.strictEqual(this,p.receiver);assert.deepEqual(args,p.args);return calls>=3},options);
 assert.equal(result,'native success');assert.equal(calls,3);assert.equal(p.state.polls,3);assert.strictEqual(p.state.options,options);
});
await check('synchronous assertion is latched once instead of retried or falsely passing',async()=>{
 const p=polling();let calls=0,caught;
 const promise=waitUntilFailFast(p.wait,()=>{calls++;try{assert.equal('actual','expected')}catch(error){caught=error;throw error}},{});
 try{await promise;assert.fail('unexpected success')}catch(error){assert.strictEqual(error,caught);assert(error instanceof assert.AssertionError)}
 assert.equal(calls,1);assert.equal(p.state.polls,1);
});
await check('asynchronous assertion after await is latched and rethrown exactly',async()=>{
 const p=polling();let calls=0,caught;
 const promise=waitUntilFailFast(p.wait,async()=>{calls++;await Promise.resolve();try{assert.equal(1,2)}catch(error){caught=error;throw error}},{});
 try{await promise;assert.fail('unexpected success')}catch(error){assert.strictEqual(error,caught);assert(error instanceof assert.AssertionError)}
 assert.equal(calls,1);assert.equal(p.state.polls,1);
});
await check('every falsy throw rejects, synchronously and asynchronously, with original value',async()=>{
 for(const value of [null,undefined,0,false,''])for(const asynchronous of [false,true]){
  const p=polling();let calls=0;
  const predicate=asynchronous?async()=>{calls++;await Promise.resolve();throw value}:()=>{calls++;throw value};
  await thrownValue(waitUntilFailFast(p.wait,predicate,{}),value);assert.equal(calls,1);assert.equal(p.state.polls,1);
 }
});
await check('a caller repeatedly invoking after the latch cannot reenter the predicate',async()=>{
 const failure={original:true};let calls=0;const answers=[];
 const wait=async condition=>{for(let i=0;i<6;i++)answers.push(await condition());return 'misleading success'};
 await thrownValue(waitUntilFailFast(wait,()=>{calls++;throw failure},{}),failure);
 assert.equal(calls,1);assert.deepEqual(answers,[true,true,true,true,true,true]);
});
await check('latched predicate failure wins even if the underlying wait rejects afterward',async()=>{
 const original=undefined,timeout=new Error('later underlying timeout');let calls=0;
 const wait=async condition=>{assert.equal(await condition(),true);assert.equal(await condition(),true);throw timeout};
 await thrownValue(waitUntilFailFast(wait,()=>{calls++;throw original},{}),original);assert.equal(calls,1);
});
await check('ordinary false timeout and underlying synchronous errors retain identity',async()=>{
 const timeout=new Error('unchanged timeout'),p=polling({max:4,timeout});let calls=0;
 await thrownValue(waitUntilFailFast(p.wait,async()=>{calls++;return false},{timeout:1}),timeout);assert.equal(calls,4);assert.equal(p.state.polls,4);
 const failure=new Error('native wait setup failed');await thrownValue(waitUntilFailFast(()=>{throw failure},()=>true,{}),failure);
});
await check('false-like readiness values are not misclassified as thrown failures',async()=>{
 const p=polling({max:7});const values=[undefined,null,0,'',false,true];let index=0;
 assert.equal(await waitUntilFailFast(p.wait,async()=>values[index++],{}),true);assert.equal(index,6);
});
await check('concurrent in-flight predicates preserve the first error and skip later entries',async()=>{
 const first={first:true},second={second:true};let rejectFirst,rejectSecond,calls=0;
 const promises=[new Promise((_,reject)=>rejectFirst=reject),new Promise((_,reject)=>rejectSecond=reject)];
 const wait=async condition=>{const a=condition(),b=condition();rejectFirst(first);await a;rejectSecond(second);await b;assert.equal(await condition(),true);return true};
 await thrownValue(waitUntilFailFast(wait,()=>promises[calls++],{}),first);assert.equal(calls,2);
});
console.log(`PASS ${groups} fail-fast polling mock groups; no browser/runtime execution`);
