#!/usr/bin/env python3
"""Actual selected-runtime native regression; no prior native evidence reuse."""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import stage as e
from select_toolchain import verify as verify_toolchain

HTTP_TEST_SOURCE = 'Tests/HTTPServerTests.swift'
HTTP_TEST_SHA256 = 'cca67f9bbd0b214f4ebeb1b6d36e07d3aa1cd5216b9cab1ab1f973d1508990e5'
COUNTS = ('totalTestCount', 'passedTests', 'failedTests', 'skippedTests', 'expectedFailures')

def verify_summary(summary, log, expected, device, bundle, os_version):
    e.need(summary.get('result') == 'Passed', 'Test summary not passed')
    expected_counts = dict(zip(COUNTS, (len(expected), len(expected), 0, 0, 0)))
    for key, value in expected_counts.items():
        e.need(type(summary.get(key)) is int and summary[key] == value, 'Unexpected test count: ' + key)
    actual = re.findall(r"Test Case '-\[([A-Za-z0-9_]+)\.([A-Za-z0-9_]+) ([A-Za-z0-9_]+)\]' passed", log)
    expected_ids = [(bundle, cls, method) for cls, method in expected]
    e.need(len(actual) == len(expected_ids) and len(actual) == len(set(actual)) and set(actual) == set(expected_ids),
           'Missing, extra, duplicate, or wrong-bundle test methods')
    devices = summary.get('devicesAndConfigurations', [])
    e.need(len(devices) == 1 and devices[0].get('device', {}).get('osVersion') == os_version
           and devices[0].get('device', {}).get('deviceId') == device, 'Wrong actual simulator/runtime')
    return {'expected': [list(row) for row in expected_ids], 'actual': [list(row) for row in actual],
            'counts': expected_counts, 'deviceID': device, 'osVersion': os_version}

