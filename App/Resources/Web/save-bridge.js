/* App-owned logical SharedObject bridge for pinned Ruffle 0.7.1.
 * No game JavaScript, filesystem paths, hostnames, capabilities or package IDs
 * are part of a logical save identity. Native code validates and backs up again.
 */
(() => {
  'use strict';
  const limits = Object.freeze({entries:256, keyBytes:4096, objectBytes:1048576, totalBytes:8388608, archiveBytes:16777216});
  const utf8 = value => new TextEncoder().encode(value).byteLength;
  const fail = message => { throw new Error('Save validation failed: ' + message); };
  function hasSOLHeader(value) {
    if (typeof value !== 'string') return false;
    try {
      const bytes = atob(value.slice(0, 24));
      return bytes.length >= 16 && bytes.charCodeAt(0) === 0 && bytes.charCodeAt(1) === 191 &&
        bytes.slice(6, 10) === 'TCSO' && [0,4,0,0,0,0].every((x, i) => bytes.charCodeAt(10 + i) === x);
    } catch (_) { return false; }
  }
  function validateValue(value) {
    if (typeof value !== 'string' || value.length > Math.ceil(limits.objectBytes / 3) * 4) fail('object size');
    let bytes;
    try { bytes = atob(value); } catch (_) { fail('base64'); }
    if (btoa(bytes) !== value || !hasSOLHeader(value)) fail('SOL encoding');
    if (bytes.length > limits.objectBytes) fail('object size');
    return bytes.length;
  }
  function validateIdentity(scope, key) {
    if (typeof key !== 'string' || !key || utf8(key) > limits.keyBytes || /[\\:\x00-\x1f\x7f]/.test(key) ||
        key.split('/').some(part => part.startsWith('.'))) fail('logical identity');
    const name = value => !!value && (!value.includes('/') || value.startsWith('#'));
    if (scope === 'package') return;
    if (scope === 'origin' && name(key)) return;
    if (scope === 'ancestor' && ['games/','capability/'].some(prefix => key.startsWith(prefix) && name(key.slice(prefix.length)))) return;
    fail('logical scope');
  }
  function create({storage, location: pageLocation, packageID}) {
    const page = new URL(pageLocation), root = new URL('../', page);
    if (page.protocol !== 'http:' || page.hostname !== '127.0.0.1' || !/^[a-f0-9-]{36}$/i.test(packageID)) fail('player context');
    const pieces = root.pathname.split('/').filter(Boolean);
    if (pieces.length !== 1) fail('player root');
    const capability = pieces[0], host = page.hostname;
    const packagePrefix = `${host}/${capability}/games/${packageID}/`;
    const gamesPrefix = `${host}/${capability}/games/`;
    const capabilityPrefix = `${host}/${capability}/`;
    const originPrefix = `${host}//`;
    function logical(raw) {
      let entry;
      if (raw.startsWith(packagePrefix)) entry = {scope:'package', key:raw.slice(packagePrefix.length)};
      else if (raw.startsWith(gamesPrefix)) entry = {scope:'ancestor', key:'games/' + raw.slice(gamesPrefix.length)};
      else if (raw.startsWith(capabilityPrefix)) entry = {scope:'ancestor', key:'capability/' + raw.slice(capabilityPrefix.length)};
      else if (raw.startsWith(originPrefix)) entry = {scope:'origin', key:raw.slice(originPrefix.length)};
      else fail('unrecognized SharedObject scope');
      validateIdentity(entry.scope, entry.key);
      return entry;
    }
    function raw(entry) {
      validateIdentity(entry.scope, entry.key);
      if (entry.scope === 'package') return packagePrefix + entry.key;
      if (entry.scope === 'origin') return originPrefix + entry.key;
      if (entry.key.startsWith('games/')) return gamesPrefix + entry.key.slice(6);
      return capabilityPrefix + entry.key.slice(11);
    }
    function validate(capture) {
      if (!capture || capture.version !== 1 || !Array.isArray(capture.entries) || capture.entries.length > limits.entries) fail('capture structure');
      const identities = new Set(), result = [];
      let total = 0;
      for (const entry of capture.entries) {
        if (!entry || typeof entry !== 'object') fail('entry structure');
        const identity = raw(entry);
        // Re-parse to reject a forged shorter scope that aliases a longer one.
        const mapped = logical(identity);
        if (mapped.scope !== entry.scope || mapped.key !== entry.key || identities.has(identity)) fail('duplicate or ambiguous identity');
        identities.add(identity);
        total += validateValue(entry.value);
        if (total > limits.totalBytes) fail('total size');
        result.push({raw:identity, scope:entry.scope, key:entry.key, value:entry.value});
      }
      if (utf8(JSON.stringify(capture)) > limits.archiveBytes) fail('archive size');
      return result;
    }
    function inventory() {
      const entries = [];
      // Snapshot names before any writes; never enumerate a mutating Storage.
      const names = Array.from({length:storage.length}, (_, index) => storage.key(index));
      for (const identity of names) {
        if (typeof identity !== 'string') fail('storage changed during capture');
        const value = storage.getItem(identity);
        if (!hasSOLHeader(value)) continue; // Ruffle preferences and unrelated app data.
        const entry = logical(identity); // Unknown SOL fails closed, rather than silently losing it.
        entries.push({...entry, value});
        if (entries.length > limits.entries) fail('object count');
      }
      const capture = {version:1, entries};
      return {capture, validated:validate(capture)};
    }
    function capture() { return inventory().capture; }
    function restore(input) {
      const incoming = validate(input), existing = inventory().validated;
      const prior = new Map(existing.map(entry => [entry.raw, entry.value]));
      // Do not overwrite a same-named unrelated/non-SOL storage value.
      for (const entry of incoming) if (!prior.has(entry.raw) && storage.getItem(entry.raw) !== null) fail('storage key collision');
      const touched = new Set([...prior.keys(), ...incoming.map(entry => entry.raw)]);
      try {
        for (const key of prior.keys()) storage.removeItem(key);
        for (const entry of incoming) storage.setItem(entry.raw, entry.value);
      } catch (_) {
        try {
          for (const key of touched) storage.removeItem(key);
          for (const [key, value] of prior) storage.setItem(key, value);
        } catch (_) { fail('restore failed; rollback incomplete'); }
        fail('restore failed; previous storage restored');
      }
      return {count:incoming.length};
    }
    return Object.freeze({capture, restore});
  }
  window.FlashNestSaveBridge = Object.freeze({create});
})();
