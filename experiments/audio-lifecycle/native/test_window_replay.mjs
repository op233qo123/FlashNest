import assert from 'node:assert/strict';
import {validateWindow,validateReceipt,metadataExtends,validateFinalTail,candidateClosedContexts} from './window-replay.mjs';
let groups=0;function test(name,body){body();groups++;console.log('PASS '+name)}
const receipt={token:'candidate/normal/0/evidence',cycle:0,start:0,endExclusive:3,count:3,bytes:100,sha256:'a'.repeat(64)};
function audio(start=3,count=1){
 const c={id:1,cycle:0,nodes:1,sourceAttempts:1,sourceThrows:0,starts:1,resumes:0,suspends:0,resumeFulfilled:0,suspendFulfilled:0,resumeRejected:0,suspendRejected:0,closeCalls:1,closeFulfilled:1,closeRejected:0,closeSnapshots:[{attachedIds:[]}]};
 return{overflow:false,contexts:[c],nodes:[{id:1,cycle:0,context:1,attached:false,attaches:1,detaches:1,starts:1}],
  events:Array.from({length:count},(_,i)=>({seq:start+i,kind:'close-fulfilled',context:1})),lastReceipt:receipt,
  eventWindow:{start,endExclusive:start+count,count,overflow:false,finalBoundary:null,postFinalActivity:0,receiptPending:false}};
}
function finalPair(){const terminal={audio:audio()},final={audio:audio(3,2)};final.audio.eventWindow.finalBoundary=5;return{terminal,final,status:structuredClone(final.audio.eventWindow)}}
test('final host tail extends the immutable terminal prefix',()=>{const x=finalPair();validateFinalTail(x.terminal,x.final,x.status,3,receipt)});
test('gaps duplicates unknown starts and missing receipts are rejected',()=>{
 for(const mutation of [a=>a.events[0].seq=4,a=>a.eventWindow.start=2,a=>a.events.push(a.events[0]),a=>a.lastReceipt=null]){
  const a=audio();mutation(a);assert.throws(()=>validateWindow(a,3,receipt));
 }
});
test('failed readback digest or bytes cannot authorize a prefix',()=>{
 const a=audio(0,3);a.lastReceipt=null;const{bytes,sha256,...eventWindow}=receipt;
 const entry={arm:'candidate',mode:'normal',eventWindow,evidence:{audio:a}};
 validateReceipt(entry,receipt,{bytes,sha256},0,0);
 assert.throws(()=>validateReceipt(entry,receipt,{bytes:101,sha256},0,0));
 assert.throws(()=>validateReceipt(entry,receipt,{bytes,sha256:'b'.repeat(64)},0,0));
 assert.throws(()=>validateReceipt(entry,{...receipt,token:'candidate/normal/1/evidence'},{bytes,sha256},0,0));
});
test('discarding global node or context metadata is rejected',()=>{
 for(const field of ['nodes','contexts']){const before=audio(),after=audio();after[field]=[];assert.throws(()=>metadataExtends(before,after))}
});
test('original close-entry attached IDs cannot be rewritten after a case',()=>{
 const before=audio(),after=audio();before.contexts[0].closeSnapshots[0].attachedIds=[1];assert.throws(()=>metadataExtends(before,after));
});
test('late terminal events cannot be dropped or replaced',()=>{
 const x=finalPair();x.final.audio.events[0].kind='different';assert.throws(()=>validateFinalTail(x.terminal,x.final,x.status,3,receipt));
});
test('activity between host snapshot and final cutoff is a failure',()=>{
 const x=finalPair();x.status.postFinalActivity=1;assert.throws(()=>validateFinalTail(x.terminal,x.final,x.status,3,receipt));
});
test('pending observed native Promise cannot pass final cutoff',()=>{
 const x=finalPair();x.final.audio.contexts[0].resumes=1;assert.throws(()=>validateFinalTail(x.terminal,x.final,x.status,3,receipt));
});
test('overflow and pending acknowledgment remain fatal',()=>{
 for(const mutation of [a=>a.overflow=true,a=>a.eventWindow.overflow=true,a=>a.eventWindow.receiptPending=true,a=>a.eventWindow.postFinalActivity=1]){
  const a=audio();mutation(a);assert.throws(()=>validateWindow(a,3,receipt));
 }
});
test('candidate interval permits source work before close and late detach/settlement',()=>{
 const a=audio(0,0);a.events=['source-attempt','source','attach','start','detach','close-entry','close-fulfilled','detach'].map((kind,seq)=>({seq,kind,context:1}));
 candidateClosedContexts(null,a);
 const next=structuredClone(a);next.events=[{seq:20,kind:'close-fulfilled',context:1},{seq:21,kind:'detach',context:1}];next.nodes[0].detaches++;
 candidateClosedContexts(a,next);
});
test('candidate same-interval source or handler activity after close is rejected',()=>{
 for(const kind of ['source-attempt','source','source-throw','attach','start','injected-start-error']){
  const a=audio(0,0);a.events=[{seq:0,kind:'close-entry',context:1},{seq:1,kind,context:1}];
  assert.throws(()=>candidateClosedContexts(null,a));
 }
});
test('old closed candidate context cannot refill or reattach after acknowledgment',()=>{
 const before=audio();for(const key of ['nodes','sourceAttempts','sourceThrows','starts']){
  const after=audio();after.events=[];after.contexts[0][key]++;assert.throws(()=>candidateClosedContexts(before,after));
 }
 for(const key of ['attaches','starts']){const after=audio();after.nodes[0][key]++;assert.throws(()=>candidateClosedContexts(before,after))}
 const after=audio();after.nodes[0].attached=true;assert.throws(()=>candidateClosedContexts(before,after));
});
test('candidate final-tail refill is rejected while baseline negative control remains allowed',()=>{
 const x=finalPair();x.final.audio.events[1].kind='source-attempt';x.final.audio.contexts[0].sourceAttempts++;
 assert.throws(()=>validateFinalTail(x.terminal,x.final,x.status,3,receipt,{arm:'candidate'}));
 validateFinalTail(x.terminal,x.final,x.status,3,receipt,{arm:'baseline'});
});
test('candidate repeated terminal prefix is not misclassified as post-close source work',()=>{
 const x=finalPair();x.terminal.audio.events[0].kind='start';x.final.audio.events[0].kind='start';
 validateFinalTail(x.terminal,x.final,x.status,3,receipt,{arm:'candidate'});
});
console.log(`PASS ${groups} final-tail/readback replay groups (synthetic only)`);
