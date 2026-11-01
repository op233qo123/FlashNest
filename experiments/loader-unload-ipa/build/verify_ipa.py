#!/usr/bin/env python3
"""Verify actual candidate-runtime native execution and unsigned test package."""
import argparse,importlib.util,json,os,plistlib,re,subprocess,sys,tempfile,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import stage as e
from select_toolchain import verify as verify_toolchain
from run_ios_tests import verify_summary
IPA_NAME='FlashNest-1.5.6-build23-unload-fix-diagnostic-v2-import-warning-unsigned.ipa'
def load_checks(baseline, x):
    root = baseline / 'experiments/release-ipa-156-build22'
    e.need(e.inventory(root) == x['releaseRecipeFiles'], 'Frozen release validators differ')
    path = root / 'package_checks.py'
    name = 'case_ipa_frozen_package_checks'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def verify_focused(path_evidence, fps_evidence, config, x, case_root):
    path_raw = path_evidence.read_bytes(); path = json.loads(path_raw)
    fixture_source = (case_root / 'path-tests/CaseCompatibilityFixture.swift').read_text()
    names = re.findall(r'try check\("([^"\n]+)"', fixture_source)
    e.need(len(names) == len(set(names)) == 18, 'Reviewed path test inventory differs')
    e.need(path.get('schema') == 'flashnest-casecompat-native-v1'
           and path.get('passed') is True and path.get('caseSensitiveFilesystemVerified') is True,
           'Actual case-sensitive path tests not passed')
    e.need(type(path.get('count')) is int and path['count'] == 18 and path.get('tests') == names,
           'Actual path test names/counts differ')
    volume = plistlib.loads((path_evidence.parent / 'native-volume.plist').read_bytes())
    e.need(volume.get('FilesystemName') == 'Case-sensitive APFS'
           and volume.get('FilesystemType') == 'apfs', 'Case-sensitive filesystem evidence differs')
    raw = fps_evidence.read_bytes(); fps = json.loads(raw)
    e.need(fps.get('schema') == 'neutral-frame-cadence-v1' and fps.get('passed') is True,
           'Actual cadence tests not passed')
    e.need(fps.get('runtimeFiles') == x['runtimeFiles'] and fps.get('inputsSHA256') == config['baselineInputsSHA256'],
           'Cadence runtime/source inputs differ')
    for name in ('make_fixture.py', 'probe.html', 'run_fps.py'):
        digest = e.sha((e.ROOT / 'fps' / name).read_bytes())
        e.need(fps.get('sourceFiles', {}).get(name) == digest
               and e.config()['recipeFiles'].get('fps/' + name) == digest, 'Cadence test source differs')
    spec = importlib.util.spec_from_file_location('case_ipa_neutral_fixture', e.ROOT / 'fps/make_fixture.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    generated = module.make_swf()
    e.need(fps.get('fixtureBytes') == len(generated) and fps.get('fixtureSHA256') == e.sha(generated),
           'Actual neutral fixture differs')
    sandbox = fps.get('sandbox', {})
    e.need(sandbox.get('requested') is True and sandbox.get('forbiddenFlagsAbsent') is True
           and sandbox.get('requestedChannel') == 'chrome', 'Sandbox/browser evidence differs')
    arguments = sandbox.get('effectiveCommandLine')
    forbidden = {'--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu-sandbox', '--enable-unsafe-swiftshader','--unsafely-disable-devtools-self-xss-warnings'}
    e.need(isinstance(arguments, list) and arguments and all(isinstance(a, str) for a in arguments)
           and not any(a.split('=')[0] in forbidden for a in arguments), 'Forbidden browser flags')
    rows = fps.get('rows', [])
    e.need(len(rows) == 5, 'Incomplete cadence matrix')
    for index, row in enumerate(rows):
        e.need(row.get('passed') is True and row.get('actualRenderer') in ('webgl', 'webgl2', 'experimental-webgl')
               and row.get('physicalGPUCertified') is False, 'Invalid renderer/acceptance evidence')
        e.need(row.get('metadata', {}).get('frameRate') == 24, 'Wrong original SWF frame rate')
        fetched = row.get('wasmResponses', [])
        e.need(fetched and all(w.get('name', '').endswith('.wasm')
               and x['runtimeFiles'].get(w.get('name')) == w.get('sha256') for w in fetched), 'Actual WASM differs')
        if index < 3:
            target = (24, 24, 48)[index]
            e.need(row.get('scheduler') == 'real-browser-wallclock' and row.get('override') == (None, 24, 48)[index]
                   and row.get('expectedFPS') == target, 'Wrong cadence wall-clock arm')
            seconds = row.get('seconds'); frames = row.get('frames'); rate = row.get('observedFPS')
            e.need(type(seconds) in (float, int) and seconds >= 4 and type(frames) is int and frames > 0
                   and type(rate) in (float, int) and abs(rate - frames / seconds) < 1e-8
                   and abs(rate - target) < target * 0.18, 'Cadence measurement/threshold mismatch')
        else:
            seconds = row.get('virtualSeconds'); frames = row.get('frames')
            e.need(row.get('scheduler') == 'synthetic-RAF-timestamps' and row.get('syntheticHz') == (60, 120)[index - 3]
                   and row.get('physicalDisplayTest') is False and row.get('expectedFPS') == 24,
                   'Synthetic timing mislabeled')
            e.need(type(seconds) in (float, int) and abs(seconds - 10) < 1e-6 and type(frames) is int
                   and abs(frames - 24 * seconds) <= 2, 'Synthetic cadence count mismatch')
    e.need(1.65 < rows[2]['observedFPS'] / rows[0]['observedFPS'] < 2.35, 'Cadence control not sensitive')
    e.need(fps.get('productFrameRateChanged') is False and fps.get('privateGameInputs') is False,
           'Unexpected cadence source/product scope')
    return {'pathEvidenceSHA256': e.sha(path_raw), 'path': path,
            'volumeEvidenceSHA256': e.sha((path_evidence.parent / 'native-volume.plist').read_bytes()),
            'fpsEvidenceSHA256': e.sha(raw), 'fps': fps}

def verify_native(native_dir,app,staged,stage_raw,baseline_inputs,toolchain,toolchain_path):
    raw=(native_dir/'verification.json').read_bytes();n=json.loads(raw)
    e.need(n['nativeExecutedThisRun'] is True and n['nativeEvidenceReused'] is False,'Fresh candidate native execution required')
    e.need(n['head']==os.environ['GITHUB_SHA'] and n['runID']==os.environ['GITHUB_RUN_ID'],'Native execution wrong current run')
    e.need(n['effectiveSourceFiles']==staged['effectiveSourceFiles'] and n['runtimeFiles']==staged['runtimeFiles'],'Native source/runtime mismatch')
    e.need(n['stageReceiptSHA256']==e.sha(stage_raw) and n['toolchainReceiptSHA256']==e.sha(toolchain_path.read_bytes()),'Native input receipt mismatch')
    e.need(n['toolchain']==toolchain and n['runnerSHA256']==e.sha((Path(__file__).parent/'run_ios_tests.py').read_bytes()),'Native runner/toolchain mismatch')
    base=[tuple(x) for x in baseline_inputs['expectedNativeTests']]
    e.need(len(base)==70,'Inherited native methods changed')
    http=re.findall(r'\bfunc\s+(test[A-Za-z0-9_]+)\s*\(', (app/'Tests/HTTPServerTests.swift').read_text())
    e.need(len(http)==len(set(http))==6,'HTTP methods changed')
    native=base+[('HTTPServerTests',m) for m in http]+[tuple(x) for x in staged['additionalNativeTests']]
    ui=[tuple(x) for x in baseline_inputs['expectedUITests']]
    e.need(len(ui)==2 and n['baselineNativeCount']==76 and n['additionalNativeTests']==staged['additionalNativeTests'],'Native lane declarations differ')
    for lane,expected,bundle in [('native',native,'FlashNestTests'),('ui',ui,'FlashNestUITests')]:
        summary_path=native_dir/(lane+'-summary.json');summary_raw=summary_path.read_bytes()
        actual=subprocess.check_output(['xcrun','xcresulttool','get','test-results','summary','--path',str(native_dir/(lane+'.xcresult'))],timeout=60)
        e.need(json.loads(actual)==json.loads(summary_raw),'Actual xcresult summary differs')
        proof=verify_summary(json.loads(summary_raw),(native_dir/(lane+'.log')).read_text(),expected,n['native']['deviceID'],bundle,toolchain['runtimeVersion'])
        proof.update(summarySHA256=e.sha(summary_raw),resultBundle=lane+'.xcresult')
        e.need(n[lane]==proof,'Native lane verification mismatch')
    return n,e.sha(raw)

def verify(a):
    app=a.app.resolve();stage_raw=a.stage_receipt.read_bytes()
    staged,effective,x=e.validate_stage(app,a.stage_receipt,a.baseline_checkout)
    toolchain=verify_toolchain(a.toolchain);checks=load_checks(a.baseline_checkout,x)
    e.need(e.git_head(a.case_checkout)==e.CASE,'Frozen case checkout identity changed')
    case_input_raw=(a.case_checkout/'experiments/case-compatible-assets-build23/inputs.json').read_bytes()
    e.need(case_input_raw==(e.ROOT/'case-inputs-reference.json').read_bytes(),'Frozen case recipe inputs changed')
    case_config=json.loads(case_input_raw)
    cadence=a.stage_receipt.parent/'cadence-inputs.json'
    e.need(e.sha(cadence.read_bytes())==staged['cadenceInputsSHA256'],'Cadence input receipt changed')
    cadence_data=json.loads(cadence.read_text())
    e.need(cadence_data['runtimeFiles']==staged['runtimeFiles'] and cadence_data['head']==staged['head'] and cadence_data['runID']==staged['runID'],'Cadence runtime/current-run input mismatch')
    adapter=e.read(e.ROOT/'fps-adapter.json')
    for name,row in adapter['files'].items():
        before=(a.case_checkout/'experiments/case-compatible-assets-build23/fps'/name).read_bytes();after=(e.ROOT/'fps'/name).read_bytes()
        e.need(e.sha(before)==row['before'] and e.sha(after)==row['after'],'FPS adapter source mismatch')
        expected_adapter=before
        if name=='run_fps.py':
            expected_adapter=before.replace(b'browser=pw.chromium.launch(**options)',b"options['ignore_default_args']=['--enable-unsafe-swiftshader','--unsafely-disable-devtools-self-xss-warnings']\n                browser=pw.chromium.launch(**options)").replace(b"'--enable-unsafe-swiftshader')",b"'--enable-unsafe-swiftshader','--unsafely-disable-devtools-self-xss-warnings')")
        e.need(after==expected_adapter,'FPS adapter changed more than safe default removal')
    focused=verify_focused(a.path_evidence,a.fps_evidence,{'baselineInputsSHA256':e.sha(cadence.read_bytes()),'recipeFiles':case_config['recipeFiles']},{'runtimeFiles':staged['runtimeFiles']},a.case_checkout/'experiments/case-compatible-assets-build23')
    native,native_hash=verify_native(a.native_dir,app,staged,stage_raw,x,toolchain,a.toolchain)
    e.need(a.ipa.name==IPA_NAME and a.ipa.is_file() and not a.ipa.is_symlink(),'Wrong/linked IPA')
    ipa_raw=a.ipa.read_bytes();checks.verify_sources(app,effective)
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(a.ipa) as z:
            checks.safe_ipa_members(z.infolist());e.need(z.testzip() is None,'IPA CRC failure');z.extractall(td)
        bundle=Path(td)/'Payload/FlashNest.app';outer=checks.verify_outer_payload(bundle)
        info=plistlib.loads((bundle/'Info.plist').read_bytes())
        expected={'CFBundleIdentifier':'com.flashnest.app','CFBundleShortVersionString':'1.5.6','CFBundleVersion':'23','DTPlatformName':'iphoneos','CFBundleExecutable':'FlashNest','MinimumOSVersion':'17.0','DTSDKName':'iphoneos'+toolchain['deviceSDK']}
        for k,v in expected.items():e.need(info.get(k)==v,'Packaged Info mismatch '+k)
        binary=(bundle/'FlashNest').read_bytes();macho=checks.device_macho(binary,minimum='17.0',sdk=toolchain['deviceSDK'])
        e.need(b'--flashnest-import-size-warning-ui-test' not in binary,'DEBUG warning harness in Release')
        for cls in staged['additionalTestSourceFiles']:e.need(cls.encode() not in binary,'WK test class leaked into Release')
        web=checks.file_map(bundle/'Web');e.need(web==checks.file_map(app/'App/Resources/Web'),'Complete Web package mismatch')
        e.need(checks.file_map(bundle/'Web/runtime')==staged['runtimeFiles'],'Candidate runtime mismatch')
        e.need("type: 'longRunDiagnostics', schema: 2" in (bundle/'Web/long-run-diagnostics.js').read_text(),'Observer schema mismatch')
        diag=(app/'App/Player/LongRunDiagnostics.swift').read_text();e.need('diagnosticSchema: 2, observerRevision: 2' in diag,'Native diagnostic schema mismatch')
        payload=checks.file_map(bundle)
    e.validate_stage(app,a.stage_receipt,a.baseline_checkout)
    e.need(a.stage_receipt.read_bytes()==stage_raw and a.ipa.read_bytes()==ipa_raw,'Inputs changed during verification')
    e.write(a.output,{'schemaVersion':1,'kind':'EXPERIMENTAL-UNLOAD-FIX-TEST-IPA','packageRevision':'unload-fix-diagnostic-v2-import-warning','version':'1.5.6','build':'23','bundleID':'com.flashnest.app','ipaFilename':a.ipa.name,'ipaSHA256':e.sha(ipa_raw),'ipaBytes':len(ipa_raw),'unsigned':True,'ipaBuilt':True,'packagingCommit':os.environ['GITHUB_SHA'],'packagingRunID':os.environ['GITHUB_RUN_ID'],'stageReceiptSHA256':e.sha(stage_raw),'engineReuseSHA256':staged['engineReuseSHA256'],'engineReference':e.read(a.stage_receipt.parent/'engine-reuse.json')['engineReference'],'engineBuildExecutedThisRun':False,'appSourceFiles':effective,'runtimeFiles':staged['runtimeFiles'],'webFiles':web,'packagedBundleFiles':payload,'outerPayloadFiles':sorted(outer),'deviceExecutable':macho,'toolchain':toolchain,'nativeExecutedThisRun':True,'nativeEvidenceReused':False,'nativeVerificationSHA256':native_hash,'nativeEvidence':native,'currentFocusedEvidence':focused,'runtimeChanged':True,'diagnosticSchema':2,'observerRevision':2,'diagnosticOptInDefault':False,'productFrameRateChanged':False,'formalRelease':False,'physicalDeviceCertified':False,'gameLoadingIssueResolved':False,'speedRootCauseEstablished':False,'fullGatePassed':False})
    print('PASS exact candidate runtime, fresh native/UI evidence and unsigned arm64 diagnostic IPA')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['ipa','app','stage-receipt','native-dir','baseline-checkout','case-checkout','toolchain','path-evidence','fps-evidence','output']:p.add_argument('--'+name,type=Path,required=True)
    verify(p.parse_args())
