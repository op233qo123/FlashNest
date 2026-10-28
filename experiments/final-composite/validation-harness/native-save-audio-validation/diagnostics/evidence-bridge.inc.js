  // DIAGNOSTIC COPY ONLY: passive closure readers; no audio/runtime hooks.
  const latePageId = crypto.randomUUID();
  const lateTraces = [];
  let lateTrustedPlay = false, lateRoot = false, lateChild = false, lateChildSerial = 0;
  function lateObserveTrace(message) {
    if (typeof message !== 'string') return;
    if (lateTrustedPlay && message === 'LIFECYCLE_ROOT_READY:undefined') lateRoot = true;
    if (message === 'LIFECYCLE_CHILD_READY' && lateRoot) lateChild = true;
    const match = /^LIFECYCLE_CHILD_KEY:32:([1-9][0-9]*)$/.exec(message);
    if (match && lateChild && Number(match[1]) === lateChildSerial + 1) lateChildSerial++;
    if (/^LIFECYCLE_(ROOT_READY|CHILD_READY|CHILD_KEY|SAVE_BEFORE)/.test(message) && lateTraces.length < 32)
      lateTraces.push(message.slice(0, 128));
  }
  const latePlayButton = document.getElementById('start');
  latePlayButton.addEventListener('click', event => {
    if (event.isTrusted && event.target === latePlayButton && !latePlayButton.disabled &&
        !latePlayButton.hidden && latePlayButton.getClientRects().length > 0) lateTrustedPlay = true;
  }, true);
  // Fail closed: only this fixture's minimal AMF0 SOL is accepted, not a general decoder.
  function lateProgress420(value) {
    try {
      const raw = atob(value), bytes = Uint8Array.from(raw, c => c.charCodeAt(0));
      const view = new DataView(bytes.buffer);
      let offset = 16;
      const string = () => { const n = view.getUint16(offset); offset += 2;
        const result = raw.slice(offset, offset + n); offset += n; return result; };
      if (raw.slice(0,2) !== '\x00\xbf' || raw.slice(6,16) !== 'TCSO\x00\x04\x00\x00\x00\x00' ||
          view.getUint32(2) !== bytes.length - 6 || string() !== 'LifecycleFixture') return false;
      if (view.getUint32(offset) !== 0) return false; offset += 4;
      if (string() !== 'progress' || bytes[offset++] !== 0) return false;
      const progress = view.getFloat64(offset); offset += 8;
      return progress === 420 && bytes[offset++] === 0 && offset === bytes.length;
    } catch (_) { return false; }
  }
  function lateSnapshot() {
    const active = !!player && started && !paused && !backgrounded && !document.hidden && !closing && !fatal;
    let solSnapshot = '', saveReady = false;
    if (saveBridge && storageReady && !closing) {
      const capture = saveBridge.capture(); // Real synchronous validated SOL, never cached or seeded.
      const entries = capture.entries.map(({scope,key,value}) => ({scope,key,value}));
      entries.sort((a,b) => a.scope < b.scope ? -1 : a.scope > b.scope ? 1 : a.key < b.key ? -1 : a.key > b.key ? 1 : 0);
      if (entries.length) solSnapshot = JSON.stringify({version: capture.version, entries});
      saveReady = entries.length === 1 && entries[0].scope === 'origin' && entries[0].key === 'LifecycleFixture' &&
        lateProgress420(entries[0].value) && lateChild && lateChildSerial >= 1;
    }
    return {active, readiness: {trustedPlay: lateTrustedPlay, rootReady: lateRoot,
      childReady: lateChild && lateChildSerial >= 1, saveReady},
      continuity: {pageId: latePageId, childInputSerial: lateChildSerial, solSnapshot},
      solValueEvidence: 'strict-LifecycleFixture-AMF0-progress-420; other encodings fail closed',
      traceRecords: [...lateTraces]};
  }
  Object.defineProperty(window, 'FlashNestLateEvidence', {value: Object.freeze({snapshot: lateSnapshot}),
    writable: false, configurable: false});
