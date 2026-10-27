// Pure protocol/crop checks, not browser-renderer evidence.
import assert from 'node:assert/strict';
import {nodeEntry,encodePNG,cropScreenshot,captureHost,fixturePixels} from './screenshot.mjs';
import {decodePNG} from './png.mjs';
assert.equal(nodeEntry({version:'9.32.0',exports:{'.':{import:'./build/node.js'}}}),'./build/node.js');
assert.throws(()=>nodeEntry({version:'9.32.0',exports:{'.':{import:'./build/index.js'}}}));
assert.throws(()=>nodeEntry({version:'9.33.0',exports:{'.':{import:'./build/node.js'}}}));
for(const dpr of [1,2,3]){
 const width=80*dpr,height=60*dpr,channels=4,pixels=Buffer.alloc(width*height*channels);
 for(let y=0;y<height;y++)for(let x=0;x<width;x++)pixels.set(x<width/2?[25,171,117,255]:[29,39,58,255],(y*width+x)*channels);
 const image={width,height,channels,pixels},full=encodePNG(image),geometry={rect:[10,10,60,40],viewport:[80,60],dpr};
 assert.deepEqual(decodePNG(full).pixels,pixels);
 const shot=cropScreenshot(full.toString('base64'),geometry);
 assert.deepEqual([shot.pixels.width,shot.pixels.height],[60*dpr,40*dpr]);assert.equal(shot.metadata.resized,false);assert(fixturePixels(shot.pixels).ready);
 for(let y=0;y<40*dpr;y++)assert.deepEqual(shot.pixels.pixels.subarray(y*60*dpr*4,(y+1)*60*dpr*4),pixels.subarray(((y+10*dpr)*width+10*dpr)*4,((y+10*dpr)*width+70*dpr)*4));
 assert.deepEqual(decodePNG(encodePNG(shot.pixels)).pixels,shot.pixels.pixels);
 for(const rect of [[-1,0,10,10],[0,0,81,60],[0,0,0,10],[0,0,10.1,10]])assert.throws(()=>cropScreenshot(full.toString('base64'),{...geometry,rect}));
 assert.throws(()=>cropScreenshot(full.toString('base64'),{...geometry,viewport:[81,60]}));
 let calls=0;const browser={execute:async()=>{calls++;return geometry},takeScreenshot:async()=>full.toString('base64')};
 const captured=await captureHost(browser);assert.equal(calls,2);assert.deepEqual(captured.pixels.pixels,shot.pixels.pixels);
 let step=0;await assert.rejects(()=>captureHost({...browser,execute:async()=>++step===1?geometry:{...geometry,rect:[0,0,60,40]}}));
}
assert.throws(()=>cropScreenshot('not-base64',{}));
assert.throws(()=>cropScreenshot('AAAA',{}));
assert.equal(fixturePixels({channels:3,pixels:Buffer.alloc(300*3)}).ready,false);
console.log('PASS pinned Node entry, raw screenshot protocol, DPR1/2/3 exact crop, bounds, viewport drift, no resizing');
const {visibleDragTarget}=await import('./screenshot.mjs');
const transparent={width:40,height:20,channels:4,pixels:Buffer.alloc(40*20*4)};
for(let i=0;i<800;i++)transparent.pixels.set(i<400?[25,171,117,0]:[29,39,58,0],i*4);
assert.equal(fixturePixels(transparent).ready,false,'Invisible RGB must not establish rendering');
let transforms=0;
for(const [width,height] of [[443,287],[319,481]])for(const mode of ['showAll','noBorder','exactFit','noScale'])for(const align of ['', 'T','B','L','R','TL','TR','BL','BR']){
 const factor=mode==='showAll'?Math.min(width/320,height/240):mode==='noBorder'?Math.max(width/320,height/240):1;
 const scaleX=mode==='exactFit'?width/320:factor,scaleY=mode==='exactFit'?height/240:factor;
 const offsetX=align.includes('L')?0:align.includes('R')?width-320*scaleX:(width-320*scaleX)/2;
 const offsetY=align.includes('T')?0:align.includes('B')?height-240*scaleY:(height-240*scaleY)/2;
 const cssX=Math.round(width*.05),cssY=Math.round(height*.05);
 const args={sx:1/scaleX,sy:1/scaleY,rootX:(cssX-offsetX)/scaleX,rootY:(cssY-offsetY)/scaleY,cssX,cssY,width,height};
 const [x,y]=visibleDragTarget(args),rootX=(x-offsetX)/scaleX,rootY=(y-offsetY)/scaleY;
 assert(x>0&&x+12<width&&y>0&&y+9<height);assert(rootX>100&&rootX<220&&rootY>70&&rootY<170);transforms++;
}
assert.equal(transforms,72);
assert.throws(()=>visibleDragTarget({sx:0,sy:1,rootX:0,rootY:0,cssX:0,cssY:0,width:100,height:100}));
assert.throws(()=>visibleDragTarget({sx:1,sy:1,rootX:1000,rootY:1000,cssX:0,cssY:0,width:100,height:100}));
console.log('PASS transparent-pixel rejection and visible drag interior across72 mode/align/aspect transforms');
