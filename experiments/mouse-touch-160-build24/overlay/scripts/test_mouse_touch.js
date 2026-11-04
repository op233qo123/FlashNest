'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const source = fs.readFileSync(process.env.MOUSE_SOURCE || path.join(__dirname,'../App/Resources/Web/mouse-touch.js'),'utf8');
class Target {
  constructor() { this.listeners={}; }
  addEventListener(n,f) { (this.listeners[n]??=[]).push(f); }
  removeEventListener(n,f) { this.listeners[n]=(this.listeners[n]||[]).filter(x=>x!==f); }
  dispatchEvent(e) { for(const f of this.listeners[e.type]||[]) { f(e); if(e.stopped) break; } return true; }
}
function setup(enabled=false) {
  const window=new Target(), document=new Target(), canvas=new Target();
  const sent=[], capture=new Set(), cursor={style:{},hidden:true}; let r={left:30,top:60,width:401,height:201};
  canvas.getBoundingClientRect=()=>r;
  canvas.setPointerCapture=id=>capture.add(id);canvas.hasPointerCapture=id=>capture.has(id);
  canvas.releasePointerCapture=id=>{capture.delete(id);};
  const dispatch=canvas.dispatchEvent.bind(canvas);
  canvas.dispatchEvent=e=>{if(e.pointerType==='mouse')sent.push(e);return dispatch(e);};
  class PointerEvent { constructor(type,init) {Object.assign(this,init,{type});} }
  let time=0, nextTimer=1;
  const timers=new Map();
  const setTimeout=(callback,delay=0)=>{const id=nextTimer++;timers.set(id,{at:time+Math.max(0,delay),callback});return id;};
  const clearTimeout=id=>timers.delete(id);
  function advance(ms) {
    const end=time+ms;
    for (;;) {
      const next=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at||a[0]-b[0])[0];
      if(!next)break;
      time=next[1].at;timers.delete(next[0]);next[1].callback();
    }
    time=end;
  }
  class FakeDate extends Date { static now(){return time;} }
  Object.assign(window,{setTimeout,clearTimeout,performance:{now:()=>time}});
  vm.runInNewContext(source,{window,document,PointerEvent,Math,Map,Set,Object,setTimeout,clearTimeout,performance:window.performance,Date:FakeDate});
  const controller=window.FlashNestMouseTouch.create({canvas,host:{focus(){}},cursor,enabled});controller.initialize();
  function event(type,id=1,x=100,y=100,dt=10, overdueInput=false) {if(overdueInput)time+=dt;else advance(dt);const e={type,pointerId:id,pointerType:'touch',clientX:x,clientY:y,timeStamp:time,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}};canvas.dispatchEvent(e);return e;}
  return {controller,sent,event,cursor,capture,window,document,advance,timers,now:()=>time,resize:v=>r=v};
}
const clicks=s=>s.sent.filter(e=>e.type==='pointerdown').map(e=>e.button);
// Default-off must be a completely unmodified direct-touch path.
{const s=setup();assert.equal(s.sent.length,0);assert.equal(s.event('pointerdown').stopped,undefined);assert.equal(s.cursor.hidden,true);}
// Single tap only emits one paired left click; movement is never held down.
{const s=setup(true);s.event('pointerdown');s.event('pointerup');assert.deepEqual(clicks(s),[0]);assert.equal(s.sent.filter(e=>e.type==='pointerup').length,0);s.advance(100);assert.equal(s.sent.filter(e=>e.type==='pointerup').length,1);assert.equal(s.capture.size,0);}
// Relative dragging can reach all CSS canvas corners independent of DPR and margins.
{const s=setup(true);s.event('pointerdown');for(const [x,y] of [[-1000,-1000],[1000,1000],[-1000,1000],[1000,-1000]])s.event('pointermove',1,x,y);s.event('pointerup',1,1000,-1000);assert.deepEqual(clicks(s),[]);const moves=s.sent.filter(e=>e.type==='pointermove');assert(moves.every(e=>e.buttons===0));assert(moves.some(e=>e.clientX===30&&e.clientY===60));assert(moves.some(e=>e.clientX===430&&e.clientY===260));assert(moves.some(e=>e.clientX===30&&e.clientY===260));assert(moves.some(e=>e.clientX===430&&e.clientY===60));}
// Two fingers suppress left click and produce exactly one paired right click.
{const s=setup(true);s.event('pointerdown',1);s.event('pointerdown',2);s.event('pointerup',1);assert.deepEqual(clicks(s),[]);s.event('pointerup',2);assert.deepEqual(clicks(s),[2]);assert.equal(s.sent.find(e=>e.type==='pointerdown').buttons,2);}
for(const kind of ['third','move','long','cancel','lost','blur','hidden','off','resize']) {
 const s=setup(true);s.event('pointerdown',1);s.event('pointerdown',2);
 if(kind==='third'){s.event('pointerdown',3);s.event('pointerup',3);}
 if(kind==='move')s.event('pointermove',2,130,100);
 if(kind==='long')s.event('pointermove',2,100,100,600);
 if(kind==='cancel')s.event('pointercancel',1);
 if(kind==='lost')s.event('lostpointercapture',1);
 if(kind==='blur')s.window.dispatchEvent({type:'blur'});
 if(kind==='hidden')s.document.dispatchEvent({type:'visibilitychange'});
 if(kind==='off')s.controller.setEnabled(false);
 if(kind==='resize')s.window.dispatchEvent({type:'resize'});
 assert.equal(s.event('pointerup',1).stopped,true);s.event('pointerup',2);assert.deepEqual(clicks(s),[],kind);assert.equal(s.capture.size,0,kind);
}
// Small jitter is tap-compatible; pointerup displacement also cancels a drag.
{const s=setup(true);s.event('pointerdown');s.event('pointermove',1,103,104);s.event('pointerup',1,103,104);assert.deepEqual(clicks(s),[0]);}
{const s=setup(true);s.event('pointerdown');s.event('pointerup',1,200,200);assert.deepEqual(clicks(s),[]);}
// Repeated transitions and cleanup leave no active input/listeners.
{const s=setup(true);s.controller.setEnabled(false);s.controller.setEnabled(true);s.event('pointerdown');s.controller.dispose();assert.equal(s.cursor.hidden,true);assert.equal(s.capture.size,0);assert.equal(s.event('pointerup').stopped,undefined);}
// Browser may discard old releases on backgrounding: a fresh down must recover.
{const s=setup(true);s.event('pointerdown',1);s.window.dispatchEvent({type:'blur'});s.event('pointerdown',1);s.event('pointerup',1);assert.deepEqual(clicks(s),[0]);}
{const s=setup(true);s.event('pointerdown',1);s.controller.setEnabled(false);assert.equal(s.event('pointerdown',1).stopped,undefined);}
{const s=setup(true);s.event('pointerdown',1);s.event('pointerdown',2);s.event('pointerup',1);s.event('pointerdown',3);s.event('pointerup',2);s.event('pointerup',3);assert.deepEqual(clicks(s),[]);}
console.log('mouse touch: 19 gesture-state/lifecycle/client-coordinate cases passed (mock DOM, not browser proof)');

