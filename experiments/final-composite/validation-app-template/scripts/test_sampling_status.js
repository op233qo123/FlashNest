// Mock contract tests only: no browser/GPU/native acceptance claimed.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const context={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../App/Resources/Web/sampling-status.js'),'utf8'),context);
const api=context.window.FlashNestSamplingStatus;
const normalize=x=>JSON.parse(JSON.stringify(x));
function canvas(applied=.75,requested=.75,renderer='wgpu-webgl') {
 const attrs={'render-request':String(requested),'render-scale':String(applied),'renderer':renderer,'viewport-width':'1329','viewport-height':'861'};
 const listeners=new Map();
 return {listeners,addEventListener:(n,cb)=>listeners.set(n,cb),removeEventListener:(n,cb)=>{if(listeners.get(n)===cb)listeners.delete(n);},width:Math.round(1329*applied),height:Math.round(861*applied),clientWidth:443,clientHeight:287,attrs,getAttribute:n=>attrs[n.replace('data-flashnest-','')]??null};
}
let c=canvas();assert.equal(api.snapshot(c,.75,3).status,'applied');
for(const renderer of ['webgl','canvas']) {
 const state=api.snapshot(canvas(1,.75,renderer),.75,3);assert.equal(state.status,'fallback');assert.equal(state.applied,1);assert.equal(state.reason,'original-fallback');
}
assert.equal(api.snapshot(canvas(1,1),1,3).status,'applied');
for(const mutate of [x=>delete x.attrs['render-scale'],x=>x.attrs['render-scale']='0.9',x=>x.attrs.renderer='other',x=>x.width--,x=>x.attrs['viewport-width']='1328',x=>x.clientWidth=444,x=>x.attrs['render-request']='0.5']) {
 c=canvas();mutate(c);assert.equal(api.snapshot(c,.75,3).status,'unknown');
}
assert.equal(api.snapshot(canvas(.5,.75),.75,3).status,'unknown','unrequested appliedscale is not silently accepted');
for(const dpr of [0,-1,Infinity,NaN,9])assert.equal(api.snapshot(canvas(),.75,dpr).status,'unknown');
for(const requested of [0,.9,Infinity])assert.equal(api.snapshot(canvas(),requested,3).status,'unknown');
assert.equal(api.snapshot(null,.75,3).status,'unknown');
const messages=[],callbacks=new Map(),observers=[];let next=0,current=canvas();
class Observer {constructor(cb){this.cb=cb;observers.push(this);}observe(c,options){this.canvas=c;this.options=options;}disconnect(){this.disconnected=true;}}
const options={session:'00112233-4455-6677-8899-aabbccddeeff',requested:.75,getCanvas:()=>current,getDPR:()=>3,send:x=>messages.push(normalize(x)),schedule:cb=>{callbacks.set(++next,cb);return next;},cancel:id=>callbacks.delete(id),Observer};
function flush(){for(const [id,cb]of[...callbacks]){callbacks.delete(id);cb();}}
const reporter=api.create(options);assert.equal(messages[0].status,'unknown');assert.equal(messages[0].sequence,1);
reporter.refresh();reporter.refresh();assert.equal(callbacks.size,1,'coalesces observations');flush();assert.equal(messages.at(-1).status,'applied');
reporter.refresh();flush();assert.equal(messages.length,2,'deduplicates same state');
reporter.refresh(true);assert.equal(messages.at(-1).status,'unknown','invalidate before next frame');current=canvas(1,.75,'webgl');flush();assert.equal(messages.at(-1).status,'fallback');
current.listeners.get('webglcontextlost')();assert.equal(messages.at(-1).status,'unknown');reporter.refresh();flush();assert.equal(messages.at(-1).status,'unknown','loss cannot be relabeled active');current.listeners.get('webglcontextrestored')();flush();assert.equal(messages.at(-1).status,'fallback');
const oldCanvas=current,oldLost=oldCanvas.listeners.get('webglcontextlost');
current=canvas();reporter.refresh(true);flush();assert.equal(messages.at(-1).status,'applied');assert.equal(oldCanvas.listeners.size,0,'old context handlers detached');oldLost();assert.equal(messages.at(-1).status,'applied','late oldcanvas loss ignored');
for(let i=0;i<40;i++){current=canvas(i%2?1:.75);observers.at(-1).cb();flush();}
assert(messages.length>24,'status independent of capped diagnostics');
for(let i=1;i<messages.length;i++)assert.equal(messages[i].sequence,messages[i-1].sequence+1);
assert(messages.every(m=>m.session===options.session && m.type==='samplingStatus'));
reporter.refresh();reporter.dispose();assert.equal(callbacks.size,0);assert.equal(messages.at(-1).status,'unknown');const count=messages.length;reporter.refresh();observers.at(-1).cb();flush();assert.equal(messages.length,count,'late observer cannot report after dispose');
const newMessages=[];const newReporter=api.create({...options,session:'11223344-5566-7788-9900-aabbccddeeff',send:m=>newMessages.push(m)});assert.equal(newMessages[0].sequence,1);assert.equal(newMessages[0].status,'unknown');assert.notEqual(newMessages[0].session,messages[0].session);newReporter.dispose();
const bad=[];api.create({...options,session:null,send:m=>bad.push(m)}).refresh();flush();assert.equal(bad.length,0,'missing native session token is not emitted');
// Optional reporting infrastructure must never break playback.
current=canvas();let attempts=0;const retry=[];const fragile=api.create({...options,send:m=>{attempts++;if(attempts===2)throw Error('bridge unavailable');retry.push(m);}});
fragile.refresh();flush();assert.equal(retry.at(-1).status,'unknown');fragile.refresh();flush();assert.equal(retry.at(-1).status,'applied','failed initial send does not poison dedup');fragile.dispose();
for(const failure of [
 {getCanvas:()=>{throw Error('detached canvas');}},
 {schedule:()=>{throw Error('scheduler unavailable');}},
 {Observer:undefined},
 {Observer:class {constructor(){throw Error('observer unavailable');}}},
 {Observer:class {observe(){throw Error('observe failed');}disconnect(){}}},
 {getRoot:()=>({}),Observer:class {observe(){throw Error('root observe failed');}disconnect(){}}}
]){const seen=[];const probe=api.create({...options,...failure,send:m=>seen.push(m)});assert.doesNotThrow(()=>probe.refresh());assert.doesNotThrow(flush);assert.equal(seen.at(-1).status,'unknown');probe.refresh();flush();assert.equal(seen.at(-1).status,'unknown','repeated observation failure remains unknown');assert.doesNotThrow(()=>probe.dispose());}
current=canvas();let setupAttempts=0;const lossMessages=[];
class Flaky extends Observer {observe(...args){super.observe(...args);if(++setupAttempts===1)throw Error('transient observe failure');}}
const lossProbe=api.create({...options,Observer:Flaky,send:m=>lossMessages.push(m)});lossProbe.refresh();flush();current.listeners.get('webglcontextlost')();lossProbe.refresh();flush();assert.equal(lossMessages.at(-1).status,'unknown','samecanvas observer retry cannot clear context loss');current.listeners.get('webglcontextrestored')();flush();assert.equal(lossMessages.at(-1).status,'applied');lossProbe.dispose();
const root={};const replacementMessages=[];current=canvas();const replacement=api.create({...options,getRoot:()=>root,send:m=>replacementMessages.push(m)});replacement.refresh();flush();const rootWatch=observers.findLast(o=>o.options?.childList);const rootCount=replacementMessages.length;rootWatch.cb();flush();assert.equal(replacementMessages.length,rootCount,'unrelated shadow DOM mutation must not invalidate');current=canvas(1,.75,'webgl');rootWatch.cb();assert.equal(replacementMessages.at(-1).status,'unknown');flush();assert.equal(replacementMessages.at(-1).status,'fallback');replacement.dispose();assert(rootWatch.disconnected);
console.log('PASS sampling status: applied/fallback/unknown, strict dimensions, resize/contextloss, dedup, >24 updates, disposal and session reset (mock only)');
