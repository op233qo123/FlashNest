// Offline validation of native-only bounded event windows. No engine execution.
import assert from 'node:assert/strict';
const integer=value=>Number.isSafeInteger(value)&&value>=0;
export function validateWindow(audio,start,lastReceipt,{final=false}={}){
 assert(audio&&Array.isArray(audio.events)&&Array.isArray(audio.nodes)&&Array.isArray(audio.contexts));
 assert.equal(audio.overflow,false);assert(audio.nodes.length<=4096&&audio.events.length<=4096&&audio.contexts.length<=8);
 const w=audio.eventWindow;assert(w&&integer(start)&&integer(w.start)&&integer(w.endExclusive)&&integer(w.count));
 assert.equal(w.start,start);assert.equal(w.endExclusive-w.start,w.count);assert.equal(w.count,audio.events.length);
 assert.equal(w.overflow,false);assert.equal(w.receiptPending,false);assert.equal(w.postFinalActivity,0);
 assert.equal(w.finalBoundary,final?w.endExclusive:null);
 assert.deepEqual(audio.lastReceipt,lastReceipt);
 for(let i=0;i<audio.events.length;i++)assert.equal(audio.events[i].seq,start+i,'Missing/duplicate/reordered event');
 for(let i=0;i<audio.nodes.length;i++)assert.equal(audio.nodes[i].id,i+1,'Node metadata reset or gap');
 for(let i=0;i<audio.contexts.length;i++)assert.equal(audio.contexts[i].id,i+1,'Context metadata reset or gap');
 return w.endExclusive;
}
export function validateReceipt(entry,receipt,{bytes,sha256},cycle,start){
 assert.deepEqual(Object.keys(receipt).sort(),['token','cycle','start','endExclusive','count','bytes','sha256'].sort());
 assert.equal(receipt.token,`${entry.arm}/${entry.mode}/${cycle}/evidence`);assert.equal(receipt.cycle,cycle);
 assert.equal(receipt.start,start);assert(integer(receipt.endExclusive)&&integer(receipt.count));
 assert.equal(receipt.count,receipt.endExclusive-start);assert(receipt.count<=4096);
 assert.equal(receipt.bytes,bytes);assert(bytes>0&&bytes<=2*1024*1024);assert.equal(receipt.sha256,sha256);
 assert(/^[a-f0-9]{64}$/.test(sha256));
 const {bytes:unusedBytes,sha256:unusedHash,...window}=receipt;
 assert.deepEqual(entry.eventWindow,window);assert.equal(entry.evidence.audio.eventWindow.endExclusive,receipt.endExclusive);
}
export function metadataExtends(previous,next){
 if(!previous)return;
 for(const [name,counters] of [['nodes',['attaches','detaches','starts']],['contexts',['nodes','sourceAttempts','sourceThrows','starts','resumes','suspends','resumeFulfilled','suspendFulfilled','resumeRejected','suspendRejected','closeCalls','closeFulfilled','closeRejected']]]){
  assert(next[name].length>=previous[name].length,'Global metadata was discarded');
  for(let i=0;i<previous[name].length;i++){
   const old=previous[name][i],now=next[name][i];for(const key of ['id','cycle',...(name==='nodes'?['context']:[])])assert.equal(now[key],old[key]);
   for(const key of counters)assert(integer(old[key])&&integer(now[key])&&now[key]>=old[key],'Metadata counter regressed: '+key);
   if(name==='contexts')assert.deepEqual(now.closeSnapshots.slice(0,old.closeSnapshots.length),old.closeSnapshots,'Close-entry ownership control changed');
  }
 }
}
// Candidate-only: retained baseline handlers are deliberate negative controls.
// Each receipt seals metadata, not just the current event array. Closed candidate
// contexts cannot start producing sources/handlers again in a later window.
export function candidateClosedContexts(previous,next){
 const closed=new Set((previous?.contexts??[]).filter(c=>c.closeCalls>0).map(c=>c.id));
 const firstNew=previous?.eventWindow.endExclusive??0;
 const sourceActivity=new Set(['source-attempt','source','source-throw','attach','start','injected-start-error']);
 for(const event of next.events){
  if(event.seq<firstNew)continue; // host snapshot repeats the immutable terminal prefix
  if(event.kind==='close-entry')closed.add(event.context);
  else if(sourceActivity.has(event.kind))assert(!closed.has(event.context),'Candidate source/handler activity after close entry');
 }
 for(const old of previous?.contexts??[]){
  if(old.closeCalls===0)continue;
  const now=next.contexts.find(c=>c.id===old.id);assert(now,'Closed context metadata missing');
  for(const key of ['nodes','sourceAttempts','sourceThrows','starts'])assert.equal(now[key],old[key],'Candidate closed-context counter changed: '+key);
 }
 for(const old of previous?.nodes??[]){
  if(!closed.has(old.context))continue;
  // Only previously closed contexts were sealed in the preceding snapshot.
  if(!previous.contexts.some(c=>c.id===old.context&&c.closeCalls>0))continue;
  const now=next.nodes.find(n=>n.id===old.id);assert(now,'Closed node metadata missing');
  for(const key of ['attaches','starts'])assert.equal(now[key],old[key],'Candidate closed-node counter changed: '+key);
 }
 for(const node of next.nodes){
  if(next.contexts.some(c=>c.id===node.context&&c.closeCalls>0))assert.equal(node.attached,false,'Candidate retained/re-attached handler after close');
 }
}
export function validateFinalTail(terminal,finalSnapshot,finalStatus,start,receipt,{arm}={}){
 validateWindow(terminal.audio,start,receipt);validateWindow(finalSnapshot.audio,start,receipt,{final:true});
 assert.deepEqual(finalSnapshot.audio.events.slice(0,terminal.audio.events.length),terminal.audio.events,'Terminal tail lost/replaced before host cutoff');
 metadataExtends(terminal.audio,finalSnapshot.audio);
 if(arm==='candidate')candidateClosedContexts(terminal.audio,finalSnapshot.audio);
 assert.deepEqual(finalStatus,finalSnapshot.audio.eventWindow,'Activity occurred after host final snapshot');
 for(const c of finalSnapshot.audio.contexts){
  assert.equal(c.resumes,c.resumeFulfilled+c.resumeRejected);assert.equal(c.suspends,c.suspendFulfilled+c.suspendRejected);
  assert.equal(c.closeCalls,c.closeFulfilled+c.closeRejected);
 }
}
