/* App-owned optional trackpad. DOM pointer events use CSS pixels; Ruffle alone
 * applies DPR and its inverse stage transform (including showAll margins).
 * No imported script, runtime private API, or movie-specific coordinates. */
(() => {
  'use strict';
  window.FlashNestMouseTouch = Object.freeze({create});
  function create({canvas, host, cursor, enabled = false, onGesture = () => {}}) {
    const contacts = new Map(), consumed = new Set();
    const threshold = 8, tapTime = 500;
    let active = false, dispatching = false, gesture = null, disposed = false;
    let position = {x:0.5, y:0.5};
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
      if (!r.width || !r.height) return;
      dispatching = true;
      try {
        canvas.dispatchEvent(new PointerEvent(type, {
          bubbles:true, composed:true, cancelable:true, pointerId:2147483646,
          pointerType:'mouse', isPrimary:true, button, buttons,
          clientX:r.left + position.x * Math.max(0, r.width - 1),
          clientY:r.top + position.y * Math.max(0, r.height - 1)
        }));
      } finally { dispatching = false; }
    }
    function hover() { host.focus({preventScroll:true}); emit('pointerenter'); emit('pointermove'); paint(); }
    function click(button) {
      hover();
      // Always pair releases, even if downstream synchronous dispatch fails.
      try { emit('pointerdown', button, button === 2 ? 2 : 1); }
      finally { emit('pointerup', button, 0); }
    }
    function releaseCapture(id) {
      try { if (canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id); } catch (_) { /* detached */ }
    }
    function cancel() {
      const ids = [...contacts.keys()];
      contacts.clear(); gesture = null;
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
        if (!gesture) gesture = {time:e.timeStamp, max:0, total:0, invalid:false};
        if (!contacts.has(e.pointerId)) gesture.total++;
        contacts.set(e.pointerId, {x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY});
        gesture.max = Math.max(gesture.max, contacts.size);
        if (gesture.total > 2 || e.timeStamp - gesture.time > tapTime) gesture.invalid = true;
        try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* WebKit cancellation */ }
        hover();
      } else if (e.type === 'pointermove') {
        const c = contacts.get(e.pointerId);
        if (!c || !gesture) return;
        if (Math.hypot(e.clientX-c.startX, e.clientY-c.startY) > threshold) gesture.invalid = true;
        if (contacts.size === 1 && gesture.max === 1) {
          const r = rect();
          position.x = Math.min(1, Math.max(0, position.x + (e.clientX-c.x)/Math.max(1,r.width-1)));
          position.y = Math.min(1, Math.max(0, position.y + (e.clientY-c.y)/Math.max(1,r.height-1)));
          hover();
        }
        c.x=e.clientX; c.y=e.clientY;
      } else if (e.type === 'pointerup') {
        const c = contacts.get(e.pointerId);
        if (!c || !gesture) return;
        if (Math.hypot(e.clientX-c.startX,e.clientY-c.startY)>threshold) gesture.invalid=true;
        const finished = gesture;
        contacts.delete(e.pointerId);
        // Remove bookkeeping before capture release, which may synchronously emit lostcapture.
        if (!contacts.size) gesture = null;
        releaseCapture(e.pointerId);
        if (!contacts.size && !finished.invalid && e.timeStamp-finished.time <= tapTime) click(finished.max === 2 ? 2 : 0);
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
    return Object.freeze({setEnabled, cancel:reset, dispose() {
      if (disposed) return;
      setEnabled(false); disposed=true;
      for (const remove of listeners) remove();
    }, initialize() { setEnabled(enabled); }});
  }
})();
