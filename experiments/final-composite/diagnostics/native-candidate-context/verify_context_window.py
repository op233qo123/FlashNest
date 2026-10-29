#!/usr/bin/env python3
"""Bounded diagnostic only. No native matrix/runtime/physical-device certification."""
import argparse,hashlib,importlib.util,json,math,sys
from pathlib import Path
from PIL import Image

def load_geometry(path):
    path=Path(path).resolve();sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('original_geometry',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def check(folder,geometry,expected_identity):
    files=[p for p in Path(folder).rglob('*') if p.is_file()]
    errors=[];observations=[]
    def demand(ok,message):
        if not ok:errors.append(message)
    demand(all(not p.is_symlink() for p in files),'Linked evidence')
    demand(sum(p.stat().st_size for p in files)<=128*1024*1024,'Evidence exceeds128MiB')
    if errors:return {'diagnosticOnly':True,'nativeAcceptance':False,'diagnosticHealthy':False,'errors':errors,'observations':[]}
    pngs={hashlib.sha256(p.read_bytes()).hexdigest():p for p in files if p.suffix.lower()=='.png'}
    records=[]
    for p in files:
        if p.suffix.lower()!='.json' or p.stat().st_size>=128000:continue
        try:r=json.loads(p.read_text())
        except (ValueError,UnicodeError):continue
        if isinstance(r,dict) and r.get('schema')=='flashnest-candidate-context-window-v1':records.append(r)
    labels=['ready','after-5s','after-15s'];demand(len(records)==3 and sorted(r.get('label','') for r in records)==sorted(labels),'Exactly ready/5s/15s records required')
    records.sort(key=lambda r:r.get('targetElapsedSeconds',-1))
    first_epoch=None;anchor=None;last_sample=None;last_calls={};identity=expected_identity;first_css=None
    for r in records[:3]:
        label=r.get('label','unknown');state=r.get('snapshot',{});m=state.get('measurement');row={'label':label,'elapsedSeconds':r.get('elapsedSeconds'),'snapshot':state};observations.append(row)
        demand(r.get('diagnosticOnly') is True and r.get('nativeAcceptance') is False,label+': diagnostic identity')
        demand(not r.get('observationError') and not r.get('cropError'),label+': observation/crop failure')
        if not isinstance(m,dict):errors.append(label+': missing measurement');continue
        if first_epoch is None:first_epoch=state.get('epoch');anchor=r.get('anchorUptimeSeconds');first_css=m.get('css')
        demand(first_epoch is not None and state.get('epoch')==first_epoch,label+': player replaced/unidentified')
        demand(state.get('identity')==identity and isinstance(identity,dict) and identity.get('arm')=='candidate',label+': candidate/source identity changed')
        demand(state.get('os')=='18.2' and state.get('screenScale')==2,label+': simulator OS/DPR differs')
        demand(isinstance(first_css,list) and len(first_css)==4 and m.get('css')==first_css,label+': viewport changed/missing')
        ready=[t for t in state.get('traces',[]) if 'DENSITY|READY|' in t]
        demand(len(ready)==1 and ready[0].endswith('|noScale|'),label+': fixture READY/mode differs')
        demand(not any('DENSITY|DOWN|' in t or 'DENSITY|UP|' in t for t in state.get('traces',[])),label+': unexpected fixture callbacks')
        demand(state.get('gate') is True and state.get('requested')==1,label+': not candidate Original')
        load=m.get('loadObservation')
        demand(isinstance(load,dict) and type(load.get('count')) is int and load.get('count')==1
               and load.get('rendererQuery') is None and load.get('hasPreferredRenderer') is True
               and load.get('preferredRenderer')=='webgl' and load.get('hasQuality') is False
               and load.get('renderScale')==1,label+': actual Automatic load configuration differs')
        demand(m.get('renderer') == 'webgl',label+': actual GL renderer unconfirmed')
        demand(not state.get('failure') and not state.get('probeError'),label+': web/probe failure')
        demand(not state.get('traceOverflow') and not m.get('overflow') and not m.get('diagnosticOverflow'),label+': evidence overflow')
        demand(m.get('contextLost') is False and m.get('canvasConnected') is True and m.get('hidden') is False,label+': lost/disconnected/hidden context')
        demand(m.get('context') in ('webgl','webgl2','experimental-webgl'),label+': unsupported/non-GL context')
        gl=m.get('gl');demand(isinstance(gl,list) and len(gl)==2 and all(isinstance(x,(int,float)) and math.isfinite(x) and x>0 for x in gl),label+': zero/missing GL backing')
        demand(not any(e.get('type')=='webglcontextlost' for e in m.get('contextEvents',[])),label+': observed context loss')
        demand(not m.get('events'),label+': unexpected fixture pointer input')
        target={'ready':0,'after-5s':5,'after-15s':15}.get(label)
        try:
            elapsed=r['elapsedSeconds'];observed=r['observedUptimeSeconds']
            demand(r['anchorUptimeSeconds']==anchor and abs(observed-anchor-elapsed)<.01,label+': monotonic anchor mismatch')
            demand(target is not None and r['targetElapsedSeconds']==target and target<=elapsed<=target+10,label+': bounded sample timing missed')
            demand(observed<=r['captureFinishedUptimeSeconds']<=observed+15,label+': capture timestamp order/duration')
            sampled=m['sampledAtMs'];demand(isinstance(sampled,(int,float)) and math.isfinite(sampled) and (last_sample is None or sampled>last_sample),label+': stale/nonmonotonic page sample');last_sample=sampled
        except (KeyError,TypeError):errors.append(label+': missing/invalid monotonic times')
        calls=m.get('renderCalls',{});row['renderCalls']=calls;row['contextLost']=m.get('contextLost');row['gl']=gl
        demand(isinstance(calls,dict) and all(isinstance(n,int) and n>=0 for n in calls.values()),label+': invalid draw observations')
        if isinstance(calls,dict) and all(type(n) is int and n>=0 for n in calls.values()):
            demand(sum(calls.get(k,0) for k in ('drawArrays','drawElements','drawArraysInstanced','drawElementsInstanced'))>0,label+': no actual draw observation')
            demand(all(calls.get(k,0)>=v for k,v in last_calls.items()),label+': renderer counters reset');last_calls=calls
        crop=r.get('cropSHA256');demand(crop in pngs,label+': exact canvas crop missing')
        if crop in pngs:
            try:
                with Image.open(pngs[crop]) as image:row['greenBounds']=geometry.green_bounds(image)
            except Exception as e:errors.append(label+': '+str(e))
    return {'diagnosticOnly':True,'nativeAcceptance':False,'diagnosticHealthy':not errors,'observedRecordCount':len(records),'errors':errors,'observations':observations,
            'limitations':['One candidate automatic/noScale/Original same-player bounded window only','Not the161-method gate or a physical-device result','No inferred timestamp for context loss preceding first observation']}

GEOMETRY_VERIFIER_SHA256 = 'd9113fc36df90cd9591fe10d3399c8482a9c0766405efbf6b28c489580905204'

def verify(folder, geometry_verifier=None, expected_identity=None):
    # Default deployment is a sibling of native-sampling-validation. An explicit
    # path is allowed only for these same pinned bytes, never an alternate predicate.
    path=Path(geometry_verifier) if geometry_verifier else Path(__file__).resolve().parent.parent/'native-sampling-validation/scripts/verify_results.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=GEOMETRY_VERIFIER_SHA256:
        raise ValueError('Original geometry verifier hash differs')
    if expected_identity is None:raise ValueError('Pre-staged external expected identity required')
    expected_path=Path(expected_identity)
    if expected_path.is_symlink() or expected_path.stat().st_size>64000:raise ValueError('Invalid external identity file')
    raw=expected_path.read_bytes();identity=json.loads(raw)
    if not isinstance(identity,dict) or identity.get('arm')!='candidate':raise ValueError('External candidate identity required')
    report=check(folder,load_geometry(path),identity)
    report['expectedIdentitySHA256']=hashlib.sha256(raw).hexdigest()
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--attachments',required=True);p.add_argument('--geometry-verifier',required=True);p.add_argument('--geometry-verifier-sha256',required=True);p.add_argument('--expected-identity',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    try:
        if a.geometry_verifier_sha256!=GEOMETRY_VERIFIER_SHA256:raise ValueError('Unreviewed geometry verifier hash')
        report=verify(a.attachments,a.geometry_verifier,a.expected_identity)
    except Exception as e:report={'diagnosticOnly':True,'nativeAcceptance':False,'diagnosticHealthy':False,'errors':[str(e)]}
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));raise SystemExit(0 if report['diagnosticHealthy'] else 1)
if __name__=='__main__':main()
