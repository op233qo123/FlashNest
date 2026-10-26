/* Shell contract unit test only: deliberately mocked Ruffle, NOT compatibility evidence. */
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const path = require('node:path');
const controls=[], elements={}; let config, suspended=0, resumed=0, appended;
const api={load:async c=>{config=c},suspend:()=>suspended++,resume:()=>resumed++};
const player={ruffle:()=>api, focus(){},dispatchEvent(){}};
for(const id of ['status','pause','start','stage']) elements[id]={textContent:'',append:p=>appended=p};
const context={URL,URLSearchParams,Object,Set,Error,String,KeyboardEvent:class{},location:{href:'http://127.0.0.1:8766/cap/web/index.html?package=11111111-1111-4111-8111-111111111111&entry=folder%2Fspace%20%23.swf'}};
context.location.search=new URL(context.location.href).search;
context.document={getElementById:id=>elements[id],querySelectorAll:()=>controls,addEventListener(){},createElement:()=>({}),head:{append:s=>{context.window.RufflePlayer.newest=()=>({createPlayer:()=>player});s.onload()}}};
context.window={fetch:async()=>({ok:true}),addEventListener(){}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../App/Resources/Web/shell.js'),'utf8'),context);
setImmediate(()=>{
 assert.equal(config.url,'http://127.0.0.1:8766/cap/games/11111111-1111-4111-8111-111111111111/folder/space%20%23.swf');
 assert.equal(config.base,'http://127.0.0.1:8766/cap/games/11111111-1111-4111-8111-111111111111/folder/');
 assert.equal(config.publicPath,'http://127.0.0.1:8766/cap/web/runtime/');
 assert.equal(config.allowNetworking,'internal'); assert.equal(config.allowScriptAccess,false);
 assert.equal(appended,player);
 elements.start.onclick(); assert.equal(resumed,1);
 context.window.FlashNest.pause(); assert.equal(suspended,1);
 context.window.FlashNest.resume(); assert.equal(resumed,2);
 assert.equal(typeof api.traceObserver,'function');
 console.log('PASS shell URL encoding, base, offline config, lifecycle contract (mock unit test only)');
});
