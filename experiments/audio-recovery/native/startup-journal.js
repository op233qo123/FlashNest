/* Isolated diagnostic host only. No game, save, URL or error payloads. */
(() => {
  'use strict';
  const allowed = new Set(Object.keys(window.__FlashNestStartupResources || {}));
  const handler = window.webkit?.messageHandlers?.flashnestStartup;
  let sequence = 0, stopped = false;
  const phases = new Set(['document-start','shell-load-call','shell-load-return','loadeddata','context-created','context-state','audio-status','resource-request','resource-complete','instance-banner','disposed']);
  function record(phase, values = {}) {
    if (stopped || !phases.has(phase) || sequence >= 96 || !handler) return;
    const body = {schema:1, sequence:++sequence, phase};
    for (const key of ['contexts','contextId','operationId','intentId'])
      if (Number.isSafeInteger(values[key]) && values[key] >= 0 && values[key] <= 1000000000) body[key] = values[key];
    if (['suspended','running','closed','interrupted'].includes(values.state)) body.state=values.state;
    if (['bind','release','core-play','core-pause','visibility','unmute'].includes(values.audioPhase)) body.audioPhase=values.audioPhase;
    if (['bound','released','pending','fulfilled','rejected'].includes(values.status)) body.status=values.status;
    if (['extensions','mvp'].includes(values.flavor)) body.flavor=values.flavor;
    if (['wgpu-webgl','webgpu','webgl','canvas'].includes(values.backend)) body.backend=values.backend;
    if (typeof values.current === 'boolean') body.current=values.current;
    if (allowed.has(values.resource)) body.resource=values.resource;
    try { handler.postMessage(body); } catch (_) { /* Evidence failure must not change player behavior. */ }
  }
  function resource(value) {
    try {
      const raw = typeof value === 'string' ? value : value instanceof URL ? value.href :
        typeof Request === 'function' && value instanceof Request ? value.url : null;
      if(raw === null)return null;
      const url = new URL(raw, location.href);
      const basename = url.pathname.split('/').pop();
      return url.origin === location.origin && url.pathname === new URL('./runtime/', location.href).pathname + basename && allowed.has(basename) ? basename : null;
    } catch (_) { return null; }
  }
  const logOriginal=console.log;
  const logObserved=function(...args) {
    if(args.length === 2 && args[1] === 'background: #37528C; color: #FFAD33' && typeof args[0] === 'string') {
      const match=/^%cNew Ruffle instance created \(Version: [^\r\n]{1,128} \| WebAssembly extensions: (ON|OFF) \| Used renderer: (wgpu-webgl|webgpu|webgl|canvas)\)$/.exec(args[0]);
      if(match)record('instance-banner',{flavor:match[1]==='ON'?'extensions':'mvp',backend:match[2]});
    }
    return Reflect.apply(logOriginal,this,args);
  };
  console.log=logObserved;
  const fetchOriginal=window.fetch;
  const fetchObserved=function(...args) {
    const name=resource(args[0]);if(name)record('resource-request',{resource:name});
    return Reflect.apply(fetchOriginal,this,args); // Preserve EXACT native Promise and exceptions; no child Promise.
  };
  if (typeof fetchOriginal==='function') window.fetch=fetchObserved;
  let observer;
  if (typeof PerformanceObserver === 'function') {
    observer=new PerformanceObserver(list=>{
      for(const entry of list.getEntries()) { const name=resource(entry.name);if(name)record('resource-complete',{resource:name}); }
    });
    try { observer.observe({type:'resource',buffered:true}); } catch (_) { observer.disconnect(); }
  }
  window.FlashNestStartupJournal=Object.freeze({record,dispose(){
    record('disposed');stopped=true;observer?.disconnect();
    if(window.fetch===fetchObserved)window.fetch=fetchOriginal;
    if(console.log===logObserved)console.log=logOriginal;
  }});
  record('document-start');
})();
