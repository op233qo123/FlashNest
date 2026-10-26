/* App-owned shell. Never evaluates imported HTML or SWF-provided JavaScript. */
(() => {
  'use strict';
  const status = document.getElementById('status');
  const requestedLanguage = new URLSearchParams(location.search).get('language');
  const language = (requestedLanguage || window.navigator?.language || 'en').toLowerCase().startsWith('zh') ? 'zh-Hans' : 'en';
  const strings = {
    en: {
      title:'FlashNest Player', preparing:'Preparing offline runtime…', play:'Play / enable audio', pause:'Pause', resume:'Resume', action:'Action', enter:'Enter', stage:'Flash player', controls:'Game controls',
      offline:'Offline policy blocked {0}. Remote servers are unavailable; include local assets in the package.', jsError:'JavaScript/resource error: {0}', unknown:'unknown', runtimeError:'Runtime error: {0}', wasmStart:'Runtime WASM fetch started: {0}', wasmResponse:'Runtime WASM response: {0}; bytes={1}', assetFailed:'Asset request failed ({0}): {1}', assetBlocked:'Asset request blocked or unavailable: {0}', invalid:'Invalid package or entry SWF.', unsafe:'Unsafe entry path.', missing:'Bundled runtime missing or blocked.', ready:'Offline runtime ready.', initializing:'Initializing bundled WASM and renderer…', pending:'Runtime initialization still pending after 20 seconds; download progress={0}; visible={1}', unavailable:'unavailable', initialized:'Bundled WASM and renderer initialized; main SWF request started.', loaded:'Movie loaded. Tap Play to start audio.', loadError:'Unable to load movie: {0}'
    },
    'zh-Hans': {
      title:'FlashNest 播放器', preparing:'正在准备离线运行环境…', play:'播放 / 开启声音', pause:'暂停', resume:'继续', action:'动作', enter:'确认', stage:'Flash 播放区域', controls:'游戏按键',
      offline:'离线策略已拦截 {0}。无法连接远程服务器，请将资源一并导入。', jsError:'脚本或资源错误：{0}', unknown:'未知', runtimeError:'运行错误：{0}', wasmStart:'正在加载 WASM：{0}', wasmResponse:'WASM 响应：{0}；字节数={1}', assetFailed:'资源请求失败（{0}）：{1}', assetBlocked:'资源被拦截或不可用：{0}', invalid:'游戏包或入口 SWF 无效。', unsafe:'入口路径不安全。', missing:'内置运行环境缺失或被拦截。', ready:'离线运行环境已就绪。', initializing:'正在初始化 WASM 和渲染器…', pending:'初始化已超过 20 秒；下载进度={0}；页面可见={1}', unavailable:'不可用', initialized:'WASM 和渲染器已初始化，正在加载主 SWF。', loaded:'文件已加载。点击“播放”开启声音。', loadError:'无法加载文件：{0}'
    }
  };
  const t = (key, ...values) => strings[language][key].replace(/\{(\d+)\}/g, (_, i) => String(values[Number(i)] ?? ''));
  if (document.documentElement) document.documentElement.lang = language;
  document.title = t('title');
  status.textContent = t('preparing');
  document.getElementById('start').textContent = t('play');
  document.getElementById('pause').textContent = t('pause');
  document.getElementById('stage').setAttribute?.('aria-label', t('stage'));
  document.getElementById('controls')?.setAttribute?.('aria-label', t('controls'));
  document.querySelectorAll('[data-key]').forEach(button => {
    if (button.dataset.key === 'Space') button.textContent = t('action');
    if (button.dataset.key === 'Enter') button.textContent = t('enter');
  });

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
  document.getElementById('pause').onclick = () => { paused = !paused; releaseKeys(); reconcile(); document.getElementById('pause').textContent = paused ? t('resume') : t('pause'); };
  document.getElementById('start').onclick = () => { started = true; paused = false; reconcile(); player?.focus(); };
  window.addEventListener('blur', releaseKeys);
  document.addEventListener('visibilitychange', () => { backgrounded = document.hidden; releaseKeys(); reconcile(); });
  document.querySelectorAll('[data-key]').forEach(button => {
    button.addEventListener('pointerdown', event => { event.preventDefault(); button.setPointerCapture(event.pointerId); button.classList.add('held'); key(button.dataset.key, true); });
    for (const name of ['pointerup','pointercancel','lostpointercapture']) button.addEventListener(name, () => { button.classList.remove('held'); key(button.dataset.key, false); });
  });
  document.addEventListener('securitypolicyviolation', e => report('diagnostic', t('offline', e.blockedURI || e.violatedDirective)));
  window.addEventListener('error', e => report('diagnostic', t('jsError', e.message || e.target?.src || t('unknown'))), true);
  window.addEventListener('unhandledrejection', e => report('error', t('runtimeError', e.reason?.message || e.reason)));
  // Report missing local subassets without converting remote URLs to local URLs.
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const resource = String(args[0]?.url || args[0]);
    const runtimeAsset = /\.wasm(?:[?#]|$)/.test(resource);
    if (runtimeAsset) report('diagnostic', t('wasmStart', resource.split('/').pop()));
    try { const response = await originalFetch(...args);
      if (runtimeAsset) report('diagnostic', t('wasmResponse', response.status, response.headers.get('content-length') || t('unknown')));
      if (!response.ok) report('diagnostic', t('assetFailed', response.status, response.url)); return response; }
    catch (error) { report('diagnostic', t('assetBlocked', String(args[0]?.url || args[0]).slice(0,300))); throw error; }
  };
  async function boot() {
    const query = new URLSearchParams(location.search);
    const entry = query.get('entry'), id = query.get('package');
    if (!id || !/^[a-f0-9-]{36}$/i.test(id) || !entry || !/\.swf$/i.test(entry)) throw Error(t('invalid'));
    const parts = entry.split('/');
    if (parts.some(p => !p || p === '.' || p === '..' || /[\\\x00-\x1f]/.test(p))) throw Error(t('unsafe'));
    const root = new URL('../', location.href);
    const url = new URL(`games/${id}/${parts.map(encodeURIComponent).join('/')}`, root);
    const runtime = new URL('./runtime/', location.href);
    window.RufflePlayer = {config:{publicPath:runtime.href, polyfills:false}};
    await new Promise((resolve,reject) => { const script = document.createElement('script'); script.src = new URL('ruffle.js',runtime).href; script.onload = resolve; script.onerror = () => reject(Error(t('missing'))); document.head.append(script); });
    const ruffle = window.RufflePlayer.newest();
    player = ruffle.createPlayer();
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
    report('diagnostic', t('initialized'));
    player.ruffle().traceObserver = message => report('diagnostic', `SWF: ${message}`);
    reconcile(); report('loaded', t('loaded'));
  }
  boot().catch(error => report('error', t('loadError', error.message)));
})();
