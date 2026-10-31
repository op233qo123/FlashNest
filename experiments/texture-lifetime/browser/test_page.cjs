'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {install}=require('./instrumentation.js');
let next=0;
class GL {
 createTexture(){return {opaque:++next}} deleteTexture(){} bindTexture(){} activeTexture(){} texImage2D(){} texSubImage2D(){} texStorage2D(){} generateMipmap(){} drawArrays(){} drawElements(){} compressedTexImage2D(){} copyTexImage2D(){}
}
class GL2 extends GL {}
const tracker=install({WebGLRenderingContext:GL,WebGL2RenderingContext:GL2}),gl=new GL2();
const listeners={};tracker.register(gl,'webgl2',{addEventListener:(name,fn)=>listeners[name]=fn});
const a=gl.createTexture(),b=gl.createTexture();gl.bindTexture(3553,a);
const pixels=new Uint8Array(512*512*4);gl.texImage2D(3553,0,6408,512,512,0,6408,5121,pixels);
let s=tracker.snapshot();assert.equal(s.summary.target512ExpectedBaseRGBA8Bytes,1048576);assert.equal(s.events.filter(e=>e.name==='texImage2D').length,1,'No double wrapping inherited WebGL2 methods');
assert.ok(!JSON.stringify(s).includes('opaque'));assert.ok(!JSON.stringify(s).includes('pixels'));
gl.activeTexture(33985);gl.bindTexture(3553,b);gl.texStorage2D(3553,3,32856,16,16);gl.texSubImage2D(3553,0,0,0,6408,5121,{width:8,height:8});
gl.activeTexture(33984);gl.texSubImage2D(3553,0,0,0,512,512,6408,5121,pixels);gl.generateMipmap(3553);
s=tracker.snapshot();assert.equal(s.textures[0].uploads,2);assert.equal(s.textures[1].uploads,2);assert.equal(s.summary.knownExpectedBaseRGBA8Bytes,1049600);
assert.equal(s.events.find(e=>e.name==='generateMipmap').texture,0);
gl.deleteTexture(a);gl.deleteTexture(a);gl.deleteTexture(null);s=tracker.snapshot();assert.equal(s.summary.deleteRequestedUnique,1);assert.equal(s.textures[0].deleteCalls,2);assert.equal(s.summary.notDeleteRequested,1);
// Deleting a bound texture leaves no inferred association on later invalid calls.
gl.texImage2D(3553,0,6408,512,512,0,6408,5121,null);assert.equal(tracker.snapshot().events.at(-1).texture,null);
gl.activeTexture(33985);gl.texImage2D(3553,0,6408,6408,5121,{naturalWidth:32,naturalHeight:16});s=tracker.snapshot();assert.equal(s.textures[1].expectedBaseRGBA8Bytes,2048);
gl.compressedTexImage2D(3553,0,1,32,16,0,new Uint8Array(16));assert.equal(tracker.snapshot().textures[1].expectedBaseRGBA8Bytes,null);
gl.texImage2D(3553,0,6407,32,16,0,6407,5121,new Uint8Array(1536));assert.equal(tracker.snapshot().textures[1].expectedBaseRGBA8Bytes,null);
listeners.webglcontextlost();assert.equal(tracker.snapshot().contexts[0].losses,1);assert.equal(tracker.snapshot().summary.notDeleteRequested,1,'Context loss does not imply observed delete request');
for(let i=0;i<20;i++)gl.drawArrays(4,0,3);s=tracker.snapshot();assert.equal(s.contexts[0].calls.drawArrays,20);assert.equal(s.events.filter(e=>e.name==='drawArrays').length,0);
class TinyGL {createTexture(){return {}}deleteTexture(){}}
const tiny=install({WebGLRenderingContext:TinyGL},{cap:2});const tg=new TinyGL();tg.createTexture();tg.createTexture();tg.createTexture();assert.equal(tiny.snapshot().overflow,true);
class ThrowGL {texImage2D(){throw Error('fake')}}
const throwing=install({WebGLRenderingContext:ThrowGL});assert.throws(()=>new ThrowGL().texImage2D(),/fake/);assert.equal(throwing.snapshot().contexts[0].thrown.texImage2D,1);
const html=fs.readFileSync(__dirname+'/page.html','utf8');const js=html.split('<script>')[1].split('</script>')[0];new vm.Script(js);
assert.ok(html.includes('new WeakRef(value)'));assert.ok(!/getError\(|\.gc\(/.test(html+fs.readFileSync(__dirname+'/instrumentation.js','utf8')));
console.log('PASS: texture requests, units, null/duplicate delete, dimensions, unknown formats, event budget, no payload copies, page syntax');