// Regression: jitter must never move the pointer or shift a tap target.
{const s=setup(true);const origin={...s.cursor.style};s.event('pointerdown');s.event('pointermove',1,103,104);assert.deepEqual(s.cursor.style,origin);s.event('pointerup',1,103,104);assert.deepEqual(clicks(s),[0]);const d=s.sent.find(e=>e.type==='pointerdown');assert.equal(d.clientX,230);assert.equal(d.clientY,160);}
// A movement gesture is permanently non-clicking, even after returning to origin.
{const s=setup(true);s.event('pointerdown');s.event('pointermove',1,109,100);assert.equal(s.cursor.style.left,'239px');s.event('pointermove',1,100,100);s.event('pointerup');assert.deepEqual(clicks(s),[]);}
// Pending second finger must not move the cursor or leak a left click.
{const s=setup(true);const origin={...s.cursor.style};s.event('pointerdown',1);s.event('pointermove',1,104,100);s.event('pointerdown',2);s.event('pointerup',2);s.event('pointerup',1,104,100);assert.deepEqual(s.cursor.style,origin);assert.deepEqual(clicks(s),[2]);}
// Button API works without simultaneous contacts and cancels an unfinished tap.
{const s=setup(true);const origin={...s.cursor.style};s.event('pointerdown');assert.equal(s.controller.rightClick(),true);s.event('pointerup');assert.deepEqual(clicks(s),[2]);assert.deepEqual(s.cursor.style,origin);assert.equal(s.capture.size,0);}
{const s=setup();assert.equal(s.controller.rightClick(),false);assert.deepEqual(clicks(s),[]);s.controller.dispose();assert.equal(s.controller.rightClick(),false);}
console.log('5 additional exclusivity / right-button regressions passed');

