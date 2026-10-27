// Raw W3C screenshot capture; no WebdriverIO environment helpers or resizing.
import assert from 'node:assert/strict';
import {deflateSync} from 'node:zlib';
import {decodePNG} from './png.mjs';
export function nodeEntry(pkg){
 assert.equal(pkg.version,'9.32.0');
 assert.equal(pkg.exports?.['.']?.import,'./build/node.js','Pinned Node WebdriverIO entry required');
 return pkg.exports['.'].import;
}
function crc(bytes){let n=0xffffffff;for(const b of bytes){n^=b;for(let i=0;i<8;i++)n=(n>>>1)^((n&1)?0xedb88320:0)}return (n^0xffffffff)>>>0}
function chunk(type,data){const t=Buffer.from(type),head=Buffer.alloc(4),tail=Buffer.alloc(4);head.writeUInt32BE(data.length);tail.writeUInt32BE(crc(Buffer.concat([t,data])));return Buffer.concat([head,t,data,tail])}
export function encodePNG(image){
 const {width,height,channels,pixels}=image;assert(Number.isSafeInteger(width)&&Number.isSafeInteger(height)&&width>0&&height>0&&width*height<=12_000_000);assert([3,4].includes(channels));assert.equal(pixels.length,width*height*channels);
 const header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=channels===3?2:6;
 const stride=width*channels,raw=Buffer.alloc((stride+1)*height);
 for(let y=0;y<height;y++)pixels.copy(raw,y*(stride+1)+1,y*stride,(y+1)*stride);
 return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),chunk('IDAT',deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);
}
export function cropScreenshot(base64,geometry){
 assert(typeof base64==='string'&&base64.length>0&&base64.length<=24*1024*1024&&/^[A-Za-z0-9+/]*={0,2}$/.test(base64),'Bounded base64 screenshot required');
 const full=Buffer.from(base64,'base64');assert.equal(full.toString('base64'),base64,'Noncanonical screenshot');
 const image=decodePNG(full),{rect,viewport,dpr}=geometry;
 assert(Array.isArray(rect)&&rect.length===4&&rect.every(Number.isFinite));assert(Array.isArray(viewport)&&viewport.length===2&&viewport.every(x=>Number.isFinite(x)&&x>0));assert([1,2,3].includes(dpr));
 assert.deepEqual([image.width,image.height],viewport.map(v=>Math.round(v*dpr)),'Screenshot must match actual CSS viewport at native DPR');
 const physical=rect.map(v=>v*dpr);assert(physical.every(Number.isSafeInteger),'Crop must use exact physical pixel boundaries');
 const [x,y,width,height]=physical;assert(x>=0&&y>=0&&width>0&&height>0&&x+width<=image.width&&y+height<=image.height,'Crop outside screenshot');
 const pixels=Buffer.alloc(width*height*image.channels),stride=width*image.channels;
 for(let row=0;row<height;row++)image.pixels.copy(pixels,row*stride,((y+row)*image.width+x)*image.channels,((y+row)*image.width+x+width)*image.channels);
 const crop={width,height,channels:image.channels,pixels};
 return {full,pixels:crop,metadata:{cssRect:rect,cssViewport:viewport,dpr,fullPixels:[image.width,image.height],cropPixels:physical,resized:false}};
}
export function fixturePixels(image){
 let green=0,background=0;for(let i=0;i<image.pixels.length;i+=image.channels){const near=(r,g,b)=>(image.channels!==4||image.pixels[i+3]===255)&&Math.abs(image.pixels[i]-r)<8&&Math.abs(image.pixels[i+1]-g)<8&&Math.abs(image.pixels[i+2]-b)<8;if(near(25,171,117))green++;if(near(29,39,58))background++}
 return {green,background,ready:green>=100&&background>=100};
}
export async function captureHost(browser){
 const before=await browser.execute(()=>window.screenshotGeometry());
 const raw=await browser.takeScreenshot();
 const after=await browser.execute(()=>window.screenshotGeometry());
 assert.deepEqual(after,before,'Viewport changed during screenshot');
 return cropScreenshot(raw,before);
}

// Select an interior point of the visible original vector, not a clipped center.
export function visibleDragTarget({sx,sy,rootX,rootY,cssX,cssY,width,height}){
 assert([sx,sy,rootX,rootY,cssX,cssY,width,height].every(Number.isFinite)&&sx>0&&sy>0&&width>0&&height>0);
 const toX=x=>cssX+(x-rootX)/sx,toY=y=>cssY+(y-rootY)/sy;
 const left=Math.max(0,toX(100)),right=Math.min(width,toX(220));
 const top=Math.max(0,toY(70)),bottom=Math.min(height,toY(170));
 assert(right-left>4&&bottom-top>4,'Original vector has no safely clickable visible interior');
 // Leave room for the unchanged +12/+9 CSS drag without exiting viewport.
 const x=Math.min((left+right)/2,width-14),y=Math.min((top+bottom)/2,height-11);
 assert(x>left+1&&x<right-1&&y>top+1&&y<bottom-1,'No safe visible drag start/end');
 return [x,y];
}
