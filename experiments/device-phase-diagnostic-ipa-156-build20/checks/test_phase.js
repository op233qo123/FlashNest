'use strict';
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.PHASE_APP+'/App/Resources/Web/shell.js','utf8');
const code=source.slice(source.indexOf('  // BEGIN opt-in'), source.indexOf('  async function boot()'));
const uuid='12345678-1234-1234-1234-123456789abc';
function harness(query='?phaseDiagnostics=1&phaseSession='+uuid, fetch=async()=>response()) {
 const events=[], context={URLSearchParams,URL,Promise,location:{search:query,origin:'http://127.0.0.1:8',href:'http://127.0.0.1:8/c/web/index.html'},swfRequestID:0,reportSWF:()=>{},report:()=>{},t:()=>'',window:{fetch,webkit:{messageHandlers:{flashnest:{postMessage:e=>events.push(e)}}}}};
 vm.runInNewContext(code,context);return {events,fetch:context.window.fetch,context};
}
function response(body=new ArrayBuffer(12), header='7') { return {status:200,ok:true,headers:{get:name=>name==='X-FlashNest-Diagnostic-Request'?header:'12'},arrayBuffer(){return Promise.resolve(body)}}; }
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 let count=0, originalPromise=Promise.resolve(new ArrayBuffer(23)), r=response();r.arrayBuffer=function(){count++;assert.equal(this,r);return originalPromise};
 let h=harness(undefined,async()=>r);assert.equal(await h.fetch('/c/package/a.swf'),r);assert.equal(count,0);assert.equal(h.events.length,1);
 assert.equal(r.arrayBuffer(),originalPromise);await flush();assert.equal(count,1);assert.deepEqual(h.events.map(e=>e.phase),['clientHeaders','clientBodyStarted','clientBodyFulfilled']);assert.equal(h.events[2].bytes,23);assert.equal(h.events[2].requestID,7);
 for(const e of h.events) assert.ok(Object.keys(e).every(k=>['type','phaseSession','phase','seq','requestID','bytes','status'].includes(k)));
 for(const q of ['', '?phaseDiagnostics=0&phaseSession='+uuid,'?phaseDiagnostics=1&phaseSession=bad']){r=response();let original=r.arrayBuffer;h=harness(q,async()=>r);await h.fetch('/secret.swf');assert.equal(r.arrayBuffer,original);await r.arrayBuffer();assert.equal(h.events.length,0)}
 r=response();let original=r.arrayBuffer;h=harness(undefined,async()=>r);await h.fetch('https://remote.invalid/private.swf');assert.equal(r.arrayBuffer,original);assert.equal(h.events.length,0);
 r=response(undefined,'bad/path');h=harness(undefined,async()=>r);await h.fetch('/secret.swf');await r.arrayBuffer();await flush();assert.equal('requestID' in h.events[0],false);
 r=response(undefined,'9999999');h=harness(undefined,async()=>r);await h.fetch('/secret.swf');assert.equal(h.events[0].requestID,9999999);
 r=response(undefined,'10000000');h=harness(undefined,async()=>r);await h.fetch('/secret.swf');assert.equal('requestID' in h.events[0],false);
 const rejection=new Error('PRIVATE SAVE TEXT');r=response();r.arrayBuffer=()=>Promise.reject(rejection);h=harness(undefined,async()=>r);await h.fetch('/secret.swf');await assert.rejects(r.arrayBuffer(),e=>e===rejection);await flush();assert.equal(h.events.at(-1).phase,'clientBodyRejected');assert.ok(!JSON.stringify(h.events).includes('PRIVATE'));
 r=response();r.arrayBuffer=()=>{throw rejection};h=harness(undefined,async()=>r);await h.fetch('/secret.swf');assert.throws(()=>r.arrayBuffer(),e=>e===rejection);assert.equal(h.events.at(-1).phase,'clientBodyRejected');
 h=harness(undefined,async()=>{throw rejection});await assert.rejects(h.fetch('/secret.swf'),e=>e===rejection);assert.equal(h.events[0].phase,'clientFetchRejected');
 r=Object.freeze(response());h=harness(undefined,async()=>r);await h.fetch('/secret.swf');await r.arrayBuffer();await flush();assert.deepEqual(h.events.map(e=>e.phase),['clientHeaders']);
 h=harness();for(let i=0;i<100;i++){r=await h.fetch('/secret.swf');await r.arrayBuffer()}await flush();assert.equal(h.events.length,64*3);assert.equal(Math.max(...h.events.map(e=>e.seq)),64);
 r=response();h=harness(undefined,async()=>r);await h.fetch('/secret.swf');for(let i=0;i<300;i++)await r.arrayBuffer();await flush();assert.equal(h.events.length,256);
 r=response();h=harness(undefined,async()=>r);h.context.window.webkit.messageHandlers.flashnest.postMessage=()=>{throw Error('bridge unavailable')};await h.fetch('/secret.swf');assert.equal((await r.arrayBuffer()).byteLength,12);
 // Real native Node Response confirms own-method wrapper does not clone/consume
 // before requested. This still does not replace WebKit device execution.
 r=new Response(new Uint8Array([1,2,3,4]),{headers:{'X-FlashNest-Diagnostic-Request':'8'}});
 let nativeArrayBuffer=r.arrayBuffer,nativePromise;
 r.arrayBuffer=function(...args){nativePromise=nativeArrayBuffer.apply(this,args);return nativePromise};
 h=harness(undefined,async()=>r);await h.fetch('/real.swf');assert.equal(r.bodyUsed,false);
 let observedPromise=r.arrayBuffer();assert.equal(observedPromise,nativePromise);
 assert.deepEqual(Array.from(new Uint8Array(await observedPromise)),[1,2,3,4]);await flush();assert.equal(h.events.at(-1).bytes,4);
 await assert.rejects(r.arrayBuffer(),TypeError);await flush();assert.equal(h.events.at(-1).phase,'clientBodyRejected');
 // Opt-in observer marks original rejection handled. This is documented behavior,
 // not an assertion that the diagnostic instrumentation has zero interference.
 let unhandled=0;const listener=()=>unhandled++;process.on('unhandledRejection',listener);
 r=response();r.arrayBuffer=()=>Promise.reject(rejection);h=harness(undefined,async()=>r);await h.fetch('/secret.swf');r.arrayBuffer();await flush();await flush();process.removeListener('unhandledRejection',listener);assert.equal(unhandled,0);
 console.log('PASS: 14 groups: identity/no eager consumption/off/remote/scalars/rejections/frozen/caps/bridge/Promise observer semantics');
})().catch(error=>{console.error(error);process.exitCode=1});
