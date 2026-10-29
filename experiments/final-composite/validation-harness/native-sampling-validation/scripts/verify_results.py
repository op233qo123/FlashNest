#!/usr/bin/env python3
"""Fail-closed verifier of exported REAL xcresult attachments (not mock evidence).

XCTest is evidence collection + local assertions; only this complete cross-arm,
cross-device check establishes the bounded simulator matrix. It cannot certify
physical-device GPU/memory/audio, and never changes runtimeValidated.
"""
import argparse, hashlib, itertools, json, math
from pathlib import Path
from PIL import Image, ImageChops
from independent_mouse_mapping import stage_position, reported_position, current_position

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

METHOD_MAP_SHA256 = '154165415a5a09ff306a8721a70bfc3729615efdfecc38bdce5fedfb2f58e22b'
def load_method_map():
    path=Path(__file__).resolve().parents[1]/'method-map-v4.json'
    raw=path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==METHOD_MAP_SHA256,'Reviewed single-tier method map differs')
    contract=json.loads(raw)
    require(contract['contract']=='flashnest-native-sampling-v4' and contract['totalNativeMethodExecutions']==198,'Wrong method partition contract')
    return contract

def check_method_row(row, contract):
    method=row.get('method');entry=contract['methods'].get(method)
    require(entry is not None and entry['kind']=='matrix','Missing/unknown matrix method provenance')
    require(all(row[field]==entry[field] for field in ('arm','rendererPolicy','scaleMode','tier','lane')),'Tier method and actual row differ')
    require(row['phase'] in entry['phases'],'Unexpected method phase')

