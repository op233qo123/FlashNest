// Bounded Chrome screenshot decoder (8-bit RGB/RGBA, non-interlaced PNG only).
import {inflateSync} from 'node:zlib';
import assert from 'node:assert/strict';
export function decodePNG(bytes){
 assert(bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])));
 let width,height,channels,end=false;const chunks=[];
 for(let offset=8;offset<bytes.length;){
  assert(offset+12<=bytes.length);const n=bytes.readUInt32BE(offset),type=bytes.toString('ascii',offset+4,offset+8);assert(offset+12+n<=bytes.length);
  const data=bytes.subarray(offset+8,offset+8+n);
  if(type==='IHDR'){assert.equal(n,13);width=data.readUInt32BE(0);height=data.readUInt32BE(4);assert.equal(data[8],8);assert([2,6].includes(data[9]));assert.equal(data[10],0);assert.equal(data[11],0);assert.equal(data[12],0);channels=data[9]===2?3:4;assert(width>0&&height>0&&width*height<=12_000_000)}
  if(type==='IDAT')chunks.push(data);if(type==='IEND'){end=true;break}offset+=n+12;
 }
 assert(end&&channels&&chunks.length);const stride=width*channels,raw=inflateSync(Buffer.concat(chunks),{maxOutputLength:(stride+1)*height});assert.equal(raw.length,(stride+1)*height);
 const pixels=Buffer.alloc(stride*height);let at=0;
 const paeth=(a,b,c)=>{const p=a+b-c,pa=Math.abs(p-a),pb=Math.abs(p-b),pc=Math.abs(p-c);return pa<=pb&&pa<=pc?a:pb<=pc?b:c};
 for(let y=0;y<height;y++){const filter=raw[at++];assert(filter<=4);for(let x=0;x<stride;x++){
  const i=y*stride+x,left=x>=channels?pixels[i-channels]:0,up=y?pixels[i-stride]:0,corner=y&&x>=channels?pixels[i-stride-channels]:0;
  const predictor=[0,left,up,Math.floor((left+up)/2),paeth(left,up,corner)][filter];pixels[i]=(raw[at++]+predictor)&255;
 }}
 return {width,height,channels,pixels};
}
export function comparePixels(actual,baseline,edgeTolerance=0){
 assert.equal(actual.width,baseline.width);assert.equal(actual.height,baseline.height);
 let changed=0,error=0,green=0,background=0;const count=actual.width*actual.height;
 const box=[Infinity,Infinity,-1,-1],referenceBox=[Infinity,Infinity,-1,-1];
 const include=(bounds,i)=>{const x=i%actual.width,y=Math.floor(i/actual.width);bounds[0]=Math.min(bounds[0],x);bounds[1]=Math.min(bounds[1],y);bounds[2]=Math.max(bounds[2],x);bounds[3]=Math.max(bounds[3],y)};
 for(let i=0;i<count;i++){
  const ai=i*actual.channels,bi=i*baseline.channels;let diff=false;
  for(let c=0;c<3;c++){const d=Math.abs(actual.pixels[ai+c]-baseline.pixels[bi+c]);error+=d;if(d)diff=true}if(diff)changed++;
  const near=(r,g,b)=>Math.abs(actual.pixels[ai]-r)<8&&Math.abs(actual.pixels[ai+1]-g)<8&&Math.abs(actual.pixels[ai+2]-b)<8;
  if(near(25,171,117)){green++;include(box,i)}if(near(29,39,58))background++;
  if(Math.abs(baseline.pixels[bi]-25)<8&&Math.abs(baseline.pixels[bi+1]-171)<8&&Math.abs(baseline.pixels[bi+2]-117)<8)include(referenceBox,i);
 }
 // Only a gross visibility gate, not an antialiasing/visual equivalence claim.
 assert(green>=100&&background>=100,'Missing original vector/background pixels');
 assert(referenceBox.every(Number.isFinite),'Missing baseline vector');for(let i=0;i<4;i++)assert(Math.abs(box[i]-referenceBox[i])<=edgeTolerance,'Visible vector silhouette differs beyond raster-edge tolerance');
 return {vectorBounds:box,baselineVectorBounds:referenceBox,edgeTolerancePixels:edgeTolerance,pixels:count,changedFraction:changed/count,meanAbsoluteRGBError:error/(count*3),greenPixels:green,backgroundPixels:background};
}
