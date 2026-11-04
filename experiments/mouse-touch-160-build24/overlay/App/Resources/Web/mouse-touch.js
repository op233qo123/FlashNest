/* App-owned optional trackpad. DOM pointer events use CSS pixels; Ruffle alone
 * applies DPR and its inverse stage transform (including showAll margins).
 * No imported script, runtime private API, or movie-specific coordinates. */
(() => {
  'use strict';
  window.FlashNestMouseTouch = Object.freeze({create});
  function create({canvas, host, cursor, enabled = false, onGesture = () => {}}) {
    const contacts = new Map(), consumed = new Set();
    const threshold = 8, tapTime = 500, holdDelay = 250, clickDuration = 100;
    let active = false, dispatching = false, gesture = null, disposed = false;
    let position = {x:0.5, y:0.5};
    let holdTimer = null, releaseTimer = null, pressed = null, pressedAt = 0, lastPoint = null;
    const now = () => window.performance.now();
    const listeners = [];
    function listen(target, name, handler) {
      target.addEventListener(name, handler, {capture:true, passive:false});
      listeners.push(() => target.removeEventListener(name, handler, true));
    }
    function rect() { return canvas.getBoundingClientRect(); }
    function paint() {
      const r = rect();
      cursor.hidden = !active || !r.width || !r.height;
      cursor.style.left = `${r.left + position.x * Math.max(0, r.width - 1)}px`;
      cursor.style.top = `${r.top + position.y * Math.max(0, r.height - 1)}px`;
    }
    function emit(type, button = -1, buttons = 0) {
      const r = rect();
      if (r.width && r.height) lastPoint = {x:r.left + position.x * Math.max(0,r.width-1), y:r.top + position.y * Math.max(0,r.height-1)};
      else if (type !== 'pointerup' || !lastPoint) return;
      dispatching = true;
      try {
        canvas.dispatchEvent(new PointerEvent(type, {
          bubbles:true, composed:true, cancelable:true, pointerId:2147483646,
          pointerType:'mouse', isPrimary:true, button, buttons,
          clientX:lastPoint.x, clientY:lastPoint.y
        }));
      } finally { dispatching = false; }
    }
    function buttonMask() { return pressed === 2 ? 2 : pressed === 0 ? 1 : 0; }
    function hover() { host.focus({preventScroll:true}); emit('pointerenter', -1, buttonMask()); emit('pointermove', -1, buttonMask()); paint(); }
    function clearHold() { if (holdTimer !== null) window.clearTimeout(holdTimer); holdTimer = null; }
    function release() {
      if (releaseTimer !== null) window.clearTimeout(releaseTimer);
      releaseTimer = null;
      const button = pressed;
      pressed = null;
      if (button !== null) emit('pointerup', button, 0);
    }
    function press(button) {
      release(); hover();
      pressed = button; pressedAt = now();
      try { emit('pointerdown', button, buttonMask()); }
      catch (error) { release(); throw error; }
    }
    function finishClick() {
      if (pressed === null) return;
      const remaining = Math.max(0, clickDuration - (now() - pressedAt));
      if (!remaining) release();
      else releaseTimer = window.setTimeout(release, remaining);
    }
    function click(button) {
      // Keep the state observable across normal game frames, not just DOM callbacks.
      press(button); finishClick();
    }
    function beginHold(candidate) {
      if (disposed || !active || document.hidden || gesture !== candidate ||
          contacts.size !== 1 || candidate.max !== 1 || candidate.moving || candidate.invalid || candidate.holding) return;
      clearHold(); candidate.holding = true; press(0);
    }
    function armHold() {
      clearHold();
      const candidate = gesture;
      holdTimer = window.setTimeout(() => { holdTimer = null; beginHold(candidate); }, holdDelay);
    }
    function releaseCapture(id) {
      try { if (canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id); } catch (_) { /* detached */ }
    }
    function cancel() {
      const ids = [...contacts.keys()];
      contacts.clear(); gesture = null; clearHold(); release();
      for (const id of ids) releaseCapture(id);
    }
    function consume(e) { e.preventDefault(); e.stopImmediatePropagation(); }
    function pointer(e) {
      if (dispatching || e.pointerType !== 'touch') return;
      if (!active) {
        // A fresh down reusing a canceled pointer ID is a new direct-touch gesture.
        if (e.type === 'pointerdown') consumed.delete(e.pointerId);
        if (!consumed.has(e.pointerId)) return;
        consume(e);
        if (e.type === 'pointerup' || e.type === 'pointercancel') consumed.delete(e.pointerId);
        return;
      }
      consume(e);
      if (e.type === 'pointerdown') consumed.add(e.pointerId);
      if (e.type === 'pointerup' || e.type === 'pointercancel') consumed.delete(e.pointerId);
      if (e.type === 'pointerdown') {
        onGesture();
        if (disposed || !active) return;
        if (!gesture) release(); // Never turn a previous click pulse into a new drag.
        if (!gesture) gesture = {time:e.timeStamp, max:0, total:0, invalid:false, moving:false, holding:false};
        if (!contacts.has(e.pointerId)) gesture.total++;
        contacts.set(e.pointerId, {x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY});
        gesture.max = Math.max(gesture.max, contacts.size);
        if (gesture.total > 2 || e.timeStamp - gesture.time > tapTime) gesture.invalid = true;
        try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* WebKit cancellation */ }
        if (gesture.max === 1 && gesture.total === 1) armHold();
        else { clearHold(); if (gesture.holding) { release(); gesture.holding = false; gesture.invalid = true; } }
        hover();
      } else if (e.type === 'pointermove') {
        const c = contacts.get(e.pointerId);
        if (!c || !gesture) return;
        // Input tasks may arrive before an overdue timer on a busy game frame.
        if (e.timeStamp - gesture.time >= holdDelay) beginHold(gesture);
        const crossed = Math.hypot(e.clientX-c.startX, e.clientY-c.startY) > threshold;
        if (crossed) { gesture.invalid = true; clearHold(); }
        if (contacts.size === 1 && gesture.max === 1 && (gesture.moving || crossed)) {
          // Pending tap jitter must not move the cursor or change its click target.
          // Once movement wins, retain that decision until every contact ends.
          const fromX = gesture.moving ? c.x : c.startX;
          const fromY = gesture.moving ? c.y : c.startY;
          gesture.moving = true;
          const r = rect();
          position.x = Math.min(1, Math.max(0, position.x + (e.clientX-fromX)/Math.max(1,r.width-1)));
          position.y = Math.min(1, Math.max(0, position.y + (e.clientY-fromY)/Math.max(1,r.height-1)));
          hover();
        }
        c.x=e.clientX; c.y=e.clientY;
      } else if (e.type === 'pointerup') {
        const c = contacts.get(e.pointerId);
        if (!c || !gesture) return;
        if (e.timeStamp - gesture.time >= holdDelay) beginHold(gesture);
        if (Math.hypot(e.clientX-c.startX,e.clientY-c.startY)>threshold) gesture.invalid=true;
        const finished = gesture;
        contacts.delete(e.pointerId);
        // Remove bookkeeping before capture release, which may synchronously emit lostcapture.
        if (!contacts.size) { gesture = null; clearHold(); }
        releaseCapture(e.pointerId);
        if (!contacts.size && finished.holding) {
          if (finished.moving || finished.invalid) release(); else finishClick();
        } else if (!contacts.size && !finished.invalid && e.timeStamp-finished.time <= tapTime) click(finished.max === 2 ? 2 : 0);
      } else if (e.type === 'pointercancel' || (e.type === 'lostpointercapture' && contacts.has(e.pointerId))) {
        cancel();
      }
    }
    for (const name of ['pointerdown','pointermove','pointerup','pointercancel','pointerenter','pointerleave','lostpointercapture']) listen(canvas,name,pointer);
    function setEnabled(value) {
      if (disposed) return;
      const wasActive = active;
      cancel(); active = value === true; paint();
      if (active) hover(); else if (wasActive) emit('pointerleave');
    }
    function reset() { cancel(); paint(); }
    listen(window,'blur',reset);
    listen(window,'resize',reset);
    listen(window,'orientationchange',reset);
    listen(document,'visibilitychange',reset);
    function rightClick() {
      if (disposed || !active) return false;
      // A separate right button must not complete an earlier left-tap candidate.
      cancel();
      onGesture();
      if (disposed || !active) return false;
      click(2);
      return true;
    }
    return Object.freeze({setEnabled, rightClick, cancel:reset, dispose() {
      if (disposed) return;
      setEnabled(false); disposed=true;
      for (const remove of listeners) remove();
    }, initialize() { setEnabled(enabled); }});
  }
})();
