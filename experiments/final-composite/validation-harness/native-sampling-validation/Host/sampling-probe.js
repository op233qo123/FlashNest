// SIMULATOR TEST HOST ONLY. Transparent observation; never sets quality, scale,
// CSS, renderer attributes, input, viewport, or WebGL state. No private assets.
(() => {
  'use strict';
  if (window.__samplingNativeProbe) throw Error('Duplicate sampling probe');
  const quality = new URLSearchParams(location.search).get('nativeSamplingQuality');
  if (quality !== null && !['low', 'high'].includes(quality)) throw Error('Invalid diagnostic quality');
  Object.defineProperty(window, '__samplingNativeDiagnosticQuality', {value: quality, writable: false});
  const contexts = new WeakMap(), events = [];
  let renderer = null, overflow = false, allocations = 0;
  const original = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (...args) {
    const context = Reflect.apply(original, this, args);
    if (context && !contexts.has(this)) contexts.set(this, { context, type: String(args[0]), storage: [] });
    return context;
  };
  // These are actual custom renderbuffer allocator arguments, NOT gl.SAMPLES
  // (which describes the unrelated default framebuffer). Keep unique tuples.
  for (const [constructor, method, samplesIndex, widthIndex, heightIndex] of [
    [window.WebGL2RenderingContext, 'renderbufferStorageMultisample', 1, 3, 4],
    [window.WebGLRenderingContext, 'renderbufferStorage', null, 2, 3]
  ]) {
    if (!constructor) continue;
    const fn = constructor.prototype[method];
    if (typeof fn !== 'function') continue;
    constructor.prototype[method] = function (...args) {
      const result = Reflect.apply(fn, this, args);
      const entry = contexts.get(this.canvas);
      if (entry) {
        allocations++;
        const tuple = [samplesIndex === null ? 1 : args[samplesIndex], args[widthIndex], args[heightIndex]];
        if (!entry.storage.some(t => t.every((n, i) => n === tuple[i]))) {
          if (entry.storage.length < 64) entry.storage.push(tuple); else overflow = true;
        }
      }
      return result;
    };
  }
  const log = console.log;
  console.log = function (...args) {
    if (typeof args[0] === 'string') {
      const m = args[0].match(/New Ruffle instance created .*\| Used renderer: ([^)]+)\)/);
      if (m) renderer = m[1];
    }
    return Reflect.apply(log, this, args);
  };
  for (const type of ['pointerdown', 'pointerup', 'pointercancel']) {
    document.addEventListener(type, event => {
      const canvas = document.querySelector('ruffle-player')?.shadowRoot?.querySelector('canvas');
      if (!canvas || !event.composedPath().includes(canvas)) return;
      if (events.length >= 64) { overflow = true; return; }
      events.push({type, trusted: event.isTrusted, x: event.clientX, y: event.clientY,
        pointerType: event.pointerType, id: event.pointerId});
    }, {capture: true, passive: true});
  }
  const measure = () => {
    const player = document.querySelector('ruffle-player'), canvas = player?.shadowRoot?.querySelector('canvas');
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect(), entry = contexts.get(canvas), gl = entry?.context;
    const attributes = Object.fromEntries([...canvas.attributes].filter(a => a.name.startsWith('data-flashnest-')).map(a => [a.name, a.value]));
    return {canvas: [canvas.width, canvas.height], client: [canvas.clientWidth, canvas.clientHeight],
      css: [rect.x, rect.y, rect.width, rect.height], dpr: devicePixelRatio,
      gl: gl && /^webgl|^experimental-webgl/.test(entry.type) ? [gl.drawingBufferWidth, gl.drawingBufferHeight] : null,
      context: entry?.type ?? null, storage: entry?.storage ?? [], allocations,
      mobileQualityBranch: typeof window.orientation !== 'undefined', diagnosticLaunchQuality: quality,
      renderer, attributes, events: events.slice(), overflow,
      wasm: performance.getEntriesByType('resource').map(r => new URL(r.name).pathname.split('/').pop()).filter(n => /^[a-zA-Z0-9._-]+\.wasm$/.test(n)),
      hidden: document.hidden, focused: document.activeElement === player};
  };
  Object.defineProperty(window, '__samplingNativeProbe', {value: Object.freeze({measure}), writable: false});
})();
