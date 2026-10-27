import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync(new URL('./renderer-observer.js', import.meta.url), 'utf8');
let passed=0;
function test(name, fn) { fn(); passed++; console.log('PASS '+name); }
function setup({failInstall=false}={}) {
 const calls=[], outputs=[];
 const logResult={native:true};
 const consoleObject={log:function(...args){calls.push({kind:'log',receiver:this,args});if(args[0]==='throw')throw logResult;return logResult;}};
 class Canvas {
  constructor(context={drawingBufferWidth:1329,drawingBufferHeight:861,isContextLost(){return false}}){this.context=context;this.width=1329;this.height=861;this.listeners=[];}
  getContext(...args){calls.push({kind:'context',receiver:this,args});if(args[0]==='throw')throw logResult;return this.context;}
  addEventListener(name,fn){this.listeners.push({name,fn});}
 }
 const originalLog=Object.getOwnPropertyDescriptor(consoleObject,'log'), originalContext=Object.getOwnPropertyDescriptor(Canvas.prototype,'getContext');
 const document={body:{appendChild(value){outputs.push(value);}},getElementById(id){return outputs.find(x=>x.id===id)||null;},createElement(){return{style:{},remove(){outputs.splice(outputs.indexOf(this),1);}};}};
 const window={console:consoleObject,HTMLCanvasElement:Canvas,document,devicePixelRatio:3};
 if(failInstall)Object.defineProperty(Canvas.prototype,'getContext',{...originalContext,writable:false,configurable:false});
 const context=vm.createContext({window});
 const install=()=>vm.runInContext(source,context);
 if(!failInstall)install();
 return{window,Canvas,calls,outputs,logResult,originalLog,originalContext,install,api:window.FlashNestRendererDiagnostic};
}
const plain=x=>JSON.parse(JSON.stringify(x));
const player=c=>({shadowRoot:{querySelector(selector){assert.equal(selector,'canvas');return c;}}});
const banner=backend=>`New Ruffle instance created (WebAssembly extensions: ON, Used renderer: ${backend})`;
test('initial exact bounded schema is unknown, not requested renderer',()=>{
 const f=setup();assert.deepEqual(plain(f.api.snapshot()),{backend:'unknown',context:'unknown',lost:null,width:null,height:null,nativeDPR:0,lossEvents:0,bannerCount:0});
 assert(f.outputs[0].textContent.startsWith('FLASHNEST_RENDERER '));assert(f.outputs[0].style.cssText.includes('pointer-events:none'));
});
test('native console receiver, args, return and thrown identity unchanged',()=>{
 const f=setup(),receiver={x:1},a={};assert.equal(f.window.console.log.call(receiver,banner('webgl'),a),f.logResult);assert.equal(f.calls[0].receiver,receiver);assert.equal(f.calls[0].args[1],a);
 assert.throws(()=>f.window.console.log('throw'),x=>x===f.logResult);assert.equal(f.api.snapshot().bannerCount,1);
});
test('only exact first-string renderer banner recognized; no object coercion',()=>{
 const f=setup();f.window.console.log({toString(){throw Error('coerced')}});f.window.console.log('other',banner('webgl'));f.window.console.log('Used renderer: webgl');assert.equal(f.api.snapshot().bannerCount,0);
 f.window.console.log(banner('wgpu-webgl'));assert.equal(f.api.snapshot().backend,'wgpu-webgl');
 f.window.console.log(banner('unexpected'));assert.equal(f.api.snapshot().backend,'unsupported');
});
test('getContext native argument identity/return/throw preserved; no sampling allocation',()=>{
 const f=setup(),c=new f.Canvas(),options={alpha:false};assert.equal(c.getContext('webgl2',options),c.context);assert.equal(f.calls[0].receiver,c);assert.equal(f.calls[0].args[1],options);
 assert.throws(()=>c.getContext('throw'),x=>x===f.logResult);const count=f.calls.length;
 const s=f.api.sample(player(c));assert.equal(f.calls.length,count);assert.deepEqual(plain(s),{backend:'unknown',context:'webgl2',lost:false,width:1329,height:861,nativeDPR:3,lossEvents:0,bannerCount:0});
});
test('null/unknown/unobserved contexts never appear ready',()=>{
 const f=setup(),c=new f.Canvas(null);c.getContext('webgl2');assert.equal(f.api.sample(player(c)).context,'unknown');
 c.context={};c.getContext('invented');assert.equal(f.api.sample(player(c)).context,'unknown');
 const neverObserved=new f.Canvas();assert.equal(f.api.sample(player(neverObserved)).context,'unknown');
});
test('WebGL1 aliases and Canvas preserve actual context kind',()=>{
 for(const kind of ['webgl','experimental-webgl','2d']){const f=setup(),c=new f.Canvas(kind==='2d'?{}:undefined);c.getContext(kind);const s=f.api.sample(player(c));assert.equal(s.context,kind);assert.equal(s.width,1329);assert.equal(s.lost,kind==='2d'?null:false);}
});
test('lost event counts without preventDefault; actual lost/zero buffer is retained',()=>{
 const f=setup(),c=new f.Canvas();c.getContext('webgl2');c.getContext('webgl2');assert.equal(c.listeners.length,1);
 c.listeners[0].fn({preventDefault(){throw Error('must not cancel')}});assert.equal(f.api.snapshot().lossEvents,1);assert.equal(f.api.snapshot().lost,true);
 c.context.isContextLost=()=>true;c.context.drawingBufferWidth=0;c.context.drawingBufferHeight=0;const s=f.api.sample(player(c));assert.equal(s.lost,true);assert.equal(s.width,0);assert.equal(s.height,0);
});
test('malformed metrics and observation exceptions fail closed without throwing into caller',()=>{
 const f=setup(),c=new f.Canvas();c.getContext('webgl2');c.context.drawingBufferWidth=NaN;c.context.drawingBufferHeight=-1;c.context.isContextLost=()=>undefined;f.window.devicePixelRatio=Infinity;
 const s=f.api.sample(player(c));assert.equal(s.width,null);assert.equal(s.height,null);assert.equal(s.lost,null);assert.equal(s.nativeDPR,0);
 c.context.isContextLost=()=>{throw Error('lost getter')};assert.equal(f.api.sample(player(c)).context,'unavailable');
});
test('snapshot copies cannot forge observer state',()=>{const f=setup(),s=f.api.snapshot();s.backend='webgl';assert.equal(f.api.snapshot().backend,'unknown');});
test('disposal restores exact descriptors; late events inert and repeated dispose safe',()=>{
 const f=setup(),c=new f.Canvas();c.getContext('webgl2');const fn=c.listeners[0].fn;f.api.dispose();assert.deepEqual(Object.getOwnPropertyDescriptor(f.window.console,'log'),f.originalLog);assert.deepEqual(Object.getOwnPropertyDescriptor(f.Canvas.prototype,'getContext'),f.originalContext);assert.equal(f.window.FlashNestRendererDiagnostic,undefined);assert.equal(f.outputs.length,0);fn({});assert.equal(f.api.snapshot().lossEvents,0);f.api.dispose();assert.throws(()=>f.api.sample(player(c)),/disposed/);
});
test('partial installation rolls back console and double install refuses',()=>{const f=setup({failInstall:true});assert.throws(f.install);assert.deepEqual(Object.getOwnPropertyDescriptor(f.window.console,'log'),f.originalLog);const g=setup();assert.throws(g.install,/already installed/);});
test('foreign hook replacement is not silently overwritten',()=>{const f=setup();f.window.console.log=()=>{};assert.throws(f.api.dispose,/replaced/);});
test('banner count is bounded and overflow cannot appear as supported backend',()=>{const f=setup();for(let i=0;i<65;i++)f.window.console.log(banner('webgl'));assert.equal(f.api.snapshot().backend,'overflow');});
test('static source has no timer, context acquisition, event cancellation or renderer setting',()=>{
 assert(!/setTimeout|setInterval|requestAnimationFrame|preventDefault\s*\(|\.getContext\s*\(|preferredRenderer\s*:/.test(source));
 assert(source.includes('new WeakMap()'));assert(source.includes('new WeakSet()'));
});
console.log(`PASS ${passed} renderer observer mock groups; no native/browser execution`);
