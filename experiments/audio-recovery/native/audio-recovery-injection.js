/* Diagnostic-host only. Never included in shipping App resources. */
(() => {
  'use strict';
  const Native = window.AudioContext;
  if (!Native || window.FlashNestAudioProbe) throw new Error('Audio probe installation invalid');
  const resume = Native.prototype.resume;
  const dispatch = EventTarget.prototype.dispatchEvent;
  const addListener = EventTarget.prototype.addEventListener;
  const removeListener = EventTarget.prototype.removeEventListener;
  let registeredButton = null, originalClick = null, wrappedClick = null, callbackEvent = null;
  let registrationOptions = null, registrationRemoved = false;
  const contexts = [];
  const startupListeners = [];
  const startup = (phase, values) => { try { window.FlashNestStartupJournal?.record(phase, values); } catch (_) {} };
  let armed = null, bound = null, pending = null, injections = 0, trustedRetries = 0;
  let baseline = false, rejectedOperation = 0, fulfilledOperation = 0, failure = null;
  let saveBefore = null, page = String(Math.random()) + ':' + String(Date.now());
  const events = [];
  let sample = 0, armOperation = 0;
  let injectedOperation = null, retryOperation = null, awaitingRetry = false;
  let retryEvent = null, retryButton = null, retryPendingCount = 0;
  const sameOperation = (a,b) => a && b && a.contextId === b.contextId &&
    a.operationId === b.operationId && a.intentId === b.intentId;
  function intended(player) {
    return player && player === document.querySelector('ruffle-player') &&
      document.querySelectorAll('ruffle-player').length === 1;
  }
  function fail(message) { failure = message; throw new Error(message); }
  function saves() {
    const entries = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i); entries.push([key, localStorage.getItem(key)]);
    }
    return JSON.stringify(entries.sort((a,b) => a[0].localeCompare(b[0])));
  }
  const Wrapped = new Proxy(Native, {
    construct(target,args,newTarget) {
      const context = Reflect.construct(target,args,newTarget === Wrapped ? target : newTarget);
      contexts.push(context);
      startup('context-created',{contexts:contexts.length,state:context.state});
      const listener=()=>startup('context-state',{contexts:contexts.length,state:context.state});
      context.addEventListener?.('statechange',listener);startupListeners.push([context,listener]);
      return context;
    }
  });
  window.AudioContext = Wrapped;
  EventTarget.prototype.dispatchEvent = function(event) {
    if (event?.type === 'ruffle-audio-status' && intended(this)) {
      const d = event.detail;
      if (d?.schema === 1) {
        startup('audio-status',{contextId:d.contextId,operationId:d.operationId,intentId:d.intentId,audioPhase:d.phase,status:d.status,state:d.state,current:d.current});
        if (events.length >= 64) fail('Audio probe event bound exceeded');
        events.push({contextId:d.contextId,operationId:d.operationId,intentId:d.intentId,
          phase:d.phase,operation:d.operation,status:d.status,state:d.state,current:d.current,retryEligible:d.retryEligible});
        if (d.status === 'bound') {
          if (contexts.length !== 1 || bound !== null) fail('Ambiguous bound audio context');
          bound = {id:d.contextId,context:contexts[0],player:this};
        }
        if (d.status === 'pending' && d.operation === 'resume' && d.current) {
          pending = d;
          if (awaitingRetry && callbackEvent === retryEvent && retryEvent?.eventPhase === 2 && retryEvent.currentTarget === retryButton &&
              d.phase === 'core-play' && d.contextId === bound?.id && this === bound.player &&
              d.operationId > rejectedOperation) {
            retryPendingCount++;
            if (retryPendingCount !== 1) fail('Duplicate owned resume during trusted retry');
            retryOperation = d;
          }
        }
        if (d.status === 'rejected' && injections === 1 && sameOperation(d,injectedOperation) && d.current && d.retryEligible)
          rejectedOperation = d.operationId;
        if (d.status === 'fulfilled' && trustedRetries === 1 && sameOperation(d,retryOperation) &&
            d.operation === 'resume' && d.phase === 'core-play' && d.current && d.state === 'running' && d.operationId > rejectedOperation)
          fulfilledOperation = d.operationId;
      }
    }
    return Reflect.apply(dispatch,this,[event]);
  };
  Native.prototype.resume = function(...args) {
    if (armed !== null) {
      if (contexts.length !== 1 || this !== contexts[0] || !intended(document.querySelector('ruffle-player')))
        return fail('Injection attempted outside the sole intended runtime context');
      if (!baseline && (!bound || bound.context !== this || pending?.contextId !== bound.id || !pending.current || pending.operationId <= armOperation))
        return fail('Injection lacks source-owned current resume operation');
      injectedOperation = baseline ? null : pending;
      const kind = armed; armed = null; injections++;
      Native.prototype.resume = resume; // Restore BEFORE rejection reaches helper or user retry.
      return Promise.reject(kind === 'known'
        ? new DOMException('Failed to start the audio device','InvalidStateError')
        : new Error('Original synthetic unknown audio failure'));
    }
    return Reflect.apply(resume,this,args);
  };
  const interceptAdd = function(type, listener, options) {
    if (type !== 'click' || this !== document.querySelector('#audio-retry'))
      return Reflect.apply(addListener, this, arguments);
    if (registeredButton || typeof listener !== 'function' || options !== undefined ||
        Object.hasOwn(this, 'addEventListener') || Object.hasOwn(this, 'removeEventListener')) {
      EventTarget.prototype.addEventListener = addListener;
      fail('Ambiguous retry callback registration');
    }
    registeredButton = this; originalClick = listener; registrationOptions = options;
    EventTarget.prototype.addEventListener = addListener;
    wrappedClick = function(...args) {
      const event = args[0];
      if (callbackEvent !== null) fail('Nested retry callback');
      callbackEvent = event;
      try { return Reflect.apply(listener, this, args); }
      finally { callbackEvent = null; }
    };
    this.addEventListener = function(type, listener, options) {
      if (type === 'click') fail('Duplicate retry callback registration');
      return Reflect.apply(addListener, this, arguments);
    };
    this.removeEventListener = function(type, listener, options) {
      if (type === 'click' && listener === originalClick && !(typeof options === 'boolean' ? options : options?.capture)) registrationRemoved = true;
      return Reflect.apply(removeListener, this,
        [type, type === 'click' && listener === originalClick ? wrappedClick : listener, options]);
    };
    return Reflect.apply(addListener, this, [type, wrappedClick, options]);
  };
  EventTarget.prototype.addEventListener = interceptAdd;
  const onClick = event => {
    const button = event.target?.closest?.('#audio-retry');
    if (button) {
      if (!event.isTrusted) fail('Audio retry was not trusted DOM input');
      if (event.target !== button || button !== registeredButton) fail('Retry requires exact registered button target');
      if (trustedRetries !== 0 || retryEvent !== null) fail('Repeated trusted retry event');
      if (button !== document.querySelector('#audio-retry')) fail('Wrong retry button');
      trustedRetries++; awaitingRetry = true; retryOperation = null; retryPendingCount = 0;
      retryEvent = event; retryButton = button;
    }
  };
  const onBubble = event => {
    if (event !== retryEvent) return;
    if (retryPendingCount !== 1) failure = 'Trusted retry did not synchronously request core-play resume';
    awaitingRetry = false; retryEvent = null; retryButton = null;
  };
  document.addEventListener('click', onClick, true);
  document.addEventListener('click', onBubble, false);
  window.FlashNestAudioProbe = Object.freeze({
    arm(kind, baselineControl = false) {
      if (!['known','unknown'].includes(kind) || armed || injections || contexts.length !== 1)
        fail('Invalid or repeated injection arm');
      baseline = baselineControl;
      if (!baseline && !bound) fail('Candidate must bind source-owned context before arming');
      if (localStorage.length < 1) fail("Original fixture must have written a real save before injection");
      armOperation = events.reduce((value,e) => Math.max(value,e.operationId),0);
      pending = null;
      saveBefore = saves(); armed = kind;
    },
    contextState() { return contexts.length === 1 ? contexts[0].state : "ambiguous"; },
    status() {
      if (awaitingRetry && retryEvent?.eventPhase === 0) {
        failure = 'Trusted retry dispatch ended without bubble validation';
        awaitingRetry = false; retryEvent = null; retryButton = null;
      }
      return {sample: ++sample,page,contexts:contexts.length,injections,trustedRetries,rejectedOperation,fulfilledOperation,
        nativeResumeRestored:Native.prototype.resume === resume,
        saveEntries:localStorage.length,sameSave:saveBefore !== null && saveBefore === saves(),failure,
        last:events.length ? events[events.length-1] : null};
    },
    dispose() {
      for(const [context,listener] of startupListeners)context.removeEventListener?.('statechange',listener);
      startupListeners.length=0;window.FlashNestStartupJournal?.dispose();
      Native.prototype.resume = resume;
      EventTarget.prototype.dispatchEvent = dispatch;
      if (EventTarget.prototype.addEventListener === interceptAdd) EventTarget.prototype.addEventListener = addListener;
      if (registeredButton) {
        Reflect.apply(removeListener, registeredButton, ['click', wrappedClick, registrationOptions]);
        if (!registrationRemoved) Reflect.apply(addListener, registeredButton, ['click', originalClick, registrationOptions]);
        delete registeredButton.addEventListener; delete registeredButton.removeEventListener;
      }
      registeredButton = null; originalClick = null; wrappedClick = null; callbackEvent = null;
      if (window.AudioContext === Wrapped) window.AudioContext = Native;
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('click', onBubble, false);
      retryEvent = null; retryButton = null;
      armed = null; awaitingRetry = false; bound = null; pending = null; contexts.length = 0;
    }
  });
})();
