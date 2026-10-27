import {installAudioObserver,nativeOnendedPreflight} from './observer.mjs';
import {installConsoleObserver} from './console-observer.mjs';
const params=new URLSearchParams(location.search),runtime=params.get('runtime'),mode=params.get('mode');
if(!['baseline','candidate'].includes(runtime))throw Error('Unknown runtime');
const evidence={runtime,mode,rows:[],errors:[],warnings:[],overflow:false};window.evidence=evidence;
let player=null,api=null,current=null,disposed=false;
function push(list,value,max=64){if(list.length>=max){evidence.overflow=true;return}list.push(value)}
function report(value){push(evidence.errors,{cycle:current?.cycle??-1,message:String(value).slice(0,2048)})}
window.addEventListener('error',e=>report('window.error: '+e.message));
window.addEventListener('unhandledrejection',e=>report('unhandledrejection: '+String(e.reason)));
const consoleObserver=installConsoleObserver(console,{
 reportError:(message,method)=>report('console.'+method+': '+message),
 reportWarning:message=>push(evidence.warnings,{cycle:current?.cycle??-1,message:message.slice(0,2048)}),
 onText:value=>{
  const match=value.match(/New Ruffle instance created .*WebAssembly extensions: (ON|OFF).*Used renderer: ([^)]+)\)/);
  if(match&&current){current.extensions=match[1];current.renderer=match[2]}
 },
});
try{evidence.preflight=nativeOnendedPreflight(window)}catch(error){evidence.preflight={passed:false,error:String(error)};report('Native onended preflight failed: '+String(error))}
const observer=installAudioObserver(window,{mode});
window.RufflePlayer={config:{autoplay:'off',unmuteOverlay:'hidden',warnOnUnsupportedContent:false,backgroundExecutionMode:'none'}};
const script=document.createElement('script');script.src='/'+runtime+'/ruffle.js';script.onload=()=>{window.runtimeReady=true};script.onerror=()=>report('Runtime loader failed');if(evidence.preflight.passed)document.head.append(script);
for(const name of ['resume','pause','remove'])document.getElementById(name).onclick=event=>{
 if(!current||!api)return;
 push(current.actions,{name,trusted:event.isTrusted,heartbeatBefore:current.heartbeats},12);
 try{
  if(!event.isTrusted)throw Error('Action was not trusted');
  if(name==='resume')api.resume();
  else if(name==='pause')api.suspend();
  else {current.removeRequested=true;player.remove();player=null;api=null;current.removed=true}
 }catch(error){report(error?.stack||error)}
};
window.startCycle=async function(cycle){
 if(disposed||player||api)throw Error('A previous player is still active');
 if(!Number.isInteger(cycle)||cycle<0||cycle>7)throw Error('Invalid bounded cycle');
 observer.setCycle(cycle);current={cycle,loaded:false,traces:[],heartbeats:0,actions:[],removeRequested:false,removed:false};evidence.rows.push(current);
 const row=current,p=window.RufflePlayer.newest().createPlayer();player=p;api=p.ruffle();document.getElementById('host').append(p);
 try{
  await api.load({url:'/fixtures/silent.swf',autoplay:'off',unmuteOverlay:'hidden',preferredRenderer:'wgpu-webgl',quality:'low',backgroundExecutionMode:'none',allowScriptAccess:false});
  if(player!==p)throw Error('Player changed during load');
  api.traceObserver=message=>{const text=String(message);if(text==='AL_ACTIVE'){row.heartbeats++;if(row.heartbeats===1)push(row.traces,text,128)}else push(row.traces,text,128)};
  const canvas=p.shadowRoot?.querySelector('canvas');if(!canvas)throw Error('Missing actual renderer canvas');
  const gl=canvas.getContext('webgl2');if(!gl)throw Error('Expected actual WebGL2 context for wgpu-webgl');
  row.context={kind:'webgl2',lost:gl.isContextLost(),drawingBufferWidth:gl.drawingBufferWidth,drawingBufferHeight:gl.drawingBufferHeight,dpr:devicePixelRatio};
  if(row.context.lost)throw Error('Renderer context already lost');
  canvas.addEventListener('webglcontextlost',()=>report('webglcontextlost'));
  row.loaded=true;
 }catch(error){report(error?.stack||error)}
};
window.snapshot=()=>({...structuredClone(evidence),playing:api?.isPlaying??null,audio:observer.snapshot()});
window.dispatchSyntheticEnded=()=>observer.dispatchSyntheticEnded();
window.dispose=()=>{if(disposed)return;try{if(player)player.remove()}finally{player=null;api=null;observer.releaseRetained();try{observer.restore()}finally{consoleObserver.restore();disposed=true}}};
