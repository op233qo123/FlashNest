/* TEST ONLY: adds Promise reactions, including rejection observation. No clone/copy/second read.
   Same Promise/receiver/result/error does NOT mean zero scheduling/unhandled-rejection impact. */
(() => {
  'use strict';
  if (window.__sceneBodyDiagnostic) return;
  const rows = [], responses = new WeakMap();
  let nextID = 0, overflow = 0;
  const originalFetch = window.fetch;
  const originalArrayBuffer = Response.prototype.arrayBuffer;
  function record(phase, entry, extra = {}) {
    try {
      if (rows.length >= 32) { overflow = Math.min(overflow + 1, 999); return; }
      rows.push({sequence: rows.length + 1, phase, id: entry.id, asset: entry.asset,
                 timeMs: performance.now(), ...extra});
    } catch (_) { /* Observation must not throw into original operation. */ }
  }
  function assetOf(value) {
    try {
      const url = new URL(typeof value === 'string' ? value : value.url, window.location.href);
      if (url.origin !== window.location.origin) return null;
      const match = url.pathname.match(/\/(main|old|new)\.swf$/);
      return match ? match[1] + '.swf' : null;
    } catch (_) { return null; }
  }
  window.fetch = function (...args) {
    const asset = assetOf(args[0]);
    if (!asset) return Reflect.apply(originalFetch, this, args);
    const entry = {id: ++nextID, asset};
    record('request', entry);
    let promise;
    try { promise = Reflect.apply(originalFetch, this, args); }
    catch (error) { record('fetch-sync-error', entry); throw error; }
    // The returned operation is still the exact original Promise.
    promise.then(response => {
      try { responses.set(response, entry); record('headers', entry, {status: response.status}); }
      catch (_) { /* no retained response/body */ }
    }, () => { record('fetch-rejected', entry); });
    return promise;
  };
  Response.prototype.arrayBuffer = function (...args) {
    const entry = responses.get(this);
    if (!entry) return Reflect.apply(originalArrayBuffer, this, args);
    record('array-buffer-start', entry);
    let promise;
    try { promise = Reflect.apply(originalArrayBuffer, this, args); }
    catch (error) { record('array-buffer-sync-error', entry); throw error; }
    promise.then(buffer => {
      try { record('array-buffer-complete', entry, {byteLength: buffer.byteLength}); }
      catch (_) { /* never retain buffer or copy bytes */ }
    }, () => { record('array-buffer-rejected', entry); });
    return promise;
  };
  window.__sceneBodyDiagnostic = Object.freeze({snapshot() {
    return {schema: 'flashnest-scene-body-observer-v1', records: rows.map(row => ({...row})),
            overflow, promiseReactionsAdded: true, unhandledRejectionObservationChanged: true,
            wasmCopyObservable: false, decompressionObservable: false};
  }});
})();
