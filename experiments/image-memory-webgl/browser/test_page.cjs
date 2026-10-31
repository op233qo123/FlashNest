const assert=require('assert/strict'),fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const code=fs.readFileSync(__dirname+'/page.html','utf8').split('<script>')[1].split('</script>')[0];
class GL{texImage2D(...args){this.last=args;return 17}texSubImage2D(){return 18}drawElements(){return 19}drawArrays(){return 20}getExtension(){return null}}
class Canvas{getContext(){return this.gl}addEventListener(name,fn){this[name]=fn}}
const gl=new GL(),canvas=new Canvas();canvas.gl=gl;
const memory=new WebAssembly.Memory({initial:1});let instantiated=0;
const wasm={Memory:WebAssembly.Memory,instantiate:async()=>{instantiated++;return {instance:{exports:{memory}}}},instantiateStreaming:async()=>({instance:{exports:{memory}}})};
const c={URLSearchParams,location:{search:'?arm=baseline'},HTMLCanvasElement:Canvas,WebGLRenderingContext:GL,WebGL2RenderingContext:class extends GL{},WebAssembly:wasm,crypto:crypto.webcrypto,performance,document:{addEventListener(){},createElement(){return {}},head:{append(){}},getElementById(){return {}}},console};c.window=c;c.addEventListener=()=>{};vm.runInNewContext(code,c);
(async()=>{
 assert.equal(canvas.getContext('webgl'),gl);const bytes=new Uint8Array(64*64*4).map((_,i)=>i%251);
 assert.equal(gl.drawElements(1,2,3,4),19);assert.equal(c.targetFrameObserved(64,64),false);
 assert.equal(gl.texImage2D(1,0,2,64,64,0,3,4,bytes),17);assert.equal(gl.last[8],bytes);assert.equal(c.targetFrameObserved(64,64),false);assert.equal(gl.drawElements(1,2,3,4),19);assert.equal(c.targetFrameObserved(64,64),true);assert.equal(c.targetFrameObserved(512,512),false);
 await c.WebAssembly.instantiate(new Uint8Array());assert.equal(instantiated,1);
 let s=await c.snapshot();assert.equal(s.memories[0].bytes,65536);assert.equal(s.uploadHashes[0].sha256,crypto.createHash('sha256').update(bytes).digest('hex'));assert.equal(s.uploadHashes[0].bytes,bytes.byteLength);
 const backing=new Uint8Array(bytes.length+97).fill(255);const offsetView=backing.subarray(37,37+bytes.length);offsetView.set(bytes);assert.equal(offsetView.byteOffset,37);
 assert.equal(gl.texImage2D(1,0,2,64,64,0,3,4,offsetView),17);s=await c.snapshot();assert.equal(s.uploadHashes[1].sha256,crypto.createHash('sha256').update(offsetView).digest('hex'));assert.notEqual(s.uploadHashes[1].sha256,crypto.createHash('sha256').update(backing).digest('hex'));
 memory.grow(1);s=await c.snapshot();assert.equal(s.memories[0].bytes,131072);
 let prevented=false;canvas.webglcontextlost({preventDefault(){prevented=true}});canvas.webglcontextrestored();s=await c.snapshot();assert.equal(prevented,false);assert.equal(s.contextEvents.map(x=>x.type).join(','),'lost,restored');assert.equal(s.errors.length,0);
 let observer;const api={set traceObserver(fn){observer=fn},async load(){c.console.log('New Ruffle instance created (Version: test | Used renderer: webgl)');assert.equal(typeof observer,'function');observer('EARLY_CONSTRUCTOR_TRACE')},resume(){}};
 const player={ruffle(){return api},focus(){}};c.RufflePlayer={newest(){return {createPlayer(){return player}}}};c.document.getElementById=()=>({append(){}});
 await c.start('fixture.swf');s=await c.snapshot();assert.equal(s.instanceTraceAttachments,1);assert.ok(s.traces.includes('EARLY_CONSTRUCTOR_TRACE'));assert.ok(s.timings.loadResolved>=s.timings.start);
 for(let i=0;i<40;i++){assert.equal(gl.texImage2D(1,0,2,64,64,0,3,4,offsetView),17);assert.equal(gl.last[8],offsetView)}s=await c.snapshot();assert.equal(s.uploadHashes.length,32);assert.equal(s.overflow,true);
 console.log('PASS nonzero view offset, bounded hashes, preserved WebGL args/returns, full upload hash, actual exported WASM memory/grow observation, context events, early trace and load timing');
})().catch(e=>{console.error(e);process.exitCode=1});