def check_measurement(row, snapshot, candidate_inventory, baseline_inventory, unsupported=None):
    m = snapshot['measurement']; arm = row['arm']; scale = TIERS[row['tier']]
    identity = snapshot['identity']; expected_inventory = candidate_inventory if arm == 'candidate' else baseline_inventory
    require(identity['runtimeInventorySHA256'] == expected_inventory, 'Runtime artifact identity mismatch')
    require(identity['arm'] == arm and identity['simulatorOnly'] is True and identity['shippingDefaultQualityOmitted'] is True, 'Host arm/config mismatch')
    require(identity['rendererPolicyContract'] == ('candidate-three-mode-v1' if arm=='candidate' else 'legacy-original-policy-v1'), 'Per-arm production policy identity differs')
    load=m['loadObservation']
    require(type(load['count']) is int and load['count']==1 and load['hasPreferredRenderer'] is True and load['preferredRenderer']=='webgl', 'Actual production load did not prefer DirectWebGL')
    require(load['rendererQuery'] == (None if row['rendererPolicy']=='automatic' else 'webgl'), 'Actual production renderer query differs')
    require(snapshot['os'] == '18.2', 'OS not exact iOS18.2')
    require(snapshot['screenScale'] in (2, 3) and numeric(m['dpr'], snapshot['screenScale'], 0), 'Live DPR not 2/3 or CSS differs')
    require(not snapshot['failure'] and not snapshot['traceOverflow'] and not m['overflow'] and m['hidden'] is False, 'Runtime/observation error, overflow or hidden page')
    require(m['contextLost'] is False, 'Positive matrix observed lost context')
    require(not any(e.get('type') == 'webglcontextlost' for e in m['contextEvents']), 'Positive matrix observed historical context loss')
    width, height = m['css'][2:]
    require((width > height) if row['phase'] == 'landscape' else (height > width), 'Actual same-player orientation aspect missing')
    require(snapshot['loaded'] is True and snapshot['gate'] == (arm == 'candidate'), 'Wrong gate or unloaded movie')
    require(numeric(snapshot['requested'], scale, 0), 'Native request differs from row')
    require(len(m['wasm']) == 1 and m['wasm'][0] in identity['runtimeFiles'], 'Actual selected WASM branch unobserved/ambiguous')
    require(m['renderer'] in ('webgl', 'wgpu-webgl', 'webgpu', 'canvas'), 'Actual runtime renderer missing')
    require(m['renderer'] == 'webgl', 'Positive automatic/compatibility matrix did not select actual DirectWebGL')
    require(m['context'] in ('webgl', 'webgl2', 'experimental-webgl'), 'No independent GL buffer evidence; WebGPU/Canvas require a separately reviewed native probe')
    require(load['hasQuality'] == (row['lane']!='shipping-default-quality') and numeric(load['renderScale'],scale,0), 'Actual load quality/scale differs from declared lane')
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
    motions, resets = trace(after, 'MOTION'), trace(after, 'RESET')
    require(len(motions)-len(trace(before,'MOTION')) == 6 and len(resets)-len(trace(before,'RESET')) == 6,
            'Missing trace-before-reset motion/reset evidence')
    require(all(r == ['100','70'] for r in resets[-6:]), 'Fixture target reset differs')
    require(float(motions[-1][0]) > 0 and events[-1]['lastMove'] is not None, 'Drag has no actual onMouseMove/trusted MOVE observation')
    require(downs[-1][2] == 'true', 'SWF hitTest failed')
    require(float(ups[-1][2]) > 100 and float(ups[-1][3]) > 70, 'SWF drag did not move before reset')
    for motion,up in zip(motions[-6:],ups):
        require(len(motion)==5 and float(motion[0])>=0 and float(motion[0]).is_integer(), 'Invalid observed motion count')
        require(pairs([float(v) for v in motion[1:]], [float(v) for v in up[:4]], 0), 'MOTION and pre-reset UP evidence disagree')
    dpr = before['measurement']['dpr']; mode = row['scaleMode']
    viewport = [math.floor(v*dpr) for v in css[2:]]
    prior_events = before['measurement']['events']
    previous = (0, 0)
    if prior_events:
        previous_event = prior_events[-1]
        require(previous_event['type'] == 'pointerup', 'Prior phase left pointer active')
        previous = stage_position([previous_event['offsetX'], previous_event['offsetY']],
            [math.floor(v*dpr) for v in previous_event['rect'][2:]], dpr, mode)
    for i, (down, up) in enumerate(zip(downs, ups)):
        down_event, up_event = events[2*i:2*i+2]
        require(down_event['id']==up_event['id'], 'DOWN/UP pointer IDs differ')
        for event in (down_event, up_event):
            require(pairs(event['rect'], css, .01), 'Input canvas rectangle changed')
            require(pairs([event['offsetX'],event['offsetY']], [event['x']-css[0],event['y']-css[1]], .01),
                    'Canvas-target offset disagrees with independent client/rect coordinates')
        current_down = current_position([down_event['offsetX'],down_event['offsetY']], viewport,dpr,mode)
        expected_down = current_down if row['arm']=='candidate' else reported_position(previous,viewport,dpr,mode)
        # Old baseline UP dispatch precedes assigning its release point as well.
        # Use independently observed last MOVE (or DOWN if no MOVE), never a SWF response.
        up_input = up_event if row['arm']=='candidate' else (up_event['lastMove'] or down_event)
        if up_event['lastMove']:
            move = up_event['lastMove']
            require(move['type']=='pointermove' and move['trusted'] is True and move['pointerType']=='touch' and move['id']==up_event['id'], 'Invalid last native MOVE')
            require(pairs(move['rect'],css,.01) and pairs([move['offsetX'],move['offsetY']], [move['x']-css[0],move['y']-css[1]],.01), 'MOVE offset/rect disagree')
        expected_up = current_position([up_input['offsetX'],up_input['offsetY']],viewport,dpr,mode)
        require(pairs([float(v) for v in down[:2]],expected_down),
                'Candidate current DOWN or explicit historical stale-DOWN negative changed')
        require(pairs([float(v) for v in up[:2]],expected_up), 'Candidate current UP or historical pre-release UP negative differs')
        expected_hit = 100 <= expected_down[0] <= 220 and 70 <= expected_down[1] <= 170
        require(down[2] == str(expected_hit).lower(), 'Independent fixture hitTest differs')
        # startDrag retains RAW stage Twips at callback time, not rounded _xmouse.
        # Historical post-resize stale DOWN may hit the old target and move it
        # during the late DOWN position update, even with no DOM MOVE in a tap.
        raw_down = stage_position([down_event['offsetX'],down_event['offsetY']],viewport,dpr,mode) if row['arm']=='candidate' else previous
        raw_up = stage_position([up_input['offsetX'],up_input['offsetY']],viewport,dpr,mode)
        expected_target = [100+(raw_up[0]-raw_down[0])/20,70+(raw_up[1]-raw_down[1])/20] if expected_hit else [100,70]
        require(pairs([float(v) for v in up[2:4]],expected_target), 'Independent pre-reset drag/tap target delta differs')
        previous = stage_position([up_event['offsetX'],up_event['offsetY']],viewport,dpr,mode)
        require(down[5] == mode and up[6] == mode and down[6] == up[7] == '', 'Stage mode/alignment changed')
        expected_stage = [320,240] if mode=='showAll' else [round(v/dpr) for v in viewport]
        require(pairs([float(v) for v in down[3:5]],expected_stage,0) and
                pairs([float(v) for v in up[4:6]],expected_stage,0), 'Independent Stage dimensions differ')
    # Ordering is material: resetting before UP would hide failed drag movement.
    relevant = [line.split('DENSITY|',1)[1].split('|',1)[0] for line in after['traces'][len(before['traces']):] if 'DENSITY|' in line]
    require(relevant == ['DOWN','UP','MOTION','RESET']*6, 'Fixture callback/reset order changed')

