/* LOCAL diagnostic sidecar. Load/create only after real Play + fixture readiness.
 * Never ship this file. No constructor, EventTarget, private-field or runtime hooks.
 */
(function (root) {
  'use strict';
  const EVENT = 'ruffle-audio-status';
  const LIMIT = 64;
  const descriptor = (object, key) => Object.getOwnPropertyDescriptor(object, key);
  const sameDescriptor = (a, b) => a === b || (!!a && !!b &&
    ['value', 'get', 'set', 'writable', 'enumerable', 'configurable'].every(k => a[k] === b[k]));
  const sameTuple = (a, b) => !!a && !!b && a.contextId === b.contextId &&
    a.operationId === b.operationId && a.intentId === b.intentId;
  const integer = n => Number.isSafeInteger(n) && n >= 0;
  const phases = new Set(['bind', 'release', 'core-play', 'core-pause', 'visibility', 'unmute']);
  const states = new Set(['running', 'suspended', 'interrupted', 'closed']);
  function copyStatus(d) {
    if (!d || d.schema !== 1 || !integer(d.contextId) || !d.contextId ||
        !integer(d.operationId) || !integer(d.intentId) || !phases.has(d.phase) ||
        !states.has(d.state) || typeof d.current !== 'boolean' || typeof d.retryEligible !== 'boolean' ||
        !['bound', 'released', 'pending', 'fulfilled', 'rejected'].includes(d.status) ||
        !['none', 'resume', 'suspend'].includes(d.operation)) return null;
    return {schema: 1, contextId: d.contextId, operationId: d.operationId, intentId: d.intentId,
      phase: d.phase, operation: d.operation, status: d.status, state: d.state,
      current: d.current, retryEligible: d.retryEligible};
  }
  function create(options) {
    const {player, button, panel, isActive, readiness, continuity, mode = 'candidate'} = options;
    const doc = root.document, Native = root.AudioContext;
    if (!['candidate', 'baseline'].includes(mode) || !Native || !doc ||
        !player || !button || !panel || typeof isActive !== 'function' ||
        typeof readiness !== 'function' || typeof continuity !== 'function')
      throw new Error('Late probe: invalid integration contract');
    const proto = Native.prototype, nativeDescriptor = descriptor(proto, 'resume');
    if (!nativeDescriptor || typeof nativeDescriptor.value !== 'function' || !nativeDescriptor.configurable)
      throw new Error('Late probe: unsupported native resume descriptor');
    const nativeResume = nativeDescriptor.value;
    let disposed = false, failure = null, phase = 'ready', scope = null;
    let context = null, contextId = null, originalOwn = null, override = null;
    let capturedPromise = null, captureOutcome = null, capturedPending = null, capturedFulfilled = null, sample = 0;
    let captureCalls = 0, injections = 0, captureComplete = false, captureCompletionStarted = false;
    let latest = null, highOperation = 0, highIntent = 0, seq = 0;
    let injectedPending = null, rejected = null, retryPending = null, retryFulfilled = null;
    let retryEvent = null, retryPendingCount = 0, trustedRetries = 0, childAtRetryFulfillment = null;
    let armOperation = 0, armIntent = 0, armedError = null, armedKind = null, pausePending = null;
    const events = [], failures = [];
    const fail = message => {
      if (!failure) failure = message;
      if (failures.length < 8 && !failures.includes(message)) failures.push(message);
    };
    const guarded = fn => function (...args) {
      try { return Reflect.apply(fn, this, args); }
      catch (_) { fail('observer-exception'); }
    };
    function intended() {
      const players = doc.querySelectorAll('ruffle-player');
      const buttons = doc.querySelectorAll('#audio-retry'), panels = doc.querySelectorAll('#audio-warning');
      return root.document === doc && player.ownerDocument === doc && player.isConnected &&
        players.length === 1 && players[0] === player && buttons.length === 1 && buttons[0] === button &&
        panels.length === 1 && panels[0] === panel && button.ownerDocument === doc &&
        panel.ownerDocument === doc && button.isConnected && panel.isConnected;
    }
    function readContinuity() {
      const value = continuity();
      if (!value || typeof value.pageId !== 'string' || !value.pageId ||
          !integer(value.childInputSerial) || typeof value.solSnapshot !== 'string' ||
          !value.solSnapshot) throw new Error('invalid continuity evidence');
      return {pageId: value.pageId, childInputSerial: value.childInputSerial, solSnapshot: value.solSnapshot};
    }
    const ready = readiness();
    if (!ready || ready.trustedPlay !== true || ready.rootReady !== true ||
        ready.childReady !== true || ready.saveReady !== true || !intended() || !isActive())
      throw new Error('Late probe: genuine startup/Play/fixture readiness required');
    const before = readContinuity();
    function checkEnvironment(active = false) {
      try {
        if (disposed || !intended()) fail('document-player-or-ui-changed');
        if (!sameDescriptor(descriptor(proto, 'resume'), nativeDescriptor)) fail('prototype-descriptor-conflict');
        if (context && context.state === 'closed') fail('context-closed');
        if (active && !isActive()) fail('inactive-intent');
        const now = readContinuity();
        if (now.pageId !== before.pageId) fail('page-identity-changed');
        if (now.solSnapshot !== before.solSnapshot) fail('real-sol-changed');
        return now;
      } catch (_) { fail('environment-evidence-exception'); return null; }
    }
    function restoreOwn() {
      if (!override || !context) return;
      try {
        if (!sameDescriptor(descriptor(context, 'resume'), override.descriptor)) fail('instance-descriptor-conflict');
        if (originalOwn) Object.defineProperty(context, 'resume', originalOwn);
        else if (!Reflect.deleteProperty(context, 'resume')) fail('instance-restore-failed');
        if (!sameDescriptor(descriptor(context, 'resume'), originalOwn)) fail('instance-restore-failed');
      } catch (_) { fail('instance-restore-failed'); }
      override = null;
    }
    function receive(event) {
      if (disposed) return;
      if (event.target !== player || event.currentTarget !== player) { fail('foreign-player-status'); return; }
      const d = copyStatus(event.detail);
      if (!d) { fail('invalid-status'); return; }
      if (events.length >= LIMIT) { fail('status-bound-exceeded'); return; }
      events.push(d); seq++;
      if (mode === 'baseline') { fail('baseline-unexpected-source-status'); return; }
      if (d.status === 'bound' || d.status === 'released' || d.phase === 'bind' || d.phase === 'release') {
        fail('context-released-or-rebound'); restoreOwn(); return;
      }
      if (!d.current || d.state === 'closed') { fail('stale-or-closed-status'); restoreOwn(); return; }
      if (contextId !== null && d.contextId !== contextId) { fail('foreign-context-status'); restoreOwn(); return; }
      if (d.operation === 'none' || !d.operationId || !d.intentId) { fail('invalid-operation-status'); return; }
      if (d.status === 'pending') {
        if (d.operationId <= highOperation || d.intentId <= highIntent) { fail('duplicate-or-stale-pending'); return; }
        highOperation = d.operationId; highIntent = d.intentId;
        latest = d;
        if (scope) {
          scope.pendingCount++;
          if (scope.pendingCount !== 1 || d.phase !== 'core-play' || d.operation !== 'resume')
            fail('scope-not-one-core-play-pending');
          scope.pending = d;
          if (scope.kind === 'capture' && contextId === null) contextId = d.contextId;
        } else if (retryEvent) {
          if (retryEvent.isTrusted !== true || retryEvent.eventPhase !== 2 || retryEvent.currentTarget !== button ||
              d.phase !== 'core-play' || d.operation !== 'resume' || !rejected ||
              d.operationId <= rejected.operationId || d.intentId <= rejected.intentId) fail('retry-not-current-target-core-play');
          retryPendingCount++;
          if (retryPendingCount !== 1) fail('duplicate-retry-pending');
          retryPending = d;
        } else if (phase === 'captured' && !pausePending && d.phase === 'core-pause' && d.operation === 'suspend') {
          pausePending = d;
        } else {
          fail('incidental-operation-outside-authorized-scope'); restoreOwn();
        }
      } else {
        if (!sameTuple(latest, d) || latest.status !== 'pending' || latest.phase !== d.phase || latest.operation !== d.operation) {
          fail('unmatched-or-duplicate-settlement'); return;
        }
        latest = d;
        if (sameTuple(capturedPending, d)) {
          if (d.status === 'fulfilled' && d.state === 'running' && d.operation === 'resume') capturedFulfilled = d;
          else fail('capture-not-fulfilled-running');
        }
        if (sameTuple(injectedPending, d)) {
          if (d.status !== 'rejected') fail('injection-not-rejected');
          else {
            rejected = d;
            if (armedKind === 'known' && !d.retryEligible) fail('known-injection-not-retry-eligible');
            if (armedKind === 'unknown' && d.retryEligible) fail('unknown-injection-wrongly-retry-eligible');
            phase = 'rejected';
          }
        }
        if (sameTuple(retryPending, d)) {
          if (d.status === 'fulfilled' && d.state === 'running' && isActive()) {
            retryFulfilled = d; childAtRetryFulfillment = readContinuity().childInputSerial; phase = 'recovered';
          }
          else fail('retry-not-fulfilled-running-active');
        }
      }
    }
    const onStatus = guarded(receive);
    const onClick = guarded(event => {
      if (event.target !== button) return;
      if (event.isTrusted !== true) { fail('untrusted-retry-click'); return; }
      if (mode !== 'candidate' || phase !== 'rejected' || armedKind !== 'known' || !rejected?.retryEligible ||
          panel.hidden || button.disabled || button.getClientRects().length === 0 || retryEvent || trustedRetries || !isActive()) {
        fail('retry-click-not-visible-enabled-current'); return;
      }
      checkEnvironment(true);
      trustedRetries++; retryEvent = event; retryPendingCount = 0; phase = 'retrying';
    });
    const onBubble = guarded(event => {
      if (event !== retryEvent) return;
      if (retryPendingCount !== 1 || !retryPending) fail('retry-no-single-synchronous-pending');
      retryEvent = null;
    });
    const onVisibility = guarded(() => {
      if (doc.visibilityState !== 'visible' || !isActive()) { fail('background-or-inactive-intent'); restoreOwn(); }
    });
    player.addEventListener(EVENT, onStatus);
    doc.addEventListener('click', onClick, true);
    doc.addEventListener('click', onBubble, false);
    doc.addEventListener('visibilitychange', onVisibility);
    function requireClean(condition, message) {
      checkEnvironment();
      if (!condition) fail(message);
      if (failure) { restoreOwn(); throw new Error('Late probe: ' + failure); }
    }
    function capture(call) {
      requireClean(phase === 'ready' && typeof call === 'function', 'capture-not-once');
      if (!isActive()) { fail('inactive-intent'); throw new Error('Late probe: inactive-intent'); }
      const saved = descriptor(proto, 'resume');
      const captureScope = {kind: 'capture', pending: null, pendingCount: 0};
      scope = captureScope; phase = 'capturing';
      let depth = 0;
      function observe(...args) {
        captureCalls = Math.min(captureCalls + 1, 5); // Four-call diagnostic bound; still forward every call.
        if (captureCalls > 4) fail('native-call-bound-exceeded');
        if (captureCalls > 1 || depth) fail('duplicate-or-reentrant-native-call');
        try {
          if (!(this instanceof Native)) fail('non-native-receiver');
          if (context && context !== this) fail('multiple-native-receivers');
          if (captureCalls === 1) {
            context = this; originalOwn = descriptor(this, 'resume');
            if (originalOwn && (originalOwn.value !== nativeResume || !originalOwn.configurable)) fail('unsupported-original-own-descriptor');
          }
          if (mode === 'candidate' && (scope.pendingCount !== 1 || scope.pending?.phase !== 'core-play' ||
              scope.pending?.operation !== 'resume' || !scope.pending.current)) fail('native-call-without-fresh-core-play-pending');
        } catch (_) { fail('native-observation-exception'); }
        depth++;
        try {
          const result = Reflect.apply(nativeResume, this, args);
          if (captureCalls === 1) capturedPromise = result;
          return result; // Exact Promise, receiver, arguments, and synchronous throw.
        } finally { depth--; }
      }
      const installed = {...saved, value: observe};
      let publicResult;
      try {
        Object.defineProperty(proto, 'resume', installed);
        publicResult = call();
      } catch (error) {
        fail('capture-synchronous-exception');
        throw error; // Never replace the original exception object.
      } finally {
        try {
          if (!sameDescriptor(descriptor(proto, 'resume'), installed)) fail('prototype-descriptor-conflict');
          Object.defineProperty(proto, 'resume', saved);
          if (!sameDescriptor(descriptor(proto, 'resume'), saved)) fail('prototype-restore-failed');
        } catch (_) { fail('prototype-restore-failed'); }
        capturedPending = captureScope.pending;
        if (captureCalls !== 1) fail('capture-not-one-native-call');
        if (mode === 'candidate' && captureScope.pendingCount !== 1) fail('capture-not-one-pending');
        scope = null; phase = disposed ? 'disposed' : 'capture-pending';
        if (disposed) { capturedPromise = null; context = null; }
      }
      if (!failure && !disposed) {
        // Post-scope observation is attached AFTER exact descriptor restoration,
        // before returning to any native bridge/event loop. The native wrapper
        // above still never chains, handles, replaces or schedules a Promise.
        try {
          captureOutcome = Promise.prototype.then.call(capturedPromise, () => undefined, error => {
            fail('capture-native-rejected');
            // Baseline has no helper fatal child. Keep one fatal route with the
            // original object; never duplicate the candidate helper-owned route.
            if (mode === 'baseline') void Promise.reject(error);
          });
        } catch (_) { fail('post-capture-observer-install-failed'); }
      }
      return publicResult;
    }
    async function completeCapture() {
      requireClean(phase === 'capture-pending' && !captureCompletionStarted, 'capture-completion-not-once');
      captureCompletionStarted = true;
      // Await the already-attached outcome, never add a second rejection observer.
      await captureOutcome;
      checkEnvironment(true);
      if (!context || context.state !== 'running') fail('capture-context-not-running');
      if (mode === 'candidate' && !capturedFulfilled) fail('capture-missing-matching-fulfilled-running');
      capturedPromise = null; captureOutcome = null;
      requireClean(!failure, 'capture-invalid');
      captureComplete = true; phase = 'captured';
      return status();
    }
    function arm({kind, error} = {}) {
      requireClean(phase === 'captured' && captureComplete && !injections && ['known', 'unknown'].includes(kind), 'invalid-arm');
      if (context.state !== 'suspended') fail('arm-before-intended-suspend');
      if (mode === 'candidate' && (!latest || latest.status !== 'fulfilled' || latest.operation !== 'suspend' ||
          latest.phase !== 'core-pause' || latest.contextId !== contextId)) fail('arm-missing-current-core-pause-fulfillment');
      if (!sameDescriptor(descriptor(context, 'resume'), originalOwn)) fail('instance-descriptor-conflict');
      if (!Object.isExtensible(context) && !originalOwn) fail('unsupported-instance-override');
      requireClean(!failure, 'invalid-arm');
      armedKind = kind;
      armedError = error === undefined ? (kind === 'known'
        ? new root.DOMException('Failed to start the audio device', 'InvalidStateError')
        : new Error('Original synthetic unknown audio failure')) : error;
      if (kind === 'known' && (!(armedError instanceof root.DOMException) || armedError.name !== 'InvalidStateError' ||
          armedError.message !== 'Failed to start the audio device')) throw new Error('Late probe: known error contract mismatch');
      armOperation = highOperation; armIntent = highIntent;
      const oneShot = function (...args) {
        let valid = !failure && this === context && scope?.kind === 'inject' && !injections;
        try {
          checkEnvironment(true);
          if (context.state === 'closed') valid = false;
          if (mode === 'candidate' && (scope?.pendingCount !== 1 || scope.pending?.contextId !== contextId ||
              scope.pending?.phase !== 'core-play' || scope.pending?.operation !== 'resume' ||
              scope.pending?.operationId <= armOperation || scope.pending?.intentId <= armIntent)) valid = false;
          if (failure) valid = false;
        } catch (_) { valid = false; fail('injection-observation-exception'); }
        restoreOwn(); // Restore BEFORE creating/returning the rejection and all handlers/retry.
        if (!valid || failure) {
          fail('unexpected-instance-resume-forwarded');
          return Reflect.apply(nativeResume, this, args);
        }
        injections++; injectedPending = mode === 'candidate' ? scope.pending : null;
        phase = 'injected';
        return Promise.reject(armedError); // Identity preserved, no error normalization/consumption.
      };
      const own = {value: oneShot, writable: true, enumerable: originalOwn?.enumerable ?? false, configurable: true};
      override = {descriptor: own};
      try {
        Object.defineProperty(context, 'resume', own);
        if (!sameDescriptor(descriptor(context, 'resume'), own)) throw new Error('unsupported override');
      } catch (_) { fail('unsupported-instance-override'); restoreOwn(); throw new Error('Late probe: unsupported-instance-override'); }
      phase = 'armed';
    }
    function inject(call) {
      requireClean(phase === 'armed' && typeof call === 'function', 'injection-not-armed');
      const injectScope = {kind: 'inject', pending: null, pendingCount: 0};
      scope = injectScope;
      try { return call(); }
      catch (error) { fail('injection-synchronous-exception'); throw error; }
      finally {
        if (injections !== 1) fail('injection-not-one-call');
        if (mode === 'candidate' && injectScope.pendingCount !== 1) fail('injection-not-one-pending');
        restoreOwn(); scope = null;
      }
    }
    function status({includeEvents = false} = {}) {
      if (retryEvent && retryEvent.eventPhase === 0) {
        fail('retry-dispatch-ended-without-bubble'); retryEvent = null;
      }
      if (!disposed && phase !== 'capturing') checkEnvironment();
      return {schema: 1, sample: ++sample, mode, phase, disposed, failure, failures: [...failures],
        capturedReceivers: captureComplete ? 1 : 0, captureCalls, totalContextCount: null,
        contextCoverage: 'one synchronous receiver only; total context count unknown',
        ownershipEvidence: mode === 'candidate' ? 'source-status-correlated-public-call' : 'weaker-public-call-inference-no-context-id',
        contextId, contextState: context ? String(context.state) : null,
        captureComplete, injections, trustedRetries,
        capturedOperation: capturedPending && {...capturedPending},
        injectedOperation: injectedPending && {...injectedPending}, rejectedOperation: rejected && {...rejected},
        retryOperation: retryPending && {...retryPending}, fulfilledRetry: retryFulfilled && {...retryFulfilled},
        prototypeRestored: sameDescriptor(descriptor(proto, 'resume'), nativeDescriptor),
        instanceRestored: !override && (!context || sameDescriptor(descriptor(context, 'resume'), originalOwn)),
        eventCount: events.length, ...(includeEvents ? {events: events.map(d => ({...d}))} : {})};
    }
    function verifyRecovery() {
      const now = checkEnvironment(true);
      const snapshot = status(), reasons = [...failures];
      if (mode !== 'candidate') reasons.push('baseline-cannot-attest-recovery');
      if (armedKind !== 'known' || injections !== 1 || !rejected?.retryEligible) reasons.push('missing-current-known-rejection');
      if (trustedRetries !== 1 || retryEvent || !retryFulfilled || !sameTuple(retryPending, retryFulfilled)) reasons.push('missing-trusted-current-retry-fulfillment');
      if (!context || context.state !== 'running') reasons.push('same-context-not-running');
      if (!panel.hidden) reasons.push('production-warning-not-cleared');
      if (!now || childAtRetryFulfillment === null || now.childInputSerial <= childAtRetryFulfillment)
        reasons.push('missing-fresh-child-input-after-retry');
      if (!snapshot.prototypeRestored || !snapshot.instanceRestored) reasons.push('descriptors-not-restored');
      return {...snapshot, ok: reasons.length === 0, reasons};
    }
    function dispose() {
      if (disposed) return;
      if (scope) fail('disposed-during-operation');
      restoreOwn();
      player.removeEventListener(EVENT, onStatus);
      doc.removeEventListener('click', onClick, true);
      doc.removeEventListener('click', onBubble, false);
      doc.removeEventListener('visibilitychange', onVisibility);
      context = null; capturedPromise = null; captureOutcome = null; armedError = null; retryEvent = null; scope = null;
      originalOwn = null; disposed = true; phase = 'disposed';
    }
    return Object.freeze({capture, completeCapture, arm, inject, status, verifyRecovery, dispose});
  }
  if (root.FlashNestLateAudioProbe) throw new Error('Late probe factory already present');
  root.FlashNestLateAudioProbe = Object.freeze({create});
})(typeof window === 'object' ? window : globalThis);
