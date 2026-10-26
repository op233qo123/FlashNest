/* App-owned shell. Never evaluates imported HTML or SWF-provided JavaScript. */
(() => {
  'use strict';
  const status = document.getElementById('status');
  const requestedLanguage = new URLSearchParams(location.search).get('language');
  const language = (requestedLanguage || window.navigator?.language || 'en').toLowerCase().startsWith('zh') ? 'zh-Hans' : 'en';
  const strings = {
    en: {
      title:'FlashNest Player', preparing:'Preparing offline runtime…', play:'Play / enable audio', pause:'Pause', resume:'Resume', action:'Action', enter:'Enter', stage:'Flash player', controls:'Game controls',
      offline:'Offline policy blocked {0}. Remote servers are unavailable; include local assets in the package.', jsError:'JavaScript/resource error: {0}', unknown:'unknown', runtimeError:'Runtime error: {0}', wasmStart:'Runtime WASM fetch started: {0}', wasmResponse:'Runtime WASM response: {0}; bytes={1}', assetFailed:'Asset request failed ({0}): {1}', assetBlocked:'Asset request blocked or unavailable: {0}', invalid:'Invalid package or entry SWF.', unsafe:'Unsafe entry path.', missing:'Bundled runtime missing or blocked.', ready:'Offline runtime ready.', initializing:'Initializing bundled WASM and renderer…', pending:'Runtime initialization still pending after 20 seconds; download progress={0}; visible={1}', unavailable:'unavailable', initialized:'Bundled WASM and renderer initialized; main SWF request started.', loaded:'Movie loaded. Tap Play to start audio.', saveReady:'Local save storage ready.', saveTimeout:'Native save preparation timed out.', swfRequest:'SWF request #{0}: {1}', swfResponse:'SWF response headers #{0}: status={1}; bytes={2}; {3}', swfFailure:'SWF fetch failed #{0}: {1}', swfLimit:'Further SWF request diagnostics omitted (limit reached).', traceSuppressed:'SWF trace limit: {0} message(s) suppressed in this interval.', graphicsEvent:'Renderer event: {0}', playerState:'Player state ({0}): started={1}; paused={2}; hidden={3}; focused={4}; canvasCSS={5}; canvasPixels={6}; DPR={7}', loadError:'Unable to load movie: {0}'
    },
    'zh-Hans': {
      title:'FlashNest 播放器', preparing:'正在准备离线运行环境…', play:'播放 / 开启声音', pause:'暂停', resume:'继续', action:'动作', enter:'确认', stage:'Flash 播放区域', controls:'游戏按键',
      offline:'离线策略已拦截 {0}。无法连接远程服务器，请将资源一并导入。', jsError:'脚本或资源错误：{0}', unknown:'未知', runtimeError:'运行错误：{0}', wasmStart:'正在加载 WASM：{0}', wasmResponse:'WASM 响应：{0}；字节数={1}', assetFailed:'资源请求失败（{0}）：{1}', assetBlocked:'资源被拦截或不可用：{0}', invalid:'游戏包或入口 SWF 无效。', unsafe:'入口路径不安全。', missing:'内置运行环境缺失或被拦截。', ready:'离线运行环境已就绪。', initializing:'正在初始化 WASM 和渲染器…', pending:'初始化已超过 20 秒；下载进度={0}；页面可见={1}', unavailable:'不可用', initialized:'WASM 和渲染器已初始化，正在加载主 SWF。', loaded:'文件已加载。点击“播放”开启声音。', saveReady:'本地存档已准备就绪。', saveTimeout:'原生存档准备超时。', swfRequest:'SWF 请求 #{0}：{1}', swfResponse:'SWF 响应头 #{0}：状态={1}；字节数={2}；{3}', swfFailure:'SWF 请求失败 #{0}：{1}', swfLimit:'后续 SWF 请求诊断已省略（达到数量上限）。', traceSuppressed:'SWF 跟踪限流：本时段已省略 {0} 条消息。', graphicsEvent:'渲染器事件：{0}', playerState:'播放器状态（{0}）：已开始={1}；暂停={2}；隐藏={3}；焦点={4}；画布CSS={5}；画布像素={6}；DPR={7}', loadError:'无法加载文件：{0}'
    }
  };
  const t = (key, ...values) => strings[language][key].replace(/\{(\d+)\}/g, (_, i) => String(values[Number(i)] ?? ''));
  if (document.documentElement) document.documentElement.lang = language;
  document.title = t('title');
  status.textContent = t('preparing');
  document.getElementById('start').textContent = t('play');
  document.getElementById('stage').setAttribute?.('aria-label', t('stage'));


  let player, saveBridge, bootPromise, shutdownPromise, resolveSaveHandshake, storageReady = false, closing = false, started = false, paused = false, backgrounded = false;
  const held = new Set();
  const keys = {ArrowLeft:37, ArrowUp:38, ArrowRight:39, ArrowDown:40, Space:32, Enter:13, Escape:27, Backspace:8, Tab:9, ShiftLeft:16, ShiftRight:16};
  for (let index = 0; index < 26; index++) keys['Key' + String.fromCharCode(65 + index)] = 65 + index;
  for (let index = 0; index < 10; index++) keys['Digit' + index] = 48 + index;
  Object.freeze(keys);
  const diagnosticRoot = new URL('../', location.href);
  const privateURLPrefix = diagnosticRoot.origin + diagnosticRoot.pathname;
  function report(type, message, updateStatus = true) {
    // Remove only this app's exact capability-bearing URL prefix, before
    // truncation. Keep resource paths/status and unrelated remote URLs intact.
    const text = String(message).split(privateURLPrefix).join(diagnosticRoot.origin + '/').slice(0, 1024);
    if (updateStatus) status.textContent = text;
    window.webkit?.messageHandlers?.flashnest?.postMessage({type, message:text});
  }
  let swfRequestID = 0, swfReports = 0, stateReports = 0, graphicsReports = 0;
  function reportSWF(message) {
    if (swfReports < 60) report('diagnostic', message, false);
    else if (swfReports === 60) report('diagnostic', t('swfLimit'), false);
    swfReports = Math.min(swfReports + 1, 61);
  }
  let traceWindowStart, traceCount = 0, suppressedTraces = 0, reportedSuppressedTraces = 0;
  function reportTraceSuppression() {
    if (suppressedTraces <= reportedSuppressedTraces) return;
    reportedSuppressedTraces = suppressedTraces;
    report('diagnostic', t('traceSuppressed', suppressedTraces), false);
  }
  function reportTrace(message) {
    const now = window.performance?.now?.() ?? Date.now();
    if (traceWindowStart === undefined || now - traceWindowStart >= 1000 || now < traceWindowStart) {
      reportTraceSuppression();
      traceWindowStart = now; traceCount = 0; suppressedTraces = 0; reportedSuppressedTraces = 0;
    }
    if (traceCount >= 20) {
      // Keep a count only: no payload queue, periodic timer, or console hook.
      suppressedTraces = Math.min(Number.MAX_SAFE_INTEGER, suppressedTraces + 1);
      if (suppressedTraces === 1) reportTraceSuppression();
      return;
    }
    traceCount++;
    report('diagnostic', `SWF: ${message}`);
  }
  function reportState(reason) {
    if (!player || stateReports >= 24) return;
    stateReports++;
    const canvas = player.shadowRoot?.querySelector('canvas');
    report('diagnostic', t('playerState', reason, started, paused, !!document.hidden,
      document.activeElement === player, canvas ? `${canvas.clientWidth}x${canvas.clientHeight}` : t('unavailable'),
      canvas ? `${canvas.width}x${canvas.height}` : t('unavailable'), window.devicePixelRatio || 1), false);
  }
  function watchRenderer() {
    const canvas = player?.shadowRoot?.querySelector('canvas');
    if (!canvas) return;
    for (const name of ['webglcontextlost', 'webglcontextrestored']) {
      // Observe only: do not preventDefault, replace the renderer, or reload.
      canvas.addEventListener(name, () => {
        if (graphicsReports++ < 4) report('diagnostic', t('graphicsEvent', name), false);
      });
    }
    reportState('renderer-ready');
  }
  function key(code, down) {
    if (!Object.hasOwn(keys, code) || !player || closing || typeof down !== 'boolean') return;
    if (down === held.has(code)) return;
    if (down) held.add(code); else held.delete(code);
    const target = player.shadowRoot?.querySelector('canvas') || player;
    // Ruffle tracks focus on its shadow host; its canvas has no tabindex.
    // Focusing the canvas can leave virtual keys ignored after focus is lost.
    if (down) {
      const hadFocus = document.activeElement === player;
      player.focus({preventScroll:true});
      if (!hadFocus) reportState('virtual-key-focus');
    }
    target.dispatchEvent(new KeyboardEvent(down ? 'keydown' : 'keyup', {
      key:code === 'Space' ? ' ' : code.startsWith('Key') ? (held.has('ShiftLeft') || held.has('ShiftRight') ? code.slice(3) : code.slice(3).toLowerCase()) : code.startsWith('Digit') ? code.slice(5) : code.startsWith('Shift') ? 'Shift' : code,
      code, keyCode:keys[code], which:keys[code], shiftKey:held.has('ShiftLeft') || held.has('ShiftRight'),
      location:code === 'ShiftLeft' ? 1 : code === 'ShiftRight' ? 2 : 0, bubbles:true, composed:true, cancelable:true
    }));
  }
  function releaseKeys() { for (const code of [...held]) key(code, false); }
  function reconcile() { if (!player || !started || closing) return; if (paused || backgrounded) player.ruffle().suspend(); else player.ruffle().resume(); }
  function pause() { const changed = !paused; releaseKeys(); paused = true; reconcile(); if (changed) reportState('pause'); }
  function resume() { const changed = paused; paused = false; reconcile(); if (changed) reportState('resume'); }
  function start(fromGesture = false) {
    if (closing) return;
    const changed = !started || paused;
    started = true; paused = false; reconcile(); player?.focus();
    if (changed) reportState('start');
    // A native evaluateJavaScript call is not a trusted audio gesture. Keep the
    // one small web affordance until the user actually taps the web content.
    if (fromGesture) document.getElementById('start').hidden = true;
  }
  function shutdownAndCapture() {
    if (shutdownPromise) return shutdownPromise;
    releaseKeys(); pause(); closing = true;
    shutdownPromise = (async () => {
      await bootPromise; // Do not let delayed WASM creation race a save snapshot.
      if (!saveBridge || !storageReady) throw new Error('Save storage is not ready');
      // Pinned Ruffle's disconnectedCallback calls instance.destroy(); dropping
      // its Rust Player flushes SharedObjects. Suspend alone does NOT flush.
      if (player) { player.remove(); player = null; }
      reportTraceSuppression();
      await Promise.resolve();
      return saveBridge.capture();
    })();
    return shutdownPromise;
  }
  function confirmSaveReady() {
    if (!resolveSaveHandshake) return false;
    resolveSaveHandshake(); resolveSaveHandshake = null;
    return true;
  }
  window.FlashNest = Object.freeze({start:() => start(false), pause, resume, key, releaseKeys, shutdownAndCapture, confirmSaveReady});
  document.getElementById('start').onclick = () => start(true);
  window.addEventListener('blur', releaseKeys);
  document.addEventListener('visibilitychange', () => { backgrounded = document.hidden; releaseKeys(); reconcile(); reportState('visibility'); });
  document.addEventListener('pointercancel', releaseKeys);
  document.addEventListener('lostpointercapture', releaseKeys, true);
  document.addEventListener('securitypolicyviolation', e => report('diagnostic', t('offline', e.blockedURI || e.violatedDirective)));
  window.addEventListener('error', e => report('diagnostic', t('jsError', e.message || e.target?.src || t('unknown'))), true);
  window.addEventListener('unhandledrejection', e => report('error', t('runtimeError', e.reason?.message || e.reason)));
  // Report missing local subassets without converting remote URLs to local URLs.
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const resource = String(args[0]?.url || args[0]);
    const runtimeAsset = /\.wasm(?:[?#]|$)/.test(resource);
    let parsed;
    try { parsed = new URL(resource, location.href); } catch (_) { /* Keep fetch's own error behavior. */ }
    const isSWF = parsed && /\.swf$/i.test(parsed.pathname);
    const requestID = isSWF ? ++swfRequestID : 0;
    // Do not log query values, credentials, response bodies, or duplicate data.
    const assetPath = isSWF ? parsed.origin + parsed.pathname : '';
    if (isSWF) reportSWF(t('swfRequest', requestID, assetPath));
    if (runtimeAsset) report('diagnostic', t('wasmStart', resource.split('/').pop()));
    try { const response = await originalFetch(...args);
      if (runtimeAsset) report('diagnostic', t('wasmResponse', response.status, response.headers.get('content-length') || t('unknown')));
      // fetch resolves at response headers, NOT at completed SWF decoding.
      if (isSWF) reportSWF(t('swfResponse', requestID, response.status, response.headers?.get('content-length') || t('unknown'), assetPath));
      else if (!response.ok) report('diagnostic', t('assetFailed', response.status, response.url));
      return response; }
    catch (error) {
      if (isSWF) reportSWF(t('swfFailure', requestID, assetPath));
      else report('diagnostic', t('assetBlocked', String(args[0]?.url || args[0]).slice(0,300)));
      throw error;
    }
  };
  async function boot() {
    const query = new URLSearchParams(location.search);
    const entry = query.get('entry'), id = query.get('package');
    if (!id || !/^[a-f0-9-]{36}$/i.test(id) || !entry || !/\.swf$/i.test(entry)) throw Error(t('invalid'));
    const parts = entry.split('/');
    if (parts.some(p => !p || p === '.' || p === '..' || /[\\\x00-\x1f]/.test(p))) throw Error(t('unsafe'));
    const root = new URL('../', location.href);
    const url = new URL(`games/${id}/${parts.map(encodeURIComponent).join('/')}`, root);
    saveBridge = window.FlashNestSaveBridge.create({storage:window.localStorage, location:location.href, packageID:id});
    if (window.__FlashNestRestore !== undefined) {
      const policy = window.__FlashNestRestorePolicy ?? 'ifEmpty';
      if (policy !== 'replace' && policy !== 'ifEmpty') throw new Error('Invalid save restore policy');
      // A newer game flush may survive an abnormal app exit while current.json
      // is older. Ordinary reopening must never overwrite that live save.
      if (policy === 'replace' || saveBridge.capture().entries.length === 0) saveBridge.restore(window.__FlashNestRestore);
      delete window.__FlashNestRestore;
      delete window.__FlashNestRestorePolicy;
    }
    storageReady = true;
    let handshake;
    if (query.get('nativeSaveHandshake') === '1') {
      handshake = new Promise((resolve, reject) => {
        const timeout = window.setTimeout(() => { resolveSaveHandshake = null; reject(new Error(t('saveTimeout'))); }, 15000);
        resolveSaveHandshake = () => { window.clearTimeout(timeout); resolve(); };
      });
    }
    // Native consumes a pending-import marker atomically before acknowledging,
    // so a crash after new gameplay begins cannot reapply an old import.
    report('saveReady', t('saveReady'));
    if (handshake) await handshake;
    if (query.get('storageOnly') === '1' || closing) return;
    const runtime = new URL('./runtime/', location.href);
    window.RufflePlayer = {config:{publicPath:runtime.href, polyfills:false}};
    await new Promise((resolve,reject) => { const script = document.createElement('script'); script.src = new URL('ruffle.js',runtime).href; script.onload = resolve; script.onerror = () => reject(Error(t('missing'))); document.head.append(script); });
    if (closing) return;
    const ruffle = window.RufflePlayer.newest();
    player = ruffle.createPlayer();
    player.addEventListener('pointerdown', event => { if (event.isTrusted) start(true); });
    let movieLoaded = false;
    // Ruffle 0.7.1 resolves load() after starting stream_from(), before the
    // root SWF download finishes. Only loadeddata confirms the movie arrived.
    player.addEventListener('loadeddata', () => {
      movieLoaded = true;
      if (closing) return;
      document.getElementById('start').disabled = false;
      reconcile(); report('loaded', t('loaded'));
    }, {once:true});
    document.getElementById('stage').append(player);
    report('ready', t('ready'));
    report('diagnostic', t('initializing'));
    const loadWatchdog = window.setTimeout?.(() => {
      const progress = player.shadowRoot?.querySelector('.loadbar-inner')?.style.width || t('unavailable');
      report('diagnostic', t('pending', progress, !document.hidden));
    }, 20000);
    try {
    await player.ruffle().load({url:url.href, base:new URL('./',url).href, publicPath:runtime.href,
      allowScriptAccess:false, allowNetworking:'internal', openUrlMode:'deny', socketProxy:[],
      autoplay:'off', unmuteOverlay:'visible', backgroundExecutionMode:'none', upgradeToHttps:false,
      showSwfDownload:false, contextMenu:'off', logLevel:'warn'});
    } finally { window.clearTimeout?.(loadWatchdog); }
    watchRenderer();
    // A small movie can dispatch loadeddata before load() resolves; do not
    // overwrite the completed state with an earlier initialization milestone.
    if (!movieLoaded) report('diagnostic', t('initialized'));
    player.ruffle().traceObserver = reportTrace;
    reconcile();
  }
  bootPromise = boot().catch(error => { report('error', t('loadError', error.message)); });
})();
