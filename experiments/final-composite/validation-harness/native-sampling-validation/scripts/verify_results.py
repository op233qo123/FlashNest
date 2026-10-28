#!/usr/bin/env python3
"""Fail-closed verifier of exported REAL xcresult attachments (not mock evidence).

XCTest is evidence collection + local assertions; only this complete cross-arm,
cross-device check establishes the bounded simulator matrix. It cannot certify
physical-device GPU/memory/audio, and never changes runtimeValidated.
"""
import argparse, hashlib, itertools, json, math
from pathlib import Path
from PIL import Image, ImageChops

TIERS = {'original': 1, 'threeQuarter': .75, 'half': .5, 'quarter': .25}
PHASES = ('portrait', 'landscape', 'portrait-return')
POLICIES = ('automatic', 'webgl')
MODES = ('showAll', 'noScale')
def require(value, message):
    if not value: raise AssertionError(message)
def numeric(a, b, tolerance=.15):
    return isinstance(a, (int, float)) and not isinstance(a, bool) and math.isfinite(a) and abs(a-b) <= tolerance
def pairs(a, b, tolerance=.15):
    return len(a) == len(b) and all(numeric(x, y, tolerance) for x, y in zip(a, b))
def trace(snapshot, kind):
    marker = 'DENSITY|' + kind + '|'
    return [line.split(marker, 1)[1].split('|') for line in snapshot['traces'] if marker in line]
def trace_equal(a, b):
    require(len(a) == len(b), 'SWF callback count changed')
    for x, y in zip(a, b):
        require(len(x) == len(y), 'SWF callback fields changed')
        for value, expected in zip(x, y):
            try: ok = numeric(float(value), float(expected), .15)
            except ValueError: ok = value == expected
            require(ok, f'Original SWF logical/input geometry changed: {value!r} != {expected!r}')

def check_measurement(row, snapshot, candidate_inventory, baseline_inventory, unsupported=None):
    m = snapshot['measurement']; arm = row['arm']; scale = TIERS[row['tier']]
    identity = snapshot['identity']; expected_inventory = candidate_inventory if arm == 'candidate' else baseline_inventory
    require(identity['runtimeInventorySHA256'] == expected_inventory, 'Runtime artifact identity mismatch')
    require(identity['arm'] == arm and identity['simulatorOnly'] is True and identity['shippingDefaultQualityOmitted'] is True, 'Host arm/config mismatch')
    require(snapshot['os'] == '18.2', 'OS not exact iOS18.2')
    require(snapshot['screenScale'] in (2, 3) and numeric(m['dpr'], snapshot['screenScale'], 0), 'Live DPR not 2/3 or CSS differs')
    require(not snapshot['failure'] and not snapshot['traceOverflow'] and not m['overflow'] and m['hidden'] is False, 'Runtime/observation error, overflow or hidden page')
    width, height = m['css'][2:]
    require((width > height) if row['phase'] == 'landscape' else (height > width), 'Actual same-player orientation aspect missing')
    require(snapshot['loaded'] is True and snapshot['gate'] == (arm == 'candidate'), 'Wrong gate or unloaded movie')
    require(numeric(snapshot['requested'], scale, 0), 'Native request differs from row')
    require(len(m['wasm']) == 1 and m['wasm'][0] in identity['runtimeFiles'], 'Actual selected WASM branch unobserved/ambiguous')
    require(m['renderer'] in ('webgl', 'wgpu-webgl', 'webgpu', 'canvas'), 'Actual runtime renderer missing')
    if row['rendererPolicy'] == 'webgl': require(m['renderer'] == 'webgl', 'Compatibility did not select actual WebGL')
    require(m['context'] in ('webgl', 'webgl2', 'experimental-webgl'), 'No independent GL buffer evidence; WebGPU/Canvas require a separately reviewed native probe')
    logical = [math.floor(n * m['dpr']) for n in m['client']]
    require(pairs(m['client'], m['css'][2:], 0), 'CSS/client geometry changed or fractional viewport unsupported')
    require(pairs(snapshot['viewport'][2:], m['client'], .01), 'Native host and actual canvas logical bounds differ')
    applied = 1
    if arm == 'candidate':
        a = m['attributes']; applied = float(a['data-flashnest-render-scale'])
        require(float(a['data-flashnest-render-request']) == scale, 'Runtime request differs from preference')
        require(applied in (scale, 1), 'Unsupported applied scale')
        require([int(a['data-flashnest-viewport-width']), int(a['data-flashnest-viewport-height'])] == logical, 'Logical viewport changed')
        require(a['data-flashnest-renderer'] == m['renderer'], 'Attribute/actual backend disagreement')
        require(numeric(snapshot['applied'], applied, 0), 'Native applied status disagrees with physical evidence')
        require(snapshot['status'] == ('fallback' if applied != scale else 'applied'), 'Unknown/falsely applied native status')
    expected = [max(1, math.floor(n * applied + .5)) for n in logical]
    require(m['canvas'] == expected and m['gl'] == expected, 'Actual canvas/GL backing ratio is not requested/applied per axis')
    # Actual calls into the custom allocator, not the unrelated gl.SAMPLES value.
    multisample = [t for t in m['storage'] if t[0] > 1]
    require(isinstance(m['mobileQualityBranch'], bool), 'Mobile quality detection was not observed')
    if row['lane'] == 'shipping-default-quality':
        require(m['diagnosticLaunchQuality'] is None, 'Shipping load quality was overridden')
    else:
        quality = row['lane'].removeprefix('diagnostic-launch-')
        require(arm == 'candidate' and m['diagnosticLaunchQuality'] == quality, 'Diagnostic launch quality identity mismatch')
        if quality == 'low':
            require(applied == scale, 'Explicit Low diagnostic did not actually reduce')
        else:
            require(quality == 'high', 'Unknown diagnostic lane')
            if not multisample or m['context'] != 'webgl2':
                item = {'row': row['row'], 'phase': row['phase'], 'control': 'legacy-WebGL2-custom-MSAA',
                        'reason': 'Explicit High did not produce an actual >1-sample custom allocation; no High/MSAA pass claimed'}
                if unsupported is not None and item not in unsupported: unsupported.append(item)
    if m['renderer'] == 'webgl' and m['context'] == 'webgl2' and multisample:
        require(applied == 1, 'Legacy custom-MSAA safety fallback was bypassed')
    return applied