def green_bounds(image):
    rgb = image.convert('RGB'); pixels = rgb.load(); xs, ys = [], []
    for y in range(rgb.height):
        for x in range(rgb.width):
            r, g, b = pixels[x, y]
            if g > r + 45 and g > b + 20 and g > 90: xs.append(x); ys.append(y)
    require(len(xs) >= 100, 'Rendered synthetic green vector not present')
    return [min(xs), min(ys), max(xs), max(ys)]

def check_oriented_crop(snapshot, capture_name, crop_sha, crops, pngs, used):
    key=(snapshot['identity']['arm'], snapshot['screenScale'], capture_name)
    require(key in crops, 'Missing oriented crop capture metadata')
    require(key not in used, 'Oriented crop capture reused');used.add(key)
    c=crops[key];dpr=snapshot['screenScale'];css=snapshot['measurement']['css'];screen=snapshot['screenBounds'];viewport=snapshot['viewport']
    require(c['cropSHA256']==crop_sha and crop_sha in pngs, 'Bound crop SHA differs/missing')
    require(c['identity']==snapshot['identity'] and c['epoch']==snapshot['epoch'], 'Crop player/source identity differs')
    require(c['css']==css and c['screenBounds']==screen and c['viewport']==viewport, 'Crop observed native geometry differs')
    require(c['normalization']=='UIImage.draw-oriented-scale1-v1', 'Crop normalization differs')
    raw=c['rawCGPixels'];orientation=c['imageOrientation'];normalized=c['normalizedPixels'];rect=c['cropRectPixels']
    require(type(orientation) is int and orientation in range(8), 'Invalid image orientation')
    require(len(raw)==2 and all(type(n) is int and n>0 for n in raw), 'Invalid raw pixel dimensions')
    require(normalized==(raw[::-1] if orientation in (2,3,6,7) else raw), 'Orientation dimensions stretched')
    require(len(screen)==2 and pairs(normalized,[n*dpr for n in screen],1), 'Normalized screen/DPR mismatch')
    require(len(css)==4 and len(viewport)==4, 'Missing native crop geometry')
    x=(viewport[0]+css[0])*dpr;y=(viewport[1]+css[1])*dpr
    expected=[math.floor(x),math.floor(y),math.ceil(x+css[2]*dpr)-math.floor(x),math.ceil(y+css[3]*dpr)-math.floor(y)]
    require(c.get('cropMapping')=='nominal-dpr-explicit-outer-edge-v1','Explicit outer-edge mapping required')
    require(c.get('desiredCropRectPixels')==expected,'Desired nominal-DPR crop differs')
    require(type(c['imageScale']) in (int,float) and math.isfinite(c['imageScale']) and c['imageScale']>0 and len(c['imagePointSize'])==2 and all(type(n) in (int,float) and math.isfinite(n) and n>0 for n in c['imagePointSize']),'Invalid UIImage point/scale metadata')
    require(pairs([n*c['imageScale'] for n in c['imagePointSize']],normalized,0.000001),'UIImage oriented point/scale dimensions differ')
    nominal=[n*dpr for n in screen];right=max(0,expected[0]+expected[2]-normalized[0]);bottom=max(0,expected[1]+expected[3]-normalized[1])
    require(expected[0]>=0 and expected[1]>=0 and expected[0]+expected[2]<=nominal[0] and expected[1]+expected[3]<=nominal[1],'Desired crop outside independent screen')
    require(right==0 or (right<=1 and expected[0]+expected[2]==nominal[0] and nominal[0]-normalized[0]==right),'Unproven/internal right edge deficit')
    require(bottom==0 or (bottom<=1 and expected[1]+expected[3]==nominal[1] and nominal[1]-normalized[1]==bottom),'Unproven/internal bottom edge deficit')
    require(c.get('missingOuterEdgePixels')==[0,0,right,bottom],'Missing edge declaration differs')
    require(rect==[expected[0],expected[1],expected[2]-right,expected[3]-bottom] and rect[2]>0 and rect[3]>0,'Actual explicit crop differs')
    original=c.get('originalPNGSHA256');require(original in pngs,'Original screenshot PNG bytes missing')
    with Image.open(pngs[original]) as image:require(list(image.size)==c.get('originalPNGPixels'),'Original PNG dimensions differ')
    with Image.open(pngs[crop_sha]) as image:require(list(image.size)==rect[2:], 'Actual crop dimensions clipped/differ')

