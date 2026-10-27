import assert from 'node:assert/strict';
import {warningText,warningLinkText,warningLink,validateWarning,dismissHardwareWarning} from './hardware-warning.mjs';
const valid={visible:true,id:'hardware-acceleration-modal',text:warningText,linkText:warningLinkText,link:warningLink,closeCount:1,closeHit:true,point:[407,22]};
assert.deepEqual(validateWarning(valid),[407,22]);
for(const delta of [{id:'panic'},{text:'another warning'},{link:'https://example.invalid/'},{closeCount:2},{closeHit:false},{point:[NaN,22]}])assert.throws(()=>validateWarning({...valid,...delta}));
function hooks(state=valid){
 const calls=[];let gone=false;
 return {calls,args:{inspect:async()=>gone?{visible:false}:state,capture:async()=>{calls.push('capture');return {sha:'mock-only'}},record:async e=>{calls.push('record');assert.equal(e.state.id,valid.id)},click:async(x,y)=>{calls.push('trusted-click');assert.deepEqual([x,y],valid.point);gone=true},waitGone:async()=>{calls.push('gone');assert(gone)}}};
}
let h=hooks();assert.equal(await dismissHardwareWarning(h.args),true);assert.deepEqual(h.calls,['capture','record','trusted-click','gone']);
h=hooks({visible:false});assert.equal(await dismissHardwareWarning(h.args),false);assert.deepEqual(h.calls,[]);
h=hooks({...valid,text:'unknown'});await assert.rejects(()=>dismissHardwareWarning(h.args));assert.deepEqual(h.calls,[]);
h=hooks();h.args.capture=async()=>{throw Error('capture failed')};await assert.rejects(()=>dismissHardwareWarning(h.args));assert.deepEqual(h.calls,[]);
h=hooks();h.args.waitGone=async()=>{throw Error('still visible')};await assert.rejects(()=>dismissHardwareWarning(h.args));assert.equal(h.calls.filter(c=>c==='trusted-click').length,1,'No dismissal retry');
console.log('PASS exact pinned hardware warning, evidence-before-one-trusted-click, no unknown/modal retry bypass');
