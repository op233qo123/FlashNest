import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('./startup-journal.js',import.meta.url),'utf8');
function setup(){
 const messages=[],calls=[],logs=[];let callback;
 const promise=Promise.resolve('actual');
 function fetch(...args){calls.push({receiver:this,args});if(args[0]==='throw')throw new Error('original');return promise;}
 function log(...args){logs.push({receiver:this,args});return 17;}
 const c={URL,Request,Reflect,Set,Object,Number,location:{href:'http://127.0.0.1:8000/token/web/index.html',origin:'http://127.0.0.1:8000'},fetch,console:{log},
 __FlashNestStartupResources:{'a.wasm':'a'.repeat(64),'core.js':'b'.repeat(64)},
 webkit:{messageHandlers:{flashnestStartup:{postMessage:b=>messages.push(b)}}},
 PerformanceObserver:class{constructor(fn){callback=fn;}observe(){}disconnect(){this.closed=true;}}};
 c.window=c;vm.createContext(c);vm.runInContext(source,c);
 return {c,messages,calls,logs,promise,fetch,log,complete:n=>callback({getEntries:()=>[{name:n}]})};
}
{
 const s=setup(),receiver={};assert.equal(s.c.fetch.call(receiver,'http://127.0.0.1:8000/token/web/runtime/a.wasm?secret=NEVER'),s.promise);assert.equal(s.calls[0].receiver,receiver);assert.equal(s.messages.at(-1).resource,'a.wasm');assert(!JSON.stringify(s.messages).includes('secret'));assert.throws(()=>s.c.fetch('throw'),/original/);
 const url=new URL('http://127.0.0.1:8000/token/web/runtime/a.wasm');assert.equal(s.c.fetch(url),s.promise);assert.equal(s.calls.at(-1).args[0],url);assert.equal(s.messages.at(-1).phase,'resource-request');
 const request=new Request(url);assert.equal(s.c.fetch(request),s.promise);assert.equal(s.calls.at(-1).args[0],request);assert.equal(s.messages.at(-1).resource,'a.wasm');
 const n=s.messages.length;s.c.fetch({url:url.href,toString(){throw new Error('must not coerce')}});assert.equal(s.messages.length,n);
}
{
 const s=setup();for(const url of ['https://other.test/token/web/runtime/a.wasm','http://127.0.0.1:8000/token/shell/runtime/a.wasm','http://127.0.0.1:8000/other/web/runtime/a.wasm','http://127.0.0.1:8000/games/private.sol','http://127.0.0.1:8000/token/web/runtime/unknown.wasm'])s.c.fetch(url);assert.equal(s.messages.length,1);s.complete('http://127.0.0.1:8000/token/web/runtime/a.wasm');assert.equal(s.messages.at(-1).phase,'resource-complete');
}
{
 const s=setup();s.c.FlashNestStartupJournal.record('audio-status',{contextId:1,operationId:3,intentId:4,audioPhase:'core-play',status:'fulfilled',state:'running',current:true,url:'PRIVATE',game:'PRIVATE',error:'PRIVATE'});assert(!JSON.stringify(s.messages).includes('PRIVATE'));assert.equal(s.messages.at(-1).contextId,1);s.c.FlashNestStartupJournal.record('invalid',{state:'PRIVATE'});assert.equal(s.messages.length,2);
}
{
 const s=setup(),receiver={};const text='%cNew Ruffle instance created (Version: original | WebAssembly extensions: ON | Used renderer: wgpu-webgl)';assert.equal(s.c.console.log.call(receiver,text,'background: #37528C; color: #FFAD33'),17);assert.equal(s.logs[0].receiver,receiver);assert.equal(s.logs[0].args[0],text);assert.equal(s.messages.at(-1).flavor,'extensions');s.c.console.log('private arbitrary payload');s.c.console.log(text,'wrong style');assert.equal(s.messages.length,2);
 for(const backend of ['webgpu','webgl','canvas'])s.c.console.log(text.replace('wgpu-webgl',backend),'background: #37528C; color: #FFAD33');assert.equal(s.messages.length,5);
}
{
 const s=setup();for(let i=0;i<200;i++)s.c.FlashNestStartupJournal.record('context-state',{state:'running'});assert.equal(s.messages.length,96);assert.equal(s.messages.at(-1).sequence,96);
}
{
 const s=setup();s.c.FlashNestStartupJournal.dispose();assert.equal(s.c.fetch,s.fetch);assert.equal(s.c.console.log,s.log);const n=s.messages.length;s.c.FlashNestStartupJournal.record('loadeddata');assert.equal(s.messages.length,n);
}
{
 const s=setup();s.c.webkit.messageHandlers.flashnestStartup.postMessage=()=>{throw new Error('handler unavailable')};assert.doesNotThrow(()=>s.c.FlashNestStartupJournal.record('loadeddata'));assert.equal(s.c.fetch('http://127.0.0.1:8000/token/web/runtime/a.wasm'),s.promise);
}
console.log('PASS 7 passive startup journal mock groups; not native startup evidence');
