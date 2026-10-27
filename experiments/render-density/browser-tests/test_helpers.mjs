import assert from 'node:assert/strict';
import {deflateSync} from 'node:zlib';
import {decodePNG,comparePixels} from './png.mjs';
function chunk(type,data){const head=Buffer.alloc(8);head.writeUInt32BE(data.length);head.write(type,4);return Buffer.concat([head,data,Buffer.alloc(4)])}
function png(filter=0){const w=20,h=20,ch=3;const header=Buffer.alloc(13);header.writeUInt32BE(w);header.writeUInt32BE(h,4);header[8]=8;header[9]=2;const raw=Buffer.alloc((w*ch+1)*h);for(let y=0;y<h;y++){raw[y*(w*ch+1)]=filter;for(let x=0;x<w;x++){const color=x<10?[25,171,117]:[29,39,58];for(let c=0;c<3;c++)raw[y*(w*ch+1)+1+x*ch+c]=color[c]}}
 return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),chunk('IDAT',deflateSync(raw)),chunk('IEND',Buffer.alloc(0))])}
const p=decodePNG(png());assert.deepEqual([p.width,p.height],[20,20]);const comparison=comparePixels(p,p);assert.equal(comparison.changedFraction,0);assert.equal(comparison.greenPixels,200);
// Each PNG reconstruction filter must yield the same known image.
for(const filter of [1,2,3,4]){
 const w=p.width,h=p.height,stride=w*3,raw=Buffer.alloc((stride+1)*h);
 const paeth=(a,b,c)=>{const v=a+b-c,pa=Math.abs(v-a),pb=Math.abs(v-b),pc=Math.abs(v-c);return pa<=pb&&pa<=pc?a:pb<=pc?b:c};
 for(let y=0;y<h;y++){raw[y*(stride+1)]=filter;for(let x=0;x<stride;x++){
  const i=y*stride+x,left=x>=3?p.pixels[i-3]:0,up=y?p.pixels[i-stride]:0,corner=y&&x>=3?p.pixels[i-stride-3]:0;
  const predicted=[0,left,up,Math.floor((left+up)/2),paeth(left,up,corner)][filter];raw[y*(stride+1)+1+x]=(p.pixels[i]-predicted)&255;
 }}
 const original=png(),encoded=Buffer.concat([original.subarray(0,33),chunk('IDAT',deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);assert.deepEqual(decodePNG(encoded).pixels,p.pixels);
}
assert.throws(()=>decodePNG(png().subarray(0,40)));assert.throws(()=>decodePNG(png(5)));
assert.throws(()=>comparePixels({...p,pixels:Buffer.alloc(p.pixels.length)},p));
console.log('PASS PNG decoding, exact self-comparison, truncated/invalid/blank rejection');
await import('./test_screenshot.mjs');
await import('./test_hardware_warning.mjs');
