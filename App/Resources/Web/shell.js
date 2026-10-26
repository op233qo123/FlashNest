/* App-owned shell. Never evaluates imported HTML or SWF-provided JavaScript. */
(() => {
  'use strict';
  const status = document.getElementById('status');
  let player, started = false, paused = false, backgrounded = false;
  const held = new Set();
  const keys = {ArrowLeft:37, ArrowUp:38, ArrowRight:39, ArrowDown:40, Space:32, Enter:13};
  function report(type, message) {
    const text = String(message).slice(0, 1024);
    status.textContent = text;
    window.webkit?.messageHandlers?.flashnest?.postMessage({type, message:text});
  }
  function key(code, down) {
    if (!Object.hasOwn(keys, code) || !player) return;
    if (down === held.has(code)) return;
    if (down) held.add(code); else held.delete(code);
    const target = player.shadowRoot?.querySelector('canvas') || player;
    if (down) target.focus();
    target.dispatchEvent(new KeyboardEvent(down ? 'keydown' : 'keyup', {
      key:code === 'Space' ? ' ' : code, code, keyCode:keys[code], which:keys[code], bubbles:true, composed:true, cancelable:true
    }));
  }
  function releaseKeys() { for (const code of [...held]) key(code, false); document.querySelectorAll('.held').forEach(x => x.classList.remove('held')); }
  function reconcile() { if (!player || !started) return; if (paused || backgrounded) player.ruffle().suspend(); else player.ruffle().resume(); }
  function pause() { releaseKeys(); paused = true; reconcile(); }
  function resume() { paused = false; reconcile(); }
  window.FlashNest = Object.freeze({pause, resume, key});
  document.getElementById('pause').onclick = () => { paused = !paused; releaseKeys(); reconcile(); document.getElementById('pause').textContent = paused ? 'Resume' : 'Pause'; };
  document.getElementById('start').onclick = () => { started = true; paused = false; reconcile(); player?.focus(); };
  window.addEventListener('blur', releaseKeys);
  document.addEventListener('visibilitychange', () => { backgrounded = document.hidden; releaseKeys(); reconcile(); });
  document.querySelectorAll('[data-key]').forEach(button => {
    button.addEventListener('pointerdown', event => { event.preventDefault(); button.setPointerCapture(event.pointerId); button.classList.add('held'); key(button.dataset.key, true); });
    for (const name of ['pointerup','pointercancel','lostpointercapture']) button.addEventListener(name, () => { button.classList.remove('held'); key(button.dataset.key, false); });
  });
  document.addEventListener('securitypolicyviolation', e => report('diagnostic', `Offline policy blocked ${e.blockedURI || e.violatedDirective}. Remote servers are unavailable; include local assets in the package.`));
  window.addEventListener('unhandledrejection', e => report('error', `Runtime error: ${e.reason?.message || e.reason}`));
  // Report missing local subassets without converting remote URLs to local URLs.
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    try { const response = await originalFetch(...args); if (!response.ok) report('diagnostic', `Asset request failed (${response.status}): ${response.url}`); return response; }
    catch (error) { report('diagnostic', `Asset request blocked or unavailable: ${String(args[0]?.url || args[0]).slice(0,300)}`); throw error; }
  };
  async function boot() {
    const query = new URLSearchParams(location.search);
    const entry = query.get('entry'), id = query.get('package');
    if (!id || !/^[a-f0-9-]{36}$/i.test(id) || !entry || !/\.swf$/i.test(entry)) throw Error('Invalid package or entry SWF.');
    const parts = entry.split('/');
    if (parts.some(p => !p || p === '.' || p === '..' || /[\\\x00-\x1f]/.test(p))) throw Error('Unsafe entry path.');
    const root = new URL('../', location.href);
    const url = new URL(`games/${id}/${parts.map(encodeURIComponent).join('/')}`, root);
    const runtime = new URL('./runtime/', location.href);
    window.RufflePlayer = {config:{publicPath:runtime.href, polyfills:false}};
    await new Promise((resolve,reject) => { const script = document.createElement('script'); script.src = new URL('ruffle.js',runtime).href; script.onload = resolve; script.onerror = () => reject(Error('Bundled runtime missing or blocked.')); document.head.append(script); });
    const ruffle = window.RufflePlayer.newest();
    player = ruffle.createPlayer();
    document.getElementById('stage').append(player);
    report('ready', 'Offline runtime ready.');
    await player.ruffle().load({url:url.href, base:new URL('./',url).href, publicPath:runtime.href,
      allowScriptAccess:false, allowNetworking:'internal', openUrlMode:'deny', socketProxy:[],
      autoplay:'off', unmuteOverlay:'visible', backgroundExecutionMode:'none', upgradeToHttps:false,
      showSwfDownload:false, contextMenu:'off', logLevel:'warn'});
    player.ruffle().traceObserver = message => report('diagnostic', `SWF: ${message}`);
    reconcile(); report('loaded', 'Movie loaded. Tap Play to start audio.');
  }
  boot().catch(error => report('error', `Unable to load movie: ${error.message}`));
})();
