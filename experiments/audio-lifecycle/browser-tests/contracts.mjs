import assert from 'node:assert/strict';
import {freshAction} from './runner-guards.mjs';
export function checkHealthy(e,{mode}) {
 assert(e&&!e.overflow&&!e.audio?.overflow,'Evidence overflow or unavailable');
 const expected=mode==='start-first'||mode==='start-second';
 const unexpected=e.errors.filter(x=>!(expected&&x.message.includes('Unable to create audio backend. No audio will be played.')));
 assert.equal(unexpected.length,0,JSON.stringify(unexpected));
 assert(e.errors.length<=(expected?1:0),'Duplicate/unexpected errors');
 assert(e.audio.events.filter(x=>x.kind==='attach'||x.kind==='detach').every(x=>x.identityPreserved),'Native onended identity changed');
}
export function verifyCycle(e,{arm,mode,cycle,synthetic=null,actions=[],playback=null,preRemove=null}) {
 checkHealthy(e,{mode});const row=e.rows.find(x=>x.cycle===cycle);assert(row?.loaded&&row.removed&&row.removeRequested,'Missing loaded/remove milestone');
 assert.equal(row.renderer,'wgpu-webgl');assert(['ON','OFF'].includes(row.extensions));
 assert(row.context?.kind==='webgl2'&&row.context.lost===false&&row.context.dpr===1&&row.context.drawingBufferWidth>0&&row.context.drawingBufferHeight>0,'Missing actual live WebGL2 context');
 const ctxs=e.audio.contexts.filter(x=>x.cycle===cycle);assert.equal(ctxs.length,1,'Exactly one WebAudio constructor context required');
 const c=ctxs[0];assert.equal(c.closeCalls,1,'Missing/duplicate close entry');assert.equal(c.closeFulfilled,1,'close Promise did not settle fulfilled');assert.equal(c.closeRejected,0);
 const fault=mode==='start-first'||mode==='start-second';
 assert(row.actions.every(x=>x.trusted));
 if(fault){
  assert.deepEqual(row.actions.map(x=>x.name),['resume','remove']);
  assert(e.audio.injected);assert.equal(c.nodes,mode==='start-first'?1:2);assert.equal(c.starts,c.nodes);
  assert.equal(e.errors.length,1,'Expected actual NullAudioBackend fallback error');
 }else{
  assert.deepEqual(row.actions.map(x=>x.name),['resume','pause','resume','remove']);
  assert(c.nodes>2,'No natural onended refill observed');assert(c.resumeFulfilled>=2&&c.suspendFulfilled>=1);
  assert.equal(c.resumeRejected,0);assert.equal(c.suspendRejected,0);
  assert.deepEqual(actions.map(x=>x.kind),['resume','suspend','resume'],'Missing action-specific Promise proof');for(const a of actions)freshAction(a.before,a.after,a.kind);
  assert(actions[2].after.nodes>=actions[1].after.nodes,'Source accounting regressed');
 }
 assert(playback&&playback.playing===true&&Number.isInteger(playback.beforeHeartbeats)&&playback.afterHeartbeats>playback.beforeHeartbeats,'No fresh post-resume AVM2 heartbeat');
 assert(preRemove&&preRemove.closeCalls===(fault?1:0),'Wrong close state before Remove');
 if(!fault)assert(preRemove.nodes>actions[2].after.nodes,'No new source after settled second resume');
 assert(row.traces.includes('AL_ACTIVE'),'Original AVM2 ENTER_FRAME did not run after trusted resume');
 if(mode!=='synthetic-ended'||arm==='candidate')assert.equal(c.sourceThrows,0,'Unexpected native source factory throw');
 const close=c.closeSnapshots[0];assert(close&&Array.isArray(close.attachedIds));
 const detach=close.attachedIds.length===0;
 if(arm==='baseline')assert.equal(detach,false,'Baseline unexpectedly detached: control mismatch, not an automatic pass');
 else assert.equal(detach,true,'Candidate left explicit handlers attached at close entry');
 if(mode==='synthetic-ended'){
  assert(synthetic,'Missing synthetic event evidence');
  if(arm==='candidate'){assert.equal(synthetic.hadHandler,false);assert.equal(synthetic.beforeNodes,synthetic.afterNodes);assert.equal(synthetic.beforeAttempts,synthetic.afterAttempts)}
  else{assert.equal(synthetic.hadHandler,true,'Baseline retained-node control did not retain a handler');assert.equal(synthetic.afterAttempts-synthetic.beforeAttempts,1,'Baseline synthetic event must attempt exactly one actual refill');assert.equal(synthetic.beforeThrows,0,'Native factory threw before synthetic event');assert([0,1].includes(synthetic.afterThrows),'Unexpected synthetic factory throw count');assert.equal(c.sourceThrows,synthetic.afterThrows,'Factory throw outside recorded synthetic event');}
 }
 return {arm,mode,cycle,context:c.id,extensions:row.extensions,sourceNodes:c.nodes,closeFulfilled:c.closeFulfilled,explicitDetachBeforeClose:detach,expectedBaselineFailure:arm==='baseline',synthetic};
}
export function verifyMatrix(rows){
 const expected=[];for(const arm of ['baseline','candidate']){for(let cycle=0;cycle<8;cycle++)expected.push(`${arm}/normal/${cycle}`);for(const mode of ['start-first','start-second','synthetic-ended'])expected.push(`${arm}/${mode}/0`)}
 assert.equal(rows.length,22);assert.equal(new Set(rows.map(r=>r.extensions)).size,1,'Baseline/candidate selected different WASM feature paths');assert.deepEqual(rows.map(r=>`${r.arm}/${r.mode}/${r.cycle}`).sort(),expected.sort());
}
