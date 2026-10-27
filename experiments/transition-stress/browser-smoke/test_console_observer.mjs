// Pure console mocks: no browser, runtime, WASM, SWF, WebAudio, or network.
import assert from 'node:assert/strict';
import {installConsoleObserver} from './console-observer.mjs';

let cases=0;
function check(name,fn){fn();cases++;console.log('PASS '+name)}
function environment(){
  const calls=[],result=Symbol('native-result'),target={};
  for(const method of ['log','warn','error'])Object.defineProperty(target,method,{value:function(...args){calls.push({method,receiver:this,args});if(this?.nativeFailure)throw this.nativeFailure;return result},writable:true,configurable:true,enumerable:method!=='warn'});
  const descriptors=Object.getOwnPropertyDescriptors(target),errors=[],warnings=[],texts=[];
  const callbacks={reportError:(message,method)=>errors.push({message,method}),reportWarning:(message,method)=>warnings.push({message,method}),onText:(message,method)=>texts.push({message,method})};
  function restored(){assert.deepEqual(Object.getOwnPropertyDescriptors(target),descriptors)}
  return {target,calls,result,errors,warnings,texts,callbacks,restored};
}
const styled=(level,message='web/src/lib.rs:123%c Unable to create audio backend. No audio will be played.')=>[`%c${level}%c ${message}`,`color: ${level==='WARN'?'orange':'red'}; background: #444`,'color: gray; font-style: italic','color: inherit'];

check('exact pinned styled ERROR/WARN log signatures produce stripped diagnostics',()=>{
 const e=environment(),o=installConsoleObserver(e.target,e.callbacks);
 try {
  const errorArgs=styled('ERROR'),warnArgs=styled('WARN','web/src/audio.rs:7%c Recoverable warning');
  assert.strictEqual(e.target.log(...errorArgs),e.result);e.target.log(...warnArgs);
  assert.deepEqual(e.errors,[{message:'web/src/lib.rs:123  Unable to create audio backend. No audio will be played.',method:'log'}]);
  assert.deepEqual(e.warnings,[{message:'web/src/audio.rs:7  Recoverable warning',method:'log'}]);
  assert.deepEqual(e.calls[0].args,errorArgs);assert.deepEqual(e.calls[1].args,warnArgs);
  assert.deepEqual(e.texts,[{message:errorArgs[0],method:'log'},{message:warnArgs[0],method:'log'}]);
 }finally{o.restore();e.restored()}
});

check('INFO/DEBUG/plain logs and malformed styled signatures are not errors or warnings',()=>{
 const e=environment(),o=installConsoleObserver(e.target,e.callbacks);
 try {
  const valid=styled('ERROR');
  const invalid=[styled('INFO'),styled('DEBUG'),['Unable to create audio backend. No audio will be played.'],
   valid.slice(0,3),[...valid,'fifth'],['prefix '+valid[0],...valid.slice(1)],
   [valid[0],valid[1]+' ',valid[2],valid[3]],[valid[0],valid[1],valid[2]+' ',valid[3]],
   [valid[0],valid[1],valid[2],valid[3]+' '],styled('WARN').map((v,i)=>i===1?valid[1]:v),
   [valid[0].replace('%cERROR%c ','%cERROR%c'),...valid.slice(1)]];
  for(const args of invalid)e.target.log(...args);
  assert.deepEqual(e.errors,[]);assert.deepEqual(e.warnings,[]);assert.equal(e.texts.length,invalid.length);
 }finally{o.restore();e.restored()}
});

