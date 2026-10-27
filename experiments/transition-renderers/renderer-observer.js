// Diagnostic only. Install before Ruffle; do not include in the production shell.
// Public preferredRenderer is a preference, so the banner AND actual context are
// observed. No getContext call, timer, event cancellation or engine setting here.
(function installRendererDiagnostic(root) {
  'use strict';
  const key = 'FlashNestRendererDiagnostic';
  if (Object.prototype.hasOwnProperty.call(root, key)) throw Error('Renderer observer already installed');
  const consoleObject = root.console, prototype = root.HTMLCanvasElement?.prototype;
  const logDescriptor = Object.getOwnPropertyDescriptor(consoleObject, 'log');
  const contextDescriptor = prototype && Object.getOwnPropertyDescriptor(prototype, 'getContext');
  if (!logDescriptor || !('value' in logDescriptor) || typeof logDescriptor.value !== 'function' ||
      !contextDescriptor || !('value' in contextDescriptor) || typeof contextDescriptor.value !== 'function') {
    throw Error('Renderer observer requires native data-property methods');
  }
  const originalLog = logDescriptor.value, originalGetContext = contextDescriptor.value;
  const contexts = new WeakMap(), watched = new WeakSet();
  let label = null, disposed = false;
  const state = {backend:'unknown', context:'unknown', lost:null, width:null, height:null,
    nativeDPR:0, lossEvents:0, bannerCount:0};
  const validBackends = new Set(['wgpu-webgl', 'webgpu', 'webgl', 'canvas']);
  const validContexts = new Set(['2d', 'webgl', 'webgl2', 'experimental-webgl', 'webgpu']);
  function snapshot() { return {...state}; }
  function publish() {
    if (disposed) return;
    try {
      if (!label && root.document.body) {
        if (root.document.getElementById('transition-renderer-status')) throw Error('Duplicate diagnostic label');
        label = root.document.createElement('output');
        label.id = 'transition-renderer-status';
        label.style.cssText = 'position:fixed;left:0;top:0;z-index:2147483647;max-width:100%;font:9px monospace;background:#fff;color:#000;pointer-events:none;overflow-wrap:anywhere;';
        root.document.body.appendChild(label);
      }
      if (label) label.textContent = 'FLASHNEST_RENDERER ' + JSON.stringify(snapshot());
    } catch (_) { /* Observation must not alter a runtime callback. */ }
  }
  function lost() {
    if (disposed) return;
    state.lossEvents = Math.min(1000000, state.lossEvents + 1);
    state.lost = true;
    publish();
  }
  const log = function (...args) {
    const result = Reflect.apply(originalLog, this, args);
    if (!disposed && typeof args[0] === 'string') {
      try {
        const match = args[0].match(/New Ruffle instance created .*WebAssembly extensions: (ON|OFF).*Used renderer: ([^)]+)\)/);
        if (match) {
          state.bannerCount = Math.min(1000000, state.bannerCount + 1);
          state.backend = state.bannerCount > 64 ? 'overflow' : validBackends.has(match[2]) ? match[2] : 'unsupported';
          publish();
        }
      } catch (_) { /* Preserve native console behavior. */ }
    }
    return result;
  };
  const getContext = function (...args) {
    const result = Reflect.apply(originalGetContext, this, args);
    if (!disposed && result !== null && typeof result === 'object' && typeof args[0] === 'string' && validContexts.has(args[0])) {
      try {
        // Weak keys do not root a canvas/context after player removal.
        if (!contexts.has(this)) contexts.set(this, {kind:args[0], value:result});
        if (!watched.has(this)) {
          this.addEventListener('webglcontextlost', lost);
          watched.add(this);
        }
      } catch (_) { /* Preserve native context result and exceptions. */ }
    }
    return result;
  };
  function sample(player) {
    if (disposed) throw Error('Renderer observer disposed');
    state.nativeDPR = Number.isFinite(root.devicePixelRatio) && root.devicePixelRatio > 0 ? root.devicePixelRatio : 0;
    try {
      const canvas = player?.shadowRoot?.querySelector('canvas');
      const recorded = canvas && contexts.get(canvas);
      state.context = recorded?.kind || 'unknown';
      state.lost = null; state.width = null; state.height = null;
      if (recorded) {
        const context = recorded.value;
        if (typeof context.isContextLost === 'function') state.lost = context.isContextLost();
        if (recorded.kind === 'webgl' || recorded.kind === 'webgl2' || recorded.kind === 'experimental-webgl') {
          state.width = context.drawingBufferWidth; state.height = context.drawingBufferHeight;
        } else { state.width = canvas.width; state.height = canvas.height; }
        if (!Number.isSafeInteger(state.width) || state.width < 0) state.width = null;
        if (!Number.isSafeInteger(state.height) || state.height < 0) state.height = null;
        if (typeof state.lost !== 'boolean') state.lost = null;
      }
    } catch (_) { state.context = 'unavailable'; state.lost = null; state.width = null; state.height = null; }
    publish();
    return snapshot();
  }
  function dispose() {
    if (disposed) return;
    if (Object.getOwnPropertyDescriptor(consoleObject, 'log')?.value !== log ||
        Object.getOwnPropertyDescriptor(prototype, 'getContext')?.value !== getContext) {
      throw Error('Renderer observer hook was replaced');
    }
    disposed = true;
    Object.defineProperty(consoleObject, 'log', logDescriptor);
    Object.defineProperty(prototype, 'getContext', contextDescriptor);
    // Listener has no canvas/player reference and becomes inert after disposal.
    label?.remove(); label = null;
    delete root[key];
  }
  try {
    Object.defineProperty(consoleObject, 'log', {...logDescriptor, value:log});
    Object.defineProperty(prototype, 'getContext', {...contextDescriptor, value:getContext});
    Object.defineProperty(root, key, {value:Object.freeze({sample, snapshot, dispose}), configurable:true});
  } catch (error) {
    Object.defineProperty(consoleObject, 'log', logDescriptor);
    Object.defineProperty(prototype, 'getContext', contextDescriptor);
    throw error;
  }
  publish();
})(window);
