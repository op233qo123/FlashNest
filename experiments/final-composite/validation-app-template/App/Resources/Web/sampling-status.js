/* App-owned observation only: no renderer changes, CSS resizing or reloads. */
(() => {
  'use strict';
  const scales = new Set([1, .75, .5, .25]);
  const renderers = new Set(['webgl', 'wgpu-webgl', 'wgpu', 'canvas']);
  const dimension = value => Number.isInteger(value) && value > 0 && value <= 65536;
  function unknown(requested) {
    return {status:'unknown', requested, applied:null, renderer:'unknown', viewport:[0,0], canvas:[0,0], dpr:0, reason:'unconfirmed'};
  }
  function snapshot(canvas, requested, dpr) {
    const result = unknown(requested);
    if (!scales.has(requested) || !canvas || !Number.isFinite(dpr) || dpr <= 0 || dpr > 8) return result;
    const attr = name => canvas.getAttribute?.('data-flashnest-' + name);
    // Missing attributes must NOT become zero or a requested/config echo.
    const requestText=attr('render-request'), appliedText=attr('render-scale');
    const allowedText = new Set(['1','0.75','0.5','0.25']);
    if (!allowedText.has(requestText) || !allowedText.has(appliedText)) return result;
    const request=Number(requestText), applied=Number(appliedText), renderer=attr('renderer');
    const viewport=[Number(attr('viewport-width')),Number(attr('viewport-height'))];
    const pixels=[canvas.width,canvas.height];
    if (request!==requested || !renderers.has(renderer) || !viewport.every(dimension) || !pixels.every(dimension) ||
        !Number.isFinite(canvas.clientWidth) || !Number.isFinite(canvas.clientHeight) ||
        viewport[0]!==Math.floor(canvas.clientWidth*dpr) || viewport[1]!==Math.floor(canvas.clientHeight*dpr) ||
        !(applied===requested || applied===1) ||
        pixels.some((n,i)=>n!==Math.max(1,Math.round(viewport[i]*applied)))) return result;
    const fallback=requested<1 && applied===1;
    return {status:fallback?'fallback':'applied',requested,applied,renderer,viewport,canvas:pixels,dpr,reason:fallback?'original-fallback':'observed'};
  }
  function create({session,requested,getCanvas,getRoot,getDPR,send,schedule,cancel,Observer}) {
    let sequence=0, last='', disposed=false, pending=null, observed=null, observer=null, lost=false;
    let root=null, rootObserver=null, onLost=null, onRestored=null, canvasReady=false, rootReady=false;
    const validSession=typeof session==='string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(session);
    function emit(state) {
      if (disposed || !validSession || !scales.has(requested) || sequence>=1000000000) return;
      const key=JSON.stringify(state); if (key===last) return;
      sequence++;
      try { send({type:'samplingStatus',session,sequence,...state}); last=key; }
      catch (_) { /* Observation must never interrupt playback; retry on next observation. */ }
    }
    const safely = action => { try { return action(); } catch (_) { emit(unknown(requested)); } };
    function detachCanvas() {
      try { observer?.disconnect(); } catch (_) {}
      try { observed?.removeEventListener?.('webglcontextlost',onLost); } catch (_) {}
      try { observed?.removeEventListener?.('webglcontextrestored',onRestored); } catch (_) {}
      observer=null; observed=null; onLost=null; onRestored=null; canvasReady=false;
    }
    function connect() {
      if (typeof Observer !== 'function') throw Error('Sampling observation unavailable');
      const currentRoot=getRoot?.();
      if (currentRoot!==root || !rootReady) {
        try { rootObserver?.disconnect(); } catch (_) {}
        root=currentRoot; rootObserver=null; rootReady=false;
        if (root && Observer) { rootObserver=new Observer(()=>safely(()=>{ if (getCanvas()!==observed) refresh(true); })); rootObserver.observe(root,{childList:true,subtree:true}); }
        rootReady=true;
      }
      const canvas=getCanvas();
      if (canvas===observed && canvasReady) return;
      if (canvas!==observed) lost=false;
      detachCanvas(); observed=canvas;
      if (canvas) {
        onLost=()=>safely(()=>{ if (disposed || observed!==canvas || getCanvas()!==canvas) return; lost=true; emit(unknown(requested)); });
        onRestored=()=>safely(()=>{ if (disposed || observed!==canvas || getCanvas()!==canvas) return; lost=false; refresh(true); });
        canvas.addEventListener?.('webglcontextlost',onLost);
        canvas.addEventListener?.('webglcontextrestored',onRestored);
        if (Observer) {
          observer=new Observer(()=>refresh());
          observer.observe(canvas,{attributes:true,attributeFilter:['width','height','data-flashnest-render-request','data-flashnest-render-scale','data-flashnest-viewport-width','data-flashnest-viewport-height','data-flashnest-renderer']});
          canvasReady=true;
        }
      }
    }
    function refresh(invalidate=false) {
      if (disposed) return;
      safely(()=>{
        if (invalidate) emit(unknown(requested));
        if (pending!==null) return;
        pending=schedule(()=>{ pending=null; if (disposed) return; safely(()=>{ connect(); emit(lost?unknown(requested):snapshot(getCanvas(),requested,getDPR())); }); });
      });
    }
    function dispose() {
      if (disposed) return;
      emit(unknown(requested)); disposed=true;
      try { if (pending!==null) cancel(pending); } catch (_) {}
      pending=null; detachCanvas();
      try { rootObserver?.disconnect(); } catch (_) {}
      rootObserver=null; root=null;
    }
    emit(unknown(requested));
    return Object.freeze({refresh,dispose});
  }
  window.FlashNestSamplingStatus=Object.freeze({snapshot,create});
})();
