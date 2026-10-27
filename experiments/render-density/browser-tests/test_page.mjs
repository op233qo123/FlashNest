// Lifecycle contracts only; deliberately not a renderer/SWF execution claim.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const html=fs.readFileSync(new URL('./page.html',import.meta.url),'utf8');const script=html.match(/<script>([\s\S]*)<\/script>/)[1];
const listeners={};
const instances=[];const host={style:{},append(){}};const button={};
class Canvas{getContext(){return null}}
const context={console:{log(){}},URLSearchParams,location:{search:'?runtime=candidate'},HTMLCanvasElement:Canvas,WeakMap,document:{addEventListener(type,callback,options){listeners[type]={callback,options}},getElementById:id=>id==='host'?host:button,createElement:()=>({}),head:{append(){}}}};context.window=context;
vm.createContext(context);vm.runInContext(script,context);
context.RufflePlayer.newest=()=>({createPlayer:()=>{
 const events={};let resolve;const api={load(){return new Promise(r=>{resolve=r})},resume(){this.resumed=true}};
 const p={ruffle:()=>api,addEventListener:(n,fn)=>events[n]=fn,remove(){this.removed=true}};
 instances.push({p,api,events,resolve:()=>resolve()});return p;
}});
const first=context.startCase('/fixtures/a.swf',1,443,287,'webgl','low');const a=instances[0];assert.equal(a.api.traceObserver,undefined);a.resolve();await first;
assert.equal(typeof a.api.traceObserver,'function');a.api.traceObserver('DENSITY|READY|320|240');button.onclick();assert(a.api.resumed);
const previous=context.evidence;const second=context.startCase('/fixtures/b.swf',.5,443,287,'webgl','low');const b=instances[1];assert(a.p.removed);
a.events.loadeddata();a.api.traceObserver('late old event');assert.equal(context.evidence.loaded,false);assert.equal(context.evidence.traces.length,0);assert(previous.traces.includes('late old event'));
b.resolve();await second;b.events.loadeddata();assert(context.evidence.loaded&&context.evidence.observerInstalled);
console.log('PASS post-instance observer, resume API, old-case callback isolation');

for(const type of ['pointerdown','pointerup']){
 assert.equal(listeners[type].options.capture,true);assert.equal(listeners[type].options.passive,true);
 listeners[type].callback({isTrusted:false});assert.equal(context.pointerEvents.length,0);
}
const event={isTrusted:true,clientX:12,clientY:19,button:0,type:'pointerdown',target:{tagName:'RUFFLE-PLAYER',id:'host'},composedPath:()=>[{tagName:'CANVAS',id:'stage'}]};
for(let i=0;i<40;i++)listeners.pointerdown.callback(event);
assert.equal(context.pointerEvents.length,32);assert.equal(context.pointerEvents[0].path[0].tag,'CANVAS');
assert(context.pointerEvents.every(e=>e.trusted&&e.x===12&&e.y===19));
console.log('PASS trusted passive pointer observations are bounded and synthetic events ignored');
// Composed hit-testing must reach this exact canvas, not a shadow overlay.
const canvas={tagName:'CANVAS',id:'canvas'},overlay={tagName:'DIV',id:'hardware-acceleration-modal'};
context.player={tagName:'RUFFLE-PLAYER',id:'',shadowRoot:{querySelector:()=>canvas,elementFromPoint:()=>canvas}};
context.document.elementFromPoint=()=>context.player;
assert.equal(context.gameHitTarget(22,14).canvasTopmost,true);
context.player.shadowRoot.elementFromPoint=()=>overlay;
assert.equal(context.gameHitTarget(22,14).canvasTopmost,false);
context.player.shadowRoot.elementFromPoint=()=>canvas;context.document.elementFromPoint=()=>overlay;
assert.equal(context.gameHitTarget(22,14).canvasTopmost,false);
const runner=fs.readFileSync(new URL('./run.mjs',import.meta.url),'utf8');
const geometry=runner.slice(runner.indexOf('async function geometry('),runner.indexOf('\ntry{\n for(const dpr'));
assert(geometry.indexOf('await move(...points[0]);')<geometry.indexOf('await closeKnownHardwareWarning();'));
assert(geometry.indexOf('await closeKnownHardwareWarning();')<geometry.indexOf('await prepareGamePoint(x,y);'));
assert(geometry.indexOf('await prepareGamePoint(x,y);')<geometry.indexOf('await move(x,y,true,true);'));
assert.equal(geometry.split('await closeKnownHardwareWarning();').length-1,1);
console.log('PASS exact composed canvas target and hover→known-warning→target-check→single-click ordering');
