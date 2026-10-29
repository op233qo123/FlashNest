const assert = require('assert'), fs=require('fs'), vm=require('vm');
const source=fs.readFileSync(require('path').join(__dirname,'../observer.js'),'utf8');
(async()=>{
 let tick=0, fetchCalls=[], bodyCalls=[], response, fetchPromise, bodyPromise;
 class Response {constructor(){this.status=200;}arrayBuffer(...args){bodyCalls.push([this,args]);return bodyPromise;}}
 const window={location:{href:'http://localhost/main.html',origin:'http://localhost'}};
 const originalFetch=function(...args){fetchCalls.push([this,args]);return fetchPromise;};window.fetch=originalFetch;
 const context={window,Response,URL,WeakMap,Object,Reflect,Math,performance:{now:()=>++tick}};
 vm.runInNewContext(source,context);
 response=new Response();fetchPromise=Promise.resolve(response);const receiver={};
 const p=window.fetch.call(receiver,'/old.swf',{method:'GET'});assert.strictEqual(p,fetchPromise);await p;
 assert.strictEqual(fetchCalls[0][0],receiver);assert.deepStrictEqual(fetchCalls[0][1],['/old.swf',{method:'GET'}]);
 const buffer=new ArrayBuffer(123);bodyPromise=Promise.resolve(buffer);const bp=response.arrayBuffer('sentinel');
 assert.strictEqual(bp,bodyPromise);assert.strictEqual(await bp,buffer);assert.strictEqual(bodyCalls[0][0],response);assert.deepStrictEqual(bodyCalls[0][1],['sentinel']);
 let state=window.__sceneBodyDiagnostic.snapshot();assert.deepStrictEqual(Array.from(state.records,r=>r.phase),['request','headers','array-buffer-start','array-buffer-complete']);assert.strictEqual(state.records[3].byteLength,123);
 const untracked=new Response();bodyPromise=Promise.resolve(buffer);assert.strictEqual(untracked.arrayBuffer(),bodyPromise);await bodyPromise;assert.strictEqual(window.__sceneBodyDiagnostic.snapshot().records.length,4);
 const foreign=window.fetch('/not-a-fixture.txt');assert.strictEqual(foreign,fetchPromise);await foreign;assert.strictEqual(window.__sceneBodyDiagnostic.snapshot().records.length,4);
 const error=new Error('same-original-error');bodyPromise=Promise.reject(error);assert.strictEqual(response.arrayBuffer(),bodyPromise);await bodyPromise.catch(e=>assert.strictEqual(e,error));
 assert.strictEqual(window.__sceneBodyDiagnostic.snapshot().records.at(-1).phase,'array-buffer-rejected');
 // Fresh installation must preserve synchronous errors too.
 const boom=new Error('sync');const w2={location:window.location,fetch(){throw boom;}};class R2{arrayBuffer(){throw boom;}}
 vm.runInNewContext(source,{...context,window:w2,Response:R2});assert.throws(()=>w2.fetch('/new.swf'),e=>e===boom);
 // Snapshot mutation cannot alter internal evidence, and volume stays bounded.
 state.records[0].phase='tampered';assert.strictEqual(window.__sceneBodyDiagnostic.snapshot().records[0].phase,'request');
 for(let i=0;i<30;i++){fetchPromise=Promise.resolve(new Response());await window.fetch('/main.swf');}
 state=window.__sceneBodyDiagnostic.snapshot();assert.strictEqual(state.records.length,32);assert(state.overflow>0);
 assert.strictEqual(state.wasmCopyObservable,false);assert.strictEqual(state.decompressionObservable,false);
 assert.strictEqual(state.unhandledRejectionObservationChanged,true);
 console.log('observer same receiver/args/Promise/result/rejection, untracked and bounds PASS');
})().catch(e=>{console.error(e);process.exit(1)});
