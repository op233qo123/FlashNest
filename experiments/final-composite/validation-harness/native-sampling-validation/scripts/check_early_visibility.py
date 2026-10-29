#!/usr/bin/env python3
"""Early rejection only; never substitutes complete native geometry/pixel acceptance."""
import argparse, hashlib, json
from pathlib import Path
from PIL import Image
from verify_results import green_bounds, require

def check(folder, expected):
    files=[p for p in Path(folder).rglob('*') if p.is_file()]
    require(all(not p.is_symlink() for p in files),'Linked early-visibility evidence')
    require(sum(p.stat().st_size for p in files)<=128*1024*1024,'Early evidence exceeds unchanged128MiB cap')
    pngs={hashlib.sha256(p.read_bytes()).hexdigest():p for p in files if p.suffix.lower()=='.png'}
    records=[]
    for p in files:
        if p.suffix.lower()!='.json' or p.stat().st_size>=2*1024*1024:continue
        try:r=json.loads(p.read_text())
        except (ValueError,UnicodeError):continue
        if isinstance(r,dict) and r.get('schema')=='flashnest-native-sampling-before-input-v1':records.append(r)
    require(len(records)==expected,'Missing/extra before-input visibility snapshots')
    seen=set();observations=[]
    for r in records:
        key=(r['row'],r['phase']);require(key not in seen,'Duplicate early visibility snapshot');seen.add(key)
        require(r['cropSHA256'] in pngs,'Missing exact before-input screenshot')
        with Image.open(pngs[r['cropSHA256']]) as image:
            bounds=green_bounds(image) # SAME existing final verifier predicate/threshold.
        observations.append({'row':r['row'],'phase':r['phase'],'greenBounds':bounds,'cropSHA256':r['cropSHA256']})
    return {'earlyVisibilityOnly':True,'nativeAcceptance':False,'observedPhases':len(records),'observations':observations}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--attachments',required=True);p.add_argument('--expected-phases',type=int,choices=(6,66),required=True);p.add_argument('--output',required=True);a=p.parse_args()
    try:report=check(a.attachments,a.expected_phases);code=0
    except Exception as e:report={'earlyVisibilityOnly':True,'nativeAcceptance':False,'error':str(e)};code=1
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));raise SystemExit(code)
if __name__=='__main__':main()
