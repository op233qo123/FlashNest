// SIMULATOR TEST HOST ONLY. Transparent observation; never sets quality, scale,
// CSS, renderer attributes, input, viewport, or WebGL state. No private assets.
(() => {
  'use strict';
  if (window.__samplingNativeProbe) throw Error('Duplicate sampling probe');
  const quality = new URLSearchParams(location.search).get('nativeSamplingQuality');
  if (quality !== null && !['low', 'high'].includes(quality)) throw Error('Invalid diagnostic quality');
  Object.defineProperty(window, '__samplingNativeDiagnosticQuality', {value: quality, writable: false});
  let loadObservation = null;
  const contexts = new WeakMap(), events = [], contextEvents = [], consoleMessages = [];
  let renderer = null, overflow = false, diagnosticOverflow = false, allocations = 0;
  // Primitive-only bounded identity telemetry. Weak keys never retain canvases or GL receivers.
  const canvasIdentities = new WeakMap(), contextIdentities = new WeakMap();
  const canvasRecords = [], contextRecords = [], getContextCalls = [];
  let nextCanvasId = 1, nextContextId = 1, getContextCallCount = 0, identityObservationErrors = 0;
  const now = () => typeof performance.now === 'function' ? performance.now() : null;
  const objectLike = value => value !== null && (typeof value === 'object' || typeof value === 'function');
  const observeSafely = callback => {
    try { return callback(); }
    catch { if (identityObservationErrors < 1000000) identityObservationErrors++; diagnosticOverflow = true; return null; }
  };
  const canvasIdentity = canvas => {
    if (!objectLike(canvas)) return null;
    let state = canvasIdentities.get(canvas);
    if (!state) {
      if (nextCanvasId > 1000000) { diagnosticOverflow = true; return null; }
      state = {canvasId: nextCanvasId++, firstObservedAtMs: now(), returnObserved: false,
        lastReturnContextId: null, lastNonNullContextId: null, knownContextIds: []};
      canvasIdentities.set(canvas, state);
      if (canvasRecords.length < 8) canvasRecords.push(state); else diagnosticOverflow = true;
    }
    return state;
  };
  const contextIdentity = (context, canvas, type, returnedByGetContext = false) => {
    if (!objectLike(context)) return null;
    let state = contextIdentities.get(context);
    if (!state) {
      if (nextContextId > 1000000) { diagnosticOverflow = true; return null; }
      state = {contextId: nextContextId++, canvasId: canvasIdentity(canvas)?.canvasId ?? null,
        firstObservedAtMs: now(), firstObservedType: type, returnedByGetContext,
        getContextReturns: 0, calls: {}, failedCalls: {}, lastCallAtMs: null};
      contextIdentities.set(context, state);
      if (contextRecords.length < 16) contextRecords.push(state); else diagnosticOverflow = true;
    }
    if (returnedByGetContext) {
      state.returnedByGetContext = true;
      if (state.getContextReturns < 1000000) state.getContextReturns++; else diagnosticOverflow = true;
    }
    return state;
  };
  const recordGetContext = (canvas, args, context, threw) => {
    const state = canvasIdentity(canvas), type = typeof args[0] === 'string' ? args[0] : 'non-string-argument';
    const returned = !threw && objectLike(context) ? contextIdentity(context, context.canvas ?? canvas, type, true) : null;
    const id = returned?.contextId ?? null;
    if (getContextCallCount < 1000000) getContextCallCount++; else diagnosticOverflow = true;
    const item = {call: getContextCallCount, observedAtMs: now(), canvasId: state?.canvasId ?? null,
      requestedType: type, threw, returnedContextId: id, returnedContextCanvasId: returned?.canvasId ?? null,
      sameAsPreviousReturn: !threw && state?.returnObserved === true ? state.lastReturnContextId === id : null,
      previousNonNullContextId: state?.lastNonNullContextId ?? null};
    if (getContextCalls.length < 32) getContextCalls.push(item); else diagnosticOverflow = true;
    if (state && !threw) {
      state.returnObserved = true; state.lastReturnContextId = id;
      if (id !== null) {
        state.lastNonNullContextId = id;
        if (!state.knownContextIds.includes(id)) {
          if (state.knownContextIds.length < 8) state.knownContextIds.push(id); else diagnosticOverflow = true;
        }
      }
    }
    return returned;
  };
  const recordReceiverCall = (receiver, method, failed) => observeSafely(() => {
    const state = contextIdentity(receiver, receiver.canvas, 'draw-or-storage-receiver-unseen');
    if (!state) return;
    const counts = failed ? state.failedCalls : state.calls, count = counts[method] ?? 0;
    if (count < 1000000) counts[method] = count + 1; else diagnosticOverflow = true;
    state.lastCallAtMs = now();
  });
  const observedCanvases = new WeakSet();
  const observeInput = canvas => {
    if (observedCanvases.has(canvas)) return;
    observedCanvases.add(canvas);
    let lastMove = null;
    canvas.addEventListener('pointermove', event => {
      const rect = canvas.getBoundingClientRect();
      lastMove = {type: 'pointermove', offsetX: event.offsetX, offsetY: event.offsetY,
        x: event.clientX, y: event.clientY, rect: [rect.x, rect.y, rect.width, rect.height],
        trusted: event.isTrusted, pointerType: event.pointerType, id: event.pointerId};
    }, {capture: true, passive: true});
    for (const type of ['pointerdown', 'pointerup', 'pointercancel']) {
      canvas.addEventListener(type, event => {
        if (events.length >= 64) { overflow = true; return; }
        if (type === 'pointerdown') lastMove = null;
        const rect = canvas.getBoundingClientRect();
        events.push({type, trusted: event.isTrusted, x: event.clientX, y: event.clientY,
          offsetX: event.offsetX, offsetY: event.offsetY, rect: [rect.x, rect.y, rect.width, rect.height],
          pointerType: event.pointerType, id: event.pointerId, lastMove});
      }, {capture: true, passive: true});
    }
  };
  const original = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (...args) {
    let context;
    try { context = Reflect.apply(original, this, args); }
    catch (error) { observeSafely(() => recordGetContext(this, args, null, true)); throw error; }
    observeSafely(() => {
      observeInput(this);
      const returned = recordGetContext(this, args, context, false);
      if (context && !contexts.has(this)) {
        // Preserve the OLD first-successful-context measurement selection so the
        // new IDs can expose a stale selection instead of silently repairing it.
        contexts.set(this, { context, type: typeof args[0] === 'string' ? args[0] : 'non-string-argument',
          storage: [], calls: {}, contextId: returned?.contextId ?? null });
        for (const type of ['webglcontextlost', 'webglcontextrestored']) {
          this.addEventListener(type, event => {
            observeSafely(() => {
              const state = canvasIdentity(this);
              if (contextEvents.length < 16) contextEvents.push({type, trusted: event.isTrusted,
                observedAtMs: now(), eventTimeStampMs: typeof event.timeStamp === 'number' ? event.timeStamp : null,
                canvasId: state?.canvasId ?? null,
                eventTargetCanvasId: canvasIdentities.get(event.target)?.canvasId ?? null,
                measuredContextId: contexts.get(this)?.contextId ?? null,
                lastNonNullContextId: state?.lastNonNullContextId ?? null,
                knownContextIds: state?.knownContextIds.slice() ?? [],
                association: 'canvas event; no context object supplied by event'});
              else diagnosticOverflow = true;
            });
            // No preventDefault: observation must preserve native recovery behavior.
          }, {passive: true});
        }
      }
    });
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
      let result;
      try { result = Reflect.apply(fn, this, args); }
      catch (error) { recordReceiverCall(this, method, true); throw error; }
      recordReceiverCall(this, method, false);
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
  // Count calls the renderer already makes. Do not read pixels, clear errors,
  // flush/finish, bind a framebuffer, or add rendering work.
  for (const constructor of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) {
    if (!constructor) continue;
    for (const method of ['clear', 'drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced', 'blitFramebuffer']) {
      const descriptor = Object.getOwnPropertyDescriptor(constructor.prototype, method);
      const fn = descriptor?.value;
      if (typeof fn !== 'function') continue; // Only own methods: inherited wrappers must not double count.
      constructor.prototype[method] = function (...args) {
        let result;
        try { result = Reflect.apply(fn, this, args); }
        catch (error) { recordReceiverCall(this, method, true); throw error; }
        recordReceiverCall(this, method, false);
        const entry = contexts.get(this.canvas);
        if (entry) {
          const count = entry.calls[method] ?? 0;
          if (count < 1000000) entry.calls[method] = count + 1; else diagnosticOverflow = true;
        }
        return result;
      };
    }
  }
  for (const level of ['warn', 'error']) {
    const fn = console[level];
    if (typeof fn !== 'function') continue;
    console[level] = function (...args) {
      // No object serialization/getters/stacks; synthetic page primitive text only.
      const message = args.filter(a => ['string', 'number', 'boolean'].includes(typeof a)).join(' ').replace(/(?:https?|file):\/\/\S+/gi, '[URL]').slice(0, 512);
      if (consoleMessages.length < 32) consoleMessages.push({level, message}); else diagnosticOverflow = true;
      return Reflect.apply(fn, this, args);
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
  const measure = () => {
    const player = document.querySelector('ruffle-player'), canvas = player?.shadowRoot?.querySelector('canvas');
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect(), entry = contexts.get(canvas), gl = entry?.context;
    const attributes = Object.fromEntries([...canvas.attributes].filter(a => a.name.startsWith('data-flashnest-')).map(a => [a.name, a.value]));
    return {canvas: [canvas.width, canvas.height], client: [canvas.clientWidth, canvas.clientHeight],
      css: [rect.x, rect.y, rect.width, rect.height], dpr: devicePixelRatio,
      gl: gl && /^webgl|^experimental-webgl/.test(entry.type) ? [gl.drawingBufferWidth, gl.drawingBufferHeight] : null,
      contextSelection: 'legacy-first-successful-getContext-per-canvas',
      currentCanvasId: canvasIdentities.get(canvas)?.canvasId ?? null,
      measuredContextId: entry?.contextId ?? null,
      currentCanvasLastNonNullContextId: canvasIdentities.get(canvas)?.lastNonNullContextId ?? null,
      identityObservationErrors, getContextCallCount, getContextCalls: getContextCalls.map(x => ({...x})),
      canvasIdentities: canvasRecords.map(x => ({...x, knownContextIds: x.knownContextIds.slice()})),
      contextIdentities: contextRecords.map(x => ({...x, calls: {...x.calls}, failedCalls: {...x.failedCalls}})),
      context: entry?.type ?? null, storage: entry?.storage ?? [], allocations,
      contextLost: typeof gl?.isContextLost === 'function' ? gl.isContextLost() : null,
      contextAttributes: typeof gl?.getContextAttributes === 'function' ? gl.getContextAttributes() : null,
      renderCalls: {...(entry?.calls ?? {})}, contextEvents: contextEvents.slice(), consoleMessages: consoleMessages.slice(),
      canvasConnected: canvas.isConnected, visibilityState: document.visibilityState, diagnosticOverflow,
      sampledAtMs: typeof performance.now === 'function' ? performance.now() : null,
      mobileQualityBranch: typeof window.orientation !== 'undefined', diagnosticLaunchQuality: quality,
      loadObservation, renderer, attributes, events: events.slice(), overflow,
      wasm: performance.getEntriesByType('resource').map(r => new URL(r.name).pathname.split('/').pop()).filter(n => /^[a-zA-Z0-9._-]+\.wasm$/.test(n)),
      hidden: document.hidden, focused: document.activeElement === player};
  };
  const observeLoad = (api, config) => {
    if (loadObservation !== null) { loadObservation.count++; overflow = true; }
    else loadObservation = {count: 1, rendererQuery: new URLSearchParams(location.search).get('renderer'),
      hasPreferredRenderer: Object.prototype.hasOwnProperty.call(config, 'preferredRenderer'),
      preferredRenderer: config.preferredRenderer ?? null,
      hasQuality: Object.prototype.hasOwnProperty.call(config, 'quality'),
      renderScale: config.renderScale ?? 1};
    return Reflect.apply(api.load, api, [config]);
  };
  Object.defineProperty(window, '__samplingNativeProbe', {value: Object.freeze({measure, observeLoad}), writable: false});
})();