const ups=s=>s.sent.filter(e=>e.type==='pointerup');
function balanced(s) {
  const state=new Set();
  for(const e of s.sent) {
    if(e.type==='pointerdown'){assert(!state.has(e.button),'duplicate down');state.add(e.button);}
    if(e.type==='pointerup'){assert(state.has(e.button),'orphan up');state.delete(e.button);assert.equal(e.buttons,0);}
  }
  assert.equal(state.size,0,'no stuck synthetic mouse button');
}
// Pulse duration is engine-visible time, not a synchronous DOM pair.
for(const button of [0,2]) {
  const s=setup(true);
  if(button===0){s.event('pointerdown');s.event('pointerup');}else assert.equal(s.controller.rightClick(),true);
  assert.deepEqual(clicks(s),[button]);assert.equal(ups(s).length,0);
  s.advance(99);assert.equal(ups(s).length,0);
  s.advance(1);assert.equal(ups(s).length,1);balanced(s);
}
// Hold threshold is measured from down; movement below it permanently chooses hover.
{const s=setup(true);s.event('pointerdown');s.advance(249);assert.deepEqual(clicks(s),[]);s.advance(1);assert.deepEqual(clicks(s),[0]);assert.equal(ups(s).length,0);s.event('pointermove',1,140,100,0);assert.equal(s.sent.filter(e=>e.type==='pointermove').at(-1).buttons,1);s.event('pointerup',1,140,100,0);assert.equal(ups(s).length,1);s.advance(1000);assert.deepEqual(clicks(s),[0]);balanced(s);}
{const s=setup(true);s.event('pointerdown');s.event('pointermove',1,109,100,100);s.advance(1000);s.event('pointermove',1,150,100,0);s.event('pointerup',1,150,100,0);s.advance(1000);assert.deepEqual(clicks(s),[]);assert(s.sent.filter(e=>e.type==='pointermove').every(e=>e.buttons===0));balanced(s);}
// Stationary hold released shortly after activation completes only its remaining pulse.
{const s=setup(true);s.event('pointerdown');s.advance(250);s.advance(20);s.event('pointerup',1,100,100,0);assert.equal(ups(s).length,0);s.advance(79);assert.equal(ups(s).length,0);s.advance(1);assert.equal(ups(s).length,1);balanced(s);}
{const s=setup(true);s.event('pointerdown');s.advance(400);s.event('pointerup',1,100,100,0);assert.equal(ups(s).length,1);balanced(s);}
// Starting another gesture releases a previous pulse before movement, never drags accidentally.
{const s=setup(true);s.event('pointerdown');s.event('pointerup');s.event('pointerdown',2,100,100,1);assert.equal(ups(s).length,1);s.event('pointermove',2,140,100,1);assert.equal(s.sent.filter(e=>e.type==='pointermove').at(-1).buttons,0);s.event('pointerup',2,140,100,0);s.advance(1000);assert.deepEqual(clicks(s),[0]);balanced(s);}
// Every cancellation phase clears both timers and pressed mouse state immediately.
let lifecycleCases=0;
for(const phase of ['pending','held','pulse','rightPulse'])for(const reason of ['cancel','blur','hidden','off','dispose','resize']) {
  const s=setup(true);
  if(phase==='rightPulse')s.controller.rightClick();
  else {s.event('pointerdown');if(phase==='held')s.advance(250);if(phase==='pulse')s.event('pointerup');}
  const before=clicks(s).length;
  if(reason==='cancel')s.controller.cancel();
  if(reason==='blur')s.window.dispatchEvent({type:'blur'});
  if(reason==='hidden'){s.document.hidden=true;s.document.dispatchEvent({type:'visibilitychange'});}
  if(reason==='off')s.controller.setEnabled(false);
  if(reason==='dispose')s.controller.dispose();
  if(reason==='resize')s.window.dispatchEvent({type:'resize'});
  balanced(s);assert.equal(s.capture.size,0,phase+reason);
  s.advance(2000);assert.equal(clicks(s).length,before,phase+reason+' delayed down');balanced(s);assert.equal(s.timers.size,0,phase+reason+' leaked timer');lifecycleCases++;
}
console.log('31 additional hold/pulse/lifecycle regressions passed ('+lifecycleCases+' lifecycle phases; deterministic timers, not browser proof)');
// A 30fps polling game sees pressed state across successive frames, then sees release.
for(const button of [0,2]) {
 const s=setup(true);let mask=0;const frames=[];
 s.event('pointerdown');s.controller.cancel(); // Warmup does not itself click.
 s.sent.length=0;
 s.sent.push = function(...events){for(const e of events){if(e.type==='pointerdown'||e.type==='pointerup')mask=e.buttons;}return Array.prototype.push.apply(this,events);};
 const sample=()=>{frames.push(mask);if(frames.length<4)s.window.setTimeout(sample,33);};
 s.window.setTimeout(sample,33);
 if(button===0){s.event('pointerdown',1,100,100,0);s.event('pointerup',1,100,100,0);}else s.controller.rightClick();
 s.advance(132);assert.deepEqual(frames,[button===2?2:1,button===2?2:1,button===2?2:1,0]);balanced(s);
}
// Detachment/zero layout cannot swallow the balancing release at the last valid position.
for(const phase of ['held','pulse']) {
 const s=setup(true);s.event('pointerdown');if(phase==='held')s.advance(250);else s.event('pointerup');
 const down=s.sent.find(e=>e.type==='pointerdown');s.resize({left:0,top:0,width:0,height:0});s.controller.cancel();
 balanced(s);assert.equal(ups(s)[0].clientX,down.clientX);assert.equal(ups(s)[0].clientY,down.clientY);s.advance(1000);assert.equal(ups(s).length,1);
}
console.log('4 frame-polling / collapsed-canvas release regressions passed');

// Busy main-thread input may be delivered before its overdue hold timer.
{const s=setup(true);s.event('pointerdown');s.event('pointermove',1,140,100,300,true);assert.deepEqual(clicks(s),[0]);assert.equal(s.sent.filter(e=>e.type==='pointermove').at(-1).buttons,1);s.event('pointerup',1,140,100);balanced(s);s.advance(1000);assert.equal(clicks(s).length,1);}
{const s=setup(true);s.event('pointerdown');s.event('pointerup',1,100,100,600,true);assert.deepEqual(clicks(s),[0]);s.advance(100);balanced(s);assert.equal(clicks(s).length,1);}
console.log('2 overdue-timer input regressions passed');
