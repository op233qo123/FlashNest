#!/usr/bin/env python3
"""Stage identical original UI fixtures around one pinned native source delta."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import yaml

BASE = 'bfa826dd9b0b1fec306a3902bf8c28a941e2162a'
GUARD = 'c40afb47ccc6ad90642dc3422233c2d81eacb045'
SESSION = 'App/Player/PlayerSession.swift'
HASHES = {'baseline': '59a449965ace4e277d97b86e0c35540e449d0d3adefb9e9944a287a648168994',
          'guarded': '5bfbf722141f7764f75ce039ca07926ef0310ac339774b1cadabe916f58252f2'}
METHOD = 'FlashNestUITests.TransitionStressUITests testThreeSceneLoadsWithRotationAndBackgroundPreserveLiveState'

def sha(data): return hashlib.sha256(data).hexdigest()
def git(root, *args): return subprocess.check_output(['git', '-C', str(root), *args])

def inventory(root):
    result = {}
    for folder in ['App', 'Tests', 'UITests', 'UITestSupport', 'fixtures']:
        for path in sorted((root / folder).rglob('*')):
            if path.is_file(): result[str(path.relative_to(root))] = sha(path.read_bytes())
    for name in ['project.yml', 'runtime.lock.json', 'runtime.files.json', 'Package.resolved']:
        result[name] = sha((root / name).read_bytes())
    return result

def prepare(driver, output, evidence):
    driver, output, evidence = map(lambda p: Path(p).resolve(), (driver, output, evidence))
    evidence.mkdir(parents=True, exist_ok=True)
    commit = git(driver, 'rev-parse', 'HEAD').decode().strip()
    fixture = driver / 'experiments/transition-stress/fixture'
    if not fixture.is_dir() or not (fixture / 'main.swf').is_file(): raise ValueError('Original frozen transition fixture is missing')
    # Lock must inventory every payload byte. No arbitrary source path accepted.
    lock = json.loads((driver / 'experiments/transition-stress/fixture.lock.json').read_text())
    actual = {str(p.relative_to(fixture)): sha(p.read_bytes()) for p in sorted(fixture.rglob('*')) if p.is_file()}
    if actual != lock['files'] or lock['variant'] != 'unload': raise ValueError('Fixture lock/variant mismatch')
    manifests = {}
    for variant, revision in [('baseline', BASE), ('guarded', GUARD)]:
        tree = output / variant
        subprocess.run(['git', '-C', str(driver), 'worktree', 'add', '--detach', str(tree), commit], check=True)
        source = git(driver, 'show', revision + ':' + SESSION)
        if sha(source) != HASHES[variant]: raise ValueError('Pinned Session source hash changed')
        (tree / SESSION).write_bytes(source)
        # Exact pre-guard Session lacks the test-only structured adapter. Remove
        # callback tests from BOTH trees; this comparison selects only UI stress.
        (tree / 'Tests/PlayerCallbackIdentityTests.swift').unlink()
        shutil.copyfile(driver / 'experiments/transition-stress/TransitionStressUITests.swift', tree / 'UITests/TransitionStressUITests.swift')
        shutil.copytree(fixture, tree / 'fixtures/transition-stress')
        seed = tree / 'UITestSupport/FixtureSource/TransitionFixtureSeed.swift'
        shutil.copyfile(driver / 'experiments/transition-stress/TransitionFixtureSeed.swift', seed)
        candidates = [p for p in seed.parent.glob('*.swift') if 'try CrossAppFixtureSeed.prepare()' in p.read_text()]
        if len(candidates) != 1: raise ValueError('Fixture source injection must match exactly once')
        target = candidates[0]; contents = target.read_text()
        if contents.count('try CrossAppFixtureSeed.prepare()') != 1: raise ValueError('Duplicate source seed invocation')
        target.write_text(contents.replace('try CrossAppFixtureSeed.prepare()', 'try CrossAppFixtureSeed.prepare(); try TransitionFixtureSeed.prepare()'))
        project = yaml.safe_load((tree / 'project.yml').read_text())
        project['targets']['FlashNestFixtureSource']['sources'].append({'path': 'fixtures/transition-stress', 'type': 'folder', 'buildPhase': 'resources'})
        (tree / 'project.yml').write_text(yaml.safe_dump(project, sort_keys=False))
        manifests[variant] = inventory(tree)
        (evidence / (variant + '-source-sha256.json')).write_text(json.dumps(manifests[variant], indent=2, sort_keys=True) + '\n')
    if manifests['baseline'].keys() != manifests['guarded'].keys(): raise ValueError('Different source inventories')
    delta = [p for p in manifests['baseline'] if manifests['baseline'][p] != manifests['guarded'][p]]
    if delta != [SESSION]: raise ValueError('Unexpected A/B source differences: ' + repr(delta))
    (evidence / 'comparison.json').write_text(json.dumps({'driverCommit': commit, 'baselineSessionCommit': BASE,
        'guardedSessionCommit': GUARD, 'onlyChangedFile': SESSION, 'fixture': lock, 'configuration': 'Debug',
        'cyclesPerArm': 3, 'order': ['baseline', 'guarded'], 'resetSameSimulatorBetweenArms': True}, indent=2) + '\n')

def verify(summary, log, root):
    spec = importlib.util.spec_from_file_location('native_gate', Path(root) / 'experiments/frame-order/candidate-native/verify_native_result.py')
    gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
    gate.LIFECYCLE_CASES['transition'] = [METHOD]
    gate.verify(summary, log.replace("Test Case '-[", "\nTest Case '-["), 'both', 'transition')
    marker_log = log.replace('FLASHNEST_TRANSITION_', '\nFLASHNEST_TRANSITION_')
    completions = re.findall(r'^FLASHNEST_TRANSITION_COMPLETE (.*)$', marker_log, re.M)
    if completions != ['cycles=3 keys=14 pointers=3 unloadCalls=3 unloadEvents=3 errors=0']:
        raise ValueError('Missing/duplicate/wrong fixed-cycle completion')
    states = []
    for line in re.findall(r'^FLASHNEST_TRANSITION_STATE (.*)$', marker_log, re.M):
        pairs = line.split()
        if any(v.count('=') != 1 for v in pairs): raise ValueError('Malformed state marker')
        state = dict(v.split('=', 1) for v in pairs)
        if len(state) != len(pairs): raise ValueError('Duplicate state field')
        states.append(state)
    expected = [('initial-input', 0)]
    for generation in range(1, 4):
        expected += [(phase, generation) for phase in ['scene-ready', 'after-landscape', 'after-background', 'after-portrait']]
        if generation == 2: expected.append(('after-paused-background', 2))
    if len(states) != 14 or len({s.get('boot') for s in states}) != 1 or not states[0].get('boot'):
        raise ValueError('Wrong state count or root boot identity')
    fields = {'phase', 'boot', 'generation', 'heartbeat', 'pointers', 'keys', 'ready', 'childGeneration', 'childHeartbeat', 'errors', 'unloadCalls', 'unloadEvents'}
    previous = None
    for index, (state, (phase, generation)) in enumerate(zip(states, expected)):
        if set(state) != fields or state['phase'] != phase: raise ValueError('Wrong state phase/fields')
        numeric = {k: int(v) for k, v in state.items() if k not in {'phase', 'boot'}}
        for key, value in {'generation': generation, 'pointers': generation, 'keys': index+1, 'ready': 1,
                           'childGeneration': generation, 'errors': 0, 'unloadCalls': generation, 'unloadEvents': generation}.items():
            if numeric[key] != value: raise ValueError('Wrong state counter: ' + key)
        if numeric['heartbeat'] < 1 or numeric['childHeartbeat'] < 1: raise ValueError('Child/root not executing')
        if previous is not None and previous['generation'] == generation:
            if numeric['heartbeat'] <= previous['heartbeat'] or numeric['childHeartbeat'] <= previous['childHeartbeat']:
                raise ValueError('Frozen root/child across OS transition')
        previous = numeric
    homes = re.findall(r'^FLASHNEST_TRANSITION_HOME cycle=(\d) phase=([a-z-]+) visibleHomeIcon=true reportedAppState=\d+$', marker_log, re.M)
    if homes != [('1', 'running-child'), ('2', 'running-child'), ('2', 'paused-menu'), ('3', 'running-child')]:
        raise ValueError('Missing actual Home evidence')
    return {'result': 'Passed', 'cycles': 3, 'states': 14, 'bootCount': 1, 'actualHomeTransitions': 4}

if __name__ == '__main__':
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest='action', required=True)
    s = sub.add_parser('prepare'); s.add_argument('driver'); s.add_argument('output'); s.add_argument('evidence')
    v = sub.add_parser('verify'); v.add_argument('summary'); v.add_argument('log'); v.add_argument('root')
    args = p.parse_args()
    if args.action == 'prepare': prepare(args.driver, args.output, args.evidence)
    else: print(json.dumps(verify(json.loads(Path(args.summary).read_text()), Path(args.log).read_text(), args.root)))
