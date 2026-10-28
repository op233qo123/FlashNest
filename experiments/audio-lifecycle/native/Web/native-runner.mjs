import assert from './assert.mjs';
import {checkHealthy,verifyCycle} from './contracts.mjs';
import {freshAction} from './fresh-action.mjs';
// No synthetic click/resume, normal callback invocation, autoplay exemption,
// mute override or retained source. Only XCUITest taps the real DOM controls.
const params=new URLSearchParams(location.search),arm=params.get('runtime'),mode=params.get('mode');
const host=window.__nativeAudioHost,rows=[];let finished=false,requestSequence=0,pendingAction=null,pendingEvidenceReceipt=null,acceptedEvidenceReceipt=null;
function send(type,payload){window.webkit.messageHandlers.audioLifecycle.postMessage({type,arm,mode,...payload})}
function snapshot(){return window.snapshot?.()}
function context(e,cycle){const rows=e.audio.contexts.filter(c=>c.cycle===cycle);assert.equal(rows.length,1,'Expected one actual AudioContext');return rows[0]}
async function waitFor(predicate,message,timeout=20000){
 const end=Math.min(host.deadlineMS,Date.now()+timeout);
 while(Date.now()<end){if(await predicate())return;await new Promise(resolve=>setTimeout(resolve,50))}
 throw Error(message+' (bounded deadline)');
}
function healthy(){const e=snapshot();if(e)checkHealthy(e,{mode});return e}
async function trustedClick(name,cycle){
 const before=healthy().rows.find(x=>x.cycle===cycle).actions.length;
 const token=`${arm}/${mode}/${cycle}/${++requestSequence}/${name}`;
 pendingAction={token,name,cycle,requestedAtMS:Date.now(),deadlineMS:Math.min(host.deadlineMS,Date.now()+90000)};
 send('action',{token,name,cycle});
 await waitFor(()=>{const row=healthy().rows.find(x=>x.cycle===cycle);if(row.actions.length===before)return false;assert.equal(row.actions.length,before+1,'Duplicated action');const action=row.actions.at(-1);assert.equal(action.name,name);assert.equal(action.trusted,true,'Untrusted DOM event');return true},'One trusted '+name,90000);
 pendingAction=null;
 send('busy',{token});
}
async function trustedAudio(kind,cycle){
 const before=context(healthy(),cycle);await trustedClick(kind==='suspend'?'pause':'resume',cycle);let after;
 await waitFor(()=>{const e=healthy();after=context(e,cycle);const key=kind==='resume'?'resumes':'suspends';return after[key]>before[key]&&after[kind+'Fulfilled']>before[kind+'Fulfilled']&&after[kind+'FulfilledLast']>before[key]&&e.playing===(kind==='resume')},'Fresh trusted '+kind+' Promise');
 freshAction(before,after,kind);return{kind,before,after};
}
// Exact serialized case bytes are persisted/read back by the host before it
// acknowledges this prefix. Never drain on send, timeout or digest mismatch.
window.__nativeAudioReceipt=receipt=>{
 assert(pendingEvidenceReceipt&&!pendingEvidenceReceipt.accepted,'Unsolicited/duplicate case receipt');
 assert.deepEqual(receipt,pendingEvidenceReceipt.expected,'Persisted case receipt differs');
 acceptedEvidenceReceipt=window.nativeAudioEvidenceWindow.acceptReceipt(receipt);
 pendingEvidenceReceipt.accepted=true;return true;
};
async function persistCase(record){
 const status=record.evidence.audio.eventWindow;
 const token=`${arm}/${mode}/${record.config.cycle}/evidence`;
 record.eventWindow={token,cycle:record.config.cycle,start:status.start,endExclusive:status.endExclusive,count:status.count};
 const caseJSON=JSON.stringify(record),bytes=new TextEncoder().encode(caseJSON);
 assert(bytes.length>0&&bytes.length<=2*1024*1024,'Serialized case exceeds original file cap');
 const hash=await crypto.subtle.digest('SHA-256',bytes);
 const sha256=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
 const expected={...record.eventWindow,bytes:bytes.length,sha256};
 window.nativeAudioEvidenceWindow.armReceipt(expected);
 pendingEvidenceReceipt={expected,accepted:false};
 send('case',{config:record.config,caseJSON,sha256});
 await waitFor(()=>{healthy();return pendingEvidenceReceipt.accepted},'Exact persisted case readback acknowledgment');
 pendingEvidenceReceipt=null;
}
function allObservedAudioPromisesSettled(e){
 return e.audio.contexts.every(c=>c.resumes===c.resumeFulfilled+c.resumeRejected&&
  c.suspends===c.suspendFulfilled+c.suspendRejected&&c.closeCalls===c.closeFulfilled+c.closeRejected);
}
async function run(){
 assert(host&&Number.isFinite(host.deadlineMS)&&host.deadlineMS>Date.now(),'Missing bounded native host identity');
 assert(Number.isFinite(host.displayScale)&&host.displayScale>0&&window.devicePixelRatio===host.displayScale,'WK DPR differs from native screen scale');
 assert(['baseline','candidate'].includes(arm)&&['normal','start-first','start-second','synthetic-ended'].includes(mode));
 await waitFor(()=>{healthy();return window.runtimeReady===true},'Pinned runtime ready',80000);
 for(let cycle=0;cycle<(mode==='normal'?8:1);cycle++){
  const config={arm,mode,cycle},actions=[];send('case-start',{...config,previousReceipt:acceptedEvidenceReceipt});
  // Do not await an unbounded runtime load Promise: poll its settled milestone.
  Promise.resolve(window.startCycle(cycle)).catch(error=>send('page-error',{message:String(error)}));
  await waitFor(()=>healthy().rows.find(x=>x.cycle===cycle)?.loaded,'Original silent fixture loaded',80000);
  if(mode.startsWith('start-'))await trustedClick('resume',cycle);
  else{
   actions.push(await trustedAudio('resume',cycle));
   await waitFor(()=>context(healthy(),cycle).nodes>2,'Natural ended refill after first resume');
   actions.push(await trustedAudio('suspend',cycle));
   actions.push(await trustedAudio('resume',cycle));
   await waitFor(()=>context(healthy(),cycle).nodes>actions[2].after.nodes,'Fresh source after second resume');
  }
  let playback;await waitFor(()=>{const e=healthy(),row=e.rows.find(x=>x.cycle===cycle),last=row.actions.filter(a=>a.name==='resume').at(-1);playback={beforeHeartbeats:last?.heartbeatBefore,afterHeartbeats:row.heartbeats,playing:e.playing};return Number.isInteger(playback.beforeHeartbeats)&&playback.afterHeartbeats>playback.beforeHeartbeats&&playback.playing===true},'Fresh AVM2 heartbeat after latest resume');
  const preRemove=context(healthy(),cycle);assert.equal(preRemove.closeCalls,mode.startsWith('start-')?1:0,'Premature/missing close');
  await trustedClick('remove',cycle);
  await waitFor(()=>{const e=healthy(),c=context(e,cycle);return e.rows.find(x=>x.cycle===cycle).removed&&c.closeCalls===1&&c.closeFulfilled===1},'Close entry and fulfilled original Promise');
  const synthetic=mode==='synthetic-ended'?window.dispatchSyntheticEnded():null;
  const evidence=healthy(),checked=verifyCycle(evidence,{...config,actions,playback,preRemove,synthetic,expectedDPR:host.displayScale});
  const result={...config,...checked,nativeDPR:host.displayScale,renderer:evidence.rows.find(x=>x.cycle===cycle).renderer};rows.push(result);
  await persistCase({type:'case',arm,mode,config,result,evidence,actions,playback,preRemove,synthetic,expectedDPR:host.displayScale});
 }
 return {passed:true,rows};
}
// Fail-fast: any predicate exception escapes immediately, including falsy throws.
function errorDetail(error){
 const message=String(error?.message??error).slice(0,2048),stack=String(error?.stack??'').slice(0,8192);
 return {error:String(error?.name??'Error').slice(0,128)+': '+message+(stack?'\n'+stack:''),errorMessage:message,errorStack:stack};
}
function failureContext(){
 const controls={};
 for(const name of ['resume','pause','remove']){
  const button=document.getElementById(name),rect=button?.getBoundingClientRect();
  controls[name]=button?{connected:button.isConnected,disabled:button.disabled,
   rect:rect?{x:rect.x,y:rect.y,width:rect.width,height:rect.height}:null}:null;
 }
 return {pendingAction,observedAtMS:Date.now(),visibility:document.visibilityState,
  viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},controls};
}
run().then(result=>finish(result),error=>finish({passed:false,rows,...errorDetail(error)}));
async function finish(result){
 if(finished)return;finished=true;
 // Capture the pending predicate and real control geometry before dispose/removal.
 let diagnosticContext;try{diagnosticContext=failureContext()}catch(error){diagnosticContext={unavailable:true,...errorDetail(error)}}
 let cleanupError=null;try{window.dispose?.()}catch(error){cleanupError=String(error)}
 if(cleanupError)result={...result,passed:false,cleanupError};
 try{await waitFor(()=>allObservedAudioPromisesSettled(healthy()),'Observed audio Promises settled before terminal tail')}catch(error){result={...result,passed:false,tailSettlementError:errorDetail(error)}}
 let lastEvidence=null;try{lastEvidence=snapshot()}catch(error){result={...result,passed:false,snapshotError:String(error)}}
 send('complete',{result,lastEvidence,diagnosticContext,lastReceipt:acceptedEvidenceReceipt});
}
