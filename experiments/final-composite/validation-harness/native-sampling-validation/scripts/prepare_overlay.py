#!/usr/bin/env python3
"""Prepare a DISPOSABLE simulator copy only; never fetch/build/dispatch/package."""
import argparse, copy, hashlib, json, shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
APPROVED_APP_MANIFEST_SHA256 = '15a788b157e88407b7ae11b0e48c8922ed9fd2f05007b78d37a6ca9deb12d062'
APPROVED_CANDIDATE_APP_MANIFEST_SHA256 = '2a9cdfb19440066b1fde2f72cdda89cec6740218ee92d58ed57a89bc5a182efa'
METADATA_ONLY = {'App/Resources/Web/runtime-identity.json', 'App/Resources/Web/Ruffle-MODIFICATIONS.md',
 'App/Resources/Web/Ruffle-THIRD-PARTY-LICENSES.md', 'App/Resources/Web/THIRD_PARTY_NOTICES.md', 'App/Resources/Web/licenses.manifest.json'}
OLD_AUDIO_INVENTORY = '25d4453b0375349e55b9f63f609bd129d6a3549e1da792e811f0e5d121247e90'
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def replace_once(text, before, after):
    assert text.count(before) == 1, 'Source anchor drift: ' + before[:90]
    return text.replace(before, after)

def session_overlay(text):
    assert 'FLASHNEST_NATIVE_SAMPLING_TEST' not in text, 'Already instrumented session'
    text = replace_once(text, '            let controller = WKUserContentController()',
        '            let controller = WKUserContentController()\n#if FLASHNEST_NATIVE_SAMPLING_TEST\n            controller.addUserScript(NativeSamplingProbe.script)\n#endif')
    text = replace_once(text, '            view.load(URLRequest(url: url))',
        '#if FLASHNEST_NATIVE_SAMPLING_TEST\n            view.load(URLRequest(url: NativeSamplingProbe.initialURL(url)))\n#else\n            view.load(URLRequest(url: url))\n#endif')
    for signature, event in [
        ('func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!)', 'provisional'),
        ('func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!)', 'commit'),
        ('func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error)', 'provisional-failure'),
        ('func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error)', 'committed-failure')]:
        anchor = signature + ' {\n        guard self.webView === webView, !processTerminated else { return }'
        text = replace_once(text, anchor, anchor + '\n#if FLASHNEST_NATIVE_SAMPLING_TEST\n        NativeSamplingProbe.record("' + event + '")\n#endif')
    text = replace_once(text, '    private func record(_ message: String) {',
        '    private func record(_ message: String) {\n#if FLASHNEST_NATIVE_SAMPLING_TEST\n        NativeSamplingProbe.recordTrace(message)\n#endif')
    anchor = '    // Status-only binding: never changes navigation policy or suppresses WebKit errors.'
    text = replace_once(text, anchor, '''#if FLASHNEST_NATIVE_SAMPLING_TEST
    func webView(_ webView: WKWebView, didReceiveServerRedirectForProvisionalNavigation navigation: WKNavigation!) {
        guard self.webView === webView, !processTerminated else { return }
        NativeSamplingProbe.record("redirect")
    }
#endif
''' + anchor)
    return text

def server_overlay(text):
    anchor = '            guard parts.first == capability, parts.count >= 3 else { throw LocalHTTPError.forbidden }'
    return replace_once(text, anchor, anchor + '''
#if FLASHNEST_NATIVE_SAMPLING_TEST
            if parts == [capability, "web", "index.html"], let response = NativeSamplingTransport.response(target: parsed.target) {
                connection.send(content: response, completion: .contentProcessed { _ in connection.cancel() })
                return
            }
#endif''')

def shell_overlay(text):
    anchor = "      ...(requestedRenderer ? {preferredRenderer:requestedRenderer} : {}),"
    text = replace_once(text, anchor, "      ...(window.__samplingNativeDiagnosticQuality ? {quality:window.__samplingNativeDiagnosticQuality} : {}), // simulator diagnostic only\n" + anchor)
    # Transparent observation of the REAL load argument, forwarding the same
    # object, receiver, result and exception. No guessed requested-renderer echo.
    return replace_once(text, 'await player.ruffle().load({url:url.href,',
                        'await window.__samplingNativeProbe.observeLoad(player.ruffle(), {url:url.href,')

