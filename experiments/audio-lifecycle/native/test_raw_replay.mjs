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
 const manifest={schemaVersion:1,adapterScope:'canvas-audio-only',files,sourceBuild:{testOnly:true},browserPrerequisite:{testOnly:true},transformations:[]};write(path.join(web,'native-manifest.json'),manifest);const pin=sha(fs.readFileSync(path.join(web,'native-manifest.json')));
 // Reuse the pure fixture builder from the locked original contract mocks.
 const source=fs.readFileSync(path.join(root,'experiments/audio-lifecycle/browser-tests/test_contracts.mjs'),'utf8');
 const definition=source.slice(source.indexOf('function fixture('),source.indexOf('\nlet checks='));
 const fixture=new Function(definition+';return fixture;')();
 for(const arm of ['baseline','candidate'])for(const mode of ['normal','start-first','start-second','synthetic-ended']){
  const folder=path.join(suite,`${arm}-${mode}`),count=mode==='normal'?8:1,results=[];let last;
  write(path.join(folder,'identity.json'),{manifestSHA256:pin,manifest,systemVersion:'18.5',displayScale:3,mediaPolicy:'require-audio-and-video-user-action',arm,mode});
  for(let cycle=0;cycle<count;cycle++){
   const{e,config}=fixture(arm,mode);e.runtime=arm;e.mode=mode;e.rows[0].cycle=cycle;e.audio.contexts[0].cycle=cycle;e.rows[0].renderer='canvas';e.rows[0].context={kind:'2d',dpr:3,backingWidth:960,backingHeight:720};
   Object.assign(config,{cycle,expectedDPR:3});if(mode==='synthetic-ended')config.synthetic={hadHandler:arm==='baseline',beforeNodes:6,afterNodes:arm==='baseline'?7:6,beforeAttempts:6,afterAttempts:arm==='baseline'?7:6,beforeThrows:0,afterThrows:0};
   const checked=verifyCycle(e,config),result={arm,mode,cycle,...checked,nativeDPR:3,renderer:'canvas'};results.push(result);last=e;
   write(path.join(folder,`case-start-${cycle}.json`),{type:'case-start',arm,mode,cycle});
   write(path.join(folder,`case-${cycle}.json`),{type:'case',arm,mode,config:{arm,mode,cycle},result,evidence:e,actions:config.actions,playback:config.playback,preRemove:config.preRemove,synthetic:config.synthetic??null,expectedDPR:3});
  }
  write(path.join(folder,'page-terminal.json'),{type:'complete',result:{passed:true,rows:results},lastEvidence:last});
  write(path.join(folder,'host-final-snapshot.json'),{snapshotJSON:JSON.stringify(last)});
  write(path.join(folder,'host-summary.json'),{passed:true,serverDrained:true,failures:[],completedCases:count,manifestSHA256:pin,systemVersion:'18.5',arm,mode,elapsedSeconds:10});
 }
 let index=0;function replay(ok){const result=spawnSync(process.execPath,[path.join(here,'check_native_evidence.mjs'),'--web',web,'--manifest-sha',pin,'--suite',suite,'--output',path.join(temp,`result-${index++}.json`)],{encoding:'utf8'});assert.equal(result.status===0,ok,result.stderr)}
 replay(true);
 function mutate(file,change){const before=fs.readFileSync(file);const value=JSON.parse(before);change(value);write(file,value);replay(false);fs.writeFileSync(file,before)}
 const candidate=path.join(suite,'candidate-normal','case-0.json');
 for(const change of [e=>e.evidence.audio.contexts[0].closeFulfilled=0,e=>e.evidence.audio.contexts[0].closeSnapshots[0].attachedIds=[7],e=>e.evidence.rows[0].actions[0].trusted=false,e=>e.evidence.rows[0].renderer='wgpu-webgl',e=>e.evidence.rows[0].context.dpr=2,e=>e.evidence.preflight.cases[3].getterCategory='undefined',e=>e.evidence.audio.events[0].identityPreserved=false,e=>e.evidence.rows[0].extensions='OFF'])mutate(candidate,change);
 mutate(path.join(suite,'baseline-normal','host-summary.json'),s=>s.serverDrained=false);
 const missing=path.join(suite,'candidate-start-first','case-0.json');fs.renameSync(missing,missing+'.held');replay(false);fs.renameSync(missing+'.held',missing);
 mutate(path.join(web,'native-manifest.json'),m=>m.adapterScope='graphics-full');
 console.log('PASS native raw22 replay +11 corrupt evidence cases on synthetic data; no native/browser/runtime execution');
}finally{fs.rmSync(temp,{recursive:true,force:true})}
