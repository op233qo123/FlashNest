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
print(json.dumps({'staticContractPassed':True,'originalDiagnosticMethods':len(methods),'nativeTestsExecutedHere':False,'physicalDeviceCertified':False}))

# Import-size policy remains an explicit decision, never a global unsafe bypass.
importer=read('App/Import/PackageImporter.swift');preflight=read('App/Import/ImportSizeWarning.swift')
library=read('App/Models/LibraryStore.swift');appmain=read('App/FlashNestApp.swift')
assert importer.index('sizePreflight(source)') < importer.index('stageApproved(source')
assert 'if let warning = inspection.warning, sizeApproval == nil { throw warning }' in importer
assert 'sizeApproval != inspection.approval' in importer and 'original.sizePreflight(source).approval == inspection.approval' in importer
assert 'bytes <= maximum - size' in importer and 'guard size == expectedSize' in importer
assert 'bufferSize: 65536' in importer and 'read(upToCount: 65536)' in importer
assert 'entry.uncompressedSize / max(entry.compressedSize, 1) <= limits.compressionRatio' in preflight
assert 'ZIPIntegrity.expectedEntryCount' in preflight and 'ImportPathRegistry' in preflight
assert 'addingReportingOverflow' in preflight and 'addingReportingOverflow' in read('App/Import/ImportControl.swift')
assert 'requestSizeConfirmation(warning, operation: operation)' in library
assert 'pending.id == id' in library and 'pending.operation == importOperation' in library
assert 'withTaskCancellationHandler' in library and 'finishSizeConfirmation(allow: false)' in library
for path in ('App/Views/LibraryView.swift','App/Views/LocalImportInboxView.swift'):
 assert '.importSizeWarning(library:' in read(path)
assert appmain.index('#if DEBUG') < appmain.index('--flashnest-import-size-warning-ui-test') < appmain.index('#endif')
print(json.dumps({'importWarningStaticContractPassed':True,'actualNativeExecution':False}))
