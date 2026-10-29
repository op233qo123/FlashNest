#!/usr/bin/env python3
"""Preserve an exact historical failed run as a negative, never native acceptance."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image
from verify_results import green_bounds,require

def verify(packet):
    p=Path(packet);manifest=json.loads((p/'manifest.json').read_text())
    require(manifest['historicalRunStatus']=='failed' and manifest['nativeAcceptance'] is False and manifest['knownNegativeOnly'] is True,'Historical failure must not become acceptance')
    require(set(manifest['files'])=={'snapshot.json','canvas.png','expected-identities.json','staging-provenance.json'},'Historical packet file selection differs')
    for name,info in manifest['files'].items():
        f=p/name;require(not f.is_symlink() and f.stat().st_size==info['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==info['sha256'],'Historical evidence bytes differ')
    snap=json.loads((p/'snapshot.json').read_text());state=snap['before'];m=state['measurement'];identity=json.loads((p/'expected-identities.json').read_text())['baseline'];provenance=json.loads((p/'staging-provenance.json').read_text())
    require(state['identity']==identity and identity['stagingProvenanceSHA256']==manifest['files']['staging-provenance.json']['sha256'],'Historical external source identity differs')
    require(provenance['gateOffAppFiles']['App/Resources/Web/shell.js']=='d523ee88178038b5f7bd12fad1e5bb54c7c6c0cc662b5cfb3bf331a0bff77ddd','Historical automatic shell changed')
    require(identity['runtimeInventorySHA256']=='25d4453b0375349e55b9f63f609bd129d6a3549e1da792e811f0e5d121247e90','Wrong historical sampling runtime')
    require(snap['arm']=='baseline' and snap['rendererPolicy']=='automatic' and snap['phase']=='portrait' and state['screenScale']==2 and state['os']=='18.2','Historical scope differs')
    require(m['renderer']=='wgpu-webgl' and m['contextLost'] is True and m['gl']==[0,0],'Pinned known context-loss negative absent')
    require(snap['cropSHA256']==manifest['files']['canvas.png']['sha256'],'Historical exact crop differs')
    absent=False
    with Image.open(p/'canvas.png') as image:
        try:green_bounds(image)
        except AssertionError:absent=True
    require(absent,'Historical negative unexpectedly has required vector')
    return {'knownNegativeOnly':True,'nativeAcceptance':False,'historicalRunStatus':'failed','sourceRun':manifest['sourceRun'],'contextLossAndMissingVectorConfirmed':True,'legacyPolicyUnmodified':True,'packetManifestSHA256':hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest()}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--packet',required=True);a.add_argument('--output',required=True);args=a.parse_args();r=verify(args.packet);Path(args.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
