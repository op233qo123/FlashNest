// Native preflight algorithm and actual page-order mocks; not real WebAudio.
import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';
import {nativeOnendedPreflight} from './observer.mjs';
function environment({normalize=true,replaceFunction=false,mismatchedDescriptor=false,throwUndefined=false}={}){
 const calls={contexts:[],sources:0,setters:[],invoked:0,start:0};
 class Scheduled{constructor(){this.handler=null}get onended(){return this.handler}set onended(value){calls.setters.push(value===null?'null':typeof value);if(throwUndefined&&value===undefined)throw Error('native setter failure');this.handler=replaceFunction&&typeof value==='function'?()=>{}:normalize&&value==null?null:value}}
 class Source extends Scheduled{start(){calls.start++;throw Error('Preflight must not start a source')}}
 if(mismatchedDescriptor)Object.defineProperty(Source.prototype,'onended',{get(){return super.onended},set(value){super.onended=value},configurable:true});
 class Offline{constructor(...args){calls.contexts.push(args)}createBufferSource(){calls.sources++;return new Source()}startRendering(){throw Error('Preflight must not start offline rendering')}}
 return{g:{OfflineAudioContext:Offline,AudioScheduledSourceNode:Scheduled,AudioContext:class{constructor(){throw Error('No live AudioContext allowed')}}},calls};
}
let groups=0;
{const {g,calls}=environment(),report=nativeOnendedPreflight(g);assert.equal(report.passed,true);assert.equal(report.descriptorMatched,true);assert.deepEqual(report.cases.map(x=>[x.setterCategory,x.getterCategory]),[['function','function'],['null','null'],['function','function'],['undefined','null']]);assert.equal(report.cleanupGetterCategory,'null');assert.deepEqual(calls.contexts,[[1,1,44100]]);assert.equal(calls.sources,1);assert.equal(calls.start,0);assert.deepEqual(calls.setters,['function','null','function','undefined','null']);assert(!JSON.stringify(report).includes('handler'));groups++}
for(const options of [{normalize:false},{replaceFunction:true},{mismatchedDescriptor:true}]){assert.equal(nativeOnendedPreflight(environment(options).g).passed,false);groups++}
{const {g,calls}=environment({throwUndefined:true});assert.throws(()=>nativeOnendedPreflight(g),/native setter failure/);assert.equal(calls.setters.at(-1),'null');assert.throws(()=>nativeOnendedPreflight({}),/OfflineAudioContext/);groups++}
const page=fs.readFileSync(new URL('./page.mjs',import.meta.url),'utf8');assert.equal((page.match(/^import /gm)||[]).length,2);const body=page.replace(/^import .*;\n/gm,'');
for(const passed of [true,false]){
 const order=[],appended=[],elements={resume:{},pause:{},remove:{},host:{append(){}}},window={addEventListener(){}},document={createElement:()=>({}),head:{append:x=>appended.push(x)},getElementById:id=>elements[id]};
 vm.runInNewContext(body,{window,document,location:{search:'?runtime=candidate&mode=normal'},URLSearchParams,structuredClone,console:{},nativeOnendedPreflight:()=>{order.push('native');return{passed}},installAudioObserver:()=>{order.push('observer');return{snapshot:()=>({}),restore(){},releaseRetained(){}}},installConsoleObserver:()=>({restore(){}})},{timeout:1000});
 assert.deepEqual(order,['native','observer']);assert.equal(appended.length,passed?1:0);assert.equal(window.snapshot().preflight.passed,passed);groups++;
}
console.log(`PASS ${groups} native-preflight/page-order mock groups; no real audio or browser execution`);
