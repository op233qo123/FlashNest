#!/usr/bin/env node
// Offline revalidation of raw WK evidence; no browser, runtime or downloaded code execution.
import assert from 'node:assert/strict';
import {validateWindow,validateReceipt,metadataExtends,validateFinalTail,candidateClosedContexts} from './window-replay.mjs';
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';import {pathToFileURL} from 'node:url';
const argv=process.argv.slice(2);assert.equal(argv.length,8,'--web DIR --manifest-sha SHA --suite DIR --output FILE');
const args={};for(let i=0;i<argv.length;i+=2){assert(!Object.hasOwn(args,argv[i]));args[argv[i]]=argv[i+1]}
assert.deepEqual(Object.keys(args).sort(),['--manifest-sha','--output','--suite','--web']);
const web=path.resolve(args['--web']),suite=path.resolve(args['--suite']),output=path.resolve(args['--output']);
assert(/^[a-f0-9]{64}$/.test(args['--manifest-sha']));assert(!fs.existsSync(output),'Refusing output overwrite');
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
let totalEvidence=0;function read(file,bounded=true){const s=fs.lstatSync(file);assert(s.isFile()&&!s.isSymbolicLink());assert(s.size<=(bounded?2:64)*1024*1024);if(bounded){totalEvidence+=s.size;assert(totalEvidence<=128*1024*1024)}return fs.readFileSync(file)}
const json=file=>JSON.parse(read(file).toString());
function inventory(dir,prefix=''){assert(fs.lstatSync(dir).isDirectory()&&!fs.lstatSync(dir).isSymbolicLink());const result={};for(const name of fs.readdirSync(dir)){assert(!name.includes('\\')&&!name.includes(':'));const file=path.join(dir,name),relative=prefix+name,s=fs.lstatSync(file);assert(!s.isSymbolicLink());if(s.isDirectory())Object.assign(result,inventory(file,relative+'/'));else{const bytes=read(file,false);result[relative]={bytes:bytes.length,sha256:sha(bytes)}}}return result}
const manifestBytes=read(path.join(web,'native-manifest.json'));assert.equal(sha(manifestBytes),args['--manifest-sha']);const manifest=JSON.parse(manifestBytes);
assert.equal(manifest.adapterScope,'canvas-audio-only');assert.equal(manifest.eventWindowProtocol,1);
const files=inventory(web);delete files['native-manifest.json'];assert.deepEqual(files,manifest.files,'Loaded resource inventory differs');
// These are staged project-owned assertion helpers authenticated above, not engine code.
const {verifyCycle,verifyMatrix,checkHealthy}=await import(pathToFileURL(path.join(web,'contracts.mjs')));
const rows=[],attachments=[];let scale=null;
const expectedFolders=[];for(const arm of ['baseline','candidate'])for(const mode of ['normal','start-first','start-second','synthetic-ended'])expectedFolders.push(`${arm}-${mode}`);
assert.deepEqual(fs.readdirSync(suite).sort(),expectedFolders.sort(),'Missing/extra native mode evidence');
for(const arm of ['baseline','candidate'])for(const mode of ['normal','start-first','start-second','synthetic-ended']){
 const folder=path.join(suite,`${arm}-${mode}`);assert(fs.lstatSync(folder).isDirectory()&&!fs.lstatSync(folder).isSymbolicLink());
 const count=mode==='normal'?8:1,identity=json(path.join(folder,'identity.json')),summary=json(path.join(folder,'host-summary.json'));
 assert.equal(identity.manifestSHA256,args['--manifest-sha']);assert.deepEqual(identity.manifest,manifest);assert.equal(identity.systemVersion,'18.5');assert.equal(identity.arm,arm);assert.equal(identity.mode,mode);
 assert.equal(identity.mediaPolicy,'require-audio-and-video-user-action');assert(Number.isFinite(identity.displayScale)&&identity.displayScale>0);
 if(scale===null)scale=identity.displayScale;assert.equal(identity.displayScale,scale,'Baseline/candidate measured different display scale');
 assert.equal(summary.passed,true);assert.equal(summary.serverDrained,true);assert.deepEqual(summary.failures,[]);assert.equal(summary.completedCases,count);assert.equal(summary.manifestSHA256,args['--manifest-sha']);assert.equal(summary.systemVersion,'18.5');assert.equal(summary.arm,arm);assert.equal(summary.mode,mode);
 const group=[];let nextSequence=0,previousReceipt=null,previousAudio=null;const expectedFiles=['identity.json','host-summary.json','host-final-snapshot.json','host-final-window.json','page-terminal.json'];
 for(let cycle=0;cycle<count;cycle++){
  for(const name of [`case-start-${cycle}.json`,`case-${cycle}.json`,`case-receipt-${cycle}.json`])expectedFiles.push(name);
  const start=json(path.join(folder,`case-start-${cycle}.json`));assert.equal(start.type,'case-start');assert.equal(start.arm,arm);assert.equal(start.mode,mode);assert.equal(start.cycle,cycle);assert.deepEqual(start.previousReceipt,previousReceipt);
  const file=path.join(folder,`case-${cycle}.json`),entry=json(file);assert.equal(entry.type,'case');assert.deepEqual(entry.config,{arm,mode,cycle});assert.equal(entry.arm,arm);assert.equal(entry.mode,mode);assert.equal(entry.expectedDPR,scale);assert.equal(entry.evidence.runtime,arm);assert.equal(entry.evidence.mode,mode);
  const checked=verifyCycle(entry.evidence,{arm,mode,cycle,synthetic:entry.synthetic,actions:entry.actions,playback:entry.playback,preRemove:entry.preRemove,expectedDPR:scale});
  const result={arm,mode,cycle,...checked,nativeDPR:scale,renderer:entry.evidence.rows.find(x=>x.cycle===cycle).renderer};assert.deepEqual(entry.result,result);rows.push(result);group.push(result);
  const data=read(file),receipt=json(path.join(folder,`case-receipt-${cycle}.json`));
  validateReceipt(entry,receipt,{bytes:data.length,sha256:sha(data)},cycle,nextSequence);
  const end=validateWindow(entry.evidence.audio,nextSequence,previousReceipt);metadataExtends(previousAudio,entry.evidence.audio);
  if(arm==='candidate')candidateClosedContexts(previousAudio,entry.evidence.audio);
  nextSequence=end;previousReceipt=receipt;previousAudio=entry.evidence.audio;
  attachments.push({file:`${arm}-${mode}/case-${cycle}.json`,bytes:data.length,sha256:sha(data)});
 }
 const terminal=json(path.join(folder,'page-terminal.json'));assert.equal(terminal.type,'complete');assert.equal(terminal.result.passed,true);assert.deepEqual(terminal.result.rows,group);assert(!terminal.result.error&&!terminal.result.cleanupError&&!terminal.result.snapshotError);checkHealthy(terminal.lastEvidence,{mode});
 const last=json(path.join(folder,'host-final-snapshot.json')),finalSnapshot=JSON.parse(last.snapshotJSON),finalStatus=json(path.join(folder,'host-final-window.json'));checkHealthy(finalSnapshot,{mode});
 assert.deepEqual(terminal.lastReceipt,previousReceipt);metadataExtends(previousAudio,terminal.lastEvidence.audio);if(arm==='candidate')candidateClosedContexts(previousAudio,terminal.lastEvidence.audio);validateFinalTail(terminal.lastEvidence,finalSnapshot,finalStatus,nextSequence,previousReceipt,{arm});
 assert.deepEqual(fs.readdirSync(folder).sort(),expectedFiles.sort(),'Unexpected/partial native evidence');
}
verifyMatrix(rows);
const result={schemaVersion:1,passed:true,suiteComplete:true,plannedCases:22,completedCases:22,osVersion:'18.5',platform:'iOS Simulator',backendRequired:'canvas',graphicsScope:'Isolated silent audio gate, not production backend stability',displayScale:scale,manifestSHA256:args['--manifest-sha'],rows,attachments,scope:'Raw WK handler/Promise lifecycle replay; not GC, RAM, speaker output or phone crash causality'};
fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({passed:true,cases:22,manifestSHA256:args['--manifest-sha']}));
