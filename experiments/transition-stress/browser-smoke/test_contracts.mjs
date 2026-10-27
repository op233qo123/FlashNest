// Pure evidence/parser mocks. No browser, runtime, compiler, SWF or network run.
import assert from 'node:assert/strict';
import {ALLOWED_KINDS,parseTrace,checkHealthy,validateMilestone,validateSummary} from './contracts.mjs';
let groups=0;
function check(name,fn){fn();groups++;console.log('PASS '+name)}
function record(kind='READY',generation=0,overrides={}){
 const x={bootToken:'0.125',generation,rootHeartbeat:generation*3,pointerCount:generation,keyCount:0,ready:1,activeChildGeneration:generation,childHeartbeat:0,errors:0,unloadCalls:generation,unloadEvents:generation,...overrides};
 return ['LT',kind,x.bootToken,x.generation,x.rootHeartbeat,x.pointerCount,x.keyCount,x.ready,x.activeChildGeneration,x.childHeartbeat,x.errors,x.unloadCalls,x.unloadEvents,...(x.detail===undefined?[]:[x.detail])].join('|');
}
function evidence(generation=3){
 return {loaded:true,observerInstalled:true,playing:true,overflow:false,errors:[],renderer:'webgl',extensions:'ON',context:{kind:'webgl2',lost:false,dpr:1,drawingBufferWidth:320,drawingBufferHeight:240},traces:[record('BOOT',0,{ready:0,activeChildGeneration:-1,detail:'unload'}),...Array.from({length:generation+1},(_,g)=>record('READY',g))],actions:[{name:'resume',trusted:true}],pointers:Array.from({length:generation},()=>['pointerdown','pointerup'].map(kind=>({kind,trusted:true,pointerId:1,pointerType:'mouse',button:0,x:160,y:120}))).flat()};
}
check('all fixed allowed markers parse canonical numeric fields and optional detail',()=>{
 for(const kind of ALLOWED_KINDS){
  const parsed=parseTrace(record(kind,0));assert.equal(parsed.kind,kind);assert.equal(parsed.generation,0);assert.equal(parsed.bootToken,'0.125');assert.equal(parsed.childHeartbeat,0);
  if(!['STATE','READY'].includes(kind))assert.equal(parseTrace(record(kind,0,{detail:'scene-0'})).detail,'scene-0');
 }
 assert.equal(parseTrace(record('BOOT',0,{bootToken:'0',ready:0,activeChildGeneration:-1})).bootToken,'0');
 assert.equal(parseTrace(record('BOOT',0,{bootToken:'1.1102230246251565e-16'})).bootToken,'1.1102230246251565e-16');
});
check('STATE/READY are exactly 13 fields; other markers are exactly 13 or 14',()=>{
 for(const kind of ['STATE','READY'])assert.throws(()=>parseTrace(record(kind,0,{detail:'forbidden'})));
 assert.throws(()=>parseTrace(record('OPEN',0,{detail:'extra|field'})));
 assert.throws(()=>parseTrace(record('READY').split('|').slice(0,12).join('|')));
 assert.throws(()=>parseTrace(record('READY').replace('LT|','XX|')));assert.throws(()=>parseTrace(record('NOT_ALLOWED')));assert.throws(()=>parseTrace({}));
});
check('malformed, unsafe, negative, noncanonical or out-of-range numeric values fail closed',()=>{
 for(const field of ['generation','rootHeartbeat','pointerCount','keyCount','ready','activeChildGeneration','childHeartbeat','errors','unloadCalls','unloadEvents'])for(const value of ['NaN','Infinity','1.2','1e2','+1','01','',' 1','9007199254740992',-2])assert.throws(()=>parseTrace(record('OPEN',0,{[field]:value})),field+' '+value);
 for(const field of ['generation','rootHeartbeat','pointerCount','keyCount','ready','childHeartbeat','errors','unloadCalls','unloadEvents'])assert.throws(()=>parseTrace(record('OPEN',0,{[field]:-1})));
 for(const value of ['','1','-1','NaN','Infinity','0.50',' 0.5','-0'])assert.throws(()=>parseTrace(record('BOOT',0,{bootToken:value})));
 assert.throws(()=>parseTrace(record('OPEN',4)));assert.throws(()=>parseTrace(record('OPEN',0,{ready:2})));assert.throws(()=>parseTrace(record('OPEN',0,{activeChildGeneration:4})));
});
check('four intended READY snapshots and final exact trusted actions pass',()=>{
 for(let generation=0;generation<=3;generation++)assert.equal(validateMilestone(evidence(generation),{generation,bootToken:'0.125'}).generation,generation);
 const summary=validateSummary(evidence());assert.deepEqual(summary.milestones.map(x=>x.generation),[0,1,2,3]);assert.equal(summary.trustedHostResumes,1);assert.equal(summary.trustedCanvasClicks,3);
 const alternate=evidence();alternate.context.kind='webgl';validateSummary(alternate);
});
check('milestone payload mismatches each fail independently',()=>{
 for(const [field,value]of [['pointerCount',7],['keyCount',1],['ready',0],['activeChildGeneration',2],['errors',1],['unloadCalls',2],['unloadEvents',2]]){
  const e=evidence();e.traces[4]=record('READY',3,{[field]:value});assert.throws(()=>validateSummary(e),field);
 }
 const e=evidence();assert.throws(()=>validateMilestone(e,{generation:3,bootToken:'0.875'}));assert.throws(()=>validateMilestone(e,{generation:4}));
});
check('no missing, duplicate, reordered, prematurely advanced or rebooted READY may pass',()=>{
 for(const mutate of [e=>e.traces.pop(),e=>e.traces.push(record('READY',3)),e=>[e.traces[1],e.traces[2]]=[e.traces[2],e.traces[1]],e=>e.traces[2]=record('READY',1,{bootToken:'0.75'}),e=>e.traces[0]=record('BOOT',0,{bootToken:'0.75'})]){const e=evidence();mutate(e);assert.throws(()=>validateSummary(e))}
 assert.throws(()=>validateMilestone(evidence(1),{generation:0}));assert.throws(()=>validateMilestone(evidence(0),{generation:1}));
});
check('transient unload events need not match completed milestone counts or a total order',()=>{
 const e=evidence();e.traces.splice(2,0,record('UNLOAD_EVENT',0,{ready:0,activeChildGeneration:-1,pointerCount:1,unloadCalls:0,unloadEvents:1,detail:'scene-0'}),record('CHILD_REMOVED',1,{ready:0,activeChildGeneration:-1,pointerCount:1,unloadCalls:1,unloadEvents:1,detail:'scene-0'}),record('PROGRESS',1,{ready:0,activeChildGeneration:-1}),record('RESIZE',1));validateSummary(e);
});
check('trace errors, unknown records, missing data and overflow cannot be hidden by READY',()=>{
 for(const mutate of [e=>e.errors.push('real exception'),e=>e.overflow=true,e=>delete e.overflow,e=>e.traces.push(record('ERROR',3)),e=>e.traces.push(record('OPEN',3,{errors:1})),e=>e.traces.push('other trace'),e=>e.traces=[],e=>delete e.errors]){const e=evidence();mutate(e);assert.throws(()=>validateSummary(e))}
});
check('reported renderer plus actual live DPR-1 WebGL drawing buffer are required',()=>{
 for(const mutate of [e=>e.loaded=false,e=>e.observerInstalled=false,e=>e.playing=false,e=>e.renderer='wgpu-webgl',e=>delete e.renderer,e=>delete e.extensions,e=>e.extensions='unknown',e=>delete e.context,e=>e.context.kind='2d',e=>e.context.lost=true,e=>delete e.context.lost,e=>e.context.dpr=2,e=>e.context.drawingBufferWidth=0,e=>e.context.drawingBufferHeight=-1,e=>e.context.drawingBufferWidth=1.25]){const e=evidence();mutate(e);assert.throws(()=>validateSummary(e))}
});
check('early health check permits not-yet-loaded empty traces but never errors or overflow',()=>{
 const early={overflow:false,errors:[],traces:[]};checkHealthy(early);assert.throws(()=>validateMilestone(early,{generation:0}));
 assert.throws(()=>checkHealthy({...early,overflow:true}));assert.throws(()=>checkHealthy({...early,errors:['exception']}));assert.throws(()=>checkHealthy({...early,traces:[record('ERROR')]}));
});
check('summary requires exactly one trusted resume plus three trusted canvas pointer pairs',()=>{
 for(const mutate of [e=>e.actions=[],e=>e.actions.push({name:'resume',trusted:true}),e=>e.actions[0].name='other',e=>e.actions[0].trusted=false,e=>delete e.actions,e=>e.pointers.pop(),e=>e.pointers.push({trusted:true}),e=>e.pointers[1].trusted=false,e=>delete e.pointers[2].trusted,e=>delete e.pointers,e=>e.pointers[0].kind='click',e=>e.pointers[1].pointerId=2,e=>e.pointers[0].button=1,e=>e.pointers[0].pointerType='touch']){const e=evidence();mutate(e);assert.throws(()=>validateSummary(e))}
});
console.log(`PASS ${groups} Loader transition contract mock groups; no runtime/browser execution`);
