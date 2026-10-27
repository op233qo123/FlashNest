// Original Loader fixture milestones only: not a complete Adobe event ordering.
import assert from 'node:assert/strict';

export const ALLOWED_KINDS=Object.freeze(['BOOT','LOAD_BEGIN','LOAD_RETURN','OPEN','PROGRESS','INIT','COMPLETE','READY','POINTER','UNLOAD_BEGIN','UNLOAD_EVENT','UNLOAD_RETURN','CHILD_ADDED','CHILD_REMOVED','RESIZE','STATE','ERROR']);
const kinds=new Set(ALLOWED_KINDS);
const numericFields=['generation','rootHeartbeat','pointerCount','keyCount','ready','activeChildGeneration','childHeartbeat','errors','unloadCalls','unloadEvents'];
function integer(text,name){
 assert(typeof text==='string'&&/^(?:0|[1-9][0-9]*|-1)$/.test(text),'Noncanonical integer: '+name);
 const value=Number(text);assert(Number.isSafeInteger(value),'Unsafe integer: '+name);
 assert(value>=0||(name==='activeChildGeneration'&&value===-1),'Negative field: '+name);
 return value;
}
export function parseTrace(text){
 assert(typeof text==='string','Trace must be a string');
 const fields=text.split('|');assert.equal(fields[0],'LT','Unexpected trace prefix');
 const kind=fields[1];assert(kinds.has(kind),'Unknown LT kind');
 assert(kind==='STATE'||kind==='READY'?fields.length===13:fields.length===13||fields.length===14,'Wrong LT field count');
 const bootToken=fields[2],bootValue=Number(bootToken);
 // Math.random() is coerced once with String(), including small exponential values.
 assert(bootToken!==''&&Number.isFinite(bootValue)&&bootValue>=0&&bootValue<1&&String(bootValue)===bootToken,'Invalid boot token');
 const result={raw:text,kind,bootToken};
 numericFields.forEach((name,index)=>{result[name]=integer(fields[index+3],name)});
 assert(result.generation<=3,'Generation out of range');
 assert(result.ready===0||result.ready===1,'Invalid ready bit');
 assert(result.activeChildGeneration<=3,'Child generation out of range');
 if(fields.length===14)result.detail=fields[13];
 return result;
}
export function checkHealthy(evidence){
 assert(evidence&&evidence.overflow===false,'Evidence missing or overflowed');
 assert(Array.isArray(evidence.errors)&&evidence.errors.length===0,'Unexpected runtime/page errors');
 assert(Array.isArray(evidence.traces),'Missing trace collection');
 const traces=evidence.traces.map(parseTrace),bootToken=traces[0]?.bootToken??null;
 for(const trace of traces){
  assert.equal(trace.bootToken,bootToken,'Root boot changed');
  assert(trace.kind!=='ERROR'&&trace.errors===0,'Fixture reported an error');
 }
 return {traces,bootToken};
}
function inspect(evidence){
 const inspected=checkHealthy(evidence);
 assert(evidence.loaded===true&&evidence.observerInstalled===true&&evidence.playing===true,'Missing loaded, observed, playing milestones');
 assert.equal(evidence.renderer,'webgl','Wrong reported renderer');
 assert(['ON','OFF'].includes(evidence.extensions),'Missing actual WASM feature-path metadata');
 const context=evidence.context;
 assert(context&&['webgl','webgl2'].includes(context.kind)&&context.lost===false&&context.dpr===1,'Missing actual live WebGL context at DPR 1');
 assert(Number.isInteger(context.drawingBufferWidth)&&context.drawingBufferWidth>0&&Number.isInteger(context.drawingBufferHeight)&&context.drawingBufferHeight>0,'Empty or invalid actual WebGL drawing buffer');
 assert(inspected.traces.length>0,'No fixture traces');
 return inspected;
}
function completedReady(trace,generation,bootToken){
 assert.equal(trace.kind,'READY');assert.equal(trace.generation,generation,'READY sequence must be 0, 1, 2, 3');
 assert.equal(trace.bootToken,bootToken,'READY boot changed');
 assert.equal(trace.pointerCount,generation,'Unexpected stage pointer count');
 assert.equal(trace.keyCount,0,'Unexpected Enter/key interaction');
 assert.equal(trace.ready,1,'READY is not ready');
 assert.equal(trace.activeChildGeneration,generation,'Wrong active child generation');
 assert.equal(trace.errors,0,'Fixture errors at READY');
 assert.equal(trace.unloadCalls,generation,'Wrong completed unload call count');
 assert.equal(trace.unloadEvents,generation,'Wrong observed UNLOAD event count');
 return trace;
}
export function validateMilestone(evidence,{generation,bootToken=null}){
 assert(Number.isInteger(generation)&&generation>=0&&generation<=3,'Invalid requested milestone');
 const inspected=inspect(evidence),ready=inspected.traces.filter(t=>t.kind==='READY');
 assert.equal(ready.length,generation+1,'Missing, duplicate or premature READY milestone');
 if(bootToken!==null)assert.equal(inspected.bootToken,bootToken,'Root boot changed between snapshots');
 ready.forEach((trace,index)=>completedReady(trace,index,inspected.bootToken));
 return ready[generation];
}
export function validateSummary(evidence){
 validateMilestone(evidence,{generation:3});
 assert(Array.isArray(evidence.actions),'Missing trusted host actions');
 assert.deepEqual(evidence.actions.map(action=>action.name),['resume'],'Expected exactly one host resume');
 assert(evidence.actions.every(action=>action.trusted===true),'Untrusted host resume');
 assert(Array.isArray(evidence.pointers)&&evidence.pointers.length===6,'Expected three canvas pointer-down/up pairs');
 assert.deepEqual(evidence.pointers.map(p=>p.kind),['pointerdown','pointerup','pointerdown','pointerup','pointerdown','pointerup']);
 assert(evidence.pointers.every(p=>p.trusted===true&&p.pointerType==='mouse'&&p.button===0&&Number.isInteger(p.pointerId)),'Invalid/untrusted canvas pointer event');
 for(let i=0;i<6;i+=2)assert.equal(evidence.pointers[i].pointerId,evidence.pointers[i+1].pointerId,'Pointer pair identity changed');
 return {milestones:evidence.traces.map(parseTrace).filter(t=>t.kind==='READY'),trustedHostResumes:1,trustedCanvasClicks:3};
}
