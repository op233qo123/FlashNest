// Execute the actual page module in a mocked DOM/API, not a real runtime/browser.
import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';import path from 'node:path';import {fileURLToPath} from 'node:url';
import {route,fixturePins} from './runner-guards.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),source=fs.readFileSync(path.join(here,'page.mjs'),'utf8');
const importLine="import {installConsoleObserver} from './console-observer.mjs';";assert(source.startsWith(importLine));assert.equal((source.match(/^import /gm)||[]).length,1);
let groups=0;
for(const href of ['http://127.0.0.1:43111/','http://127.0.0.1:49876/?diagnostic=1','http://127.0.0.1:43210/nested/host.html?x=1']){
 const loads=[],listeners=[],elements={host:{append(){}},resume:{}},gl={isContextLost:()=>false,drawingBufferWidth:320,drawingBufferHeight:240};
 const canvas={getContext:kind=>kind==='webgl2'?gl:null,addEventListener:(...args)=>listeners.push(args)};
 const api={load:async options=>loads.push(options),isPlaying:false},player={ruffle:()=>api,shadowRoot:{querySelector:selector=>selector==='canvas'?canvas:null}};
 const window={addEventListener(){}},document={createElement:()=>({}),head:{append(){}},getElementById:id=>elements[id]};
 const sandbox={window,document,location:{href},URL,devicePixelRatio:1,structuredClone,console:{},installConsoleObserver:()=>({restore(){}})};
 vm.runInNewContext(source.slice(importLine.length),sandbox,{filename:'actual-page.mjs',timeout:1000});
 window.RufflePlayer.newest=()=>({createPlayer:()=>player});await window.start();
 assert.equal(loads.length,1);const options=JSON.parse(JSON.stringify(loads[0])),origin=new URL(href).origin;
 assert.deepEqual(options,{url:'/fixtures/main.swf',base:origin+'/fixtures/',autoplay:'off',unmuteOverlay:'hidden',preferredRenderer:'webgl',quality:'low',backgroundExecutionMode:'none',allowScriptAccess:false});
 const main=new URL(options.url,href),child=new URL('sub/child.swf',options.base);
 assert.equal(main.href,origin+'/fixtures/main.swf');assert.equal(options.base,new URL('./',main).href);
 assert.equal(child.origin,main.origin);assert.equal(child.pathname,'/fixtures/sub/child.swf');assert.notEqual(child.pathname,'/sub/child.swf');
 assert.equal(route(child.pathname.slice(1),{fixtures:'/fixture-root',helpers:'/helpers',runtime:'/runtime'},{}),'/fixture-root/sub/child.swf');assert(Object.hasOwn(fixturePins,child.pathname.slice('/fixtures/'.length)));
 assert.equal(window.evidence.errors.length,0);assert.equal(window.evidence.loaded,true);assert.equal(window.evidence.observerInstalled,true);assert.equal(typeof api.traceObserver,'function');
 assert.deepEqual(listeners.filter(x=>x[0].startsWith('pointer')).map(x=>x[0]),['pointerdown','pointerup']);
 await assert.rejects(window.start(),/Only one original player allowed/);assert.equal(loads.length,1);groups++;
}
console.log(`PASS ${groups} actual-page load-option/base-resolution mock groups; no browser/SWF/runtime execution`);
