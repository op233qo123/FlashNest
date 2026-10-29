#!/usr/bin/env python3
"""Rebind the reviewed late-audio harness; source-only, never builds or dispatches.

`plan` checks current App/diagnostics and emits only a small overlay manifest.
`stage` is for the final CI workspace: a NEW isolated target with explicitly
hash-pinned final candidate or historical baseline runtime, never shipping App.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parents[1]
LOCK = json.loads((HERE / 'input-lock.json').read_text())
CANDIDATE_LOCK_SHA256 = '90ac374cd76accf9c9904ebf771beb4d256ef4f30f7d54706439d350da73da81'
assert hashlib.sha256((HERE / 'candidate-input-lock.json').read_bytes()).hexdigest() == CANDIDATE_LOCK_SHA256
CANDIDATE_LOCK = json.loads((HERE / 'candidate-input-lock.json').read_text())
SHELL = 'App/Resources/Web/shell.js'
SESSION = 'App/Player/PlayerSession.swift'
RUNTIME = 'App/Resources/Web/runtime/'
# Final engine metadata may be independently finalized by the package owner.
# Neither executable code nor preferences/save/localization bytes may drift.
FINAL_METADATA = {
    'App/Resources/Web/runtime-identity.json',
    'App/Resources/Web/Ruffle-MODIFICATIONS.md',
    'App/Resources/Web/Ruffle-THIRD-PARTY-LICENSES.md',
    'App/Resources/Web/THIRD_PARTY_NOTICES.md',
    'App/Resources/Web/licenses.manifest.json',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(data):
    return {'sha256': digest(data), 'bytes': len(data)}


def fail(message):
    raise ValueError(message)


def path_key(name):
    if not isinstance(name, str) or not name:
        fail('unsafe inventory path')
    p = PurePosixPath(name)
    if '\\' in name or p.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')):
        fail('unsafe inventory path')
    return name


def no_symlink_ancestors(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.is_symlink():
            fail('symlink ancestor forbidden')


def read(root, name):
    name = path_key(name)
    root = Path(root)
    no_symlink_ancestors(root)
    if root.is_symlink():
        fail('symlink root forbidden')
    p = root
    for part in name.split('/'):
        p = p / part
        if p.is_symlink():
            fail('symlink input forbidden: ' + name)
    if not p.is_file():
        fail('missing regular input: ' + name)
    return p.read_bytes()


def inventory(root):
    root = Path(root)
    no_symlink_ancestors(root)
    if root.is_symlink() or not root.is_dir():
        fail('regular input directory required')
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            fail('symlink tree forbidden')
        if p.is_file():
            name = p.relative_to(root).as_posix()
            result[name] = record(read(root, name))
        elif not p.is_dir():
            fail('nonregular tree member forbidden')
    return result


def replace_once(text, anchor, replacement):
    if text.count(anchor) != 1:
        fail('diagnostic transform anchor drift')
    return text.replace(anchor, replacement)


def diagnostic_bytes():
    output = {}
    for name, expected in LOCK['diagnostics'].items():
        data = read(HERE / 'diagnostics', name)
        if record(data) != {k: expected[k] for k in ('sha256', 'bytes')}:
            fail('reviewed diagnostic input drift: ' + name)
        output[name] = data
    return output


def transform_shell(data, diagnostics):
    # Same two operations as the reviewed stage_overlay.py; only input pins
    # were rebound to this composite's unchanged production intent reader.
    text = data.decode()
    anchor = '  const held = new Set();\n'
    text = replace_once(text, anchor, diagnostics['evidence-bridge.inc.js'].decode() + anchor)
    text = replace_once(text, '  function reportTrace(message) {\n',
                        '  function reportTrace(message) {\n    lateObserveTrace(message);\n')
    return text.encode()


def transform_session(data):
    text = data.decode()
    if any(x in text for x in ('audio-recovery-injection', 'FlashNestAudioProbe', 'diagnosticLateInject')):
        fail('old/duplicate injector forbidden')
    insert = '''    // LOCAL diagnostic copy only: native state + exactly one synchronous scoped JS call.
    func diagnosticLateInject(kind: String) async throws {
        guard ["known", "unknown"].contains(kind), ready, paused, failure == nil,
              let view = webView else { throw NSError(domain: "LateAudio.invalidInject", code: 1) }
        paused = false
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            var completed = false
            view.evaluateJavaScript("window.FlashNestLateHost.inject('\\(kind)')") { _, error in
                guard !completed else { return }; completed = true
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume() }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                guard !completed else { return }; completed = true
                continuation.resume(throwing: NSError(domain: "LateAudio.javascriptDeadline", code: 2))
            }
        }
    }

'''
    return replace_once(text, '    func setPaused(_ value: Bool) {\n', insert + '    func setPaused(_ value: Bool) {\n').encode()


GATE = 'App/Player/RenderSamplingSettings.swift'
GATE_OFF = b'static let runtimeValidated = false'
GATE_ON = b'static let runtimeValidated = true'

def source_bytes(source, final_metadata=None, candidate_gate_on=False):
    result = {}
    source_lock = CANDIDATE_LOCK if candidate_gate_on else LOCK
    actual_app = {'App/' + k: v for k, v in inventory(Path(source) / 'App').items() if not ('App/' + k).startswith(RUNTIME)}
    expected_app = {k: v for k, v in source_lock['files'].items() if k.startswith('App/')}
    if set(actual_app) != set(expected_app):
        fail('App file set differs from frozen source')
    if final_metadata is not None:
        if set(final_metadata) - FINAL_METADATA:
            fail('metadata override attempted to authorize executable/source change')
    for name, expected in source_lock['files'].items():
        data = read(source, name)
        accepted = (final_metadata or {}).get(name, expected)
        checked = data
        if candidate_gate_on and name == GATE:
            if data.count(GATE_ON) != 1 or GATE_OFF in data:
                fail('candidate gate-on exact transform missing')
            checked = data.replace(GATE_ON, GATE_OFF)
        if record(checked) != accepted:
            fail('frozen source drift: ' + name)
        result[name] = data
    return result


def overlay(source, final_metadata=None, candidate_gate_on=False):
    inputs = source_bytes(source, final_metadata, candidate_gate_on)
    diagnostics = diagnostic_bytes()
    changes = {SHELL: transform_shell(inputs[SHELL], diagnostics), SESSION: transform_session(inputs[SESSION])}
    # The production predicate is read verbatim, not replaced or forced true.
    predicate = '!!player && started && !paused && !backgrounded && !document.hidden && !closing && !fatal'
    if predicate not in inputs[SHELL].decode() or predicate not in diagnostics['evidence-bridge.inc.js'].decode():
        fail('production active-intent correspondence drift')
    manifest = {'schema': 2, 'candidateGateOn': candidate_gate_on, 'state': 'authored-not-executed', 'shippingSourceUnchanged': True,
        'audibleOutputProven': False, 'totalContextCount': None,
        'runtimeBound': False, 'sourceInputs': {k: record(v) for k, v in inputs.items()},
        'changes': {k: {'baseline': record(inputs[k]), 'diagnostic': record(v)} for k, v in changes.items()},
        'diagnostics': {k: record(v) for k, v in diagnostics.items()}}
    return inputs, diagnostics, changes, manifest


def validate_runtime(runtime, runtime_inventory, expected_inventory_sha256, role):
    no_symlink_ancestors(runtime_inventory)
    raw = Path(runtime_inventory).read_bytes()
    if digest(raw) != expected_inventory_sha256:
        fail('explicit runtime inventory identity mismatch')
    declared = json.loads(raw)
    if not isinstance(declared, dict) or not declared:
        fail('full runtime map required')
    for key, value in declared.items():
        path_key(key)
        if not isinstance(value, dict) or set(value) != {'sha256', 'bytes'} or type(value['bytes']) is not int or value['bytes'] < 0:
            fail('full runtime path->{sha256,bytes} map required')
    actual = inventory(runtime)
    if actual != declared:
        fail('full runtime bytes/file-set mismatch')
    if 'ruffle.js' not in actual or sum(p.endswith('.wasm') for p in actual) != 2:
        fail('release-equivalent dual runtime required')
    old = json.loads(read(HERE / 'diagnostics', 'baseline-runtime-identity.json'))['runtimeFiles']
    if role == 'baseline-historical' and actual != old:
        fail('baseline requires original40614335019 exact bytes')
    if role == 'candidate-composite' and actual == old:
        fail('baseline cannot masquerade as final candidate')
    retired = json.loads(read(HERE / 'diagnostics', 'retired-candidate-runtime-files.json'))
    if role == 'candidate-composite' and actual == retired:
        fail('pre-composite155 runtime cannot masquerade as final candidate')
    if role not in ('candidate-composite', 'baseline-historical'):
        fail('explicit runtime role required')
    return actual, raw


def project():
    return {
        'name': 'LateAudioDiagnostic',
        'options': {'minimumXcodeGenVersion': '2.42.0', 'deploymentTarget': {'iOS': '17.0'}},
        'settings': {'base': {'SWIFT_VERSION': '5.0', 'CODE_SIGNING_ALLOWED': 'NO', 'CODE_SIGNING_REQUIRED': 'NO', 'ENABLE_USER_SCRIPT_SANDBOXING': 'YES'}},
        'packages': {'ZIPFoundation': {'url': 'https://github.com/weichsel/ZIPFoundation.git', 'exactVersion': '0.9.20'}},
        'targets': {
            'LateAudioDiagnostic': {'type': 'application', 'platform': 'iOS', 'sources': [
                {'path': 'Host'}, {'path': 'staged/App', 'excludes': ['FlashNestApp.swift', 'Resources', 'Info.plist', 'Info-Debug.plist']},
                {'path': 'staged/App/Resources/Assets.xcassets', 'buildPhase': 'resources'},
                {'path': 'staged/App/Resources/Localization', 'buildPhase': 'resources'},
                {'path': 'staged/App/Resources/Web', 'type': 'folder', 'buildPhase': 'resources'},
                {'path': 'staged/lifecycle', 'type': 'folder', 'buildPhase': 'resources'},
                *[{'path': 'staged/' + n, 'buildPhase': 'resources'} for n in ('late-audio-probe.js', 'late-host-adapter.js', 'late-runtime-identity.json')]],
                'dependencies': [{'package': 'ZIPFoundation'}],
                'settings': {'base': {'PRODUCT_BUNDLE_IDENTIFIER': 'com.flashnest.late-audio.diagnostic', 'GENERATE_INFOPLIST_FILE': 'NO', 'INFOPLIST_FILE': 'staged/Info.plist'}}},
            'LateAudioUITests': {'type': 'bundle.ui-testing', 'platform': 'iOS', 'sources': ['UITests'],
                'dependencies': [{'target': 'LateAudioDiagnostic'}],
                'settings': {'base': {'GENERATE_INFOPLIST_FILE': 'YES', 'PRODUCT_BUNDLE_IDENTIFIER': 'com.flashnest.late-audio.tests', 'TEST_TARGET_NAME': 'LateAudioDiagnostic'}}}},
        'schemes': {'LateAudioDiagnostic': {'build': {'targets': {'LateAudioDiagnostic': 'all', 'LateAudioUITests': ['test']}}, 'test': {'targets': ['LateAudioUITests']}}}}


def validate_gate_role(role, enabled):
    if role not in ('candidate-composite', 'baseline-historical') or enabled != (role == 'candidate-composite'):
        fail('candidate requires gate-on App; historical negative must remain gate-off')


def stage(args):
    no_symlink_ancestors(args.source)
    no_symlink_ancestors(args.output)
    source = Path(args.source).resolve()
    output = Path(args.output)
    # A new sibling/disjoint destination only; never overwrite frozen source.
    if output.exists() or output.is_symlink():
        fail('new isolated output required')
    output = output.resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        fail('output must be disjoint from production source')
    runtime_root = Path(args.runtime).resolve()
    if output == runtime_root or output.is_relative_to(runtime_root) or runtime_root.is_relative_to(output):
        fail('output must be disjoint from runtime input')
    metadata = json.loads(Path(args.final_metadata).read_text()) if args.final_metadata else None
    validate_gate_role(args.role, args.candidate_gate_on)
    inputs, diagnostics, changes, manifest = overlay(source, metadata, args.candidate_gate_on)
    files, raw_inventory = validate_runtime(args.runtime, args.runtime_inventory, args.runtime_inventory_sha256, args.role)
    contents = {}
    for name, data in inputs.items():
        if name.startswith('App/'):
            contents['staged/' + name] = changes.get(name, data)
        elif name.startswith('fixtures/lifecycle/'):
            contents['staged/lifecycle/' + name.removeprefix('fixtures/lifecycle/')] = data
        elif name == 'Package.resolved':
            contents[name] = data
    for name in files:
        contents['staged/' + RUNTIME + name] = read(args.runtime, name)
    for name in ('Host/LateAudioHost.swift', 'UITests/LateAudioUITests.swift'):
        contents[name] = diagnostics[name]
    for name in ('late-audio-probe.js', 'late-host-adapter.js', 'Info.plist'):
        contents['staged/' + name] = diagnostics[name]
    identity = {'schema': 2, 'role': args.role, 'candidateGateOn': args.candidate_gate_on, 'runtimeInventorySHA256': digest(raw_inventory),
        'runtimeFiles': files, 'scope': 'isolated diagnostic only; no IPA, audible-output or context-census claim'}
    contents['staged/late-runtime-identity.json'] = (json.dumps(identity, indent=2) + '\n').encode()
    contents['project.yml'] = (json.dumps(project(), indent=2) + '\n').encode()
    manifest.update(runtimeBound=True, runtime=identity, files={k: record(v) for k, v in contents.items()})
    # Read/check everything before creating outputs, then recheck immutable inputs.
    output.mkdir(parents=True, exist_ok=False)
    for name, data in contents.items():
        p = output / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    source_bytes(source, metadata, args.candidate_gate_on); diagnostic_bytes()
    validate_runtime(args.runtime, args.runtime_inventory, args.runtime_inventory_sha256, args.role)
    (output / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan'); plan.add_argument('--source', required=True); plan.add_argument('--final-metadata')
    run = sub.add_parser('stage')
    for name in ('source', 'runtime', 'runtime-inventory', 'runtime-inventory-sha256', 'role', 'output'):
        run.add_argument('--' + name, required=True)
    run.add_argument('--final-metadata')
    run.add_argument('--candidate-gate-on', action='store_true')
    args = parser.parse_args()
    if args.command == 'plan':
        metadata = json.loads(Path(args.final_metadata).read_text()) if args.final_metadata else None
        result = overlay(args.source, metadata)[3]
    else:
        result = stage(args)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
