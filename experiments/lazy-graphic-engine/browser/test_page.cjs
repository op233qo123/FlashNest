const assert=require('assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/page.html','utf8'),code=html.split('<script>')[1].split('</script>')[0];
class GL {texImage2D(...args){this.last=args;return 17}texSubImage2D(){return 18}drawElements(){return 19}drawArrays(){return 20}}
class Canvas {getContext(){return this.gl}addEventListener(){}}
const gl=new GL(),canvas=new Canvas();canvas.gl=gl;
const context={URLSearchParams,location:{search:'?arm=baseline'},HTMLCanvasElement:Canvas,WebGLRenderingContext:GL,WebGL2RenderingContext:class extends GL{},document:{addEventListener(){},createElement(){return {}},head:{append(){}},getElementById(){return {}}},console};context.window=context;
context.addEventListener=()=>{};vm.runInNewContext(code,context);
assert.equal(canvas.getContext('webgl'),gl);assert.equal(gl.texImage2D(1,0,2,16,16,0,3,4,null),17);
assert.equal(gl.last.length,9);assert.equal(context.evidence.contexts.length,1);assert.equal(context.evidence.calls.length,1);assert.equal(context.evidence.calls[0].width,16);assert.equal(context.evidence.calls[0].height,16);
assert.equal(gl.drawElements(1,2,3,4),19);assert.equal(context.evidence.calls[1].name,'drawElements');
assert.equal(context.evidence.calls[1].width,null);console.log('PASS wrapper preservesreturn/args, observesactualcontext, scalarcounts');

// The accepted setter ignores writes before instance creation. Install from the
// pinned renderer-created log so constructor traces before load() resolves survive.
let observer=null;const api={set traceObserver(fn){observer=fn},async load(){
 context.console.log('New Ruffle instance created (Version: test | Used renderer: webgl)');
 assert.equal(typeof observer,'function');observer('EARLY_CONSTRUCTOR_TRACE');
},resume(){}};
const player={ruffle(){return api},focus(){}};context.RufflePlayer={newest(){return {createPlayer(){return player}}}};
context.document.getElementById=()=>({append(){}});
context.start('fixture.swf').then(()=>{assert.ok(context.evidence.traces.includes('EARLY_CONSTRUCTOR_TRACE'));assert.equal(context.evidence.traceAttached,true);assert.equal(context.evidence.instanceTraceAttachments,1);console.log('PASS live-instance trace hook precedes load resolution')}).catch(e=>{console.error(e);process.exitCode=1});