def verify_enhanced_boundary(records, boundaries, pngs, expected_identity, crops=None, used=None):
    require(len(records)==6 and len(boundaries)==2, 'Enhanced requires3 window samples and1 error boundary perDPR')
    keyed={};outcomes=[]
    for item in records:
        snap=item['snapshot'];key=(snap['screenScale'],item['label'])
        require(key not in keyed, 'Duplicate Enhanced window');keyed[key]=item
    require(set(keyed)==set(itertools.product((2,3),('ready','after-5s','after-15s'))), 'Enhanced DPR/window selection differs')
    for dpr in (2,3):
        first=keyed[(dpr,'ready')];initial=first['snapshot'];last_sample=-1
        for label,target in [('ready',0),('after-5s',5),('after-15s',15)]:
            item=keyed[(dpr,label)];snap=item['snapshot'];m=snap['measurement'];load=m['loadObservation']
            require(item['diagnosticOnly'] is True and item['nativeAcceptance'] is False, 'Enhanced observation must never be native acceptance')
            require(snap['identity']==expected_identity and snap['identity']['rendererPolicyContract']=='candidate-three-mode-v1', 'Enhanced source/policy identity differs')
            require(snap['os']=='18.2' and snap['epoch']==initial['epoch'] and m['css']==initial['measurement']['css'], 'Enhanced same-player geometry differs')
            require(snap['gate'] is True and snap['requested']==1 and not snap['failure'], 'Enhanced must be Original candidate without hidden WebKit failure')
            require(type(load['count']) is int and load['count']==1 and load['rendererQuery']=='enhanced' and load['hasPreferredRenderer'] is False and load['preferredRenderer'] is None and load['hasQuality'] is False and numeric(load['renderScale'],1,0), 'Enhanced production load must exactly omit preference/quality/reduction')
            require(len(trace(snap,'READY'))==1 and trace(snap,'READY')[0][-2:]==['noScale',''] and all(not trace(snap,k) for k in ('DOWN','UP','MOTION')), 'Enhanced fixture READY/mode/input callbacks differ')
            require(numeric(m['dpr'],dpr,0),'Enhanced actual page DPR differs')
            require(not m['events'] and not snap['traceOverflow'] and not m['overflow'] and not m['diagnosticOverflow'], 'Enhanced fixture input/overflow changed diagnostic')
            require(item['targetElapsedSeconds']==target and target<=item['elapsedSeconds']<=target+10 and item['anchorUptimeSeconds']==first['anchorUptimeSeconds'], 'Enhanced bounded timing differs')
            require(numeric(item['observedUptimeSeconds']-item['anchorUptimeSeconds'],item['elapsedSeconds'],.01), 'Enhanced monotonic observation mismatch')
            require(item['observedUptimeSeconds']<=item['captureFinishedUptimeSeconds']<=item['observedUptimeSeconds']+15, 'Enhanced crop timing differs')
            require(m['sampledAtMs']>last_sample,'Enhanced stale page sample');last_sample=m['sampledAtMs']
            require(m['renderer'] in ('webgl','wgpu-webgl','webgpu','canvas'), 'Enhanced actual backend unobserved')
            require(item.get('cropSHA256') in pngs and not item.get('observationError') and not item.get('cropError'), 'Enhanced actual diagnostic crop missing')
            require(crops is not None and used is not None, 'Oriented crop authority required')
            check_oriented_crop(snap,'enhanced-policy-'+label,item['cropSHA256'],crops,pngs,used)
            vector=False
            with Image.open(pngs[item['cropSHA256']]) as image:
                try:green_bounds(image);vector=True
                except AssertionError:pass
            visible=vector and m['contextLost'] is False and m['gl'] and all(x>0 for x in m['gl'])
            outcome='bounded-visible' if visible else ('bounded-unhealthy' if not vector or m['contextLost'] is True or m['gl']==[0,0] else 'bounded-unverified-backend')
            outcomes.append({'dpr':dpr,'label':label,'renderer':m['renderer'],'contextLost':m['contextLost'],'gl':m['gl'],'vectorObserved':vector,
                'observedOutcome':outcome,'nativeAcceptance':False,'platformRenderHealthCertified':False,'cropSHA256':item['cropSHA256']})
    seen=set()
    for item in boundaries:
        before=item['beforeFailure'];failed=item['failed'];dpr=before['screenScale'];require(dpr not in seen,'Duplicate Enhanced failure boundary');seen.add(dpr)
        require(item['diagnosticOnly'] is True and item['nativeAcceptance'] is False,'Enhanced boundary is not render acceptance')
        require(before['identity']==failed['identity']==expected_identity and failed['epoch']==before['epoch']==keyed[(dpr,'ready')]['snapshot']['epoch'],'Enhanced error-boundary source/player changed')
        require(before['measurement']['css']==keyed[(dpr,'ready')]['snapshot']['measurement']['css'] and before['measurement']['sampledAtMs']>keyed[(dpr,'after-15s')]['snapshot']['measurement']['sampledAtMs'],'Enhanced boundary is not the observed final window player')
        require(item['beforeFailureUptimeSeconds']>=keyed[(dpr,'after-15s')]['captureFinishedUptimeSeconds'] and item['failedUptimeSeconds']>=item['beforeFailureUptimeSeconds'],'Enhanced boundary timing is not after window')
        require(failed['failure'] and failed['status']=='unknown' and any(e in ('provisional-failure','committed-failure') for e in failed['navigationEvents']), 'Enhanced real failure visibility/status boundary missing')
    require(seen=={2,3},'Enhanced failure boundary DPR missing')
    return {'configurationAndErrorBoundaryVerified':True,'diagnosticOnly':True,'nativeAcceptance':False,'platformRenderHealthCertified':False,'contextLossUserErrorReportingCertified':False,'explicitNavigationFailureVisibilityVerified':True,'observations':outcomes}

