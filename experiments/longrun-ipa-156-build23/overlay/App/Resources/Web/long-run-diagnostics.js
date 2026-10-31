/* App-owned, opt-in, scalar-only long-run diagnostics. Never measures GPU/RSS. */
(function (root) {
  'use strict';
  const COUNT_MAX = 2147483647, BYTE_MAX = 1099511627776, ELAPSED_MAX = 1000000000000;
  const CONTEXT_MAX = 4, TEXTURE_METADATA_MAX = 16384, INTERVAL_MS = 10000;
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  function install(env, config) {
    // Missing/invalid native document-start configuration is an inert opt-out.
    if (!config || typeof config.session !== 'string' || !UUID.test(config.session) ||
        !Number.isInteger(config.epoch) || config.epoch < 1 || config.epoch > 9999999) return null;
    const bridge = env.webkit && env.webkit.messageHandlers && env.webkit.messageHandlers.flashnest;
    if (!bridge || typeof bridge.postMessage !== 'function' || typeof env.setInterval !== 'function' ||
        typeof env.clearInterval !== 'function') return null;
    const session = config.session, epoch = config.epoch;
    const contextMap = new WeakMap(), textureMap = new WeakMap(), installed = new WeakSet();
    // Entries hold scalar counters only. They never hold a GL context, texture,
    // pixel buffer, source image, URL, console text, or game object.
    const states = [], replacements = [], listeners = [];
    const totals = { contextLost: 0, contextRestored: 0, texturesCreated: 0, texturesDeleted: 0,
      textureUploads: 0, textureBytesEstimate: 0, unknownUploads: 0, drawCalls: 0,
      texImage2DNullishRequests: 0, texImage2DViewRequests: 0, texImage2DOtherRequests: 0,
      framebufferCreateRequests: 0, framebufferDeleteRequests: 0, framebufferTexture2DRequests: 0,
      renderbufferCreateRequests: 0, renderbufferDeleteRequests: 0,
      renderbufferStorageRequests: 0, renderbufferStorageMultisampleRequests: 0,
      hookFailures: 0, sendFailures: 0 };
    let active = true, overflow = false, seq = 0, elapsed = 0, timer = null, textureMetadataCount = 0;
    const clock = () => {
      try { const v = env.performance && env.performance.now(); if (Number.isFinite(v)) return v; } catch (_) {}
      return Date.now();
    };
    const start = clock();
    function add(name, amount = 1) {
      const max = name === 'textureBytesEstimate' ? BYTE_MAX : COUNT_MAX;
      if (!Number.isSafeInteger(amount) || amount < 0 || totals[name] > max - amount) {
        totals[name] = max; overflow = true;
      } else totals[name] += amount;
    }
    function failed() { add('hookFailures'); overflow = true; }
    function safe(action) { try { return action(); } catch (_) { failed(); return undefined; } }
    function object(value) { return value !== null && (typeof value === 'object' || typeof value === 'function'); }
    function state(gl) {
      if (!object(gl)) { failed(); return null; }
      let s = contextMap.get(gl);
      if (s !== undefined) return s;
      if (states.length === CONTEXT_MAX) { overflow = true; return null; }
      s = { id: states.length + 1, listening: false };
      states.push(s); contextMap.set(gl, s); return s;
    }
    function register(gl, canvas) {
      const s = state(gl);
      if (!s || s.listening || !canvas || typeof canvas.addEventListener !== 'function') return;
      const lost = () => { if (active) safe(() => add('contextLost')); };
      const restored = () => { if (active) safe(() => add('contextRestored')); };
      canvas.addEventListener('webglcontextlost', lost);
      try { canvas.addEventListener('webglcontextrestored', restored); } catch (error) {
        if (typeof canvas.removeEventListener === 'function') canvas.removeEventListener('webglcontextlost', lost);
        throw error;
      }
      s.listening = true;
      // Optional cleanup references are weak. On platforms without WeakRef the
      // callbacks are inert after stop and do not retain the canvas/context.
      if (typeof env.WeakRef === 'function') listeners.push({ canvas: new env.WeakRef(canvas), lost, restored });
    }
    function classifyTexImage2D(args) {
      // Overload shape only: never inspect source properties, pixels or byteLength.
      // Numeric PBO offsets and DOM-source overloads remain deliberately 'other'.
      let dimensions = args.length === 9 || args.length === 10;
      // Conservative scalar shape check, not WebGL validity/success validation.
      for (let i = 0; dimensions && i < 8; i++) {
        dimensions = Number.isSafeInteger(args[i]) && args[i] >= 0;
      }
      if (dimensions && args.length === 10) dimensions = Number.isSafeInteger(args[9]) && args[9] >= 0;
      if (dimensions && (args[8] === null || args[8] === undefined)) add('texImage2DNullishRequests');
      else if (dimensions && ArrayBuffer.isView(args[8])) add('texImage2DViewRequests');
      else add('texImage2DOtherRequests');
    }
    function upload(name, args) {
      add('textureUploads');
      // Only numeric, base-level 2D RGBA8 request dimensions. Never read source
      // pixel data or arbitrary image object properties. Other overloads unknown.
      let width, height, known = false;
      if ((name === 'texImage2D' || name === 'texSubImage2D') && args.length >= 9) {
        width = args[name === 'texImage2D' ? 3 : 4]; height = args[name === 'texImage2D' ? 4 : 5];
        known = args[0] === 3553 && args[1] === 0 && args[6] === 6408 && args[7] === 5121;
      } else if (name === 'texStorage2D' && args.length === 5) {
        width = args[3]; height = args[4]; known = args[0] === 3553 && args[2] === 32856 && args[1] === 1;
      }
      if (known && Number.isSafeInteger(width) && Number.isSafeInteger(height) &&
          width >= 0 && height >= 0 && width <= 16384 && height <= 16384) add('textureBytesEstimate', width * height * 4);
      else add('unknownUploads');
    }
    function replace(proto, name, make) {
      if (!proto) return;
      safe(() => {
        const original = proto[name];
        if (typeof original !== 'function' || installed.has(original)) return;
        const own = Object.getOwnPropertyDescriptor(proto, name);
        const wrapper = make(original);
        proto[name] = wrapper;
        if (proto[name] !== wrapper) { failed(); return; }
        installed.add(wrapper); replacements.push({ proto, name, original, own, wrapper });
      });
    }
    const uploadNames = ['texImage2D', 'texSubImage2D', 'texStorage2D', 'compressedTexImage2D',
      'compressedTexSubImage2D', 'texImage3D', 'texSubImage3D', 'texStorage3D', 'copyTexImage2D', 'copyTexSubImage2D'];
    // These count requests that return normally, NOT successful allocations,
    // unique resources, attachments, current ownership or physical memory.
    const resourceRequests = {
      createFramebuffer: 'framebufferCreateRequests', deleteFramebuffer: 'framebufferDeleteRequests',
      framebufferTexture2D: 'framebufferTexture2DRequests',
      createRenderbuffer: 'renderbufferCreateRequests', deleteRenderbuffer: 'renderbufferDeleteRequests',
      renderbufferStorage: 'renderbufferStorageRequests',
      renderbufferStorageMultisample: 'renderbufferStorageMultisampleRequests'
    };
    const drawNames = ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced'];
    try {
    for (const ctor of [env.WebGLRenderingContext, env.WebGL2RenderingContext]) {
      if (!ctor) continue;
      for (const name of ['createTexture', 'deleteTexture', ...uploadNames, ...drawNames, ...Object.keys(resourceRequests)]) {
        replace(ctor.prototype, name, original => function (...args) {
          // Original receiver/args/result/throw are preserved. No GL getError,
          // finishing, flushing, preventDefault, or recovery call is introduced.
          const result = Reflect.apply(original, this, args);
          if (active) safe(() => {
            const s = state(this); if (!s) return;
            if (name === 'createTexture') {
              if (object(result) && !textureMap.has(result)) {
                add('texturesCreated');
                if (textureMetadataCount < TEXTURE_METADATA_MAX) {
                  textureMetadataCount++; textureMap.set(result, { context: s.id, deleted: false });
                } else overflow = true; // Counters continue; unique-delete tracking is now incomplete.
              }
            } else if (name === 'deleteTexture') {
              const t = object(args[0]) ? textureMap.get(args[0]) : undefined;
              if (t && t.context === s.id && !t.deleted) { t.deleted = true; add('texturesDeleted'); }
            } else if (drawNames.includes(name)) add('drawCalls');
            else if (resourceRequests[name]) add(resourceRequests[name]);
            else {
              if (name === 'texImage2D') classifyTexImage2D(args);
              upload(name, args);
            }
          });
          return result;
        });
      }
    }
    for (const ctor of [env.HTMLCanvasElement, env.OffscreenCanvas]) {
      if (!ctor) continue;
      replace(ctor.prototype, 'getContext', original => function (...args) {
        const result = Reflect.apply(original, this, args);
        if (active && result && ['webgl', 'webgl2', 'experimental-webgl'].includes(args[0])) safe(() => register(result, this));
        return result;
      });
    }
    } catch (_) { failed(); stop(); return null; }
    function sample() {
      if (!active) return;
      safe(() => {
        if (seq === COUNT_MAX) { overflow = true; stop(); return; }
        const raw = Math.floor(clock() - start);
        if (!Number.isFinite(raw) || raw < elapsed) overflow = true;
        else elapsed = Math.min(raw, ELAPSED_MAX);
        if (raw > ELAPSED_MAX) overflow = true;
        const body = { type: 'longRunDiagnostics', schema: 2, session, wkEpoch: epoch,
          seq: ++seq, webElapsedMs: elapsed, contexts: states.length, ...totals, overflow };
        // wasmBytes is deliberately absent: the unchanged bundled engine does
        // not safely expose Memory. No instantiate/Promise interception is used.
        try { Reflect.apply(bridge.postMessage, bridge, [body]); } catch (_) { add('sendFailures'); }
      });
    }
    function stop() {
      if (!active) return;
      active = false;
      if (timer !== null) safe(() => env.clearInterval(timer));
      for (const item of listeners) safe(() => {
        const canvas = item.canvas.deref();
        if (canvas && typeof canvas.removeEventListener === 'function') {
          canvas.removeEventListener('webglcontextlost', item.lost);
          canvas.removeEventListener('webglcontextrestored', item.restored);
        }
      });
      for (const item of replacements.reverse()) safe(() => {
        if (item.proto[item.name] !== item.wrapper) return;
        if (item.own) Object.defineProperty(item.proto, item.name, item.own);
        else delete item.proto[item.name];
      });
    }
    try { timer = env.setInterval(sample, INTERVAL_MS); } catch (_) { failed(); stop(); return null; }
    sample();
    return Object.freeze({ stop, isActive: () => active });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { install };
  else {
    try {
      // Native generates this config for a new WK session only. An ordinary
      // page without the config does not modify any prototypes or start timers.
      if (Object.prototype.hasOwnProperty.call(root, '__FlashNestLongRunObserver')) return;
      const observer = install(root, root.__FlashNestLongRunConfig);
      if (observer) {
        try { Object.defineProperty(root, '__FlashNestLongRunObserver', { value: observer, configurable: true }); }
        catch (_) { observer.stop(); }
      }
    } catch (_) { /* Optional diagnostics must never prevent player startup. */ }
  }
})(typeof window === 'undefined' ? globalThis : window);
