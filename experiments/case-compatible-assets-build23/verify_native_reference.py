#!/usr/bin/env python3
"""Reuse pinned native evidence only for identical product/test/runner bytes."""
import argparse, importlib.util, json, os, stat, subprocess, sys, zipfile
from pathlib import Path
import experiment as e
import run_ios_tests as native
PIN = {'runID': '41309016865', 'head': '11c3fb4ad9cca3a3673ded55cd5ffd0df9271188',
       'artifactID': 13085011484, 'bytes': 119270,
       'sha256': 'f8879550f57bbec7b15f6d1190ca19081cada08c81faca2a4e00cef70d18cc66'}
MEMBERS = {'evidence/fps-result.json', 'case-staging.json', 'evidence/hdiutil-create-help.txt',
 'evidence/hdiutil-create.log', 'evidence/ios/fixture-source-build.log',
 'evidence/ios/native-summary.json', 'evidence/ios/native.log', 'evidence/ios/simulator-cleanup.json',
 'evidence/ios/ui-summary.json', 'evidence/ios/ui-verification.json', 'evidence/ios/ui.log',
 'evidence/ios/verification.json'}

def read_archive(path):
    raw = path.read_bytes()
    e.need(len(raw) == PIN['bytes'] and e.sha(raw) == PIN['sha256'], 'Native reference archive identity differs')
    with zipfile.ZipFile(path) as z:
        rows = z.infolist(); names = [row.filename for row in rows]
        e.need(len(names) == len(set(names)) and set(names) == MEMBERS, 'Unexpected or duplicate artifact payload')
        e.need(sum(row.file_size for row in rows) <= 16 * 1024 * 1024, 'Oversized artifact payload')
        for row in rows:
            p = Path(row.filename)
            e.need(not p.is_absolute() and '..' not in p.parts and '\\' not in row.filename
                   and ':' not in row.filename and not row.is_dir(), 'Unsafe artifact path')
            e.need(stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG), 'Nonregular artifact member')
            e.need(row.file_size <= 8 * 1024 * 1024, 'Oversized artifact member')
        e.need(z.testzip() is None, 'Artifact CRC failure')
        return {name: z.read(name) for name in names}

