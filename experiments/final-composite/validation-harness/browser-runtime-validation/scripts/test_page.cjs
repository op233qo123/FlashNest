const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(require('node:path').join(__dirname,'../page.html'),'utf8');
const source=html.split('<script>')[1].split('</script>')[0];
let calls=[],loadConfig,host={style:{},append(){}},play={};
function GL(){this.canvas=null;this.drawingBufferWidth=111;this.drawingBufferHeight=72}
GL.prototype.renderbufferStorage=function(...args){calls.push(args);return 'single'};
function GL2(){};GL2.prototype=Object.create(GL.prototype);GL2.prototype.constructor=GL2;
GL2.prototype.renderbufferStorageMultisample=function(...args){calls.push(args);return 'multi'};
function Canvas(){this.context=new GL2();this.context.canvas=this}
Canvas.prototype.getContext=function(type){return this.context};
function GPU(){};GPU.prototype.getCurrentTexture=function(){return{width:111,height:72}};
function Device(){};Device.prototype.createTexture=function(...args){calls.push(args);return {sampleCount:4,width:111,height:72}};
let sandbox={URLSearchParams,WeakMap,Object,String,Number,Reflect,console:{log(){}},HTMLCanvasElement:Canvas,WebGLRenderingContext:GL,WebGL2RenderingContext:GL2,GPUCanvasContext:GPU,GPUDevice:Device,location:{search:'?runtime=candidate'},document:{head:{append(){}},createElement(){return{}},getElementById(id){return id==='host'?host:play},addEventListener(){}},devicePixelRatio:1};sandbox.window=sandbox;
vm.runInNewContext(source,sandbox);
const canvas=new Canvas();const gl=canvas.getContext('webgl2');
assert.equal(gl.renderbufferStorageMultisample(1,4,2,443,287),'multi');
assert.deepEqual(calls,[[1,4,2,443,287]]);
assert.equal(JSON.stringify(sandbox.contexts.get(canvas).storage),'[[4,443,287]]');
gl.renderbufferStorageMultisample(1,4,2,443,287);assert.equal(sandbox.contexts.get(canvas).storage.length,1);
const canvas2=new Canvas();canvas2.context=new GPU();canvas2.context.canvas=canvas2;const gpu=canvas2.getContext('webgpu');assert.equal(gpu.getCurrentTexture().width,111);assert.equal(JSON.stringify(sandbox.contexts.get(canvas2).texture),'[111,72]');
new Device().createTexture({size:[111,72],sampleCount:4});assert.equal(JSON.stringify(sandbox.gpuAllocations),'[[4,111,72]]');
const api={load:async config=>{loadConfig=config},resume(){}};sandbox.RufflePlayer.newest=()=>({createPlayer:()=>({ruffle:()=>api,addEventListener(){},remove(){}})});
(async()=>{
 await sandbox.startCase('/fixtures/showAll-center.swf',.25,443,287,'auto',null);
 assert.equal('quality' in loadConfig,false);assert.equal('preferredRenderer' in loadConfig,false);assert.equal(loadConfig.renderScale,.25);
 await sandbox.startCase('/fixtures/showAll-center.swf',.25,443,287,'webgl','high');
 assert.equal(loadConfig.quality,'high');assert.equal(loadConfig.preferredRenderer,'webgl');
 assert.equal(sandbox.allocationOverflow,false);
 console.log('PASS transparent allocator, dedup, WebGPU texture, omitted/default and explicit launch config (mocked only)');
})().catch(e=>{console.error(e);process.exitCode=1});