check('native warn/error and renderer banner use only first string, never inspect objects',()=>{
 const e=environment(),o=installConsoleObserver(e.target,e.callbacks);let inspections=0;
 const hostile=new Proxy({},{get(){inspections++;throw Error('logged object inspected')}});
 try {
  const banner='New Ruffle instance created (WebAssembly extensions: ON, Used renderer: wgpu-webgl)';
  e.target.log(banner,hostile);e.target.warn('warning',hostile);e.target.error('error',hostile);
  e.target.log(hostile,'later string');e.target.warn(hostile,'later string');e.target.error(hostile,'later string');
  const args=styled('ERROR');args[1]=hostile;e.target.log(...args);
  assert.equal(inspections,0);assert.deepEqual(e.errors,[{message:'error',method:'error'}]);assert.deepEqual(e.warnings,[{message:'warning',method:'warn'}]);
  assert.deepEqual(e.texts.map(x=>x.message),[banner,'warning','error',args[0]]);
  assert.strictEqual(e.calls[0].args[1],hostile);assert.strictEqual(e.calls[3].args[0],hostile);
 }finally{o.restore();e.restored()}
});

check('logger receiver, arguments, return value and original thrown error are preserved',()=>{
 const e=environment(),o=installConsoleObserver(e.target,e.callbacks),receiver={};
 try {
  const arg={opaque:true};assert.strictEqual(Reflect.apply(e.target.error,receiver,['message',arg]),e.result);
  assert.strictEqual(e.calls[0].receiver,receiver);assert.strictEqual(e.calls[0].args[1],arg);
  const nativeFailure=new Error('native logger threw'),badReceiver={nativeFailure};
  assert.throws(()=>Reflect.apply(e.target.error,badReceiver,['not reported']),x=>x===nativeFailure);
  assert.deepEqual(e.errors,[{message:'message',method:'error'}]);assert.equal(e.texts.length,1);
 }finally{o.restore();e.restored()}
});

check('callback failures and nested console calls never alter native logger behavior',()=>{
 const e=environment();let reports=0,texts=0;
 const o=installConsoleObserver(e.target,{reportError(){reports++;e.target.warn('nested warning');throw Error('report failed')},reportWarning(){throw Error('nested report must not run')},onText(){texts++;throw Error('onText failed')}});
 try {
  assert.strictEqual(e.target.error('outer'),e.result);assert.equal(reports,1);assert.equal(texts,1);
  assert.deepEqual(e.calls.map(x=>[x.method,x.args[0]]),[['error','outer'],['warn','nested warning']]);
  assert.strictEqual(e.target.error('next'),e.result);assert.equal(reports,2);assert.equal(texts,2);
 }finally{o.restore();e.restored()}
});

check('restore preserves exact own descriptors and deletes temporary inherited hooks',()=>{
 const e=environment(),o=installConsoleObserver(e.target,e.callbacks);o.restore();o.restore();e.restored();
 const inherited=Object.create(e.target),p=installConsoleObserver(inherited,e.callbacks);
 assert.equal(Object.keys(inherited).length,3);p.restore();assert.deepEqual(Reflect.ownKeys(inherited),[]);
 assert.strictEqual(inherited.log,e.target.log);
});

check('partial install failures roll back previously installed hooks',()=>{
 const e=environment();Object.defineProperty(e.target,'warn',{writable:false,configurable:false});
 const descriptors=Object.getOwnPropertyDescriptors(e.target);
 assert.throws(()=>installConsoleObserver(e.target,e.callbacks),TypeError);
 assert.deepEqual(Object.getOwnPropertyDescriptors(e.target),descriptors);
 const incomplete={log(){}};const initial=Object.getOwnPropertyDescriptors(incomplete);
 assert.throws(()=>installConsoleObserver(incomplete,e.callbacks),/Required console method unavailable/);
 assert.deepEqual(Object.getOwnPropertyDescriptors(incomplete),initial);
});

check('restore detects an overwritten hook instead of silently replacing another owner',()=>{
 const e=environment(),o=installConsoleObserver(e.target,e.callbacks),wrapper=e.target.warn,replacement=()=>{};
 e.target.warn=replacement;assert.throws(()=>o.restore(),/Console observer hook replaced: warn/);assert.strictEqual(e.target.warn,replacement);
 e.target.warn=wrapper;o.restore();e.restored();
});

console.log(`PASS ${cases} console observer mock groups; no runtime or browser execution`);