def run_ui_lane(app,out,x,staged,device,release,helper,os_version):
 mapping={'testClasses':x['uiTestClasses'],'testSourceFiles':x['uiTestSourceFiles']}
 expected=helper.expected_test_methods(app,mapping,directory='UITests')
 e.need(expected and expected==[tuple(i) for i in x['expectedUITests']],'UI inventory differs')
 release.c.verify_sources(app,staged['diagnosticSourceFiles'])
 fixture=helper.install_fixture_source(app,out,device)
 result=out/'ui.xcresult'
 args=['xcodebuild','test','-project','FlashNest.xcodeproj','-scheme','FlashNestUI','-configuration','Debug','-sdk','iphonesimulator','-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(out/'build'),'-resultBundlePath',str(result),'-disableAutomaticPackageResolution','-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1','-test-timeouts-enabled','YES','-default-test-execution-time-allowance','420','-maximum-test-execution-time-allowance','420']
 args += ['-only-testing:FlashNestUITests/'+cls+'/'+method for cls,method in expected]+['CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
 with (out/'ui.log').open('w') as log:r=subprocess.run(args,cwd=app,stdout=log,stderr=subprocess.STDOUT,timeout=1500)
 raw=subprocess.check_output(['xcrun','xcresulttool','get','test-results','summary','--path',str(result)],timeout=60);(out/'ui-summary.json').write_bytes(raw)
 summary=json.loads(raw);e.need(r.returncode==0 and summary.get('result')=='Passed','UI confirmation tests failed')
 for k,v in {'totalTestCount':len(expected),'passedTests':len(expected),'failedTests':0,'skippedTests':0,'expectedFailures':0}.items():e.need(type(summary.get(k)) is int and summary[k]==v,'Unexpected UI count '+k)
 log=(out/'ui.log').read_text();actual=re.findall(r"Test Case '-\[([A-Za-z0-9_]+)\.([A-Za-z0-9_]+) ([A-Za-z0-9_]+)\]' passed",log)
 e.need(len(actual)==len(expected) and set(actual)=={('FlashNestUITests',cls,m) for cls,m in expected},'Unexpected/missing UI methods or bundle')
 ds=summary.get('devicesAndConfigurations',[]);e.need(len(ds)==1 and ds[0].get('device',{}).get('osVersion')==os_version and ds[0].get('device',{}).get('deviceId')==device,'Wrong UI simulator')
 release.c.verify_sources(app,staged['diagnosticSourceFiles'])
 e.write(out/'ui-verification.json',{'importConfirmationUIPassed':True,'scope':'Actual Files cross-container synthetic-fixture import and production confirmation UI with DEBUG warning threshold; not real large-file or all-provider acceptance','expected':[list(i) for i in expected],'counts':{k:summary[k] for k in ['totalTestCount','passedTests','failedTests','skippedTests','expectedFailures']},'sourceFiles':staged['diagnosticSourceFiles'],'deviceID':device,'fixtureSourceInstalled':fixture,'fullGatePassed':False,'physicalDeviceCertified':False,'runID':os.environ.get('GITHUB_RUN_ID'),'head':os.environ.get('GITHUB_SHA')})

def run(app, output, baseline, stage_receipt, toolchain_path):
    app = app.resolve(); output = output.resolve(); baseline = baseline.resolve(); stage_receipt = stage_receipt.resolve()
    toolchain=verify_toolchain(toolchain_path)
    toolchain_raw=toolchain_path.read_bytes()
    receipt_bytes=stage_receipt.read_bytes()
    staged,effective,baseline_inputs=e.validate_stage(app,stage_receipt,baseline)
    baseline_recipe=baseline/e.RECIPE
    def verify_identity():
        e.need(toolchain_path.read_bytes()==toolchain_raw,'Toolchain receipt changed')
        e.need(stage_receipt.read_bytes() == receipt_bytes, 'Immutable staging receipt changed')
        e.verify(app, effective)
        e.need(e.inventory(app / 'App/Resources/Web/runtime') == staged['runtimeFiles'], 'Runtime bytes changed')
    verify_identity()
    # Import unchanged, baseline-hash-verified helper implementation. Its config
    # and recipe are never modified to make the experimental overlay look baseline.
    for path, digest in baseline_inputs['recipeFiles'].items():
        e.need(e.sha((baseline_recipe / path).read_bytes()) == digest, 'Baseline helper recipe differs: ' + path)
    sys.path.insert(0, str(baseline_recipe))
    spec = importlib.util.spec_from_file_location('casecompat_baseline_runner', baseline_recipe / 'run_focused_tests.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    package = helper.p
    baseline_config = package.config()
    release, _, _, _ = package.load_release(baseline, baseline_config)
    expected = helper.expected_test_methods(app, baseline_config)
    e.need(expected == [tuple(row) for row in baseline_config['expectedNativeTests']] and len(expected) == 70,
           'Original selected native methods differ')
    e.need(effective[HTTP_TEST_SOURCE] == HTTP_TEST_SHA256 and e.sha((app / HTTP_TEST_SOURCE).read_bytes()) == HTTP_TEST_SHA256,
           'HTTP test source differs from reviewed baseline')
    http_methods = helper.swift_test_classes((app / HTTP_TEST_SOURCE).read_text()).get('HTTPServerTests', [])
    e.need(len(http_methods) == 6 and len(set(http_methods)) == 6, 'HTTP test inventory differs')
    expected += [('HTTPServerTests', method) for method in http_methods]
    e.need(len(expected) == 76 and len(set(expected)) == 76, 'Duplicate or missing selected native tests')
    ui_expected = helper.expected_test_methods(app, {'testClasses': baseline_config['uiTestClasses'],
        'testSourceFiles': baseline_config['uiTestSourceFiles']}, directory='UITests')
    e.need(ui_expected == [tuple(row) for row in baseline_config['expectedUITests']] and len(ui_expected) == 2,
           'Original UI inventory differs')
    ui_extra=[tuple(v) for v in staged['additionalUITests']]
    ui_mapping=staged['additionalUITestSourceFiles']
    ui_actual_extra=helper.expected_test_methods(app,{'testClasses':list(dict.fromkeys(cls for cls,method in ui_extra)),'testSourceFiles':ui_mapping},directory='UITests')
    e.need(ui_actual_extra==ui_extra and ui_extra,'Additional UI source/method inventory differs')
    ui_expected += ui_extra
    e.need(len(ui_expected)==len(set(ui_expected)),'Duplicate UI methods')
    ui_config=dict(baseline_config)
    ui_config['uiTestClasses']=baseline_config['uiTestClasses']+list(ui_mapping)
    ui_config['uiTestSourceFiles']={**baseline_config['uiTestSourceFiles'],**ui_mapping}
    ui_config['expectedUITests']=[list(v) for v in ui_expected]
    additional=[tuple(v) for v in staged['additionalNativeTests']]
    mapping=staged['additionalTestSourceFiles']
    actual_extra=helper.expected_test_methods(app,{'testClasses':list(dict.fromkeys(cls for cls,method in additional)),'testSourceFiles':mapping})
    e.need(additional and actual_extra==additional and len(set(additional))==len(additional),'Additional WK test inventory differs')
    expected += additional
    e.need(len(set(expected))==len(expected),'Additional tests overlap baseline')
    output.mkdir(parents=True, exist_ok=False)
    device = None
    completed = None
    try:
        device = subprocess.check_output(['xcrun', 'simctl', 'create', 'FlashNestMouseTouch160',
            toolchain['deviceTypeID'], toolchain['runtimeID']], text=True, timeout=60).strip()
        e.need(re.fullmatch(r'[0-9A-Fa-f-]{36}', device) is not None, 'Invalid simulator ID')
        subprocess.run(['xcrun', 'simctl', 'boot', device], check=True, timeout=60)
        subprocess.run(['xcrun', 'simctl', 'bootstatus', device, '-b'], check=True, timeout=180)
        verify_identity()
        result = output / 'native.xcresult'
        args = ['xcodebuild', 'test', '-project', 'FlashNest.xcodeproj', '-scheme', 'FlashNest',
            '-configuration', 'Debug', '-sdk', 'iphonesimulator', '-destination', 'platform=iOS Simulator,id=' + device,
            '-derivedDataPath', str(output / 'build'), '-resultBundlePath', str(result),
            '-disableAutomaticPackageResolution', '-parallel-testing-enabled', 'NO',
            '-maximum-concurrent-test-simulator-destinations', '1', '-test-timeouts-enabled', 'YES',
            '-default-test-execution-time-allowance', '180', '-maximum-test-execution-time-allowance', '180']
        args += ['-only-testing:FlashNestTests/' + cls + '/' + method for cls, method in expected]
        args += ['CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO']
        with (output / 'native.log').open('w') as log:
            process = subprocess.run(args, cwd=app, stdout=log, stderr=subprocess.STDOUT, timeout=2100)
        raw = subprocess.check_output(['xcrun', 'xcresulttool', 'get', 'test-results', 'summary', '--path', str(result)], timeout=60)
        (output / 'native-summary.json').write_bytes(raw)
        e.need(process.returncode == 0, 'Selected native tests failed')
        native = verify_summary(json.loads(raw), (output / 'native.log').read_text(), expected, device, 'FlashNestTests', toolchain['runtimeVersion'])
        native.update(summarySHA256=e.sha(raw), resultBundle='native.xcresult')
        verify_identity()
        run_ui_lane(app, output, ui_config, {'diagnosticSourceFiles': effective}, device, release, helper, toolchain['runtimeVersion'])
        ui_raw = (output / 'ui-summary.json').read_bytes()
        ui = verify_summary(json.loads(ui_raw), (output / 'ui.log').read_text(), ui_expected, device, 'FlashNestUITests', toolchain['runtimeVersion'])
        ui.update(summarySHA256=e.sha(ui_raw), resultBundle='ui.xcresult')
        ui_receipt = e.read(output / 'ui-verification.json')
        e.need(ui_receipt['sourceFiles'] == effective and ui_receipt['deviceID'] == device,
               'UI verification identity differs')
        verify_identity()
        completed = {'schema': 'flashnest-mouse-ios-selected-v1', 'nativeExecutedThisRun': True, 'nativeEvidenceReused':False, 'baselineNativeCount':76, 'additionalNativeTests':[list(v) for v in additional], 'toolchain':toolchain, 'toolchainReceiptSHA256':e.sha(toolchain_raw), 'runnerSHA256':e.sha(Path(__file__).read_bytes()), 'selectedNativeTestsPassed': True,
            'native': native, 'ui': ui, 'effectiveSourceFiles': effective,
            'stageReceiptSHA256': e.sha(receipt_bytes), 'runtimeFiles': staged['runtimeFiles'],
            'baselineCommit': e.BASE, 'head': os.environ.get('GITHUB_SHA'), 'runID': os.environ.get('GITHUB_RUN_ID'),
            'scope': '76 inherited native methods plus declared mouse/touch/focus candidate tests and 2 import plus1draggable-menu UI methods on the selected actual iOS simulator; not physical-device acceptance',
            'fullGatePassed': False, 'physicalDeviceCertified': False, 'speedRootCauseEstablished': False, 'ipaBuilt': False}
    finally:
        try:
            verify_identity()
        finally:
            if device:
                shutdown_code = None
                try:
                    shutdown_code = subprocess.run(['xcrun', 'simctl', 'shutdown', device], timeout=60, check=False).returncode
                finally:
                    deleted = subprocess.run(['xcrun', 'simctl', 'delete', device], timeout=60, check=False)
                    e.write(output / 'simulator-cleanup.json', {'deviceID': device, 'shutdownReturnCode': shutdown_code,
                        'deleteReturnCode': deleted.returncode})
                    e.need(deleted.returncode == 0, 'Failed to delete dedicated simulator')
    e.need(completed is not None, 'Test execution incomplete')
    e.write(output / 'verification.json', completed)
    print('Verified inherited76 +',len(additional),'mouse/focus/unload native methods and',len(ui_expected),'UI methods; no skips, no physical-device claim')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-checkout', type=Path, required=True)
    parser.add_argument('--stage-receipt', type=Path, required=True)
    parser.add_argument('--toolchain',type=Path,required=True)
    args = parser.parse_args()
    run(args.app, args.output, args.baseline_checkout, args.stage_receipt,args.toolchain)
