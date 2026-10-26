/* Shell contract unit test only: deliberately mocked Ruffle, NOT compatibility evidence. */
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../App/Resources/Web/shell.js'), 'utf8');
const language = process.argv[2] || 'en';
const settle = () => new Promise(resolve => setImmediate(resolve));

async function exercise(timing) {
  const controls = [], elements = {}, messages = [], listeners = new Map(), windowListeners = new Map();
  let config, suspended = 0, resumed = 0, appended, fetchResponse = {ok:true}, fetchError;
  const player = {
    ruffle: () => api, focus() {},
    addEventListener(type, callback, options) {
      const entries = listeners.get(type) || [];
      entries.push({callback, once:options?.once}); listeners.set(type, entries);
    },
    dispatchEvent(event) {
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
      // Like Ruffle 0.7.1, resolving this promise is not SWF completion.
    },
    suspend: () => suspended++, resume: () => resumed++
  };
  for (const id of ['status','pause','start','stage']) elements[id] = {textContent:'', append:p => appended = p};
  const context = {
    URL, URLSearchParams, Object, Set, Error, String, KeyboardEvent:class {},
    location:{href:'http://127.0.0.1:8766/cap/web/index.html?package=11111111-1111-4111-8111-111111111111&entry=folder%2Fspace%20%23.swf&language=' + encodeURIComponent(language)}
  };
  context.location.search = new URL(context.location.href).search;
  context.document = {
    documentElement:{}, getElementById:id => elements[id], querySelectorAll:() => controls,
    addEventListener() {}, createElement:() => ({}),
    head:{append:script => { context.window.RufflePlayer.newest = () => ({createPlayer:() => player}); script.onload(); }}
  };
  context.window = {
    webkit:{messageHandlers:{flashnest:{postMessage:message => messages.push(message)}}},
    fetch:async () => { if (fetchError) throw fetchError; return fetchResponse; },
    addEventListener:(type, callback) => windowListeners.set(type, callback)
  };
  vm.runInNewContext(source, context);
  await settle();

  assert.equal(config.url, 'http://127.0.0.1:8766/cap/games/11111111-1111-4111-8111-111111111111/folder/space%20%23.swf');
  assert.equal(config.base, 'http://127.0.0.1:8766/cap/games/11111111-1111-4111-8111-111111111111/folder/');
  assert.equal(config.publicPath, 'http://127.0.0.1:8766/cap/web/runtime/');
  assert.equal(config.allowNetworking, 'internal'); assert.equal(config.allowScriptAccess, false);
  assert.equal(appended, player);
  assert.equal(context.document.documentElement.lang, language);
  assert.equal(elements.start.textContent, language === 'zh-Hans' ? '播放 / 开启声音' : 'Play / enable audio');
  assert(messages.some(m => m.type === 'ready'));

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
  assert.equal(messages.at(-1).type, 'loaded', 'Initialization must not overwrite early SWF completion');
  player.dispatchEvent({type:'loadeddata'});
  assert.equal(messages.filter(m => m.type === 'loaded').length, 1, 'Completion is reported once');
  assert.equal(elements.status.textContent, language === 'zh-Hans' ? '文件已加载。点击“播放”开启声音。' : 'Movie loaded. Tap Play to start audio.');
  elements.start.onclick(); assert.equal(resumed, 1);
  context.window.FlashNest.pause(); assert.equal(suspended, 1);
  context.window.FlashNest.resume(); assert.equal(resumed, 2);

  if (timing === 'delayed') {
    const sanitizedURL = config.url.replace('/cap/', '/');
    fetchResponse = {ok:false, status:404, url:config.url};
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
  }
}

(async () => {
  for (const timing of ['delayed','early','rejected']) await exercise(timing);
  console.log(language + ': PASS shell URL/base, offline config, lifecycle, loadeddata timing, load failure and exact-root diagnostic redaction (mock unit test only)');
})().catch(error => { console.error(error); process.exitCode = 1; });