def check_inputs(row):
    before, after = row['before'], row['after']
    require(before['epoch'] == after['epoch'], 'Player replaced during phase')
    require(before['measurement']['css'] == after['measurement']['css'], 'Viewport changed within input phase')
    for label in ('DOWN', 'UP'):
        require(len(trace(after, label)) - len(trace(before, label)) == 6, 'Five taps + one drag missing/duplicated')
    events = after['measurement']['events'][len(before['measurement']['events']):]
    require(len(events) == 12, 'Trusted pointer callback count is not 12')
    require(all(e['trusted'] is True and e['pointerType'] == 'touch' for e in events), 'Input was not trusted UIKit touch')
    require([e['type'] for e in events] == ['pointerdown', 'pointerup'] * 6, 'Touch cancellation/stuck/duplicated pointer')
    css = before['measurement']['css']; positions = list(itertools.chain.from_iterable([[p, p] for p in row['points']])) + row['drag']
    for event, pos in zip(events, positions):
        require(pairs([event['x']-css[0], event['y']-css[1]], pos, .51), 'Trusted touch reached wrong DOM coordinates')
    downs, ups = trace(after, 'DOWN')[-6:], trace(after, 'UP')[-6:]
    require(downs[-1][2] == 'true', 'SWF hitTest failed')
    require(float(ups[-1][2]) > float(ups[-2][2]) and float(ups[-1][3]) > float(ups[-2][3]), 'SWF drag did not move')
    for down, up in zip(downs, ups):
        require(down[5] == row['scaleMode'] and up[6] == row['scaleMode'] and down[6] == up[7] == '', 'Stage mode/alignment changed')

def green_bounds(image):
    rgb = image.convert('RGB'); pixels = rgb.load(); xs, ys = [], []
    for y in range(rgb.height):
        for x in range(rgb.width):
            r, g, b = pixels[x, y]
            if g > r + 45 and g > b + 20 and g > 90: xs.append(x); ys.append(y)
    require(len(xs) >= 100, 'Rendered synthetic green vector not present')
    return [min(xs), min(ys), max(xs), max(ys)]