def verify(folder, candidate_inventory, baseline_inventory, expected_identities):
    method_contract=load_method_map()
    require(set(expected_identities) == {'baseline', 'candidate'}, 'External reviewed identities for both arms are required')
    for arm, expected in expected_identities.items():
        require(expected.get('arm') == arm and expected.get('simulatorOnly') is True, 'Invalid external arm identity')
        for field in ('observerSHA256', 'stagingProvenanceSHA256', 'approvedAppManifestSHA256'):
            value = expected.get(field)
            require(isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'Missing external provenance hash: ' + field)
    records, lifecycle, navigation, pngs = [], [], [], {}
    enhanced_windows,enhanced_boundaries=[],[]
    crops={};used_crops=set()
    files = [p for p in Path(folder).rglob('*') if p.is_file()]
    require(sum(p.stat().st_size for p in files) <= 128 * 1024 * 1024, 'Exported evidence exceeds128MiB; do not silently truncate')
    for p in files:
        if p.suffix.lower() == '.png': pngs[hashlib.sha256(p.read_bytes()).hexdigest()] = p
        elif p.suffix.lower() == '.json' and p.stat().st_size < 2 * 1024 * 1024:
            try: record = json.loads(p.read_text())
            except (ValueError, UnicodeError): continue
            if not isinstance(record, dict): continue
            schema = record.get('schema')
            if schema == 'flashnest-oriented-crop-v1':
                crop_key=(record['identity']['arm'],record['screenScale'],record['captureName'])
                require(crop_key not in crops, 'Duplicate oriented crop capture key');crops[crop_key]=record
            if schema == 'flashnest-native-sampling-v4': records.append(record)
            if schema == 'flashnest-native-sampling-lifecycle-v1': lifecycle.append(record)
            if schema == 'flashnest-native-sampling-navigation-v1': navigation.append(record)
            if schema == 'flashnest-enhanced-policy-window-v1': enhanced_windows.append(record)
            if schema == 'flashnest-enhanced-policy-boundary-v1': enhanced_boundaries.append(record)
    keyed = {}
    for row in records:
        check_method_row(row,method_contract)
        key = (row['arm'], row['before']['screenScale'], row['rendererPolicy'], row['scaleMode'], row['tier'], row['lane'], row['phase'])
        require(key not in keyed, 'Duplicate matrix evidence key'); keyed[key] = row
    expected = set()
    for arm in ('baseline','candidate'):
        for dpr,policy,mode,phase in itertools.product((2,3),('webgl',) if arm=='baseline' else POLICIES,MODES,PHASES):
            for tier in (('original',) if arm=='baseline' else TIERS):expected.add((arm,dpr,policy,mode,tier,'shipping-default-quality',phase))
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
        baseline_key = ('baseline', dpr, 'webgl', mode, 'original', lane, phase) if lane == 'shipping-default-quality' else ('candidate', dpr, policy, mode, 'original', lane, phase)
        reference = keyed[baseline_key]
        require(row['before']['measurement']['css'] == reference['before']['measurement']['css'], 'Original CSS stage geometry changed')
        require(row['points'] == reference['points'], 'Trusted test targets changed between tiers')
        # Historical DOWN is intentionally a negative control, not candidate compatibility.
        # Candidate tier parity remains strict against that lane's candidate Original.
        if arm=='candidate' and lane=='shipping-default-quality':
            trace_equal([u[:2]+u[4:] for u in trace(row['after'],'UP')[-6:-1]],
                        [u[:2]+u[4:] for u in trace(reference['after'],'UP')[-6:-1]])
        input_reference = keyed[('candidate',dpr,policy,mode,'original',lane,phase)] if arm=='candidate' else reference
        for moment in ('before', 'after'):
            for label in ('DOWN','UP','RESET'): trace_equal(trace(row[moment],label),trace(input_reference[moment],label))
        require(row['cropSHA256'] in pngs and reference['cropSHA256'] in pngs, 'Actual canvas screenshot missing')
        check_oriented_crop(row['before'],row['row']+'-'+row['phase'],row['cropSHA256'],crops,pngs,used_crops)
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
    enhanced=verify_enhanced_boundary(enhanced_windows,enhanced_boundaries,pngs,expected_identities['candidate'],crops,used_crops)
    require(set(crops)==used_crops, 'Unexpected/unconsumed oriented crop captures')
    policies_reduced = []
    for policy in POLICIES:
        needed = {('candidate', dpr, policy, mode, tier, 'shipping-default-quality', phase)
                  for dpr, mode, tier, phase in itertools.product((2, 3), MODES, ('threeQuarter', 'half', 'quarter'), PHASES)}
        if needed <= reduction_keys: policies_reduced.append(policy)
    return {'contract':'flashnest-native-sampling-v4', 'methodPartition':'single-tier-v1', 'methodMapSHA256':METHOD_MAP_SHA256, 'candidateMatrixMethodsPerDPR':22, 'baselineMatrixMethodsPerDPR':2, 'historicalStaleDownNegativePhases':12,
        'candidateCurrentDownUpPhases':132, 'independentMapping':'source-f32-twips-center-320x240',
        'fixtureResetsAfterObservedUp':864, 'matrixEvidenceConsistent': True, 'matrixPassed': not unsupported, 'unsupportedControls': unsupported,
        'shippingRows': 36, 'diagnosticRows': 12, 'phases': 144,
        'trustedTaps': 720, 'trustedDrags': 144, 'actualShippingReductionPolicies': policies_reduced,
        'enhancedBoundaryDiagnostic':enhanced,'shippingReductionRequirementMet': bool(policies_reduced), 'wasmActuallyObserved': {k: sorted(v) for k,v in wasm_by_arm.items()},
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
