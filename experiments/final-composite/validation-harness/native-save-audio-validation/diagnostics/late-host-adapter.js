/* LOCAL diagnostic-host adapter. Loaded only after native readiness; never a WK document-start script. */
(() => {
  'use strict';
  if (window.FlashNestLateHost) throw new Error('late adapter already loaded');
  let probe = null, captureState = 'not-started', error = null, disposed = false;
  const evidence = () => window.FlashNestLateEvidence.snapshot();
  function snapshot() {
    const state = probe?.status() ?? null, observed = evidence();
    const warningVisible = !document.getElementById('audio-warning').hidden;
    const pending = state?.retryOperation, fulfilled = state?.fulfilledRetry;
    const retryReady = !!state && !disposed && state.failure === null && state.failures?.length === 0 &&
      observed.active && !warningVisible && state.contextState === 'running' && state.trustedRetries === 1 &&
      !!pending && !!fulfilled && pending.current === true && fulfilled.current === true &&
      pending.phase === 'core-play' && fulfilled.phase === 'core-play' &&
      pending.operation === 'resume' && fulfilled.operation === 'resume' &&
      pending.status === 'pending' && fulfilled.status === 'fulfilled' && fulfilled.state === 'running' &&
      pending.contextId === state.contextId && fulfilled.contextId === state.contextId &&
      pending.operationId === fulfilled.operationId && pending.intentId === fulfilled.intentId;
    return {schema: 1, probe: state, captureState, error, disposed, warningVisible, retryReady, ...observed};
  }
  function begin(mode) {
    if (probe || disposed || !['candidate-known','candidate-unknown','baseline-known'].includes(mode)) throw new Error('invalid/duplicate begin');
    const observed = evidence();
    if (!observed.active || Object.values(observed.readiness).some(value => value !== true)) throw new Error('native and fixture readiness required');
    const players = document.querySelectorAll('ruffle-player');
    if (players.length !== 1) throw new Error('exact sole player required');
    probe = window.FlashNestLateAudioProbe.create({mode: mode === 'baseline-known' ? 'baseline' : 'candidate',
      player: players[0], button: document.getElementById('audio-retry'), panel: document.getElementById('audio-warning'),
      isActive: () => evidence().active, readiness: () => evidence().readiness, continuity: () => evidence().continuity});
    captureState = 'pending';
    try {
      probe.capture(() => window.FlashNest.resume());
      // WK evaluateJavaScript does not await Promises. Native polls this state.
      probe.completeCapture().then(() => { if (!disposed) captureState = 'fulfilled'; }, reason => {
        captureState = 'rejected'; error = String(reason?.message ?? reason);
      });
    } catch (reason) { captureState = 'rejected'; error = String(reason?.message ?? reason); throw reason; }
    return true;
  }
  function inject(kind) {
    if (disposed || captureState !== 'fulfilled' || !probe || !['known','unknown'].includes(kind)) throw new Error('capture required');
    probe.arm({kind});
    probe.inject(() => window.FlashNest.resume());
    return true;
  }
  function verify() { if (disposed || !probe) throw new Error('probe unavailable'); return probe.verifyRecovery(); }
  function dispose() {
    try { probe?.dispose(); } finally { disposed = true; }
    if (!probe) return false;
    const state = probe.status(); // Disposed status never rereads storage/environment.
    return state.disposed === true && state.prototypeRestored === true &&
      state.instanceRestored === true && state.failure === null;
  }
  Object.defineProperty(window, 'FlashNestLateHost', {value:Object.freeze({begin,snapshot,inject,verify,dispose}), configurable:false});
})();
