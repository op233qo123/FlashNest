#!/usr/bin/env python3
"""Static integration contract, not Swift compilation or physical-device proof."""
import os,re,json,hashlib
from pathlib import Path
app=Path(os.environ.get('DIAGNOSTIC_APP', str(Path(__file__).resolve().parents[1]/'staged-app')))
read=lambda p:(app/p).read_text()
session=read('App/Player/PlayerSession.swift');store=read('App/Player/LongRunDiagnostics.swift');web=read('App/Resources/Web/long-run-diagnostics.js');html=read('App/Resources/Web/index.html');view=read('App/Views/PlayerView.swift')
assert 'UserDefaults.standard.bool(forKey: LongRunDiagnostics.preferenceKey)' in session
assert 'if longRunDiagnosticsEnabled && !storageOnly' in session
assert '"session": snapshot.session.uuidString, "epoch": snapshot.wkEpoch' in session
assert '__FlashNestLongRunConfig' in session and 'config.epoch' in web
assert '__FlashNestLongRunObserver' in web and 'window.__FlashNestLongRunObserver?.stop()' in session
assert html.index('long-run-diagnostics.js') < html.index('shell.js')
assert web.count('setInterval(sample, INTERVAL_MS)')==1 and 'INTERVAL_MS = 10000' in web
assert all(x not in web for x in ['readPixels(', 'getImageData(', '.arrayBuffer(', 'localStorage', 'XMLHttpRequest', 'fetch('])
assert 'new WeakMap()' in web and 'CONTEXT_MAX = 4' in web and '16384' in web
assert 'wasmBytes:' not in web, 'Current observer must not pretend unchanged Ruffle exposes WASM capacity'
assert 'source === active, !processTerminated' in session
assert 'guard isMainFrame' in session and 'current.path == shell.path' in session
assert 'snapshot.session == generation' in session and 'now - $0 >= 5' in session
clear=session.split('func clearLongRunDiagnostics()',1)[1].split('var longRunExport',1)[0]
assert clear.index('longRunSnapshot = nil') < clear.index('longRunStore.clear()')
term=session.split('func webViewWebContentProcessDidTerminate',1)[1]
assert term.index('self.webView === webView') < term.index('recordLongRun(.webProcessTerminated)') < term.index('generation = UUID()')
assert 'static let eventLimit = 120' in store and 'static let maximumBytes = 262_144' in store
assert 'Set(body.keys).isSubset' in store and 'CFGetTypeID(value) != CFBooleanGetTypeID()' in store
assert 'ShareLink(item: export)' in view and 'let export = session.longRunExport' in view
assert 'WASM capacity is unavailable in this build.' in view and 'Counters observe WebGL only' in view
assert 'Internal Flash scenes are not automatically detected.' in view
for loc in ('en','zh-Hans'):
 strings=read('App/Resources/Localization/'+loc+'.lproj/Localizable.strings')
 for key in ('Long-run diagnostics','Enable long-run diagnostics','Mark observation','Share long-run record','Clear long-run records'):
  assert ('"'+key+'" = ') in strings
classes=('LongRunDiagnosticsTests','LongRunSessionTests','LoadingPhaseDiagnosticsTests','LoopbackLoadPhaseTests')
methods=[]
for name in classes:
 methods.extend((name,m) for m in re.findall(r'\bfunc (test\w+)\(',read('Tests/'+name+'.swift')))
assert len(methods)==25 and len(set(methods))==25, methods
print(json.dumps({'staticContractPassed':True,'expectedNativeTests':len(methods),'nativeTestsExecutedHere':False,'physicalDeviceCertified':False}))
