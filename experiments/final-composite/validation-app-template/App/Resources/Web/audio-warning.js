/* App-owned audio warning UI. Runtime, not this UI, classifies resume failures. */
(() => {
  'use strict';
  const phases = new Set(['bind', 'release', 'core-play', 'core-pause', 'visibility', 'unmute']);
  const states = new Set(['running', 'suspended', 'interrupted', 'closed']);
  const statuses = new Set(['bound', 'released', 'pending', 'fulfilled', 'rejected']);
  const safeID = value => Number.isSafeInteger(value) && value >= 0;
  function valid(value) {
    if (!value || typeof value !== 'object' || value.schema !== 1 ||
        !safeID(value.contextId) || value.contextId === 0 || !safeID(value.operationId) ||
        !safeID(value.intentId) || !phases.has(value.phase) || !states.has(value.state) ||
        !statuses.has(value.status) || typeof value.current !== 'boolean' ||
        typeof value.retryEligible !== 'boolean') return false;
    if (value.status === 'bound') return value.phase === 'bind' && value.operation === 'none' && value.current;
    if (value.status === 'released') return value.phase === 'release' && value.operation === 'none';
    return ['resume', 'suspend'].includes(value.operation) && !['bind', 'release'].includes(value.phase);
  }
  window.FlashNestAudioWarning = Object.freeze({create({player, panel, message, button, text, isActive, retry, diagnostic}) {
    let disposed = false, contextId = null, newestContext = 0, latest = null;
    let warning = false, retryEligible = false, arming = false, attempt = null, reports = 0;
    const same = (a, b) => a && b && a.contextId === b.contextId &&
      a.operationId === b.operationId && a.intentId === b.intentId;
    function record(kind, value = latest) {
      if (reports++ >= 16) return;
      diagnostic?.(`Audio UI: ${kind}; context=${value?.contextId ?? 0}; operation=${value?.operationId ?? 0}; intent=${value?.intentId ?? 0}`);
    }
    function render() {
      const waiting = latest?.operation === 'resume' && latest.status === 'pending';
      panel.hidden = disposed || !warning;
      message.textContent = text(waiting ? 'waiting' : 'warning');
      button.textContent = text(waiting ? 'retrying' : 'retry');
      button.disabled = disposed || !warning || !retryEligible || !isActive() ||
        !contextId || latest?.state === 'closed' || waiting || arming || !!attempt;
    }
    function reset() { latest = null; warning = false; retryEligible = false; attempt = null; arming = false; }
    function receive(event) {
      // CustomEvents are necessarily synthetic; only the attached player host
      // is accepted. This is status consumption, not error classification.
      if (disposed || event.target !== player || !valid(event.detail)) return;
      const value = event.detail;
      if (value.status === 'bound') {
        if (value.contextId <= newestContext) return;
        newestContext = contextId = value.contextId; reset(); latest = {...value}; render(); return;
      }
      if (value.contextId !== contextId) return;
      if (value.status === 'released') {
        if (latest && value.intentId < latest.intentId) return;
        contextId = null; reset(); render(); return;
      }
      if (!value.current || (latest && (value.operationId < latest.operationId || value.intentId < latest.intentId))) return;
      if (same(latest, value)) {
        if (latest.status === value.status) return;
        // A completed operation cannot become pending or complete twice.
        if (latest.status !== 'pending') return;
      } else if (value.status !== 'pending' || (latest && (value.operationId <= latest.operationId || value.intentId <= latest.intentId))) return;
      latest = {...value};
      if (attempt && !same(attempt, value)) attempt = null;
      if (arming && value.phase === 'core-play' && value.operation === 'resume' && value.status === 'pending') {
        attempt = {...value};
      }
      if (value.status === 'rejected' && value.operation === 'resume' && value.retryEligible && value.state !== 'closed') {
        warning = true; retryEligible = true; record('warning', value);
      }
      if (attempt && same(attempt, value) && value.status !== 'pending') {
        if (value.status === 'fulfilled' && value.state === 'running' && isActive()) {
          warning = false; retryEligible = false; record('retry-fulfilled', value);
        } else record('retry-not-confirmed', value);
        attempt = null;
      }
      render();
    }
    // Async solely preserves an unexpected synchronous API throw as a rejected
    // Promise for the existing unhandledrejection fatal route. No awaited or
    // returned API value is interpreted as audio success.
    async function click(event) {
      if (disposed || !event.isTrusted || event.currentTarget !== button || button.disabled ||
          !warning || !retryEligible || !contextId || !isActive()) return;
      arming = true; render(); record('retry-tap');
      try { retry(); }
      finally {
        arming = false;
        if (!attempt) record('retry-no-current-operation');
        render();
      }
    }
    player.addEventListener('ruffle-audio-status', receive);
    button.addEventListener('click', click);
    render();
    return Object.freeze({
      synchronize() {
        if (!isActive()) attempt = null;
        render();
      },
      dispose() {
        if (disposed) return;
        disposed = true; contextId = null; reset();
        player.removeEventListener('ruffle-audio-status', receive);
        button.removeEventListener('click', click); render();
      }
    });
  }});
})();
