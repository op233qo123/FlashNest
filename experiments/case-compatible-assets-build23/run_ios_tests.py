#!/usr/bin/env python3
"""Actual iOS 18.2 selected regression; no IPA and no simulated case-sensitive claim."""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
import experiment as e

HTTP_TEST_SOURCE = 'Tests/HTTPServerTests.swift'
HTTP_TEST_SHA256 = 'cca67f9bbd0b214f4ebeb1b6d36e07d3aa1cd5216b9cab1ab1f973d1508990e5'
COUNTS = ('totalTestCount', 'passedTests', 'failedTests', 'skippedTests', 'expectedFailures')

def verify_summary(summary, log, expected, device, bundle):
    e.need(summary.get('result') == 'Passed', 'Test summary not passed')
    expected_counts = dict(zip(COUNTS, (len(expected), len(expected), 0, 0, 0)))
    for key, value in expected_counts.items():
        e.need(type(summary.get(key)) is int and summary[key] == value, 'Unexpected test count: ' + key)
    actual = re.findall(r"Test Case '-\[([A-Za-z0-9_]+)\.([A-Za-z0-9_]+) ([A-Za-z0-9_]+)\]' passed", log)
    expected_ids = [(bundle, cls, method) for cls, method in expected]
    e.need(len(actual) == len(expected_ids) and len(actual) == len(set(actual)) and set(actual) == set(expected_ids),
           'Missing, extra, duplicate, or wrong-bundle test methods')
    devices = summary.get('devicesAndConfigurations', [])
    e.need(len(devices) == 1 and devices[0].get('device', {}).get('osVersion') == '18.2'
           and devices[0].get('device', {}).get('deviceId') == device, 'Wrong actual simulator/runtime')
    return {'expected': [list(row) for row in expected_ids], 'actual': [list(row) for row in actual],
            'counts': expected_counts, 'deviceID': device, 'osVersion': '18.2'}

def run(app, output, baseline, stage_receipt):
    app = app.resolve(); output = output.resolve(); baseline = baseline.resolve(); stage_receipt = stage_receipt.resolve()
    config = e.config()
    e.need(subprocess.check_output(['git', '-C', str(baseline), 'rev-parse', 'HEAD'], text=True).strip() == e.BASE,
           'Wrong baseline checkout')
    receipt_bytes = stage_receipt.read_bytes(); staged = json.loads(receipt_bytes)
    e.need(staged.get('baselineCommit') == e.BASE and staged.get('sourceCommit') == e.SOURCE,
           'Wrong staging source identity')
    e.need(staged.get('overlay') == config['overlay'] and staged.get('recipeFiles') == config['recipeFiles'],
           'Staging recipe/overlay differs')
    for flag in ('runtimeChanged', 'ipaBuilt', 'fullGatePassed', 'physicalDeviceCertified', 'speedRootCauseEstablished'):
        e.need(staged.get(flag) is False, 'Unexpected stage acceptance flag: ' + flag)
    e.need(staged.get('diagnosticOptInDefault') is False, 'Diagnostic default changed')
    e.need(staged.get('head') == os.environ.get('GITHUB_SHA') and staged.get('runID') == os.environ.get('GITHUB_RUN_ID'),
           'Staging run identity differs')
    baseline_recipe = baseline / e.RECIPE
    input_bytes = (baseline_recipe / 'inputs.json').read_bytes()
    e.need(e.sha(input_bytes) == config['baselineInputsSHA256'], 'Baseline inputs differ')
    baseline_inputs = json.loads(input_bytes)
    effective = dict(baseline_inputs['baselineAppFiles'])
    effective.update({path: row['after'] for path, row in baseline_inputs['overlay'].items()})
    e.need(staged['baselineSourceFiles'] == effective, 'Baseline source inventory differs')
    for path, row in config['overlay'].items():
        e.need(effective[path] == row['before'], 'Unexpected original overlay source')
        effective[path] = row['after']
    e.need(staged['effectiveSourceFiles'] == effective, 'Candidate inventory differs')
    e.need(staged['runtimeFiles'] == baseline_inputs['runtimeFiles'] and len(staged['runtimeFiles']) == 12,
           'Runtime inventory changed')
    def verify_identity():
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
    output.mkdir(parents=True, exist_ok=False)
    device = None
    completed = None
    try:
        device = subprocess.check_output(['xcrun', 'simctl', 'create', 'FlashNestCaseCompatibility',
            'com.apple.CoreSimulator.SimDeviceType.iPhone-SE-3rd-generation',
            'com.apple.CoreSimulator.SimRuntime.iOS-18-2'], text=True, timeout=60).strip()
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
        native = verify_summary(json.loads(raw), (output / 'native.log').read_text(), expected, device, 'FlashNestTests')
        native.update(summarySHA256=e.sha(raw), resultBundle='native.xcresult')
        verify_identity()
        helper.run_ui_lane(app, output, baseline_config, {'diagnosticSourceFiles': effective}, device, release)
        ui_raw = (output / 'ui-summary.json').read_bytes()
        ui = verify_summary(json.loads(ui_raw), (output / 'ui.log').read_text(), ui_expected, device, 'FlashNestUITests')
        ui.update(summarySHA256=e.sha(ui_raw), resultBundle='ui.xcresult')
        ui_receipt = e.read(output / 'ui-verification.json')
        e.need(ui_receipt['sourceFiles'] == effective and ui_receipt['deviceID'] == device,
               'UI verification identity differs')
        verify_identity()
        completed = {'schema': 'flashnest-casecompat-ios-selected-v1', 'selectedNativeTestsPassed': True,
            'native': native, 'ui': ui, 'effectiveSourceFiles': effective,
            'stageReceiptSHA256': e.sha(receipt_bytes), 'runtimeFiles': staged['runtimeFiles'],
            'baselineCommit': e.BASE, 'head': os.environ.get('GITHUB_SHA'), 'runID': os.environ.get('GITHUB_RUN_ID'),
            'scope': '76 original selected/native HTTP methods and 2 original import UI methods on iOS 18.2; case-fold fixture evidence is separate host APFSX verification',
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
    print('Verified 76 selected native and 2 UI methods; no skips, no IPA, no physical-device claim')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-checkout', type=Path, required=True)
    parser.add_argument('--stage-receipt', type=Path, required=True)
    args = parser.parse_args()
    run(args.app, args.output, args.baseline_checkout, args.stage_receipt)
