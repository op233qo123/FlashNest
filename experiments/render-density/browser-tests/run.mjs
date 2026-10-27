#!/usr/bin/env node
// Isolated diagnostic: no production app code, no game assets, no uploads.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {decodePNG,comparePixels} from './png.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(here);
const args={};for(let i=2;i<process.argv.length;i+=2){assert(process.argv[i].startsWith('--')&&process.argv[i+1],'--key value required');args[process.argv[i].slice(2)]=process.argv[i+1]}
for(const k of ['baseline','candidate','baseline-manifest','candidate-manifest','webdriverio','backend','output'])assert(args[k],`Missing --${k}`);
assert(['webgl','wgpu-webgl'].includes(args.backend));
const renderer=args.backend;
assert(args.chrome&&args.driver,'Explicit installed --chrome and --driver required; no automatic browser download');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function inventory(dir,prefix=''){
 const out={};for(const e of fs.readdirSync(path.join(dir,prefix),{withFileTypes:true})){
  assert(!e.isSymbolicLink(),'No runtime symlinks');const rel=prefix?prefix+'/'+e.name:e.name;
  if(e.isDirectory())Object.assign(out,inventory(dir,rel));else if(/\.(js|wasm)$/.test(e.name))out[rel]=sha(fs.readFileSync(path.join(dir,rel)));
 }return out;
}
const provenance={};for(const name of ['baseline','candidate']){
 args[name]=path.resolve(args[name]);const actual=inventory(args[name]);const expected=JSON.parse(fs.readFileSync(args[name+'-manifest'],'utf8'));
 assert.deepEqual(actual,expected,`${name} runtime manifest mismatch`);assert(actual['ruffle.js']&&Object.keys(actual).some(k=>k.endsWith('.wasm')));
 provenance[name]=actual;
}
const pkg=JSON.parse(fs.readFileSync(path.join(args.webdriverio,'package.json')));assert.equal(pkg.version,'9.32.0');assert(fs.existsSync(args.chrome)&&fs.existsSync(args.driver),'Installed browser/driver missing');
const {remote}=await import(pathToFileURL(path.resolve(args.webdriverio,'build/index.js')).href);
const fixtures=JSON.parse(fs.readFileSync(path.join(root,'fixtures/manifest.json')));
for(const [name,info] of Object.entries(fixtures.files))assert.equal(sha(fs.readFileSync(path.join(root,'fixtures',name))),info.sha256);
const nestedRoot=path.resolve(root,'../frame-order/fixtures');
const nested=JSON.parse(fs.readFileSync(path.join(nestedRoot,'manifest.json')));
for(const [name,info] of Object.entries(nested.files))assert.equal(sha(fs.readFileSync(path.join(nestedRoot,name))),info.sha256);
const expectedFrames={};
for(const [fixture,name,digest] of [
 ['nested-child-goto.swf','nested-repair-target.txt','57648847e013eb2aaa9e45a91eb0a55c66c97862defd8e3c1cd5b74ef4e3c2ae'],
 ['control-no-child-goto.swf','control.txt','cb1f8c5a8f0770d7ed9c92fd3219dc11294746258fa9a4ec8558c82eda9626c0']]){
 const data=fs.readFileSync(path.resolve(nestedRoot,'../engine-patch/expectations',name));assert.equal(sha(data),digest);expectedFrames[fixture]=data.toString().trim().split('\n');
}
const output=path.resolve(args.output);fs.mkdirSync(output,{recursive:true});
const result={schema:1,passed:false,backendRequired:args.backend,provenance,fixtureManifest:fixtures,nestedManifest:nested,rows:[],nested:[],fallbacks:[],failures:[],screenshots:[],started:new Date().toISOString()};
const journal=path.join(output,'cases.jsonl');fs.writeFileSync(journal,'');let journalBytes=0;
function record(kind,data){const line=JSON.stringify({kind,at:new Date().toISOString(),...data})+'\n';journalBytes+=Buffer.byteLength(line);assert(journalBytes<=16*1024*1024,'Evidence journal exceeds16MiB');fs.appendFileSync(journal,line)}
function setCase(data){result.activeCase=data;record('start',data);const temporary=path.join(output,'active-case.json.tmp');fs.writeFileSync(temporary,JSON.stringify(data));fs.renameSync(temporary,path.join(output,'active-case.json'))}
fs.writeFileSync(path.join(output,'provenance.json'),JSON.stringify({backend:args.backend,provenance,fixtureManifest:fixtures,nestedManifest:nested},null,2)+'\n');
const deadline=Date.now()+60*60*1000;
const routes={baseline:args.baseline,candidate:args.candidate,fixtures:path.join(root,'fixtures'),nested:nestedRoot};
const server=http.createServer((req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost');if(url.pathname==='/'){res.setHeader('Content-Type','text/html');res.end(fs.readFileSync(path.join(here,'page.html')));return}
  const parts=decodeURIComponent(url.pathname).split('/').filter(Boolean),base=routes[parts.shift()];assert(base);const file=path.resolve(base,...parts);assert(file.startsWith(base+path.sep));
  const stat=fs.statSync(file);assert(stat.isFile());res.setHeader('Content-Type',file.endsWith('.wasm')?'application/wasm':file.endsWith('.js')?'text/javascript':'application/octet-stream');res.setHeader('Content-Length',stat.size);fs.createReadStream(file).pipe(res);
 }catch{res.statusCode=404;res.end('Not found')}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
let browser,shotCount=0;
async function screenshot(label){if(shotCount>=40)return;const name=`${String(shotCount++).padStart(2,'0')}-${label.replace(/[^a-zA-Z0-9-]/g,'_').slice(0,100)}.png`;await browser.saveScreenshot(path.join(output,name));result.screenshots.push(name)}
async function waitFor(fn,message,timeout=15000){await browser.waitUntil(fn,{timeout,interval:100,timeoutMsg:message})}
async function traces(){return browser.execute(()=>({...window.evidence}))}
async function move(x,y,down=false,up=false){const actions=[{type:'pointerMove',duration:100,x:Math.round(x),y:Math.round(y),origin:'viewport'}];if(down)actions.push({type:'pointerDown',button:0});if(up)actions.push({type:'pointerUp',button:0});await browser.performActions([{type:'pointer',id:'mouse',parameters:{pointerType:'mouse'},actions}])}
async function play(){await (await browser.$('#play')).click()}
function checkCanvas(m,arm,scale,w,h,dpr){
 assert(m,'Canvas missing');assert.equal(m.actualRenderer,renderer,'runtime-reported selected backend');assert.equal(m.dpr,dpr);assert.deepEqual(m.client,[w,h]);assert.deepEqual(m.css,[0,0,w,h]);
 assert(['webgl','webgl2','experimental-webgl'].includes(m.backend),`Actual context ${m.backend} is not WebGL`);
 const virtual=[Math.floor(w*dpr),Math.floor(h*dpr)],expected=virtual.map(v=>Math.max(1,Math.round(v*scale)));
 assert.deepEqual([m.width,m.height],expected,'actual backing');if(m.gl)assert.deepEqual(m.gl,expected,'actual GL drawing buffer');
 if(arm==='candidate'){
  const a=m.attributes;assert.equal(Number(a['data-flashnest-render-request']),scale);assert.equal(Number(a['data-flashnest-render-scale']),scale,'fallback not allowed in target-backend gate');
  assert.equal(Number(a['data-flashnest-viewport-width']),virtual[0]);assert.equal(Number(a['data-flashnest-viewport-height']),virtual[1]);
  assert.equal(a['data-flashnest-renderer'],renderer);
 }
}
function parse(lines,label){return lines.filter(x=>x.startsWith('DENSITY|'+label+'|')).map(x=>x.split('|').slice(2))}
function compare(actual,expected,label){assert.equal(actual.length,expected.length,label+' count');for(let i=0;i<actual.length;i++){assert.equal(actual[i].length,expected[i].length);for(let j=0;j<actual[i].length;j++){const a=Number(actual[i][j]),b=Number(expected[i][j]);if(actual[i][j]!==''&&expected[i][j]!==''&&Number.isFinite(a)&&Number.isFinite(b))assert(Math.abs(a-b)<=0.1,`${label}[${i},${j}] ${a} != ${b}`);else assert.equal(actual[i][j],expected[i][j],label)}}}
async function geometry(arm,scale,fixture,w,h,dpr){
 setCase({arm,scale,fixture,viewport:[w,h],dpr});assert(Date.now()<deadline,'Global 60-minute deadline exceeded');await browser.execute((f,s,w,h,r)=>window.startCase('/fixtures/'+f,s,w,h,r,'low'),fixture,scale,w,h,renderer);
 await waitFor(async()=>{const e=await traces();if(e.errors.length||e.overflow)throw Error(JSON.stringify(e));return e.loaded&&e.observerInstalled},'real loadeddata');await play();
 await waitFor(async()=>(await traces()).traces.some(s=>s.startsWith('DENSITY|READY|')),'real SWF READY');
 await waitFor(async()=>{const m=await browser.execute(()=>window.measure());return m&&m.width===Math.max(1,Math.round(Math.floor(w*dpr)*scale))&&m.height===Math.max(1,Math.round(Math.floor(h*dpr)*scale))},'backing resize');
 const canvas=await browser.execute(()=>window.measure());checkCanvas(canvas,arm,scale,w,h,dpr);
 const points=[[.05,.05],[.95,.05],[.05,.95],[.95,.95],[.5,.5]].map(([x,y])=>[Math.round(w*x),Math.round(h*y)]);
 for(const [x,y]of points)await move(x,y,true,true);
 await waitFor(async()=>parse((await traces()).traces,'UP').length===5,'five trusted pointer sequences');
 let e=await traces(),downs=parse(e.traces,'DOWN');assert.equal(downs.length,5);
 // Infer stock coordinate transform from real SWF pointer observations, then
 // target the vector center. No JS fake hit-test, synthetic DOM mouse event or
 // renderer-specific stage-size assumption is used.
 const sx=(Number(downs[1][0])-Number(downs[0][0]))/(points[1][0]-points[0][0]);
 const sy=(Number(downs[2][1])-Number(downs[0][1]))/(points[2][1]-points[0][1]);assert(sx>0&&sy>0);
 const tx=points[0][0]+(160-Number(downs[0][0]))/sx,ty=points[0][1]+(120-Number(downs[0][1]))/sy;
 assert(tx>0&&tx<w&&ty>0&&ty<h,'Vector center outside test viewport');
 await move(tx,ty,true,false);await move(tx+12,ty+9);await move(tx+12,ty+9,false,true);await browser.releaseActions();
 await waitFor(async()=>parse((await traces()).traces,'UP').length===6,'trusted drag completion');e=await traces();assert(!e.overflow&&!e.errors.length);
 assert(e.traces.every(x=>/^DENSITY\|(READY|RESIZE|DOWN|UP)\|/.test(x)),'Unexpected geometry trace');
 const down=parse(e.traces,'DOWN'),up=parse(e.traces,'UP');assert.equal(down.length,6);assert.equal(down[5][2],'true','actual SWF hitTest');
 const info=fixtures.files[fixture];for(const row of down){assert(Number.isFinite(Number(row[3]))&&Number(row[3])>0);assert(Number.isFinite(Number(row[4]))&&Number(row[4])>0);assert.equal(row[5],info.mode);assert.equal([...row[6].toUpperCase()].sort().join(''),[...info.align].sort().join(''));}
 assert(Number(up[5][2])>100&&Number(up[5][3])>70,'actual SWF drag moved');
 return {arm,scale,fixture,viewport:[w,h],dpr,canvas,down,up};
}
try{
 for(const dpr of [1,2,3]){
  browser=await remote({logLevel:'error',connectionRetryCount:0,connectionRetryTimeout:30000,capabilities:{browserName:'chrome','wdio:chromedriverOptions':{binary:args.driver},'goog:chromeOptions':{...(args.chrome?{binary:args.chrome}:{}),args:['--headless=new',`--force-device-scale-factor=${dpr}`,'--window-size=900,900']}}});
  await browser.setTimeout({script:45000,pageLoad:30000,implicit:0});await browser.setWindowSize(900,900);result.browserCapabilities=browser.capabilities;record('browser',{dpr,capabilities:browser.capabilities});
  const references=new Map(),pixelReferences=new Map();
  for(const arm of ['baseline','candidate']){
   await browser.url(origin+'/?runtime='+arm);await waitFor(()=>browser.execute(()=>window.runtimeReady===true),'runtime script',30000);
   for(const [w,h]of [[443,287],[319,481]])for(const fixture of Object.keys(fixtures.files))for(const scale of (arm==='baseline'?[1]:[1,.75,.5,.25])){
    const row=await geometry(arm,scale,fixture,w,h,dpr),key=`${fixture}/${w}/${h}`;
    if(arm==='baseline')references.set(key,row);else{const ref=references.get(key);compare(row.down,ref.down,'DOWN');compare(row.up,ref.up,'UP');assert.deepEqual(row.down.map(x=>x.slice(3)),ref.down.map(x=>x.slice(3)),'exact Stage metadata');assert.deepEqual(row.up.map(x=>x.slice(4)),ref.up.map(x=>x.slice(4)),'exact Stage metadata')}
    result.rows.push(row);
    if(fixture==='showAll-center.swf'){
     const name=`geometry-${arm}-${scale}-dpr${dpr}-${w}x${h}.png`;
     const png=await (await browser.$('#host')).saveScreenshot(path.join(output,name));
     result.screenshots.push(name);const pixels=decodePNG(png),pixelKey=`${w}/${h}`;
     if(arm==='baseline')pixelReferences.set(pixelKey,pixels);
     row.pixelComparison=comparePixels(pixels,pixelReferences.get(pixelKey),Math.ceil(4*pixels.width/w));
     if(arm==='candidate'&&scale===1){assert.equal(row.pixelComparison.changedFraction,0,'Original density exact pixel parity');assert.equal(row.pixelComparison.meanAbsoluteRGBError,0,'Original density exact RGB parity');}
    }
    record('geometry',row);
   }
   if(dpr===1)for(const fixture of Object.keys(nested.files))for(const scale of (arm==='baseline'?[1]:[1,.75,.5,.25])){
    setCase({arm,scale,fixture,dpr});await browser.execute((f,s,r)=>window.startCase('/nested/'+f,s,443,287,r,'low'),fixture,scale,renderer);await waitFor(async()=>{const e=await traces();return e.loaded&&e.observerInstalled},'nested loadeddata');await play();
    await waitFor(async()=>(await traces()).traces.some(x=>x.startsWith('FO_DONE')),'nested exact completion');
    const e=await traces();assert(!e.overflow&&!e.errors.length);const rows=e.traces;assert(rows.every(x=>x.startsWith('FO_')),'Unexpected trace must not be filtered');
    const ticks=rows.filter(x=>x.startsWith('FO_STATE '));assert.equal(ticks.length,12);assert.deepEqual(ticks.map(x=>Number(x.split(/\s+/)[1])),Array.from({length:12},(_,i)=>i+1));
    assert.equal(rows.filter(x=>x.startsWith('FO_DONE')).length,1);
    const expected=expectedFrames[fixture];assert.deepEqual(rows.slice(0,expected.length),expected,'exact canonical frame-order golden');
    const tail=rows.slice(expected.length);assert.equal(tail.length%2,0);for(let i=0;i<tail.length;i+=2)assert.deepEqual(tail.slice(i,i+2),['FO_B_LOOP 7','FO_B_OPENING 5']);
    const measurement={arm,scale,fixture,canonical:rows.slice(0,expected.length),postWindowLoopPairs:tail.length/2,rows};result.nested.push(measurement);record('nested',measurement);
   }
   if(arm==='candidate'&&dpr===1)for(const [fallbackRenderer,quality]of [['canvas','low'],['webgl','high']]){
    setCase({arm,dpr,fallbackRenderer,quality,scale:.5});await browser.execute((r,q)=>window.startCase('/fixtures/showAll-center.swf',.5,443,287,r,q),fallbackRenderer,quality);
    await waitFor(async()=>{const e=await traces();return e.loaded&&e.observerInstalled},'fallback loadeddata');await play();
    await waitFor(async()=>(await traces()).traces.some(x=>x.startsWith('DENSITY|READY|')),'fallback real SWF READY');
    const m=await browser.execute(()=>window.measure()),a=m?.attributes;assert(m);
    assert.equal(m.actualRenderer,fallbackRenderer);assert.equal(a['data-flashnest-renderer'],fallbackRenderer,'fallback must run requested backend');
    assert.equal(Number(a['data-flashnest-render-request']),.5);assert.equal(Number(a['data-flashnest-render-scale']),1);
    assert.deepEqual([m.width,m.height],[443,287]);assert.deepEqual(m.css,[0,0,443,287]);
    if(fallbackRenderer==='canvas')assert.equal(m.backend,'2d');else{assert(['webgl','webgl2'].includes(m.backend));assert.deepEqual(m.gl,[443,287])}
    const measurement={renderer:fallbackRenderer,quality,canvas:m};result.fallbacks.push(measurement);record('fallback',measurement);
   }
  }
  await browser.deleteSession();browser=null;
 }
 assert.equal(result.rows.length,1080);assert.equal(result.nested.length,10);assert.equal(result.fallbacks.length,2);result.passed=true;
}catch(error){result.failures.push(String(error.stack||error).slice(0,12000));if(browser){try{result.lastEvidence=await traces();result.lastCanvas=await browser.execute(()=>window.measure());await screenshot('FAIL')}catch{}}process.exitCode=1;
}finally{
 if(browser)try{await browser.deleteSession()}catch{}
 server.closeAllConnections();server.close();result.finished=new Date().toISOString();fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify({passed:result.passed,cases:result.rows.length,nested:result.nested.length,failures:result.failures}));
}
