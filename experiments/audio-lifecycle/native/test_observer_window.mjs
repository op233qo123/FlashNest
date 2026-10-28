import assert from 'node:assert/strict';
import {createNativeEventWindow} from './Web/observer-window.mjs';
let groups=0;
function test(name,fn){fn();groups++;console.log('PASS '+name)}
function setup(){const events=[],window=createNativeEventWindow(events);return{events,window}}
function receipt(cycle,start,endExclusive){return{kind:'case',ordinal:cycle,token:'case/'+cycle,cycle,start,endExclusive,count:endExclusive-start,bytes:123,sha256:'a'.repeat(64)}}
test('monotonic sequence survives exact acknowledged prefix drain',()=>{
 const {events,window}=setup();window.record('context',{context:1});window.record('attach',{context:1,node:1});
 const r=receipt(0,0,2);window.armReceipt(r);window.acceptReceipt(r);window.record('source',{context:2,node:2});
 assert.deepEqual(events,[{seq:2,kind:'source',context:2,node:2}]);assert.equal(window.status().start,2);
 const r2=receipt(1,2,3);window.armReceipt(r2);window.acceptReceipt(r2);assert.equal(window.status().endExclusive,3);
});
test('late old-context events during write and after acknowledgment remain visible',()=>{
 const {events,window}=setup();window.record('close-entry',{context:1});const r=receipt(0,0,1);window.armReceipt(r);
 window.record('close-fulfilled',{context:1});window.acceptReceipt(r);window.record('source',{context:1,node:9});
 assert.deepEqual(events.map(x=>[x.seq,x.context,x.kind]),[[1,1,'close-fulfilled'],[2,1,'source']]);
});
test('missing acknowledgment never drains or clears a pending receipt',()=>{
 const {events,window}=setup();window.record('source',{node:1});window.armReceipt(receipt(0,0,1));
 assert.equal(events.length,1);assert.equal(window.status().receiptPending,true);
 assert.throws(()=>window.markFinalBoundary());
});
test('wrong token cycle prefix count bytes or hash cannot acknowledge a case',()=>{
 for(const [key,value] of [['token','wrong'],['cycle',1],['start',1],['endExclusive',2],['count',0],['bytes',124],['sha256','b'.repeat(64)]]){
  const {events,window}=setup();window.record('source');const r=receipt(0,0,1);window.armReceipt(r);
  assert.throws(()=>window.acceptReceipt({...r,[key]:value}));assert.equal(events.length,1);assert.equal(window.status().receiptPending,true);
 }
});
test('duplicate unsolicited future and out-of-order receipts are rejected',()=>{
 const {window}=setup();window.record('source');assert.throws(()=>window.acceptReceipt(receipt(0,0,1)));
 assert.throws(()=>window.armReceipt(receipt(0,0,2)));assert.throws(()=>window.armReceipt(receipt(1,0,1)));
 const r=receipt(0,0,1);window.armReceipt(r);assert.throws(()=>window.armReceipt(r));window.acceptReceipt(r);
 assert.throws(()=>window.acceptReceipt(r));assert.throws(()=>window.armReceipt(receipt(0,1,1)));
});
test('overflow remains fatal and cannot be cured by drain',()=>{
 const {events,window}=setup();for(let i=0;i<4096;i++)window.record('source');const r=receipt(0,0,4096);window.armReceipt(r);
 window.record('one-too-many');assert.equal(events.length,4096);assert.equal(window.status().overflow,true);
 assert.throws(()=>window.acceptReceipt(r));assert.equal(events.length,4096);assert.throws(()=>window.markFinalBoundary());
});
test('final boundary never disables writer and latches later activity',()=>{
 const {events,window}=setup();window.record('close-fulfilled');const initial=window.markFinalBoundary();assert.equal(initial.finalBoundary,1);
 window.record('late-close',{context:1});assert.equal(window.status().postFinalActivity,1);assert.equal(events.at(-1).seq,1);
 assert.throws(()=>window.armReceipt(receipt(0,0,2)));assert.throws(()=>window.markFinalBoundary());
});
test('foreign sequence mutation and cap changes fail closed',()=>{
 assert.throws(()=>createNativeEventWindow([],8192));assert.throws(()=>createNativeEventWindow([{}]));
 const {events,window}=setup();window.record('source');events[0].seq=7;assert.throws(()=>window.status());
});
test('nonadjacent token reuse is rejected within the bounded eight-case mode',()=>{
 const {window}=setup();
 for(let cycle=0;cycle<2;cycle++){window.record('source');const r=receipt(cycle,cycle,cycle+1);window.armReceipt(r);window.acceptReceipt(r)}
 window.record('source');assert.throws(()=>window.armReceipt({...receipt(2,2,3),token:'case/0'}));
});
test('event metadata cannot override authoritative kind or sequence',()=>{
 const {events,window}=setup();assert.throws(()=>window.record('source',{seq:9}));assert.throws(()=>window.record('source',{kind:'fake'}));
 assert.equal(events.length,0);window.record('source');assert.equal(events[0].seq,0);
});
test('mid-case receipts preserve the current cycle and monotonically numbered tail',()=>{
 const {events,window}=setup();
 const chunk=(ordinal,start)=>({kind:'chunk',ordinal,token:'chunk/'+ordinal,cycle:0,start,endExclusive:start+1024,count:1024,bytes:1,sha256:'a'.repeat(64)});
 for(let n=0;n<6;n++){
  for(let i=0;i<1024;i++)window.record('source',{context:1});
  const r=chunk(n,n*1024);window.armReceipt(r);window.acceptReceipt(r);
 }
 assert.equal(window.status().endExclusive,6144);assert.equal(events.length,0);
 const end={...receipt(0,6144,6144),ordinal:6};window.armReceipt(end);window.acceptReceipt(end);
 window.record('source');const next={...receipt(1,6144,6145),ordinal:7};window.armReceipt(next);window.acceptReceipt(next);
});
test('chunk ordinal cycle kind highwater and fixed32chunk cap are independent',()=>{
 const {window}=setup();
 const chunk=(n)=>({kind:'chunk',ordinal:n,token:'c/'+n,cycle:0,start:n*1024,endExclusive:(n+1)*1024,count:1024,bytes:1,sha256:'a'.repeat(64)});
 for(let i=0;i<1024;i++)window.record('source');
 for(const bad of [{...chunk(0),ordinal:1},{...chunk(0),cycle:1},{...chunk(0),kind:'other'},{...chunk(0),count:1023,endExclusive:1023}])assert.throws(()=>window.armReceipt(bad));
 for(let n=0;n<32;n++){
  if(n)for(let i=0;i<1024;i++)window.record('source');
  const r=chunk(n);window.armReceipt(r);window.acceptReceipt(r);
 }
 for(let i=0;i<1024;i++)window.record('source');assert.throws(()=>window.armReceipt(chunk(32)));
 assert.equal(window.status().count,1024);assert.equal(window.status().receiptPending,false);
});
console.log(`PASS ${groups} native event-window primitive groups (not integrated/native acceptance)`);
