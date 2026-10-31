/* Scalar-only WebGL request observation. No GPU allocation/free success claims. */
(function (root) {
  'use strict';
  function install(env, options = {}) {
    const cap = options.cap || 16000;
    const events = [], contexts = [], textures = [];
    const contextMap = new WeakMap(), textureMap = new WeakMap();
    let overflow = false;
    function event(entry) {
      if (events.length < cap) events.push({ seq: events.length, ...entry });
      else overflow = true;
    }
    function state(gl) {
      let s = contextMap.get(gl);
      if (!s) {
        s = { id: contexts.length, type: 'unregistered', activeUnit: 33984, bindings: {}, calls: {}, thrown: {}, losses: 0, restores: 0 };
        contexts.push(s); contextMap.set(gl, s);
      }
      return s;
    }
    function tid(texture) { return texture ? textureMap.get(texture) : undefined; }
    function bound(s, target) { return s.bindings[s.activeUnit + ':' + target]; }
    function dimensions(name, a) {
      if (name === 'texImage2D') {
        if (a.length >= 9) return { level: a[1], width: a[3], height: a[4], format: a[6], type: a[7], sourceKind: a[8] === null ? 'null' : (ArrayBuffer.isView(a[8]) ? 'view' : typeof a[8]) };
        if (a.length === 6) return { level: a[1], width: a[5]?.videoWidth || a[5]?.naturalWidth || a[5]?.width, height: a[5]?.videoHeight || a[5]?.naturalHeight || a[5]?.height, format: a[3], type: a[4], sourceKind: 'image-source' };
      }
      if (name === 'texSubImage2D') {
        if (a.length >= 9) return { level: a[1], width: a[4], height: a[5], format: a[6], type: a[7], sourceKind: ArrayBuffer.isView(a[8]) ? 'view' : typeof a[8] };
        if (a.length === 7) return { level: a[1], width: a[6]?.videoWidth || a[6]?.naturalWidth || a[6]?.width, height: a[6]?.videoHeight || a[6]?.naturalHeight || a[6]?.height, format: a[4], type: a[5], sourceKind: 'image-source' };
      }
      if (name === 'texStorage2D') return { level: 0, levels: a[1], width: a[3], height: a[4], format: a[2], type: null, sourceKind: 'storage' };
      return null;
    }
    const names = ['createTexture', 'deleteTexture', 'bindTexture', 'activeTexture', 'texImage2D', 'texSubImage2D', 'texStorage2D', 'generateMipmap', 'drawElements', 'drawArrays', 'drawElementsInstanced', 'drawArraysInstanced', 'compressedTexImage2D', 'compressedTexSubImage2D', 'texImage3D', 'texSubImage3D', 'texStorage3D', 'copyTexImage2D', 'copyTexSubImage2D'];
    for (const ctor of [env.WebGLRenderingContext, env.WebGL2RenderingContext]) {
      if (!ctor) continue;
      for (const name of names) {
        const original = ctor.prototype[name];
        if (!original || original.textureLifetimeWrapped) continue;
        const wrapper = function (...args) {
          const s = state(this); s.calls[name] = (s.calls[name] || 0) + 1;
          let result;
          try { result = Reflect.apply(original, this, args); }
          catch (error) { s.thrown[name] = (s.thrown[name] || 0) + 1; event({ context: s.id, name, threw: true }); throw error; }
          if (name.startsWith('draw')) return result;
          if (name === 'activeTexture') { s.activeUnit = args[0]; return result; }
          if (name === 'bindTexture') { s.bindings[s.activeUnit + ':' + args[0]] = tid(args[1]) ?? null; return result; }
          if (name === 'createTexture') {
            const id = result ? textures.length : null;
            if (result) { textureMap.set(result, id); textures.push({ id, context: s.id, deleteRequested: false, deleteCalls: 0, baseWidth: null, baseHeight: null, expectedBaseRGBA8Bytes: null, uploads: 0, target512Uploads: 0 }); }
            event({ context: s.id, name, texture: id }); return result;
          }
          if (name === 'deleteTexture') {
            const id = tid(args[0]);
            if (id !== undefined) { const t = textures[id]; t.deleteCalls++; t.deleteRequested = true; for (const key of Object.keys(s.bindings)) if (s.bindings[key] === id) s.bindings[key] = null; }
            event({ context: s.id, name, texture: id ?? null, nullArgument: args[0] === null }); return result;
          }
          const id = bound(s, args[0]), t = id == null ? null : textures[id];
          const d = dimensions(name, args);
          const entry = { context: s.id, name, texture: id ?? null, target: args[0] };
          if (d) {
            const valid = Number.isInteger(d.width) && Number.isInteger(d.height) && d.width >= 0 && d.height >= 0;
            Object.assign(entry, { level: d.level, width: valid ? d.width : null, height: valid ? d.height : null, format: d.format, type: d.type, sourceKind: d.sourceKind });
            const source = name === 'texStorage2D' ? null : args[(name === 'texImage2D' && args.length === 6) ? 5 : (name === 'texSubImage2D' && args.length === 7) ? 6 : 8];
            entry.sourceViewByteLength = ArrayBuffer.isView(source) ? source.byteLength : null;
            // Only texture2D base-level RGBA8-compatible request sizes are estimated.
            const rgba8 = args[0] === 3553 && valid && ((name === 'texStorage2D' && d.format === 32856) || (d.format === 6408 && d.type === 5121));
            entry.expectedRequestRGBA8Bytes = rgba8 ? d.width * d.height * 4 : null;
            if (t) {
              t.uploads++;
              if (d.width === 512 && d.height === 512) t.target512Uploads++;
              if ((name === 'texImage2D' || name === 'texStorage2D') && d.level === 0) {
                t.baseWidth = valid ? d.width : null; t.baseHeight = valid ? d.height : null;
                t.expectedBaseRGBA8Bytes = rgba8 ? d.width * d.height * 4 : null;
              }
            }
          } else if (t && (name.includes('Image') || name.includes('Storage'))) {
            // Unhandled redefinitions cannot retain a formerly known size estimate.
            if (name === 'compressedTexImage2D' || name === 'copyTexImage2D') t.expectedBaseRGBA8Bytes = null;
          }
          event(entry); return result;
        };
        wrapper.textureLifetimeWrapped = true; ctor.prototype[name] = wrapper;
      }
    }
    function register(gl, type, canvas) {
      const s = state(gl); s.type = type;
      if (canvas && !s.listenersAttached) {
        s.listenersAttached = true;
        canvas.addEventListener('webglcontextlost', () => { s.losses++; event({ context: s.id, name: 'contextlost' }); });
        canvas.addEventListener('webglcontextrestored', () => { s.restores++; event({ context: s.id, name: 'contextrestored' }); });
      }
    }
    function summary() {
      const pending = textures.filter(t => !t.deleteRequested);
      return { createdReturnedObjects: textures.length, deleteRequestedUnique: textures.length - pending.length, notDeleteRequested: pending.length, knownExpectedBaseRGBA8Bytes: pending.reduce((n,t) => n + (t.expectedBaseRGBA8Bytes || 0), 0), unknownBaseSizeObjects: pending.filter(t => t.expectedBaseRGBA8Bytes === null).length, target512NotDeleteRequested: pending.filter(t => t.baseWidth === 512 && t.baseHeight === 512).length, target512ExpectedBaseRGBA8Bytes: pending.filter(t => t.baseWidth === 512 && t.baseHeight === 512).reduce((n,t) => n + (t.expectedBaseRGBA8Bytes || 0), 0) };
    }
    function snapshot() {
      return { scope: 'Observed API requests, not GL success, driver residency or physical GPU freeing. RGBA8 bytes are base-level dimension estimates, exclude mipmaps/overheads.', overflow,
        contexts: contexts.map(s => ({ id: s.id, type: s.type, calls: { ...s.calls }, thrown: { ...s.thrown }, losses: s.losses, restores: s.restores })),
        summary: summary(),
        textures: textures.map(t => ({ ...t })), events: events.map(e => ({ ...e })) };
    }
    return { register, snapshot, summary };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { install };
  else root.TextureLifetime = { install };
})(typeof window === 'undefined' ? globalThis : window);