def resolve_app_manifest(approved, external_path=None, external_sha=None, authority_sha=APPROVED_APP_MANIFEST_SHA256):
    assert bool(external_path) == bool(external_sha), 'Manifest path/hash pair required'
    if not external_path: return approved, authority_sha
    assert sha(external_path) == external_sha, 'External reviewed manifest hash differs'
    rows = json.loads(Path(external_path).read_text())['files']
    assert len({r['path'] for r in rows}) == len(rows), 'Duplicate manifest paths rejected'
    revised = {r['path']: r['sha256'] for r in rows
               if r['path'].startswith('App/') and not r['path'].startswith('App/Resources/Web/runtime/')}
    assert set(revised) == set(approved), 'App file-set changes need separate review'
    assert all(revised[p] == approved[p] for p in approved if p not in METADATA_ONLY), 'Executable/source changes cannot be authorized by metadata repin'
    return revised, external_sha

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', required=True, type=Path, help='Already copied disposable App source root')
    parser.add_argument('--arm', required=True, choices=['baseline', 'candidate'])
    parser.add_argument('--runtime-inventory-sha256', required=True)
    parser.add_argument('--candidate-freeze', type=Path, help='Parent-reviewed release provenance acceptance, mandatory for candidate')
    parser.add_argument('--approved-app-manifest', type=Path, help='Externally reviewed per-arm App manifest; metadata-only changes allowed')
    parser.add_argument('--approved-app-manifest-sha256')
    args = parser.parse_args(); app = args.app.resolve()
    marker = json.loads((app / 'NATIVE_VALIDATION_COPY.json').read_text())
    assert marker.get('disposable') is True and marker.get('sdk') == 'iphonesimulator', 'Explicit disposable simulator copy marker required'
    assert sha(app / 'runtime.files.json') == args.runtime_inventory_sha256
    runtime = json.loads((app / 'runtime.files.json').read_text())
    actual = {str(p.relative_to(app / 'App/Resources/Web/runtime')): sha(p)
              for p in (app / 'App/Resources/Web/runtime').rglob('*') if p.is_file()}
    assert actual == runtime, 'Exact runtime inventory mismatch'
    assert len([name for name in runtime if name.endswith('.wasm')]) == 2, 'Exact regular + MVP release bytes required'
    if args.arm == 'candidate':
        assert args.candidate_freeze, 'No candidate run before parent-reviewed final release source/artifact freeze'
        proof = json.loads(args.candidate_freeze.read_text())
        assert proof.get('frozen') is True and proof.get('releaseEquivalent') is True
        assert proof.get('runtimeInventorySHA256') == args.runtime_inventory_sha256
        assert args.runtime_inventory_sha256 != OLD_AUDIO_INVENTORY, 'Old audio-only runtime is ineligible'
    else:
        assert args.runtime_inventory_sha256 == OLD_AUDIO_INVENTORY, 'Baseline must be the approved delivered155 audio runtime'
    authority_sha = APPROVED_CANDIDATE_APP_MANIFEST_SHA256 if args.arm == 'candidate' else APPROVED_APP_MANIFEST_SHA256
    approved_path = ROOT / ('approved-candidate-app-source-manifest.json' if args.arm == 'candidate' else 'approved-app-source-manifest.json')
    assert sha(approved_path) == authority_sha, 'Approved App manifest changed without reviewed freeze'
    approved = {row['path']: row['sha256'] for row in json.loads(approved_path.read_text())['files']
                if row['path'].startswith('App/') and not row['path'].startswith('App/Resources/Web/runtime/')}
    approved, effective_app_manifest_sha = resolve_app_manifest(approved, args.approved_app_manifest, args.approved_app_manifest_sha256, authority_sha)
    actual_app = {str(p.relative_to(app)): sha(p) for p in (app / 'App').rglob('*')
                  if p.is_file() and not str(p.relative_to(app)).startswith('App/Resources/Web/runtime/')}
    assert actual_app == approved, 'Gate-off App/shell/status/navigation source differs from approved source map'
    if args.arm == 'candidate':
        assert proof.get('approvedAppManifestSHA256') == effective_app_manifest_sha
    target = app / 'NativeSamplingValidation'
    assert not target.exists(), 'No implicit overwrite or repeat apply'
    before = {str(p.relative_to(app)): sha(p) for p in (app / 'App').rglob('*') if p.is_file()}
    for name in ['Host', 'UITests']:
        shutil.copytree(ROOT / name, target / name)
    shutil.copytree(ROOT / 'fixtures', target / 'SamplingFixtures')
    session = app / 'App/Player/PlayerSession.swift'; session.write_text(session_overlay(session.read_text()))
    server = app / 'App/Server/LoopbackServer.swift'; server.write_text(server_overlay(server.read_text()))
    shell = app / 'App/Resources/Web/shell.js'; shell.write_text(shell_overlay(shell.read_text()))
    settings = app / 'App/Player/RenderSamplingSettings.swift'
    assert 'static let runtimeValidated = false' in settings.read_text(), 'Start from exact gate-off source'
    if args.arm == 'candidate':
        settings.write_text(replace_once(settings.read_text(), 'static let runtimeValidated = false', 'static let runtimeValidated = true'))
    after = {str(p.relative_to(app)): sha(p) for p in (app / 'App').rglob('*') if p.is_file()}
    changed = sorted(k for k in before if before[k] != after[k])
    assert changed == sorted(['App/Player/PlayerSession.swift', 'App/Server/LoopbackServer.swift', 'App/Resources/Web/shell.js'] +
                             (['App/Player/RenderSamplingSettings.swift'] if args.arm == 'candidate' else []))
    identity = {'schema': 1, 'arm': args.arm, 'runtimeInventorySHA256': args.runtime_inventory_sha256,
        'runtimeFiles': runtime, 'gateOffAppFiles': before, 'changedAppFiles': {k: {'before': before[k], 'after': after[k]} for k in changed},
        'observerSHA256': sha(target / 'Host/sampling-probe.js'), 'simulatorOnly': True,
        'rendererPolicyContract': 'candidate-three-mode-v1' if args.arm == 'candidate' else 'legacy-original-policy-v1',
        'shippingDefaultQualityOmitted': True, 'approvedAppManifestSHA256': effective_app_manifest_sha, 'authoredNotExecuted': True}
    # Compact runtime/source identities in all phase attachments; full map kept in staging provenance.
    (target / 'staging-provenance.json').write_text(json.dumps(identity, indent=2) + '\n')
    compact = {k: v for k, v in identity.items() if k not in ['gateOffAppFiles', 'changedAppFiles']}
    compact['stagingProvenanceSHA256'] = sha(target / 'staging-provenance.json')
    (target / 'SamplingIdentity.json').write_text(json.dumps(compact, sort_keys=True) + '\n')
    project = yaml.safe_load((app / 'project.yml').read_text())
    host = copy.deepcopy(project['targets']['FlashNest'])
    host['sources'][0]['excludes'].append('FlashNestApp.swift')
    host['sources'] += [
        {'path': 'NativeSamplingValidation/Host', 'excludes': ['*.js']},
        {'path': 'NativeSamplingValidation/Host/sampling-probe.js', 'buildPhase': 'resources'},
        {'path': 'NativeSamplingValidation/SamplingFixtures', 'type': 'folder', 'buildPhase': 'resources'},
        {'path': 'NativeSamplingValidation/SamplingIdentity.json', 'buildPhase': 'resources'}]
    host['info']['path'] = 'NativeSamplingValidation/Host/Info.plist'
    host['info']['properties']['CFBundleDisplayName'] = 'Sampling Validation'
    host['settings'].pop('configs', None)
    host['settings']['base'].update({'PRODUCT_BUNDLE_IDENTIFIER': 'com.flashnest.validation.sampling',
        'SUPPORTED_PLATFORMS': 'iphonesimulator', 'SUPPORTS_MACCATALYST': False,
        'SWIFT_ACTIVE_COMPILATION_CONDITIONS': '$(inherited) FLASHNEST_NATIVE_SAMPLING_TEST',
        'INFOPLIST_FILE': 'NativeSamplingValidation/Host/Info.plist'})
    project['targets']['FlashNestSamplingHost'] = host
    project['targets']['FlashNestSamplingUITests'] = {'type': 'bundle.ui-testing', 'platform': 'iOS',
        'sources': ['NativeSamplingValidation/UITests', {'path': 'NativeSamplingValidation/SamplingIdentity.json', 'buildPhase': 'resources'}],
        'settings': {'base': {'PRODUCT_BUNDLE_IDENTIFIER': 'com.flashnest.validation.sampling.uitests', 'GENERATE_INFOPLIST_FILE': True,
            'TEST_TARGET_NAME': 'FlashNestSamplingHost', 'SUPPORTED_PLATFORMS': 'iphonesimulator'}},
        'dependencies': [{'target': 'FlashNestSamplingHost'}]}
    project['schemes']['FlashNestSamplingUI'] = {
        'build': {'targets': {'FlashNestSamplingHost': 'all', 'FlashNestSamplingUITests': ['test']}},
        'test': {'targets': ['FlashNestSamplingUITests'], 'parallelizable': False}}
    (app / 'project.yml').write_text(yaml.safe_dump(project, sort_keys=False))
    print(json.dumps({'prepared': True, 'executed': False, 'arm': args.arm, 'changedAppFiles': changed,
                      'runtimeInventorySHA256': args.runtime_inventory_sha256, 'scheme': 'FlashNestSamplingUI'}))

if __name__ == '__main__': main()