def verify(archive, app, stage_receipt, baseline, output):
    app = app.resolve(); baseline = baseline.resolve()
    config = e.config()
    e.need(config.get('nativeReference') == PIN, 'Native reference config pin differs')
    stage_raw = stage_receipt.read_bytes(); stage = json.loads(stage_raw)
    payload = read_archive(archive)
    prior_stage_raw = payload['case-staging.json']; prior_stage = json.loads(prior_stage_raw)
    prior = json.loads(payload['evidence/ios/verification.json'])
    ui_proof = json.loads(payload['evidence/ios/ui-verification.json'])
    for receipt in (prior_stage, prior, ui_proof):
        e.need(receipt.get('head') == PIN['head'] and receipt.get('runID') == PIN['runID'], 'Wrong prior execution identity')
    e.need(bool(os.environ.get('GITHUB_SHA')) and bool(os.environ.get('GITHUB_RUN_ID')), 'Current run identity missing')
    e.need(stage.get('head') == os.environ['GITHUB_SHA'] and stage.get('runID') == os.environ['GITHUB_RUN_ID'],
           'Current stage run identity differs')
    e.need(stage.get('recipeFiles') == config['recipeFiles'] and stage.get('overlay') == config['overlay'], 'Current recipe differs')
    e.need(subprocess.check_output(['git', '-C', str(baseline), 'rev-parse', 'HEAD'], text=True).strip() == e.BASE,
           'Wrong baseline checkout')
    base_recipe = baseline / e.RECIPE; input_raw = (base_recipe / 'inputs.json').read_bytes()
    e.need(e.sha(input_raw) == config['baselineInputsSHA256'], 'Baseline inputs differ')
    x = json.loads(input_raw)
    original = dict(x['baselineAppFiles']); original.update({p: r['after'] for p, r in x['overlay'].items()})
    effective = dict(original)
    for p, row in config['overlay'].items():
        e.need(effective[p] == row['before'], 'Unexpected original source')
        effective[p] = row['after']
    e.need(len(x['runtimeFiles']) == 12, 'Incomplete runtime inventory')
    for receipt in (stage, prior_stage):
        e.need(receipt.get('baselineCommit') == e.BASE and receipt.get('sourceCommit') == e.SOURCE, 'Wrong source lineage')
        e.need(receipt.get('baselineSourceFiles') == original and receipt.get('effectiveSourceFiles') == effective,
               'Source changed since reference execution')
        e.need(receipt.get('overlay') == config['overlay'] and receipt.get('runtimeFiles') == x['runtimeFiles'], 'Product/runtime changed')
        for key in ('diagnosticOptInDefault', 'runtimeChanged', 'ipaBuilt', 'fullGatePassed', 'physicalDeviceCertified', 'speedRootCauseEstablished'):
            e.need(receipt.get(key) is False, 'Unexpected stage acceptance/default flag')
    runner_sha = e.sha((e.ROOT / 'run_ios_tests.py').read_bytes())
    e.need(prior_stage['recipeFiles'].get('run_ios_tests.py') == runner_sha
           and config['recipeFiles'].get('run_ios_tests.py') == runner_sha, 'Native runner changed')
    e.verify(app, effective)
    e.need(e.inventory(app / 'App/Resources/Web/runtime') == x['runtimeFiles'], 'Actual runtime differs')
    for p, digest in x['recipeFiles'].items():
        e.need(e.sha((base_recipe / p).read_bytes()) == digest, 'Baseline helper differs')
    sys.path.insert(0, str(base_recipe))
    spec = importlib.util.spec_from_file_location('casecompat_reference_helper', base_recipe / 'run_focused_tests.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    expected = helper.expected_test_methods(app, x)
    e.need(expected == [tuple(row) for row in x['expectedNativeTests']] and len(expected) == 70, 'Native baseline tests differ')
    e.need(effective[native.HTTP_TEST_SOURCE] == native.HTTP_TEST_SHA256, 'HTTP test source differs')
    methods = helper.swift_test_classes((app / native.HTTP_TEST_SOURCE).read_text()).get('HTTPServerTests', [])
    e.need(len(methods) == 6 and len(set(methods)) == 6, 'HTTP inventory differs')
    expected += [('HTTPServerTests', method) for method in methods]
    ui_expected = helper.expected_test_methods(app, {'testClasses': x['uiTestClasses'], 'testSourceFiles': x['uiTestSourceFiles']}, directory='UITests')
    e.need(ui_expected == [tuple(row) for row in x['expectedUITests']] and len(ui_expected) == 2, 'UI baseline tests differ')
    e.need(prior.get('schema') == 'flashnest-casecompat-ios-selected-v1' and prior.get('selectedNativeTestsPassed') is True,
           'Reference native execution not passed')
    e.need(prior.get('baselineCommit') == e.BASE and prior.get('stageReceiptSHA256') == e.sha(prior_stage_raw)
           and prior.get('effectiveSourceFiles') == effective and prior.get('runtimeFiles') == x['runtimeFiles'], 'Reference proof identity differs')
    for key in ('ipaBuilt', 'fullGatePassed', 'physicalDeviceCertified', 'speedRootCauseEstablished'):
        e.need(prior.get(key) is False, 'Unexpected prior native acceptance')
    device = prior['native']['deviceID']; verified = {}
    for lane, tests, bundle in [('native', expected, 'FlashNestTests'), ('ui', ui_expected, 'FlashNestUITests')]:
        raw = payload['evidence/ios/' + lane + '-summary.json']
        proof = native.verify_summary(json.loads(raw), payload['evidence/ios/' + lane + '.log'].decode(), tests, device, bundle)
        proof.update(summarySHA256=e.sha(raw), resultBundle=lane + '.xcresult')
        e.need(proof == prior[lane], 'Reference summary/log/receipt mismatch: ' + lane)
        verified[lane] = proof
    e.need(ui_proof.get('importConfirmationUIPassed') is True and ui_proof.get('sourceFiles') == effective
           and ui_proof.get('deviceID') == device and ui_proof.get('counts') == verified['ui']['counts'], 'UI proof differs')
    fixture = ui_proof.get('fixtureSourceInstalled', {})
    e.need(fixture.get('bundleID') == 'com.flashnest.fixture-source' and fixture.get('installedOnTestDevice') is True,
           'Cross-container fixture not installed')
    cleanup = json.loads(payload['evidence/ios/simulator-cleanup.json'])
    e.need(cleanup.get('deviceID') == device and cleanup.get('deleteReturnCode') == 0, 'Reference simulator cleanup incomplete')
    e.verify(app, effective); e.need(stage_receipt.read_bytes() == stage_raw, 'Current stage receipt changed')
    result = {'schema': 'flashnest-native-reference-reuse-v1', 'nativeEvidenceVerified': True,
        'nativeExecutedThisRun': False, 'reusedFromRun': PIN['runID'], 'reference': PIN,
        'nativeRunnerSHA256': runner_sha, 'currentStageReceiptSHA256': e.sha(stage_raw),
        'originalStageReceiptSHA256': e.sha(prior_stage_raw), 'effectiveSourceFiles': effective,
        'testSourceFiles': {p:h for p,h in effective.items() if p.startswith(('Tests/', 'UITests/'))},
        'runtimeFiles': x['runtimeFiles'], 'native': verified['native'], 'ui': verified['ui'],
        'head': os.environ['GITHUB_SHA'], 'runID': os.environ['GITHUB_RUN_ID'],
        'scope': 'Pinned prior 76 native + 2 UI executions, identical product/test/runner; not new native execution or case-sensitive fixture acceptance',
        'fullGatePassed': False, 'physicalDeviceCertified': False, 'speedRootCauseEstablished': False, 'ipaBuilt': False}
    e.write(output, result)
    print('Verified pinned prior 76 native + 2 UI evidence; no new native execution')

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('archive', 'app', 'stage-receipt', 'baseline-checkout', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); verify(a.archive, a.app, a.stage_receipt, a.baseline_checkout, a.output)
