'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../App/Resources/Web/mouse-touch.js'),'utf8');
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
  vm.runInNewContext(source,{window,document,PointerEvent,Math,Map,Set,Object});
  const controller=window.FlashNestMouseTouch.create({canvas,host:{focus(){}},cursor,enabled});controller.initialize();
  let time=0;
  function event(type,id=1,x=100,y=100,dt=10) {const e={type,pointerId:id,pointerType:'touch',clientX:x,clientY:y,timeStamp:time+=dt,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}};canvas.dispatchEvent(e);return e;}
  return {controller,sent,event,cursor,capture,window,document,resize:v=>r=v};
}
const clicks=s=>s.sent.filter(e=>e.type==='pointerdown').map(e=>e.button);
// Default-off must be a completely unmodified direct-touch path.
{const s=setup();assert.equal(s.sent.length,0);assert.equal(s.event('pointerdown').stopped,undefined);assert.equal(s.cursor.hidden,true);}
// Single tap only emits one paired left click; movement is never held down.
{const s=setup(true);s.event('pointerdown');s.event('pointerup');assert.deepEqual(clicks(s),[0]);assert.equal(s.sent.filter(e=>e.type==='pointerup').length,1);assert.equal(s.capture.size,0);}
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
