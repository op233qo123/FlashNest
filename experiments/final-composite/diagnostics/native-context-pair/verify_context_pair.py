#!/usr/bin/env python3
"""Paired context/rotation DIAGNOSTIC. Any loss stays unhealthy; never native acceptance."""
import argparse,hashlib,importlib.util,json,math,sys
from pathlib import Path
from PIL import Image
GEOMETRY_SHA256='3b8c35cc6dbf8c97f947b18856ec04e720c26ea2724706d76df38d48b7a3b0dd'
MAPPING_SHA256='73779ad174509ed86400b47278a11ee902a86cc70471a541fbdb8378aaf70704'
PROBE_SHA256='4c551bfd2b2a2a92e8141f14724d1264e196aa8e9cceb4a0fa06ee2a27bae1d8'
FIXTURE_SHA256='49239943a9dc7388b171cc0d3fecf249a7fcac1ec1c277bfc8d91ee8cb7eac6e'
LABELS=('ready','after-5s','after-15s','landscape')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def same(a,b,tolerance=0):return len(a)==len(b) and all(finite(x) and finite(y) and abs(x-y)<=tolerance for x,y in zip(a,b))
def traces(s,label):return [t.split('DENSITY|'+label+'|',1)[1].split('|') for t in s.get('traces',[]) if 'DENSITY|'+label+'|' in t]
def load_geometry(path):
    p=Path(path).resolve()
    if sha(p)!=GEOMETRY_SHA256 or sha(p.with_name('independent_mouse_mapping.py'))!=MAPPING_SHA256:raise ValueError('Unreviewed geometry predicate/dependency')
    sys.path.insert(0,str(p.parent));spec=importlib.util.spec_from_file_location('pair_original_geometry',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def expected_green_bounds(css,dpr):
    # Known synthetic fixture only: centered320x240,noScale, target100,70,size120x100.
    # Inclusive final pixels: far edge minus1. A fixed2px allowance covers <=1px
    # integral crop origin expansion plus <=1px raster/threshold edge uncertainty.
    left=(css[2]-320)/2+100;top=(css[3]-240)/2+70
    return [left*dpr,top*dpr,(left+120)*dpr-1,(top+100)*dpr-1]

def verify(folder,geometry_verifier,expected_identities_path):
    geometry=load_geometry(geometry_verifier)
    identity_path=Path(expected_identities_path)
    if identity_path.is_symlink() or identity_path.stat().st_size>128000:raise ValueError('Invalid external identity file')
    expected=json.loads(identity_path.read_text())
    if set(expected)!= {'baseline','candidate'}:raise ValueError('Both pre-staged external identities required')
    for arm,identity in expected.items():
        if identity.get('arm')!=arm or identity.get('observerSHA256')!=PROBE_SHA256:raise ValueError('External arm/probe identity differs')
    files=[p for p in Path(folder).rglob('*') if p.is_file()]
    if any(p.is_symlink() for p in files) or sum(p.stat().st_size for p in files)>128*1024*1024:raise ValueError('Unsafe/oversized evidence folder')
    pngs={sha(p):p for p in files if p.suffix.lower()=='.png'};records=[]
    for p in files:
        if p.suffix.lower()!='.json' or p.stat().st_size>=128000:continue
        try:x=json.loads(p.read_text())
        except (ValueError,UnicodeError):continue
        if isinstance(x,dict) and x.get('schema')=='flashnest-paired-context-window-v1':records.append(x)
    errors=[];observations=[];keyed={}
    def need(ok,message):
        if not ok:errors.append(message)
    need(len(records)==8,'Exactly4 bounded observations perarm required')
    for r in records:
        key=(r.get('arm'),r.get('label'))
        need(key not in keyed,'Duplicate arm/label observation: '+str(key));keyed[key]=r
    need(set(keyed)=={(a,l) for a in expected for l in LABELS},'Missing/unexpected paired arm/label')
    for arm in ('baseline','candidate'):
        anchor=None;epoch=None;css0=None;sampled_previous=None;calls_previous={};record_previous=None;call_count_previous=-1
        for label in LABELS:
            r=keyed.get((arm,label))
            if r is None:continue
            prefix=arm+'/'+label+': '
            s=r.get('snapshot',{});m=s.get('measurement');row={'arm':arm,'label':label,'snapshot':s,'record':{k:v for k,v in r.items() if k!='snapshot'},'errors':[]};observations.append(row)
            start_errors=len(errors)
            def check(ok,msg):need(ok,prefix+msg)
            try:
                check(r.get('diagnosticOnly') is True and r.get('nativeAcceptance') is False,'diagnostic identity changed')
                check(r.get('rendererPolicy')==('webgl' if arm=='baseline' else 'automatic'),'wrong requested product policy')
                check(s.get('identity')==expected[arm],'external source/runtime identity mismatch')
                check(s.get('os')=='18.2' and s.get('screenScale')==2,'exactDPR2/iOS18.2 required')
                check(s.get('gate') is (arm=='candidate') and s.get('requested')==1,'per-arm gate/Original request differs')
                check(not s.get('failure') and not s.get('probeError') and not r.get('observationError') and not r.get('cropError'),'web/probe/observation/crop failure')
                if not isinstance(m,dict):raise ValueError('measurement unavailable; retained raw/fullscreen evidence')
                if anchor is None:anchor=r['anchorUptimeSeconds'];epoch=s['epoch'];css0=m['css']
                check(s['epoch']==epoch,'player replaced')
                check(r['anchorUptimeSeconds']==anchor and finite(r['elapsedSeconds']) and finite(r['observedUptimeSeconds']) and abs(r['observedUptimeSeconds']-anchor-r['elapsedSeconds'])<=.01,'monotonic anchor mismatch')
                check(r['observedUptimeSeconds']<=r['captureFinishedUptimeSeconds']<=r['observedUptimeSeconds']+15,'crop capture duration/order')
                if label!='landscape':
                    target={'ready':0,'after-5s':5,'after-15s':15}[label]
                    check(r['targetElapsedSeconds']==target and target<=r['elapsedSeconds']<=target+10,'bounded window timing missed')
                    check(same(m['css'],css0) and m['css'][3]>m['css'][2],'portrait window geometry changed')
                else:
                    check(r['targetElapsedSeconds']==-1 and record_previous is not None and r['rotationRequestedUptimeSeconds']>=record_previous['captureFinishedUptimeSeconds'],'rotation not after15s capture')
                    check(r['rotationRequestedUptimeSeconds']<=r['observedUptimeSeconds']<=r['rotationRequestedUptimeSeconds']+55,'bounded rotation observation missed')
                    check(m['css'][2]>m['css'][3],'landscape not observed')
                check(finite(m['sampledAtMs']) and (sampled_previous is None or m['sampledAtMs']>sampled_previous),'page sample timestamp stale/reset')
                sampled_previous=m['sampledAtMs'];record_previous=r
                ready=traces(s,'READY');check(len(ready)==1 and ready[0][-2:]==['noScale',''],'one known fixture READY/noScale required')
                check(all(not traces(s,k) for k in ('DOWN','UP','MOTION','RESET')) and not m['events'],'unexpected gameplay input/callbacks')
                check(not s['traceOverflow'] and not m['overflow'] and not m['diagnosticOverflow'] and m['identityObservationErrors']==0,'incomplete/overflowed telemetry')
                check(m['canvasConnected'] is True and m['hidden'] is False,'canvas disconnected/hidden')
                check(m['dpr']==2 and len(m['css'])==4 and same(m['client'],m['css'][2:]),'independent CSS/client/DPR geometry mismatch')
                load=m['loadObservation']
                check(type(load['count']) is int and load['count']==1 and load['rendererQuery']==('webgl' if arm=='baseline' else None) and load['hasPreferredRenderer'] is True and load['preferredRenderer']=='webgl' and load['hasQuality'] is False and finite(load['renderScale']) and load['renderScale']==1,'actual product load forwarding differs')
                check(expected[arm].get('rendererPolicyContract')==('legacy-original-policy-v1' if arm=='baseline' else 'candidate-three-mode-v1'),'external product policy identity differs')
                check(m['renderer']=='webgl','actual DirectWebGL backend missing')
                row['actualWasmFiles']=[name for name in m.get('wasm',[]) if isinstance(name,str)] if isinstance(m.get('wasm'),list) else []
                row['wasmObservationKnown']=isinstance(m.get('wasm'),list) and len(m['wasm'])==1 and isinstance(m['wasm'][0],str) and m['wasm'][0] in expected[arm]['runtimeFiles']
                check(len(m['wasm'])==1 and m['wasm'][0] in expected[arm]['runtimeFiles'],'actual selectedWASM missing')
                # NEVER turn a retained green picture into a healthy context result.
                check(m['contextLost'] is False,'measured context lost')
                check(not any(e.get('type')=='webglcontextlost' for e in m['contextEvents']),'observed context-loss event')
                check(m['context'] in ('webgl','webgl2','experimental-webgl') and len(m['gl'])==2 and all(finite(v) and v>0 for v in m['gl']),'zero/unobserved GL backing')
                check(same(m['canvas'],[m['css'][2]*2,m['css'][3]*2]) and same(m['gl'],m['canvas']),'Original logical/canvas/GL dimensions differ')
                check(m['contextSelection']=='legacy-first-successful-getContext-per-canvas','legacy observation choice was silently changed')
                check(len(m['canvasIdentities'])<=8 and len(m['contextIdentities'])<=16 and len(m['getContextCalls'])<=32 and len(m['contextEvents'])<=16,'identity buffer bound violated')
                check(type(m['getContextCallCount']) is int and m['getContextCallCount']>=call_count_previous,'getContext counter reset');call_count_previous=m['getContextCallCount']
                stats={x['contextId']:x for x in m['contextIdentities']}
                check(m['measuredContextId'] in stats and stats[m['measuredContextId']]['canvasId']==m['currentCanvasId'],'measured receiver/canvas identity unresolved')
                row['measuredContextId']=m['measuredContextId'];row['currentCanvasId']=m['currentCanvasId']
                row['selectionDiffersFromLastNonNullReturn']=m['measuredContextId']!=m['currentCanvasLastNonNullContextId']
                check(not row['selectionDiffersFromLastNonNullReturn'],'measured context differs from last non-null return; active context health uncertain')
                deltas={}
                for cid,entry in stats.items():
                    previous=calls_previous.get(cid,{})
                    check(all(type(n) is int and n>=previous.get(k,0) for k,n in entry['calls'].items()),'receiver call counter reset/invalid')
                    deltas[str(cid)]={k:n-previous.get(k,0) for k,n in entry['calls'].items()};calls_previous[cid]=entry['calls'].copy()
                row['observedReceiverCallDeltas']=deltas # calls, NOT GPU-completed frames
            except (KeyError,TypeError,ValueError,IndexError) as e:check(False,'invalid/missing observation field: '+str(e))
            # Pixel geometry is independent of GL/context telemetry validity.
            # Still inspect the exact crop after a loss or malformed GL field.
            try:
                crop=r.get('cropSHA256');check(crop in pngs,'exact crop bytes missing')
                cg=r.get('cropGeometry',{});screen=s.get('screenBounds',[]);viewport=s.get('viewport',[])
                check(cg.get('normalization')=='UIImage.draw-oriented-scale1-v1','oriented crop normalization missing')
                check(same(cg.get('normalizedPixels',[]),[n*2 for n in screen],1) and len(screen)==2,'normalized full-screen/DPR mismatch')
                raw=cg.get('rawCGPixels',[]);orientation=cg.get('imageOrientation')
                check(type(orientation) is int and orientation in range(8),'invalid UIImage orientation')
                oriented=list(reversed(raw)) if orientation in (2,3,6,7) else raw
                check(same(oriented,cg.get('normalizedPixels',[])) and len(raw)==2,'raw orientation dimensions changed/stretched')
                css=m.get('css') if isinstance(m,dict) else None
                check(isinstance(css,list) and len(css)==4 and all(finite(x) for x in css) and css[2]>0 and css[3]>0,'pixel geometry unavailable')
                if crop in pngs and isinstance(css,list) and len(css)==4 and all(finite(x) for x in css) and css[2]>0 and css[3]>0:
                    rect=cg.get('cropRectPixels',[])
                    check(len(viewport)==4,'native viewport unavailable')
                    if len(viewport)==4:
                        x=(viewport[0]+css[0])*2;y=(viewport[1]+css[1])*2
                        expected_rect=[math.floor(x),math.floor(y),math.ceil(x+css[2]*2)-math.floor(x),math.ceil(y+css[3]*2)-math.floor(y)]
                        check(same(rect,expected_rect),'oriented crop rectangle differs')
                    with Image.open(pngs[crop]) as image:
                        check(same([image.width,image.height],rect[2:]),'actual crop dimensions differ/clip')
                        bounded=image.width<=4096 and image.height<=4096 and image.width*image.height<=12000000
                        check(bounded,'unexpected crop dimensions')
                        if bounded:
                            check(same([image.width,image.height],[css[2]*2,css[3]*2],1),'screenshot physical/CSS size mismatch')
                            expected_bounds=expected_green_bounds(css,2);row['expectedGreenBounds']=expected_bounds;row['greenBoundsTolerancePhysicalPixels']=2
                            try:bounds=geometry.green_bounds(image);row['observedGreenBounds']=bounds;check(same(bounds,expected_bounds,2),'independent centered fixture rectangle differs')
                            except AssertionError as e:check(False,str(e))
            except (TypeError,ValueError,OSError) as e:check(False,'crop observation failed: '+str(e))
            row['errors']=errors[start_errors:]
    rotation=[]
    for arm in expected:
        rows={x['label']:x for x in observations if x['arm']==arm}
        a=rows.get('after-15s',{});b=rows.get('landscape',{})
        aligned=all('observedGreenBounds' in x and same(x['observedGreenBounds'],x['expectedGreenBounds'],2) for x in (a,b))
        changed=aligned and not same(a['expectedGreenBounds'],b['expectedGreenBounds'],2)
        rotation.append({'arm':arm,'independentRectangleAlignedBeforeAndAfterRotation':aligned,'expectedRectanglePositionChanged':changed,
            'interpretation':'geometry observation only; does not establish live GPU recovery or context health','nativeAcceptance':False})
    return {'schema':1,'diagnosticOnly':True,'nativeAcceptance':False,'diagnosticHealthy':not errors,'expectedIdentitiesSHA256':sha(identity_path),
        'geometryVerifierSHA256':GEOMETRY_SHA256,'probeSHA256':PROBE_SHA256,'fixtureSHA256':FIXTURE_SHA256,'observedRecordCount':len(records),
        'errors':errors,'observations':observations,'rotationEvidence':rotation,
        'actualWasmFilesByArm':{arm:sorted({name for row in observations if row['arm']==arm for name in row.get('actualWasmFiles',[])}) for arm in expected},
        'limitations':['Any context loss remains unhealthy even with green pixels or geometry updates','Receiver call counters do not prove GPU completion','Canvas events do not supply a context object; identity association is explicit','No recovery, gameplay input, or production mutation; not native matrix/IPA acceptance']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attachments',required=True);p.add_argument('--geometry-verifier',required=True);p.add_argument('--expected-identities',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    try:r=verify(a.attachments,a.geometry_verifier,a.expected_identities)
    except Exception as e:r={'diagnosticOnly':True,'nativeAcceptance':False,'diagnosticHealthy':False,'errors':[str(e)]}
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['diagnosticHealthy'] else 1)
