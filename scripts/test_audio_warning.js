/* UI-state contracts only. No real AudioContext or audible-output evidence. */
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs'), path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../App/Resources/Web/audio-warning.js'), 'utf8');
function fixture() {
  const listeners = new Map(), clicks = new Map(), records = [];
  const player = {addEventListener:(n,f)=>listeners.set(n,f), removeEventListener:(n,f)=>{if(listeners.get(n)===f)listeners.delete(n);}};
  const panel = {}, message = {}, button = {addEventListener:(n,f)=>clicks.set(n,f), removeEventListener:(n,f)=>{if(clicks.get(n)===f)clicks.delete(n);}};
  const context = {window:{}}; vm.runInNewContext(source, context);
  let active = true, retry = ()=>{}, count = 0;
  const ui = context.window.FlashNestAudioWarning.create({player,panel,message,button,text:k=>k,
    isActive:()=>active,retry:()=>{count++;return retry();},diagnostic:s=>records.push(s)});
  const base = {schema:1,contextId:1,operationId:0,intentId:0,phase:'bind',operation:'none',status:'bound',state:'suspended',current:true,retryEligible:false};
  const send = (value={},target=player)=>listeners.get('ruffle-audio-status')?.({target,detail:{...base,...value}});
  const operation = (id,status='pending',extra={}) => send({operationId:id,intentId:id,phase:'core-play',operation:'resume',status,...extra});
  const warning = id=>{operation(id);operation(id,'rejected',{retryEligible:true});};
  return {ui,panel,message,button,records,send,operation,warning,player,listeners,
    setActive(value){active=value;ui.synchronize();},setRetry(value){retry=value;},get count(){return count;},
    click(trusted=true){return clicks.get('click')?.({isTrusted:trusted,currentTarget:button});}};
}
(async()=>{
  let f=fixture(); assert.equal(f.panel.hidden,true);assert.equal(f.button.disabled,true);
  f.send();f.warning(1);assert.equal(f.panel.hidden,false);assert.equal(f.button.disabled,false);
  assert.equal(f.message.textContent,'warning');
  const before=f.records.length;f.operation(1,'rejected',{retryEligible:true});assert.equal(f.records.length,before,'Duplicate status is a no-op');
  f.send({contextId:2},{});f.send({contextId:2,schema:2});f.send({contextId:NaN});f.send({contextId:2,state:'unknown'});
  assert.equal(f.panel.hidden,false,'Malformed/foreign status cannot clear warning');
  await f.click(false);f.setActive(false);await f.click();assert.equal(f.count,0);
  f.setActive(true);f.setRetry(()=>f.operation(2));await f.click();await f.click();
  assert.equal(f.count,1);assert.equal(f.button.disabled,true);assert.equal(f.message.textContent,'waiting');
  f.operation(1,'fulfilled',{state:'running'});assert.equal(f.panel.hidden,false);
  f.operation(2,'fulfilled',{state:'running',current:false});assert.equal(f.panel.hidden,false);
  f.operation(2,'fulfilled',{state:'running'});assert.equal(f.panel.hidden,true,'Only exact live retry clears');

  f=fixture();f.send();f.warning(1);f.setRetry(()=>f.operation(2));await f.click();
  f.operation(2,'rejected',{retryEligible:true});assert.equal(f.panel.hidden,false);assert.equal(f.button.disabled,false);
  f.setRetry(()=>f.operation(3));await f.click();f.operation(4);
  f.operation(3,'fulfilled',{state:'running'});f.operation(4,'fulfilled',{state:'running'});
  assert.equal(f.panel.hidden,false,'A later automatic resume is not explicit retry confirmation');
  f.setRetry(()=>f.operation(5));await f.click();f.setActive(false);
  f.operation(5,'fulfilled',{state:'running'});f.setActive(true);assert.equal(f.panel.hidden,false,'Inactive intent invalidates explicit retry');

  f=fixture();f.send();f.warning(1);f.setRetry(()=>{});await f.click();
  assert.equal(f.panel.hidden,false);assert.equal(f.button.disabled,false,'Void API return is not success');
  f.operation(2,'fulfilled',{state:'running'});assert.equal(f.panel.hidden,false,'Completion without observed pending cannot clear');
  const unknown=new Error('unknown native failure');f.setRetry(()=>{throw unknown;});
  await assert.rejects(f.click(),error=>error===unknown,'Unknown synchronous retry error keeps original rejected Promise identity');
  assert.equal(f.panel.hidden,false);

  f=fixture();f.send();f.warning(1);f.setRetry(()=>f.operation(2));await f.click();
  assert.equal(f.button.disabled,true);await f.click();assert.equal(f.count,1,'Unsettled resume cannot overlap another explicit retry');
  f.send({phase:'release',operation:'none',status:'released',operationId:2,intentId:3,current:false});
  assert.equal(f.panel.hidden,true);f.send();f.warning(3);assert.equal(f.panel.hidden,true,'Retired context cannot bind again');
  f.send({contextId:2});f.operation(1,'pending',{contextId:2});f.operation(1,'rejected',{contextId:2,retryEligible:true});
  assert.equal(f.panel.hidden,false);f.operation(2,'fulfilled',{state:'running'});assert.equal(f.panel.hidden,false);
  f.ui.dispose();assert.equal(f.panel.hidden,true);assert.equal(f.listeners.size,0);assert.equal(f.button.disabled,true);

  f=fixture();f.send();f.operation(1);f.operation(1,'rejected',{retryEligible:false});assert.equal(f.panel.hidden,true,'Unknown rejection is not UI-classified');
  f.operation(2);f.operation(2,'rejected',{retryEligible:true,state:'closed'});assert.equal(f.panel.hidden,true,'Closed context is not retryable');
  for(let i=3;i<50;i++)f.warning(i);assert.equal(f.records.length,16,'Diagnostics are bounded');
  console.log('Audio warning: 7 state/intent/ownership groups PASS (mocked only)');
})().catch(error=>{console.error(error);process.exitCode=1;});