def verify(folder, candidate_inventory, baseline_inventory, expected_identities):
    require(set(expected_identities) == {'baseline', 'candidate'}, 'External reviewed identities for both arms are required')
    for arm, expected in expected_identities.items():
        require(expected.get('arm') == arm and expected.get('simulatorOnly') is True, 'Invalid external arm identity')
        for field in ('observerSHA256', 'stagingProvenanceSHA256', 'approvedAppManifestSHA256'):
            value = expected.get(field)
            require(isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'Missing external provenance hash: ' + field)
    records, lifecycle, navigation, pngs = [], [], [], {}
    files = [p for p in Path(folder).rglob('*') if p.is_file()]
    require(sum(p.stat().st_size for p in files) <= 128 * 1024 * 1024, 'Exported evidence exceeds128MiB; do not silently truncate')
    for p in files:
        if p.suffix.lower() == '.png': pngs[hashlib.sha256(p.read_bytes()).hexdigest()] = p
        elif p.suffix.lower() == '.json' and p.stat().st_size < 2 * 1024 * 1024:
            try: record = json.loads(p.read_text())
            except (ValueError, UnicodeError): continue
            if not isinstance(record, dict): continue
            schema = record.get('schema')
            if schema == 'flashnest-native-sampling-v1': records.append(record)
            if schema == 'flashnest-native-sampling-lifecycle-v1': lifecycle.append(record)
            if schema == 'flashnest-native-sampling-navigation-v1': navigation.append(record)
    keyed = {}
    for row in records:
        key = (row['arm'], row['before']['screenScale'], row['rendererPolicy'], row['scaleMode'], row['tier'], row['lane'], row['phase'])
        require(key not in keyed, 'Duplicate matrix evidence key'); keyed[key] = row
    expected = set()
    for arm, dpr, policy, mode, phase in itertools.product(('baseline', 'candidate'), (2, 3), POLICIES, MODES, PHASES):
        for tier in (('original',) if arm == 'baseline' else TIERS): expected.add((arm, dpr, policy, mode, tier, 'shipping-default-quality', phase))
    for quality in ('low', 'high'):
        for dpr, tier, phase in itertools.product((2, 3), (('original','quarter') if quality == 'low' else TIERS), PHASES):
            expected.add(('candidate', dpr, 'webgl', 'showAll', tier, 'diagnostic-launch-' + quality, phase))
    require(set(keyed) == expected, f'Incomplete/unexpected matrix: missing={sorted(expected-set(keyed))}, extra={sorted(set(keyed)-expected)}')
    unsupported = []; reduction_keys = set(); wasm_by_arm = {'baseline': set(), 'candidate': set()}
    for key, row in keyed.items():
        for moment in ('before', 'after'):
            require(row[moment]['identity'] == expected_identities[row['arm']], 'Observed host/probe/App identity differs from externally reviewed staging identity')
        applied = check_measurement(row, row['before'], candidate_inventory, baseline_inventory, unsupported)
        require(applied == check_measurement(row, row['after'], candidate_inventory, baseline_inventory, unsupported), 'Applied tier changed during phase')
        check_inputs(row)
        portrait = keyed[key[:-1] + ('portrait',)]
        require(row['before']['epoch'] == portrait['before']['epoch'], 'Orientation created a new WK player')
        if row['phase'] == 'portrait-return':
            require(row['before']['measurement']['css'] == portrait['before']['measurement']['css'], 'Portrait return did not restore original geometry')
        wasm_by_arm[row['arm']].add(row['before']['measurement']['wasm'][0])
        arm, dpr, policy, mode, tier, lane, phase = key
        baseline_key = ('baseline', dpr, policy, mode, 'original', lane, phase) if lane == 'shipping-default-quality' else ('candidate', dpr, policy, mode, 'original', lane, phase)
        reference = keyed[baseline_key]
        require(row['before']['measurement']['css'] == reference['before']['measurement']['css'], 'Original CSS stage geometry changed')
        require(row['points'] == reference['points'], 'Trusted test targets changed between tiers')
        for moment in ('before', 'after'):
            for label in ('DOWN', 'UP'): trace_equal(trace(row[moment], label), trace(reference[moment], label))
        require(row['cropSHA256'] in pngs and reference['cropSHA256'] in pngs, 'Actual canvas screenshot missing')
        with Image.open(pngs[row['cropSHA256']]) as image, Image.open(pngs[reference['cropSHA256']]) as original:
            require(image.size == original.size, 'Screenshot logical size changed')
            require(pairs(green_bounds(image), green_bounds(original), math.ceil(2 * dpr / applied)), 'Rendered vector bounds moved')
            if applied == 1:
                require(ImageChops.difference(image.convert('RGB'), original.convert('RGB')).getbbox() is None, 'Original/fallback pixels are not baseline-identical')
        if arm == 'candidate' and lane == 'shipping-default-quality' and applied < 1: reduction_keys.add(key)
    # Lifecycle evidence must be complete for both policies on both DPRs.
    require(len(lifecycle) == 4, 'Missing candidate quarter/showAll native lifecycle rows')
    seen = set()
    for item in lifecycle:
        before, stale, returned, invalidated, reloaded, restarted = [item[k] for k in ('before','stale','returned','invalidated','afterReload','restarted')]
        require(all(s['identity'] == expected_identities['candidate'] for s in (before, stale, returned, invalidated, reloaded, restarted)), 'Lifecycle provenance mismatch')
        key = (before['screenScale'], before['measurement']['renderer'])
        # Do not use resolved backend as policy identity: auto may resolve WebGL too.
        policy = 'automatic' if '-automatic-' in item['row'] else 'webgl'; seen.add((before['screenScale'], policy))
        require(stale['staleBarrier'] is True and stale['status'] == before['status'] and stale['applied'] == before['applied'], 'Late-message delivery not rejected after real barrier')
        require(returned['epoch'] == before['epoch'] and not returned['measurement']['hidden'], 'Background return replaced/left hidden player')
        require(invalidated['status'] == reloaded['status'] == 'unknown' and reloaded['epoch'] == before['epoch'], 'Same-view replacement falsely rebound status')
        require(restarted['epoch'] == before['epoch'] + 1 and restarted['requested'] == .25 and restarted['status'] != 'unknown', 'Fresh WK restart did not restore real status')
    require(seen == set(itertools.product((2, 3), POLICIES)), 'Lifecycle device/policy rows missing')
    require(len(navigation) == 2 and {r['loaded']['screenScale'] for r in navigation} == {2, 3}, 'Real initial redirect/failure evidence missing')
    for item in navigation:
        require(all(item[k]['identity'] == expected_identities['candidate'] for k in ('loaded', 'failed')), 'Navigation provenance mismatch')
        e = item['loaded']['navigationEvents']; failed = item['failed']
        require(e.index('provisional') < e.index('redirect') < e.index('commit'), 'Initial real callback order wrong')
        require(item['loaded']['status'] != 'unknown' and failed['status'] == 'unknown' and failed['failure'], 'Initial binding/failure reporting regressed')
        require(any(x in failed['navigationEvents'] for x in ('provisional-failure', 'committed-failure')), 'No actual WK failure callback')
    policies_reduced = []
    for policy in POLICIES:
        needed = {('candidate', dpr, policy, mode, tier, 'shipping-default-quality', phase)
                  for dpr, mode, tier, phase in itertools.product((2, 3), MODES, ('threeQuarter', 'half', 'quarter'), PHASES)}
        if needed <= reduction_keys: policies_reduced.append(policy)
    return {'matrixEvidenceConsistent': True, 'matrixPassed': not unsupported, 'unsupportedControls': unsupported,
        'shippingRows': 40, 'diagnosticRows': 12, 'phases': 156,
        'trustedTaps': 780, 'trustedDrags': 156, 'actualShippingReductionPolicies': policies_reduced,
        'shippingReductionRequirementMet': bool(policies_reduced), 'wasmActuallyObserved': {k: sorted(v) for k,v in wasm_by_arm.items()},
        'physicalDeviceAcceptance': False, 'runtimeValidated': False,
        'limitations': ['Simulator only, not real GPU/device/memory/audio proof', 'Only naturally selected WASM branch observed',
                        'Center alignment and showAll/noScale only', 'No claim of full filters/cache/masks/context-loss matrix']}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attachments', required=True); parser.add_argument('--candidate-inventory-sha256', required=True)
    parser.add_argument('--baseline-inventory-sha256', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--expected-identities', required=True, help='Externally reviewed {baseline,candidate} SamplingIdentity.json contents, frozen before simulator launch')
    args = parser.parse_args()
    try:
        report = verify(args.attachments, args.candidate_inventory_sha256, args.baseline_inventory_sha256, json.loads(Path(args.expected_identities).read_text()))
        code = (0 if report['shippingReductionRequirementMet'] else 2) if report['matrixPassed'] else 1
    except Exception as error:
        report = {'matrixPassed': False, 'runtimeValidated': False, 'error': str(error)}; code = 1
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n'); print(json.dumps(report)); raise SystemExit(code)
if __name__ == '__main__': main()
