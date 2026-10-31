'use strict';
const assert = require('node:assert/strict');
const modulePath = process.env.LONG_RUN_MODULE || require('node:path').join(__dirname,'long-run-diagnostics.js');
const { install } = require(modulePath);
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
 assert.deepEqual(Object.keys(e.latest()).sort(),['type','schema','session','wkEpoch','seq','webElapsedMs','contexts','contextLost','contextRestored','texturesCreated','texturesDeleted','textureUploads','textureBytesEstimate','unknownUploads','drawCalls','hookFailures','sendFailures','overflow'].sort());
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
console.log(JSON.stringify({passed:count,failed:0}));
