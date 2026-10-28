#!/usr/bin/env node
// Synthetic evidence only: exercise the offline replay, never instantiate a player.
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';import os from 'node:os';import crypto from 'node:crypto';import {spawnSync} from 'node:child_process';import {fileURLToPath,pathToFileURL} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../..');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'audio-native-replay-mock-'));
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,typeof value==='string'?value:JSON.stringify(value))};
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
try{
 const web=path.join(temp,'Web'),suite=path.join(temp,'suite');fs.mkdirSync(web);fs.mkdirSync(suite);
 const python=`import sys\nfrom pathlib import Path\nsys.path.insert(0,${JSON.stringify(here)})\nimport stage_native as s\nb=Path(${JSON.stringify(path.join(root,'experiments/audio-lifecycle/browser-tests/contracts.mjs'))}).read_bytes()\nPath(${JSON.stringify(path.join(web,'contracts.mjs'))}).write_bytes(s.transform(b,s.CONTRACT_TRANSFORMS,'test','test')[0])\n`;
 const transformed=spawnSync('python3',['-'],{input:python,encoding:'utf8'});assert.equal(transformed.status,0,transformed.stderr);
 for(const name of ['assert.mjs','fresh-action.mjs'])fs.copyFileSync(path.join(here,'Web',name),path.join(web,name));
 const {verifyCycle}=await import(pathToFileURL(path.join(web,'contracts.mjs')));
 const files=Object.fromEntries(fs.readdirSync(web).map(name=>{const bytes=fs.readFileSync(path.join(web,name));return[name,{bytes:bytes.length,sha256:sha(bytes)}]}));
 const manifest={schemaVersion:1,adapterScope:'canvas-audio-only',eventWindowProtocol:2,files,sourceBuild:{testOnly:true},browserPrerequisite:{testOnly:true},transformations:[]};write(path.join(web,'native-manifest.json'),manifest);const pin=sha(fs.readFileSync(path.join(web,'native-manifest.json')));
 // Reuse the pure fixture builder from the locked original contract mocks.
 const source=fs.readFileSync(path.join(root,'experiments/audio-lifecycle/browser-tests/test_contracts.mjs'),'utf8');
 const definition=source.slice(source.indexOf('function fixture('),source.indexOf('\nlet checks='));
 const fixture=new Function(definition+';return fixture;')();
 for(const arm of ['baseline','candidate'])for(const mode of ['normal','start-first','start-second','synthetic-ended']){
  const folder=path.join(suite,`${arm}-${mode}`),count=mode==='normal'?8:1,results=[];let last,previousReceipt=null,nextSequence=0,allContexts=[],allNodes=[];
  write(path.join(folder,'identity.json'),{manifestSHA256:pin,manifest,systemVersion:'18.5',displayScale:3,mediaPolicy:'require-audio-and-video-user-action',arm,mode});
  for(let cycle=0;cycle<count;cycle++){
   const{e,config}=fixture(arm,mode);e.runtime=arm;e.mode=mode;e.rows[0].cycle=cycle;e.audio.contexts[0].cycle=cycle;e.rows[0].renderer='canvas';e.rows[0].context={kind:'2d',dpr:3,backingWidth:960,backingHeight:720};
   Object.assign(config,{cycle,expectedDPR:3});if(mode==='synthetic-ended')config.synthetic={hadHandler:arm==='baseline',beforeNodes:6,afterNodes:arm==='baseline'?7:6,beforeAttempts:6,afterAttempts:arm==='baseline'?7:6,beforeThrows:0,afterThrows:0};
   const c=e.audio.contexts[0];c.id=cycle+1;const nodeBase=allNodes.length;
   c.closeSnapshots[0].attachedIds=arm==='baseline'?[nodeBase+1,nodeBase+2]:[];
   allContexts.push(structuredClone(c));
   for(let i=0;i<c.nodes;i++)allNodes.push({id:allNodes.length+1,context:c.id,cycle,attached:arm==='baseline',attaches:1,detaches:arm==='candidate'?1:0,starts:1});
   e.audio.contexts=structuredClone(allContexts);e.audio.nodes=structuredClone(allNodes);
   e.audio.events=e.audio.events.map((event,i)=>({...event,seq:nextSequence+i,context:c.id,node:nodeBase+1}));
   const endExclusive=nextSequence+e.audio.events.length;
   e.audio.eventWindow={start:nextSequence,endExclusive,count:e.audio.events.length,overflow:false,finalBoundary:null,postFinalActivity:0,receiptPending:false};
   e.audio.lastReceipt=previousReceipt;
   const checked=verifyCycle(e,config),result={arm,mode,cycle,...checked,nativeDPR:3,renderer:'canvas'};results.push(result);
   write(path.join(folder,`case-start-${cycle}.json`),{type:'case-start',arm,mode,cycle,previousReceipt});
   const eventWindow={kind:'case',ordinal:cycle,token:`${arm}/${mode}/${cycle}/case/${cycle}`,cycle,start:nextSequence,endExclusive,count:e.audio.events.length};
   const entry={type:'case',arm,mode,config:{arm,mode,cycle},result,evidence:e,actions:config.actions,playback:config.playback,preRemove:config.preRemove,synthetic:config.synthetic??null,expectedDPR:3,eventWindow};
   const bytes=Buffer.from(JSON.stringify(entry));write(path.join(folder,`case-${cycle}.json`),bytes.toString());
   previousReceipt={...eventWindow,bytes:bytes.length,sha256:sha(bytes)};write(path.join(folder,`case-receipt-${cycle}.json`),previousReceipt);
   nextSequence=endExclusive;last=structuredClone(e);last.audio.events=[];last.audio.lastReceipt=previousReceipt;
   last.audio.eventWindow={...last.audio.eventWindow,start:nextSequence,endExclusive:nextSequence,count:0};
  }
  write(path.join(folder,'page-terminal.json'),{type:'complete',result:{passed:true,rows:results},lastEvidence:last,lastReceipt:previousReceipt});
  const final=structuredClone(last);final.audio.eventWindow.finalBoundary=nextSequence;
  write(path.join(folder,'host-final-snapshot.json'),{snapshotJSON:JSON.stringify(final)});
  write(path.join(folder,'host-final-window.json'),final.audio.eventWindow);
  write(path.join(folder,'host-summary.json'),{passed:true,serverDrained:true,failures:[],completedCases:count,midcaseChunks:0,receiptCount:count,manifestSHA256:pin,systemVersion:'18.5',arm,mode,elapsedSeconds:10});
 }
 let index=0;function replay(ok,pattern=null){const result=spawnSync(process.execPath,[path.join(here,'check_native_evidence.mjs'),'--web',web,'--manifest-sha',pin,'--suite',suite,'--output',path.join(temp,`result-${index++}.json`)],{encoding:'utf8'});assert.equal(result.status===0,ok,result.stderr);if(pattern)assert.match(result.stderr,pattern)}
 replay(true);
 function mutate(file,change){const before=fs.readFileSync(file);const value=JSON.parse(before);change(value);write(file,value);replay(false);fs.writeFileSync(file,before)}
 const candidate=path.join(suite,'candidate-normal','case-0.json');
 for(const change of [e=>e.evidence.audio.contexts[0].closeFulfilled=0,e=>e.evidence.audio.contexts[0].closeSnapshots[0].attachedIds=[7],e=>e.evidence.rows[0].actions[0].trusted=false,e=>e.evidence.rows[0].renderer='wgpu-webgl',e=>e.evidence.rows[0].context.dpr=2,e=>e.evidence.preflight.cases[3].getterCategory='undefined',e=>e.evidence.audio.events[0].identityPreserved=false,e=>e.evidence.rows[0].extensions='OFF'])mutate(candidate,change);
 mutate(path.join(suite,'baseline-normal','host-summary.json'),s=>s.serverDrained=false);
 const missing=path.join(suite,'candidate-start-first','case-0.json');fs.renameSync(missing,missing+'.held');replay(false);fs.renameSync(missing+'.held',missing);
 mutate(path.join(web,'native-manifest.json'),m=>m.adapterScope='graphics-full');
 // Keep interval/digest gates internally valid: this must reach the candidate
 // post-close predicate, not merely fail a case-file checksum.
 for(const arm of ['baseline','candidate']){
  const finalFile=path.join(suite,`${arm}-normal`,'host-final-snapshot.json'),statusFile=path.join(suite,`${arm}-normal`,'host-final-window.json');
  const originalFinal=fs.readFileSync(finalFile),originalStatus=fs.readFileSync(statusFile);
  const wrapper=JSON.parse(originalFinal),snapshot=JSON.parse(wrapper.snapshotJSON),audio=snapshot.audio;
  const seq=audio.eventWindow.endExclusive;audio.events.push({seq,kind:'source-attempt',context:1});audio.contexts[0].sourceAttempts++;
  audio.eventWindow.endExclusive++;audio.eventWindow.count++;audio.eventWindow.finalBoundary++;
  wrapper.snapshotJSON=JSON.stringify(snapshot);write(finalFile,wrapper);write(statusFile,audio.eventWindow);
  replay(arm==='baseline');fs.writeFileSync(finalFile,originalFinal);fs.writeFileSync(statusFile,originalStatus);
 }
 // Insert an acknowledged mid-case window before cycle1, then rebind every
 // later exact byte receipt and tail. This is synthetic metadata, not a player.
 for(const arm of ['baseline','candidate']){
  const folder=path.join(suite,`${arm}-normal`),load=name=>JSON.parse(fs.readFileSync(path.join(folder,name)));
  const first=load('case-0.json');let previousReceipt=load('case-receipt-0.json');
  const evidence=structuredClone(first.evidence),start=previousReceipt.endExclusive,end=start+1024;
  evidence.audio.events=Array.from({length:1024},(_,i)=>({seq:start+i,kind:'close-fulfilled',context:1}));
  evidence.audio.eventWindow={...evidence.audio.eventWindow,start,endExclusive:end,count:1024};evidence.audio.lastReceipt=previousReceipt;
  const eventWindow={kind:'chunk',ordinal:1,token:`${arm}/normal/1/chunk/1`,cycle:1,start,endExclusive:end,count:1024};
  const chunk={type:'event-chunk',arm,mode:'normal',config:{arm,mode:'normal',cycle:1},evidence,eventWindow};
  const bytes=Buffer.from(JSON.stringify(chunk));write(path.join(folder,'event-chunk-1.json'),bytes.toString());
  previousReceipt={...eventWindow,bytes:bytes.length,sha256:sha(bytes)};write(path.join(folder,'event-receipt-1.json'),previousReceipt);
  for(let cycle=1;cycle<8;cycle++){
   const entry=load(`case-${cycle}.json`);if(cycle>1){const begin=load(`case-start-${cycle}.json`);begin.previousReceipt=previousReceipt;write(path.join(folder,`case-start-${cycle}.json`),begin)}
   for(const e of entry.evidence.audio.events)e.seq+=1024;
   for(const key of ['start','endExclusive']){entry.evidence.audio.eventWindow[key]+=1024;entry.eventWindow[key]+=1024}
   entry.evidence.audio.lastReceipt=previousReceipt;entry.eventWindow.ordinal=cycle+1;entry.eventWindow.token=`${arm}/normal/${cycle}/case/${cycle+1}`;
   const data=Buffer.from(JSON.stringify(entry));write(path.join(folder,`case-${cycle}.json`),data.toString());
   previousReceipt={...entry.eventWindow,bytes:data.length,sha256:sha(data)};write(path.join(folder,`case-receipt-${cycle}.json`),previousReceipt);
  }
  const terminal=load('page-terminal.json');terminal.lastReceipt=previousReceipt;terminal.lastEvidence.audio.lastReceipt=previousReceipt;
  for(const key of ['start','endExclusive'])terminal.lastEvidence.audio.eventWindow[key]+=1024;
  write(path.join(folder,'page-terminal.json'),terminal);
  const final=structuredClone(terminal.lastEvidence);final.audio.eventWindow.finalBoundary=final.audio.eventWindow.endExclusive;
  write(path.join(folder,'host-final-snapshot.json'),{snapshotJSON:JSON.stringify(final)});write(path.join(folder,'host-final-window.json'),final.audio.eventWindow);
  const summary=load('host-summary.json');summary.midcaseChunks=1;summary.receiptCount=9;write(path.join(folder,'host-summary.json'),summary);
 }
 replay(true);
 const chunkFile=path.join(suite,'candidate-normal/event-chunk-1.json'),chunkReceiptFile=path.join(suite,'candidate-normal/event-receipt-1.json');
 const savedChunk=fs.readFileSync(chunkFile),savedReceipt=fs.readFileSync(chunkReceiptFile);
 function corruptChunk(change,pattern){
  const c=JSON.parse(savedChunk);change(c);write(chunkFile,c);
  const bytes=fs.readFileSync(chunkFile),r=JSON.parse(savedReceipt);r.bytes=bytes.length;r.sha256=sha(bytes);write(chunkReceiptFile,r);
  replay(false,pattern);fs.writeFileSync(chunkFile,savedChunk);fs.writeFileSync(chunkReceiptFile,savedReceipt);
 }
 corruptChunk(c=>c.evidence.audio.events[0]={...c.evidence.audio.events[0],kind:'attach',setterCategory:'function',getterCategory:'function',identityPreserved:false},/function identity changed/);
 corruptChunk(c=>c.evidence.audio.events[0].kind='source-attempt',/Candidate source\/handler activity after close entry/);
 corruptChunk(c=>c.evidence.audio.events[0].seq++,/Missing\/duplicate\/reordered event/);
 corruptChunk(c=>c.config.cycle=2,/deep-equal/);
 fs.renameSync(chunkFile,chunkFile+'.held');replay(false);fs.renameSync(chunkFile+'.held',chunkFile);
 mutate(chunkReceiptFile,r=>r.ordinal=9);
 replay(true);
 console.log('PASS native raw22 receipt replay, mid-case chunk chain +17 corrupt cases +candidate late-refill rejection/baseline control on synthetic data; no native/browser/runtime execution');
}finally{fs.rmSync(temp,{recursive:true,force:true})}
