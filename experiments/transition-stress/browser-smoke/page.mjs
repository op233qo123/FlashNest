import {installConsoleObserver} from './console-observer.mjs';
const e={loaded:false,observerInstalled:false,playing:false,traces:[],errors:[],warnings:[],actions:[],pointers:[],overflow:false};window.evidence=e;
let player=null,api=null,disposed=false;
function append(list,value,max=512){if(list.length>=max){e.overflow=true;return}list.push(value)}
function error(value){append(e.errors,String(value).slice(0,2048),64)}
window.addEventListener('error',event=>error('window.error: '+event.message));window.addEventListener('unhandledrejection',event=>error('unhandledrejection: '+String(event.reason)));
const logger=installConsoleObserver(console,{reportError:(message,method)=>error('console.'+method+': '+message),reportWarning:message=>append(e.warnings,message.slice(0,2048),64),onText:text=>{const m=text.match(/New Ruffle instance created .*WebAssembly extensions: (ON|OFF).*Used renderer: ([^)]+)\)/);if(m){e.extensions=m[1];e.renderer=m[2]}}});
window.RufflePlayer={config:{autoplay:'off',unmuteOverlay:'hidden',warnOnUnsupportedContent:false,backgroundExecutionMode:'none'}};
const script=document.createElement('script');script.src='/runtime/ruffle.js';script.onload=()=>window.runtimeReady=true;script.onerror=()=>error('Runtime loader failed');document.head.append(script);
window.start=async()=>{
 if(player||disposed)throw Error('Only one original player allowed');
 player=window.RufflePlayer.newest().createPlayer();api=player.ruffle();document.getElementById('host').append(player);
 try{
  await api.load({url:'/fixtures/main.swf',base:new URL('/fixtures/',location.href).href,autoplay:'off',unmuteOverlay:'hidden',preferredRenderer:'webgl',quality:'low',backgroundExecutionMode:'none',allowScriptAccess:false});
  api.traceObserver=message=>append(e.traces,String(message),512);e.observerInstalled=true;
  const canvas=player.shadowRoot?.querySelector('canvas');if(!canvas)throw Error('Missing renderer canvas');
  const gl2=canvas.getContext('webgl2'),gl=gl2||canvas.getContext('webgl');if(!gl)throw Error('Missing actual WebGL context');
  e.context={kind:gl2?'webgl2':'webgl',lost:gl.isContextLost(),drawingBufferWidth:gl.drawingBufferWidth,drawingBufferHeight:gl.drawingBufferHeight,dpr:devicePixelRatio};if(e.context.lost)throw Error('Context already lost');
  canvas.addEventListener('webglcontextlost',()=>error('webglcontextlost'));
  for(const kind of ['pointerdown','pointerup'])canvas.addEventListener(kind,event=>append(e.pointers,{kind,trusted:event.isTrusted,pointerId:event.pointerId,pointerType:event.pointerType,button:event.button,x:event.offsetX,y:event.offsetY},12),{capture:true,passive:true});
  e.loaded=true;
 }catch(err){error(err?.stack||err)}
};
document.getElementById('resume').onclick=event=>{append(e.actions,{name:'resume',trusted:event.isTrusted},4);try{if(!event.isTrusted||!api)throw Error('Expected trusted resume after load');api.resume();e.playing=api.isPlaying}catch(err){error(err?.stack||err)}};
window.canvasRect=()=>{const canvas=player?.shadowRoot?.querySelector('canvas');if(!canvas)throw Error('No canvas');const r=canvas.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,viewportWidth:innerWidth,viewportHeight:innerHeight,dpr:devicePixelRatio}};
window.snapshot=()=>({...structuredClone(e),playing:api?.isPlaying??false});
window.dispose=()=>{if(disposed)return;try{player?.remove()}finally{player=null;api=null;logger.restore();disposed=true}};
