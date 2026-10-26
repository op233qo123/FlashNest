/* Shell contract unit test only: deliberately mocked Ruffle, NOT compatibility evidence. */
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../App/Resources/Web/shell.js'), 'utf8');
const bridgeSource = fs.readFileSync(path.join(__dirname, '../App/Resources/Web/save-bridge.js'), 'utf8');
const language = process.argv[2] || 'en';
const settle = () => new Promise(resolve => setImmediate(resolve));

async function exercise(timing) {
  const controls = [], elements = {}, messages = [], keyEvents = [], listeners = new Map(), windowListeners = new Map(), documentListeners = new Map(), stored = new Map();
  let finishLoad, config, suspended = 0, resumed = 0, removed = 0, appended, fetchResponse = {ok:true}, fetchError, fetchCalls = 0, canvasFocusCalls = 0, clockTime = 0, traceCloseStart;
  const canvasListeners = new Map();
  const canvas = {
    clientWidth:390, clientHeight:844, width:1170, height:2532,
    focus() { canvasFocusCalls++; }, // Deliberately unfocusable, like pinned Ruffle's canvas.
    dispatchEvent:event => player.dispatchEvent(event),
    addEventListener:(name, callback) => canvasListeners.set(name, callback)
  };
  const player = {
    ruffle: () => api, focus() { context.document.activeElement = player; }, remove() { removed++; },
    shadowRoot:{querySelector:selector => selector === 'canvas' ? canvas : null},
    addEventListener(type, callback, options) {
      const entries = listeners.get(type) || [];
      entries.push({callback, once:options?.once}); listeners.set(type, entries);
    },
    dispatchEvent(event) {
      if (event.type === 'keydown') assert.equal(context.document.activeElement, player, 'Focus must be restored before dispatch');
      if (event.type.startsWith('key')) keyEvents.push(event);
      for (const listener of [...(listeners.get(event.type) || [])]) {
        if (listener.once) listeners.set(event.type, listeners.get(event.type).filter(x => x !== listener));
        listener.callback(event);
      }
    }
  };
  const api = {
    load: async options => {
      config = options;
      assert.equal(listeners.get('loadeddata')?.length, 1, 'Install the completion listener before load');
      if (timing === 'early') player.dispatchEvent({type:'loadeddata'});
      if (timing === 'rejected') throw new Error('fixture load failed: ' + options.url);
      if (timing === 'closewhileloading') await new Promise(resolve => { finishLoad = resolve; });
      // Like Ruffle 0.7.1, resolving this promise is not SWF completion.
    },
    suspend: () => suspended++, resume: () => resumed++
  };
  for (const id of ['status','start','stage']) elements[id] = {textContent:'', disabled:id === 'start', hidden:false, append:p => appended = p};
  const context = {
    URL, URLSearchParams, Object, Set, Error, String, TextEncoder, atob, btoa, KeyboardEvent:class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
    location:{href:'http://127.0.0.1:8766/cap/web/index.html?package=11111111-1111-4111-8111-111111111111&entry=folder%2Fspace%20%23.swf&language=' + encodeURIComponent(language)}
  };
  if (['storageonly','invalidrestore','livewins','replace'].includes(timing)) context.location.href += '&storageOnly=1';
  if (timing === 'handshake') context.location.href += '&nativeSaveHandshake=1';
  context.location.search = new URL(context.location.href).search;
  context.document = {
    documentElement:{}, getElementById:id => elements[id], querySelectorAll:() => controls,
    addEventListener:(type, callback) => documentListeners.set(type, callback), createElement:() => ({}),
    head:{append:script => { context.window.RufflePlayer.newest = () => ({createPlayer:() => player}); script.onload(); }}
  };
  context.window = {
    webkit:{messageHandlers:{flashnest:{postMessage:message => messages.push(message)}}},
    localStorage:{get length() { return stored.size; }, key:index => [...stored.keys()][index], getItem:key => stored.get(key) ?? null, setItem:(key,value) => stored.set(key,value), removeItem:key => stored.delete(key)},
    fetch:async () => { fetchCalls++; if (fetchError) throw fetchError; return fetchResponse; },
    devicePixelRatio:3, performance:{now:() => clockTime},
    addEventListener:(type, callback) => windowListeners.set(type, callback),
    setTimeout:() => 1, clearTimeout() {}
  };
  if (['storageonly','livewins','replace'].includes(timing)) {
    const bytes = Buffer.alloc(24); bytes[1] = 191; bytes.write('TCSO', 6); bytes[11] = 4;
    context.window.__FlashNestRestore = {version:1,entries:[{scope:'origin',key:'Saved',value:bytes.toString('base64')}]};
    if (timing === 'livewins' || timing === 'replace') {
      stored.set('127.0.0.1//NewerLive', bytes.toString('base64'));
      context.window.__FlashNestRestorePolicy = timing === 'replace' ? 'replace' : 'ifEmpty';
    }
  }
  if (timing === 'invalidrestore') context.window.__FlashNestRestore = {version:99,entries:[]};
  vm.runInNewContext(bridgeSource, context);
  vm.runInNewContext(source, context);
  await settle();

  if (['storageonly','livewins','replace'].includes(timing)) {
    assert.equal(config, undefined); assert.equal(appended, undefined);
    assert.deepEqual(messages.map(message => message.type), ['saveReady']);
    const saved = await context.window.FlashNest.shutdownAndCapture();
    assert.equal(saved.entries[0].key, timing === 'livewins' ? 'NewerLive' : 'Saved'); assert.equal(saved.entries[0].scope, 'origin');
    assert.equal(context.window.RufflePlayer, undefined, 'Storage-only mode must not load Ruffle');
    assert.equal(context.window.__FlashNestRestore, undefined);
    return;
  }
  if (timing === 'handshake') {
    assert.equal(config, undefined, 'Ruffle must wait for native acknowledgement');
    assert.equal(messages.at(-1).type, 'saveReady');
    assert.equal(context.window.FlashNest.confirmSaveReady(), true);
    assert.equal(context.window.FlashNest.confirmSaveReady(), false, 'Acknowledgement is one-shot');
    await settle(); assert(config, 'Ruffle starts only after native consumed the import marker');
    await context.window.FlashNest.shutdownAndCapture(); return;
  }
  if (timing === 'invalidrestore') {
    assert.equal(config, undefined); assert.equal(appended, undefined);
    assert(!messages.some(message => message.type === 'saveReady'));
    assert.equal(messages.at(-1).type, 'error');
    await assert.rejects(context.window.FlashNest.shutdownAndCapture(), /not ready/);
    return;
  }
  if (timing === 'closewhileloading') {
    const close = context.window.FlashNest.shutdownAndCapture();
    await settle(); assert.equal(removed, 0, 'Do not snapshot while WASM can still create an instance');
    finishLoad(); await close;
    assert.equal(removed, 1); assert(!messages.some(message => message.type === 'loaded'));
    return;
  }

  assert.equal(config.url, 'http://127.0.0.1:8766/cap/games/11111111-1111-4111-8111-111111111111/folder/space%20%23.swf');
  assert.equal(config.base, 'http://127.0.0.1:8766/cap/games/11111111-1111-4111-8111-111111111111/folder/');
  assert.equal(config.publicPath, 'http://127.0.0.1:8766/cap/web/runtime/');
  assert.equal(config.allowNetworking, 'internal'); assert.equal(config.allowScriptAccess, false);
  assert.equal(appended, player);
  assert.equal(context.document.documentElement.lang, language);
  assert.equal(elements.start.textContent, language === 'zh-Hans' ? '播放 / 开启声音' : 'Play / enable audio');
  assert(messages.some(m => m.type === 'ready'));
  assert.equal(messages[0].type, 'saveReady');

  if (timing === 'rejected') {
    assert.equal(messages.filter(m => m.type === 'loaded').length, 0, 'A failed load must not report completion');
    assert.equal(messages.at(-1).type, 'error');
    const failurePrefix = language === 'zh-Hans' ? '无法加载文件：' : 'Unable to load movie: ';
    assert.equal(elements.status.textContent, failurePrefix + 'fixture load failed: ' + config.url.replace('/cap/', '/'));
    assert(messages.every(m => !m.message.includes('/cap/')), 'Boot errors must not expose the app capability');
    return;
  }
  assert.equal(typeof api.traceObserver, 'function');
  if (timing === 'delayed') {
    assert.equal(messages.filter(m => m.type === 'loaded').length, 0, 'load() resolution must not report completion');
    assert.equal(elements.status.textContent, language === 'zh-Hans' ? 'WASM 和渲染器已初始化，正在加载主 SWF。' : 'Bundled WASM and renderer initialized; main SWF request started.');
    player.dispatchEvent({type:'loadeddata'});
  }
  assert.equal(messages.filter(m => m.type !== 'diagnostic').at(-1).type, 'loaded', 'Initialization must not overwrite early SWF completion');
  player.dispatchEvent({type:'loadeddata'});
  assert.equal(messages.filter(m => m.type === 'loaded').length, 1, 'Completion is reported once');
  assert.equal(elements.status.textContent, language === 'zh-Hans' ? '文件已加载。点击“播放”开启声音。' : 'Movie loaded. Tap Play to start audio.');
  context.window.FlashNest.start(); assert.equal(resumed, 1);
  assert.equal(elements.start.hidden, false, 'Native start is not a trusted web audio gesture');
  elements.start.onclick(); assert.equal(resumed, 2); assert.equal(elements.start.hidden, true);
  context.window.FlashNest.pause(); assert.equal(suspended, 1);
  context.window.FlashNest.resume(); assert.equal(resumed, 3);

  const input = context.window.FlashNest;
  context.document.activeElement = {outside:true};
  input.key('KeyA', true);
  assert.equal(context.document.activeElement, player, 'Virtual keydown must restore Ruffle host focus');
  assert.equal(canvasFocusCalls, 0, "Do not try to focus Ruffle's unfocusable canvas");
  input.key('KeyA', true); input.key('KeyA', true);
  assert.equal(keyEvents.length, 1); assert.equal(keyEvents[0].key, 'a'); assert.equal(keyEvents[0].keyCode, 65);
  input.key('KeyA', false); input.key('ShiftLeft', true); input.key('KeyZ', true);
  assert.equal(keyEvents.at(-1).key, 'Z'); assert.equal(keyEvents.at(-1).shiftKey, true);
  input.releaseKeys(); assert.equal(keyEvents.at(-1).type, 'keyup');
  const count = keyEvents.length;
  input.key('__proto__', true); input.key('F12', true); input.key('KeyA', 'true');
  assert.equal(keyEvents.length, count, 'Only finite codes and boolean key state are accepted');
  for (const code of ['Digit0','Digit9','Escape','Backspace','Tab','ShiftRight']) { input.key(code, true); input.key(code, false); }
  input.key('ArrowLeft', true); windowListeners.get('blur')();
  assert.equal(keyEvents.at(-1).type, 'keyup');
  input.key('Space', true); documentListeners.get('pointercancel')();
  assert.equal(keyEvents.at(-1).type, 'keyup');

  if (timing === 'delayed') {
    const sanitizedURL = config.url.replace('/cap/', '/');
    fetchResponse = {ok:false, status:404, url:config.url, headers:{get:() => '44'},
      clone() { throw new Error('Must not clone a game response'); },
      arrayBuffer() { throw new Error('Must not buffer a game response'); },
      get body() { throw new Error('Must not consume the response stream'); }};
    assert.equal(await context.window.fetch(config.url), fetchResponse, 'Diagnostic redaction must not alter the response');
    assert(messages.at(-1).message.includes('404'));
    assert(messages.at(-1).message.includes(sanitizedURL), 'Keep the resource path in diagnostics');
    fetchError = new Error('fixture transport failure');
    await assert.rejects(context.window.fetch(config.url), error => error === fetchError);
    assert(messages.at(-1).message.includes(sanitizedURL));
    windowListeners.get('error')({message:'Resource error: ' + config.url});
    windowListeners.get('unhandledrejection')({reason:new Error('Rejected: ' + config.url)});
    assert(messages.at(-1).message.includes(sanitizedURL));
    assert(!elements.status.textContent.includes('/cap/'));
    assert(messages.every(m => !m.message.includes('/cap/')), 'Local capability must not appear in posted messages');

    // Even the same path on a different origin is not the app's URL prefix.
    const remoteURL = config.url.replace('http://127.0.0.1:8766', 'https://example.com');
    windowListeners.get('error')({message:'Remote: ' + remoteURL});
    assert(messages.at(-1).message.includes(remoteURL), 'Do not rewrite unrelated remote URLs');

    fetchError = undefined;
    const callsBefore = fetchCalls;
    const reportsBefore = messages.length;
    for (let i = 0; i < 100; i++) await context.window.fetch(config.url + '?privateSave=do-not-log');
    assert.equal(fetchCalls - callsBefore, 100, 'Diagnostics must forward each fetch exactly once');
    assert(messages.length - reportsBefore <= 61, 'SWF request diagnostics must have a finite budget');
    assert(messages.every(m => !m.message.includes('privateSave') && !m.message.includes('do-not-log')));
    assert(messages.some(m => m.message.includes('status=404') || m.message.includes('状态=404')));
    assert(messages.some(m => m.message.includes('bytes=44') || m.message.includes('字节数=44')));
    for (let i = 0; i < 12; i++) canvasListeners.get('webglcontextlost')({preventDefault() { throw new Error('Do not change renderer behavior'); }});
    assert.equal(messages.filter(m => m.message.includes('webglcontextlost')).length, 4, 'Context-loss diagnostics are bounded');
    for (let i = 0; i < 40; i++) { input.pause(); input.resume(); }
    assert(messages.filter(m => m.message.startsWith('Player state') || m.message.startsWith('播放器状态')).length <= 24);
    assert(messages.some(m => m.message.includes('1170x2532') && m.message.includes('DPR=3')));

    const traceStart = messages.length;
    const isSuppression = m => m.message.startsWith('SWF trace limit:') || m.message.startsWith('SWF 跟踪限流：');
    for (let i = 0; i < 20; i++) api.traceObserver('FLASHNEST_FIXTURE_' + i + ' ' + config.url);
    assert.equal(messages.length - traceStart, 20, 'Ordinary fixture-rate traces remain available');
    // A dropped trace must not even be formatted or retained by our observer.
    const discarded = {toString() { throw new Error('Suppressed payload was inspected'); }};
    api.traceObserver('suppressed-secret-save-payload ' + config.url);
    for (let i = 0; i < 9999; i++) api.traceObserver(discarded);
    assert.equal(messages.length - traceStart, 21, 'A 10,000-trace storm adds only one immediate count notice');
    assert.equal(messages.slice(traceStart).filter(isSuppression).length, 1);
    assert(messages.slice(traceStart).every(m => !m.message.includes('/cap/') && !m.message.includes('suppressed-secret-save-payload')), 'Accepted traces redact capabilities and dropped payloads never enter diagnostics');
    clockTime = 999;
    api.traceObserver(discarded);
    assert.equal(messages.length - traceStart, 21, 'Budget must not reset before the interval expires');
    clockTime = 1000;
    api.traceObserver('FLASHNEST_AFTER_RATE_RESET');
    assert.equal(messages.at(-1).message, 'SWF: FLASHNEST_AFTER_RATE_RESET');
    assert(isSuppression(messages.at(-2)) && messages.at(-2).message.includes('10001'), 'Next interval reports the previous final suppression count');
    for (let i = 0; i < 19; i++) api.traceObserver('ordinary');
    for (let i = 0; i < 7; i++) api.traceObserver(discarded);
    traceCloseStart = messages.length;
  }
  input.key('Enter', true);
  const firstClose = input.shutdownAndCapture();
  assert.equal(firstClose, input.shutdownAndCapture(), 'Close must be idempotent');
  const capture = await firstClose;
  assert.equal(capture.version, 1); assert.equal(capture.entries.length, 0); assert.equal(removed, 1);
  if (timing === 'delayed') {
    const finalCounts = messages.slice(traceCloseStart).filter(m => m.message.startsWith('SWF trace limit:') || m.message.startsWith('SWF 跟踪限流：'));
    assert.equal(finalCounts.length, 1, 'Idempotent shutdown emits at most one final suppression count');
    assert(finalCounts[0].message.includes('7'));
  }
  assert.equal(keyEvents.at(-1).type, 'keyup', 'Close releases held native keys');
  const afterClose = keyEvents.length; input.key('KeyA', true); assert.equal(keyEvents.length, afterClose);
}

(async () => {
  for (const timing of ['delayed','early','rejected','storageonly','invalidrestore','closewhileloading','livewins','replace','handshake']) await exercise(timing);
  console.log(language + ': PASS shell URL/base, offline config, key focus/lifecycle, bounded scene/trace diagnostics, loadeddata timing, redaction, restore ordering, storage-only and close-race (mock unit test only)');
})().catch(error => { console.error(error); process.exitCode = 1; });

require("./test_save_bridge.js");
