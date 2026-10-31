'use strict';
const assert = require('node:assert/strict');
const modulePath = process.env.LONG_RUN_MODULE || require('node:path').join(__dirname,'../app/App/Resources/Web/long-run-diagnostics.js');
const { install } = require(modulePath);
const v2Counters = ['texImage2DNullishRequests','texImage2DViewRequests','texImage2DOtherRequests',
 'framebufferCreateRequests','framebufferDeleteRequests','framebufferTexture2DRequests',
 'renderbufferCreateRequests','renderbufferDeleteRequests','renderbufferStorageRequests','renderbufferStorageMultisampleRequests'];
const config = {session:'00000000-0000-4000-8000-000000000001',epoch:1};
function environment() {
  let now = 100, interval = null, clears = 0, sends = [], timerMS = null;
  class GL {
    createTexture() { return {}; }
    deleteTexture(t) { return 'deleted'; }
    texImage2D(...args) { return args.length; }
    texSubImage2D() { return 7; }
    texStorage2D() { return 8; }
    compressedTexImage2D() { return 9; }
    createFramebuffer() { return null; }
    deleteFramebuffer() { return 'deleteFramebuffer'; }
    framebufferTexture2D() { return 'framebufferTexture2D'; }
    createRenderbuffer() { return null; }
    deleteRenderbuffer() { return 'deleteRenderbuffer'; }
    renderbufferStorage() { return 'renderbufferStorage'; }
    renderbufferStorageMultisample() { return 'renderbufferStorageMultisample'; }
    drawArrays() { return 'draw'; }
    drawElements() { return 'drawElements'; }
  }
  class GL2 extends GL { drawArraysInstanced() { return 2; } }
  class Canvas {
    constructor(gl = new GL()) { this.gl = gl; this.events = new Map(); }
    getContext() { return this.gl; }
    addEventListener(name, fn) { let s = this.events.get(name); if (!s) this.events.set(name, s = new Set()); s.add(fn); }
    removeEventListener(name, fn) { this.events.get(name)?.delete(fn); }
    emit(name) { const event = {preventDefault() { throw Error('must not prevent default'); }}; for (const fn of this.events.get(name) || []) fn(event); }
  }
  const env = {WebGLRenderingContext:GL,WebGL2RenderingContext:GL2,HTMLCanvasElement:Canvas,WeakRef,
    performance:{now:()=>now},setInterval(fn, ms) { interval = fn; timerMS = ms; return 99; },
    clearInterval(id) { assert.equal(id,99); ++clears; interval=null; },
    webkit:{messageHandlers:{flashnest:{postMessage(body) { sends.push(body); }}}}};
  return {env, GL, GL2, Canvas, sends, latest:()=>sends.at(-1), tick(ms=10000) {now+=ms;interval?.();},
    clearCount:()=>clears, intervalMS:()=>timerMS};
}
let count=0;
function test(name, fn) {fn(); ++count; console.log('PASS',name);}
test('default off leaves methods and timers untouched',()=>{
 const e=environment(), old=e.GL.prototype.createTexture;
 assert.equal(install(e.env,undefined),null);assert.equal(old,e.GL.prototype.createTexture);
 assert.equal(e.intervalMS(),null);assert.equal(e.sends.length,0);
});
test('invalid config and missing native bridge inert',()=>{
 for(const c of [{...config,epoch:0},{...config,epoch:1.2},{...config,session:'private/url'},{}]) {
  const e=environment();assert.equal(install(e.env,c),null);assert.equal(e.sends.length,0);
 }
 const e=environment();delete e.env.webkit;assert.equal(install(e.env,config),null);
});
test('strict schema and no WASM/Promise interception',()=>{
 const e=environment();const wasm={instantiate:()=>{}};e.env.WebAssembly=wasm;const before=wasm.instantiate;
 const o=install(e.env,config);assert.equal(before,wasm.instantiate);assert.equal(e.intervalMS(),10000);
 assert.deepEqual(Object.keys(e.latest()).sort(),['type','schema','session','wkEpoch','seq','webElapsedMs','contexts','contextLost','contextRestored','texturesCreated','texturesDeleted','textureUploads','textureBytesEstimate','unknownUploads','drawCalls','hookFailures','sendFailures','overflow',...v2Counters].sort());
 assert.equal(e.latest().schema,2);for(const name of v2Counters)assert.equal(e.latest()[name],0);
 assert.equal(e.latest().seq,1);assert.equal(e.latest().contexts,0);assert.equal(e.latest().wasmBytes,undefined);o.stop();
});
test('native session envelope snapshot',()=>{
 const e=environment();install(e.env,config);e.tick();assert.equal(e.latest().session,config.session);assert.equal(e.latest().wkEpoch,1);assert.equal(e.latest().seq,2);assert.equal(e.latest().webElapsedMs,10000);
});
test('create/unique delete and normal return semantics',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');const t=gl.createTexture();
 assert.equal(gl.deleteTexture(t),'deleted');gl.deleteTexture(t);gl.deleteTexture(null);gl.deleteTexture({});e.tick();
 assert.equal(e.latest().texturesCreated,1);assert.equal(e.latest().texturesDeleted,1);
});
test('cross context delete not credited',()=>{
 const e=environment();install(e.env,config);const a=new e.Canvas().getContext('webgl'),b=new e.Canvas().getContext('webgl');const t=a.createTexture();b.deleteTexture(t);e.tick();assert.equal(e.latest().texturesDeleted,0);a.deleteTexture(t);e.tick();assert.equal(e.latest().texturesDeleted,1);
});
test('scalar RGBA8 request estimates and unknown overloads',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');const source=new Proxy({}, {get(){throw Error('source inspected');}});
 assert.equal(gl.texImage2D(3553,0,6408,512,512,0,6408,5121,source),9);
 gl.texSubImage2D(3553,0,0,0,2,4,6408,5121,source);
 gl.texStorage2D(3553,1,32856,4,8);
 gl.texImage2D(3553,0,6408,6408,5121,source);
 gl.texImage2D(3553,1,6408,512,512,0,6408,5121,null);
 gl.compressedTexImage2D(3553,0,1,512,512,0,source);
 e.tick();assert.equal(e.latest().textureUploads,6);assert.equal(e.latest().textureBytesEstimate,1048576+32+128);assert.equal(e.latest().unknownUploads,3);
});
test('inherited WebGL2 methods counted once and draw counted',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas(new e.GL2()).getContext('webgl2');gl.createTexture();gl.drawArrays();gl.drawArraysInstanced();e.tick();assert.equal(e.latest().texturesCreated,1);assert.equal(e.latest().drawCalls,2);
});
test('original exception exact identity and receiver/args retained',()=>{
 const e=environment(), error=new Error('original'), arg={};let receiver,args;
 e.GL.prototype.texImage2D=function(...a){receiver=this;args=a;throw error;};install(e.env,config);const gl=new e.Canvas().getContext('webgl');
 assert.throws(()=>gl.texImage2D(arg), x=>x===error);assert.equal(receiver,gl);assert.equal(args[0],arg);e.tick();assert.equal(e.latest().textureUploads,0);
});
test('observer exception cannot change original result',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');const obj={};assert.equal(gl.texImage2D(3553,0,6408,obj,8,0,6408,5121,null),9);e.tick();assert.equal(e.latest().unknownUploads,1);
});
test('context events do not prevent default or auto recover',()=>{
 const e=environment();install(e.env,config);const c=new e.Canvas();c.getContext('webgl');c.getContext('webgl');c.emit('webglcontextlost');c.emit('webglcontextrestored');e.tick();assert.equal(e.latest().contextLost,1);assert.equal(e.latest().contextRestored,1);assert.equal(c.events.get('webglcontextlost').size,1);
});
test('four-context cap marks overflow without retaining unbounded scalar states',()=>{
 const e=environment();install(e.env,config);for(let n=0;n<8;n++)new e.Canvas().getContext('webgl').createTexture();e.tick();assert.equal(e.latest().contexts,4);assert.equal(e.latest().texturesCreated,4);assert.equal(e.latest().overflow,true);
});
test('send failures do not stop timer and next sample reports count/gap',()=>{
 const e=environment();let fail=true; e.env.webkit.messageHandlers.flashnest.postMessage=function(b){if(fail)throw Error('bridge');e.sends.push(b);};
 install(e.env,config);fail=false;e.tick();assert.equal(e.latest().seq,2);assert.equal(e.latest().sendFailures,1);
});
test('readonly prototypes are reported but cannot stop initialization',()=>{
 const e=environment();Object.defineProperty(e.GL.prototype,'createTexture',{value:e.GL.prototype.createTexture,writable:false});const o=install(e.env,config);assert.ok(o);assert.ok(e.latest().hookFailures>=1);assert.equal(e.latest().overflow,true);o.stop();
});
test('stop cancels timers restores descriptors and removes listeners',()=>{
 const e=environment(), old=e.GL.prototype.createTexture,oldGet=e.Canvas.prototype.getContext;const o=install(e.env,config),c=new e.Canvas();c.getContext('webgl');const size=e.sends.length;assert.equal(o.isActive(),true);o.stop();assert.equal(o.isActive(),false);o.stop();e.tick();c.emit('webglcontextlost');assert.equal(e.sends.length,size);assert.equal(e.clearCount(),1);assert.equal(e.GL.prototype.createTexture,old);assert.equal(e.Canvas.prototype.getContext,oldGet);assert.equal(c.events.get('webglcontextlost').size,0);assert.equal(Object.hasOwn(e.GL2.prototype,'createTexture'),false);
});
test('stop does not overwrite a later owner wrapper',()=>{
 const e=environment();const o=install(e.env,config),later=()=>42;e.GL.prototype.createTexture=later;o.stop();assert.equal(e.GL.prototype.createTexture,later);
});
test('long run retains reporting beyond old event cap',()=>{
 const e=environment();install(e.env,config);for(let n=0;n<1000;n++)e.tick();assert.equal(e.latest().seq,1001);assert.equal(e.latest().webElapsedMs,10000000);
});
test('metadata cap preserves ongoing counters and flags incomplete unique deletion',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');let last;
 for(let n=0;n<16385;n++)last=gl.createTexture();gl.deleteTexture(last);gl.drawArrays();e.tick();
 assert.equal(e.latest().texturesCreated,16385);assert.equal(e.latest().texturesDeleted,0);assert.equal(e.latest().drawCalls,1);assert.equal(e.latest().overflow,true);
});
test('config is copied and cannot alter native identity after installation',()=>{
 const e=environment(),c={...config};install(e.env,c);c.session='changed';c.epoch=42;e.tick();assert.equal(e.latest().session,config.session);assert.equal(e.latest().wkEpoch,1);
});
test('setup failure after partial hooks rolls back originals',()=>{
 const e=environment(),old=e.GL.prototype.createTexture;
 Object.defineProperty(e.env,'HTMLCanvasElement',{get(){throw Error('setup');}});
 assert.equal(install(e.env,config),null);assert.equal(e.GL.prototype.createTexture,old);assert.equal(e.intervalMS(),null);
});
test('timer setup failure rolls back prototypes',()=>{
 const e=environment(),old=e.GL.prototype.createTexture;e.env.setInterval=()=>{throw Error('timer');};
 assert.equal(install(e.env,config),null);assert.equal(e.GL.prototype.createTexture,old);assert.equal(e.sends.length,0);
});
test('no WeakRef still attaches no strong cleanup references and stop disables callback',()=>{
 const e=environment();delete e.env.WeakRef;const o=install(e.env,config),c=new e.Canvas();c.getContext('webgl');o.stop();c.emit('webglcontextlost');assert.equal(e.sends.length,1);
});
test('browser bootstrap config and duplicate script install are bounded',()=>{
 const vm=require('node:vm'),source=require('node:fs').readFileSync(modulePath,'utf8');
 const e=environment();e.env.__FlashNestLongRunConfig={...config};const ctx=vm.createContext({window:e.env});vm.runInContext(source,ctx);assert.ok(e.env.__FlashNestLongRunObserver);assert.equal(e.env.__FlashNestLongRunObserver.isActive(),true);const original=e.GL.prototype.createTexture;vm.runInContext(source,ctx);assert.equal(e.GL.prototype.createTexture,original);assert.equal(e.sends.length,1);e.env.__FlashNestLongRunObserver.stop();assert.equal(e.env.__FlashNestLongRunObserver.isActive(),false);
});
test('browser bootstrap default off and failure to expose stop handle rolls back',()=>{
 const vm=require('node:vm'),source=require('node:fs').readFileSync(modulePath,'utf8');
 const e=environment(),old=e.GL.prototype.createTexture;vm.runInNewContext(source,{window:e.env});assert.equal(e.GL.prototype.createTexture,old);assert.equal(e.sends.length,0);
 e.env.__FlashNestLongRunConfig={...config};Object.preventExtensions(e.env);vm.runInNewContext(source,{window:e.env});assert.equal(e.GL.prototype.createTexture,old);assert.equal(e.clearCount(),1);
});
test('v2 numeric texImage2D overloads separate null undefined and views',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');
 for(const source of [null,undefined,new Uint8Array(4),new DataView(new ArrayBuffer(4))]) {
  for(const suffix of [[],[0]]) gl.texImage2D(3553,0,6408,1,1,0,6408,5121,source,...suffix);
 }
 e.tick();assert.equal(e.latest().texImage2DNullishRequests,4);assert.equal(e.latest().texImage2DViewRequests,4);
 assert.equal(e.latest().texImage2DOtherRequests,0);assert.equal(e.latest().textureUploads,8);
});
test('v2 offsets DOM overloads unsupported dimensions and arity remain other',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');
 gl.texImage2D(3553,0,6408,1,1,0,6408,5121,0);
 gl.texImage2D(3553,0,6408,6408,5121,null);
 gl.texImage2D(3553,0,6408,'1',1,0,6408,5121,null);
 gl.texImage2D(3553,0,6408,1,1,0,6408,5121,null,0,0);
 gl.texImage2D(3553,0,6408,1,1,0,6408,5121);
 gl.texSubImage2D(3553,0,0,0,1,1,6408,5121,null);
 e.tick();assert.equal(e.latest().texImage2DOtherRequests,5);assert.equal(e.latest().texImage2DNullishRequests,0);
 assert.equal(e.latest().texImage2DViewRequests,0);assert.equal(e.latest().textureUploads,6);
});
test('v2 classification never accesses source pixels properties or byteLength',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');let reads=0;
 const source=new Proxy({}, {get(){reads++;throw Error('private source property');}});
 const revoked=Proxy.revocable({},{});revoked.revoke();
 const view=new Uint8Array(1);Object.defineProperty(view,'byteLength',{get(){reads++;throw Error('byteLength');}});
 const crossRealm=require('node:vm').runInNewContext('new Uint8Array(1)');
 for(const item of [source,revoked.proxy,view,crossRealm])gl.texImage2D(3553,0,6408,1,1,0,6408,5121,item);
 e.tick();assert.equal(reads,0);assert.equal(e.latest().texImage2DOtherRequests,2);assert.equal(e.latest().texImage2DViewRequests,2);assert.equal(e.latest().hookFailures,0);
});
test('v2 resource counters are requests even for null creates and repeated deletes',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');
 assert.equal(gl.createFramebuffer(),null);assert.equal(gl.createRenderbuffer(),null);
 assert.equal(gl.deleteFramebuffer(null),'deleteFramebuffer');gl.deleteFramebuffer(null);
 assert.equal(gl.deleteRenderbuffer(null),'deleteRenderbuffer');gl.deleteRenderbuffer(null);
 assert.equal(gl.framebufferTexture2D(1,2,3,null,0),'framebufferTexture2D');
 assert.equal(gl.renderbufferStorage(1,2,3,4),'renderbufferStorage');
 assert.equal(gl.renderbufferStorageMultisample(1,2,3,4,5),'renderbufferStorageMultisample');e.tick();
 for(const name of v2Counters.slice(3))assert.equal(e.latest()[name],name.includes('Delete')?2:1);
 assert.equal(e.latest().textureUploads,0);assert.equal(e.latest().texturesCreated,0);assert.equal(e.latest().textureBytesEstimate,0);
});
test('v2 new request wrappers preserve receiver args exact return and thrown identity',()=>{
 for(const name of ['createFramebuffer','deleteFramebuffer','framebufferTexture2D','createRenderbuffer','deleteRenderbuffer','renderbufferStorage','renderbufferStorageMultisample']) {
  const e=environment(), token={}, arg={}, err=new Error('original');let receiver,received,throws=false;
  e.GL.prototype[name]=function(...args){receiver=this;received=args;if(throws)throw err;return token;};
  install(e.env,config);const gl=new e.Canvas().getContext('webgl');assert.equal(gl[name](arg),token);assert.equal(receiver,gl);assert.equal(received[0],arg);
  throws=true;assert.throws(()=>gl[name](arg),error=>error===err);e.tick();
  assert.equal(v2Counters.slice(3).reduce((sum,key)=>sum+e.latest()[key],0),1);
 }
 const e=environment(),err={};e.GL.prototype.texImage2D=()=>{throw err;};install(e.env,config);const gl=new e.Canvas().getContext('webgl');
 assert.throws(()=>gl.texImage2D(3553,0,6408,1,1,0,6408,5121,null),error=>error===err);e.tick();assert.equal(e.latest().texImage2DNullishRequests,0);
});
test('v2 inherited resource methods count once and four-context cap applies',()=>{
 const e=environment();install(e.env,config);
 for(let i=0;i<5;i++){const gl=new e.Canvas(new e.GL2()).getContext('webgl2');gl.createFramebuffer();gl.createRenderbuffer();gl.texImage2D(3553,0,6408,1,1,0,6408,5121,null);}
 e.tick();assert.equal(e.latest().framebufferCreateRequests,4);assert.equal(e.latest().renderbufferCreateRequests,4);assert.equal(e.latest().texImage2DNullishRequests,4);assert.equal(e.latest().overflow,true);
});
test('v2 default off and stop restore every newly observed resource method',()=>{
 const e=environment(),names=['createFramebuffer','deleteFramebuffer','framebufferTexture2D','createRenderbuffer','deleteRenderbuffer','renderbufferStorage','renderbufferStorageMultisample'];
 const originals=names.map(name=>e.GL.prototype[name]);assert.equal(install(e.env,null),null);
 names.forEach((name,i)=>assert.equal(e.GL.prototype[name],originals[i]));
 const observer=install(e.env,config);observer.stop();
 names.forEach((name,i)=>{assert.equal(e.GL.prototype[name],originals[i]);assert.equal(Object.hasOwn(e.GL2.prototype,name),false);});
});
test('v2 new cumulative counters use existing saturating bound and overflow flag',()=>{
 const vm=require('node:vm'),fs=require('node:fs'),source=fs.readFileSync(modulePath,'utf8').replace('COUNT_MAX = 2147483647','COUNT_MAX = 3');
 const box={module:{exports:{}}};vm.runInNewContext(source,box);
 const e=environment();box.module.exports.install(e.env,config);const gl=new e.Canvas().getContext('webgl');
 for(let i=0;i<5;i++){gl.createFramebuffer();gl.renderbufferStorage(1,2,3,4);gl.texImage2D(3553,0,6408,1,1,0,6408,5121,null);}
 e.tick();assert.equal(e.latest().framebufferCreateRequests,3);assert.equal(e.latest().renderbufferStorageRequests,3);assert.equal(e.latest().texImage2DNullishRequests,3);assert.equal(e.latest().overflow,true);
});
test('v2 unavailable hooks are optional and readonly hooks report incomplete coverage',()=>{
 const e=environment();delete e.GL.prototype.renderbufferStorageMultisample;
 Object.defineProperty(e.GL.prototype,'createFramebuffer',{value:e.GL.prototype.createFramebuffer,writable:false});
 const observer=install(e.env,config);assert.ok(observer);const gl=new e.Canvas().getContext('webgl');gl.createFramebuffer();gl.createRenderbuffer();e.tick();
 assert.equal(e.latest().framebufferCreateRequests,0);assert.equal(e.latest().renderbufferCreateRequests,1);assert.equal(e.latest().renderbufferStorageMultisampleRequests,0);assert.ok(e.latest().hookFailures>=1);assert.equal(e.latest().overflow,true);observer.stop();
});

test('v2 malformed numeric overload fields and offsets classify other without coercion',()=>{
 const e=environment();install(e.env,config);const gl=new e.Canvas().getContext('webgl');let coercions=0;
 const hostile={valueOf(){coercions++;throw Error('coercion');}};
 const bad=[NaN,Infinity,-1,0.5,Number.MAX_SAFE_INTEGER+1,hostile];let calls=0;
 for(let position=0;position<8;position++)for(const value of bad){const a=[3553,0,6408,1,1,0,6408,5121,null];a[position]=value;gl.texImage2D(...a);calls++;}
 for(const offset of bad){gl.texImage2D(3553,0,6408,1,1,0,6408,5121,new Uint8Array(4),offset);calls++;}
 e.tick();assert.equal(coercions,0);assert.equal(e.latest().texImage2DOtherRequests,calls);assert.equal(e.latest().texImage2DNullishRequests,0);assert.equal(e.latest().texImage2DViewRequests,0);
});
console.log(JSON.stringify({passed:count,failed:0}));
