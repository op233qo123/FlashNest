#!/usr/bin/env node
// Loopback-only diagnostic; explicit installed binaries; no downloads or publishing.
import fs from 'node:fs';import path from 'node:path';import http from 'node:http';import assert from 'node:assert/strict';import {fileURLToPath} from 'node:url';
import {waitUntilFailFast} from './wait-until.mjs';
import {webdriverNodeEntry} from './webdriver-node-entry.mjs';import {parseArgs,verifyRuntime,route,sha,freshAction,prepareOutput} from './runner-guards.mjs';import {checkHealthy,verifyCycle,verifyMatrix} from './contracts.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),args=parseArgs(process.argv.slice(2)),output=path.resolve(args.output);
for(const key of ['baseline','candidate','fixtures'])args[key]=path.resolve(args[key]);
for(const input of [args.baseline,args.candidate,args.fixtures,here])assert(output!==input&&!output.startsWith(input+path.sep),'Output must not overwrite inputs/helpers');
prepareOutput(output,[args.baseline,args.candidate,args.fixtures,here]);
const result={schemaVersion:1,passed:false,suiteComplete:false,plannedCases:22,completedCases:0,backendRequired:'wgpu-webgl',quality:'low',provenance:{},rows:[],failures:[],started:new Date().toISOString(),scope:'Explicit WebAudio handler lifecycle, close Promise settlement and labeled fault injection; not GC, native crash, memory release or physical audio proof'};
let browser=null,server=null,journalBytes=0,artifactBytes=0;const deadline=Date.now()+10*60*1000;
const journal=path.join(output,'cases.jsonl');fs.writeFileSync(journal,'');
function record(kind,data){const s=JSON.stringify({kind,at:new Date().toISOString(),...data})+'\n';journalBytes+=Buffer.byteLength(s);assert(journalBytes<=16*1024*1024);fs.appendFileSync(journal,s)}
function artifact(name,data){assert(!name.includes('/')&&!name.includes('..'));const bytes=Buffer.from(typeof data==='string'?data:JSON.stringify(data,null,2)+'\n');artifactBytes+=bytes.length;assert(artifactBytes<=64*1024*1024);fs.writeFileSync(path.join(output,name),bytes);return{file:name,bytes:bytes.length,sha256:sha(bytes)}}
function active(config){result.activeCase=config;record('start',config);const p=path.join(output,'active-case.json');fs.writeFileSync(p+'.tmp',JSON.stringify(config,null,2));fs.renameSync(p+'.tmp',p)}
async function evidence(){return browser.execute(()=>window.snapshot?.())}
async function waitFor(fn,message,timeout=20000){await waitUntilFailFast(browser.waitUntil.bind(browser),async()=>{assert(Date.now()<deadline,'Global 10-minute deadline');return await fn()},{timeout,interval:50,timeoutMsg:message})}
function context(e,cycle){const rows=e.audio.contexts.filter(c=>c.cycle===cycle);assert.equal(rows.length,1,'Expected one context');return rows[0]}
async function trustedAudio(kind,cycle,mode){const before=context(await evidence(),cycle);await(await browser.$(kind==='suspend'?'#pause':'#resume')).click();let after;await waitFor(async()=>{const e=await evidence();checkHealthy(e,{mode});after=context(e,cycle);const key=kind==='resume'?'resumes':'suspends';return after[key]>before[key]&&after[kind+'Fulfilled']>before[kind+'Fulfilled']&&after[kind+'FulfilledLast']>before[key]&&e.playing===(kind==='resume')},'Fresh trusted '+kind+' call and its settled Promise');freshAction(before,after,kind);return{kind,before,after}}
try{
 for(const arm of ['baseline','candidate'])result.provenance[arm]=verifyRuntime(args[arm],args[arm+'-manifest'],args[arm+'-manifest-sha256']);
 assert(!fs.lstatSync(args.fixtures).isSymbolicLink());const fixture=path.join(args.fixtures,'silent.swf');assert(fs.lstatSync(fixture).isFile()&&!fs.lstatSync(fixture).isSymbolicLink());assert.equal(sha(fs.readFileSync(fixture)),'e25f5dba4162a25b9a07832be4e6f8f62242734f6f39e92983c53467a28e7fd2');
 const manifest=fs.readFileSync(path.join(args.fixtures,'manifest.json'));assert.equal(sha(manifest),'40687509557be41070b3a3eb19e550870e3ca8d902f2bfea2cedb03c8995ae0f');result.provenance.fixture={manifestSha256:sha(manifest),sha256:sha(fs.readFileSync(fixture))};
 const helpers=['page.mjs','observer.mjs','console-observer.mjs'];result.provenance.helpers=Object.fromEntries([...helpers,'page.html','run.mjs','contracts.mjs','runner-guards.mjs','webdriver-node-entry.mjs','wait-until.mjs'].map(x=>[x,sha(fs.readFileSync(path.join(here,x)))]));
 const pkg=JSON.parse(fs.readFileSync(path.join(args.webdriverio,'package.json'))),entry=webdriverNodeEntry(pkg,args.webdriverio);assert(fs.statSync(args.chrome).isFile()&&fs.statSync(args.driver).isFile(),'Explicit installed browser/driver required');const {remote}=await import(entry);
 artifact('provenance.json',result.provenance);
 const roots={baseline:args.baseline,candidate:args.candidate,fixtures:args.fixtures,helpers:here};
 server=http.createServer((req,res)=>{try{assert.equal(req.method,'GET');assert.equal(req.socket.remoteAddress,'127.0.0.1');const name=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname).slice(1),file=route(name,roots,result.provenance,helpers),stat=fs.lstatSync(file);assert(stat.isFile()&&!stat.isSymbolicLink());res.setHeader('Cache-Control','no-store');res.setHeader('Content-Type',file.endsWith('.html')?'text/html':/\.(mjs|js)$/.test(file)?'text/javascript':file.endsWith('.wasm')?'application/wasm':'application/octet-stream');res.setHeader('Content-Length',stat.size);fs.createReadStream(file).pipe(res)}catch{res.statusCode=404;res.end('Not found')}});
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve)});const origin=`http://127.0.0.1:${server.address().port}`;
 browser=await remote({logLevel:'error',connectionRetryCount:0,connectionRetryTimeout:30000,capabilities:{browserName:'chrome','wdio:chromedriverOptions':{binary:path.resolve(args.driver)},'goog:chromeOptions':{binary:path.resolve(args.chrome),args:['--headless=new','--force-device-scale-factor=1','--window-size=900,700']}}});await browser.setTimeout({script:30000,pageLoad:30000,implicit:0});record('browser',{capabilities:browser.capabilities});
 for(const arm of ['baseline','candidate'])for(const mode of ['normal','start-first','start-second','synthetic-ended']){
  await browser.url(`${origin}/?runtime=${arm}&mode=${mode}`);await waitFor(async()=>{const e=await evidence();if(e)checkHealthy(e,{mode});return browser.execute(()=>window.runtimeReady===true)},'Runtime loader ready');
  for(let cycle=0;cycle<(mode==='normal'?8:1);cycle++){
   const config={arm,mode,cycle},label=`${arm}-${mode}-${cycle}`,actions=[];active(config);
   await browser.execute(c=>window.startCycle(c),cycle);await waitFor(async()=>{const e=await evidence();checkHealthy(e,{mode});return e.rows.find(x=>x.cycle===cycle)?.loaded},'Original fixture loaded');
   if(mode.startsWith('start-'))await(await browser.$('#resume')).click();
   else{
    actions.push(await trustedAudio('resume',cycle,mode));await waitFor(async()=>{const e=await evidence();checkHealthy(e,{mode});return context(e,cycle).nodes>2},'Natural onended refill after first trusted resume');
    actions.push(await trustedAudio('suspend',cycle,mode));
    actions.push(await trustedAudio('resume',cycle,mode));await waitFor(async()=>{const e=await evidence();checkHealthy(e,{mode});return context(e,cycle).nodes>actions[2].after.nodes},'Fresh natural source after post-pause resume');
   }
   let playback;await waitFor(async()=>{const e=await evidence();checkHealthy(e,{mode});const row=e.rows.find(x=>x.cycle===cycle),lastResume=row?.actions.filter(a=>a.name==='resume').at(-1);playback={beforeHeartbeats:lastResume?.heartbeatBefore,afterHeartbeats:row?.heartbeats,playing:e.playing};return Number.isInteger(playback.beforeHeartbeats)&&playback.afterHeartbeats>playback.beforeHeartbeats&&playback.playing===true},'Fresh original AVM2 ENTER_FRAME after latest trusted resume');
   const preRemove=context(await evidence(),cycle);assert.equal(preRemove.closeCalls,mode.startsWith('start-')?1:0,'Premature/missing constructor close before Remove');
   await(await browser.$('#remove')).click();await waitFor(async()=>{const e=await evidence();checkHealthy(e,{mode});const c=context(e,cycle);return e.rows.find(x=>x.cycle===cycle)?.removed&&c.closeCalls===1&&c.closeFulfilled===1},'Actual close entry and fulfilled close Promise');
   let synthetic=null;if(mode==='synthetic-ended')synthetic=await browser.execute(()=>window.dispatchSyntheticEnded());
   const e=await evidence(),attachment=artifact(label+'-evidence.json',{evidence:e,actions,synthetic,playback,preRemove});
   const checked=verifyCycle(e,{...config,synthetic,actions,playback,preRemove}),row={...config,...checked,evidence:attachment};result.rows.push(row);result.completedCases=result.rows.length;record('passed',row);
  }
  await browser.execute(()=>window.dispose());
 }
 verifyMatrix(result.rows);result.suiteComplete=true;result.passed=true;
}catch(error){result.failures.push(String(error?.stack||error).slice(0,16000));process.exitCode=1;if(browser){try{result.lastEvidence=artifact('FAIL-evidence.json',await evidence())}catch(e){result.failures.push('Evidence capture failed: '+String(e).slice(0,2000))}try{await browser.saveScreenshot(path.join(output,'FAIL-browser.png'))}catch{}}}
finally{if(browser){try{await browser.execute(()=>window.dispose?.())}catch(e){result.passed=false;result.failures.push('Page cleanup: '+String(e).slice(0,2000));process.exitCode=1}try{await browser.deleteSession()}catch(e){result.passed=false;result.failures.push('Session cleanup: '+String(e).slice(0,2000));process.exitCode=1}}if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve))}result.finished=new Date().toISOString();result.artifactBytes=artifactBytes;fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({passed:result.passed,suiteComplete:result.suiteComplete,cases:result.completedCases,failures:result.failures}))}
