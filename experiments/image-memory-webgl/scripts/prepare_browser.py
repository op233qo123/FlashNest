#!/usr/bin/env python3
import argparse,hashlib,json,os,pathlib,sys
P=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(P.parent/'lazy-graphic-engine/scripts'));from derive_engine_flavors import derive
p=argparse.ArgumentParser();p.add_argument('engines',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);a=p.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inv(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
b=json.loads((P/'source-binding.json').read_text());c={'schema':'image-memory-webgl-contract-v1','source':{'baselineSourceSetSHA256':sha(a.engines/'baseline/source-before.json'),'candidatePatchSHA256':sha(P/'product.patch'),'candidateReconstructed':True},'runtimes':{},'fixtures':inv(P/'fixtures')}
for arm in ['baseline','candidate']:
 root=a.engines/arm;r=json.loads((root/'provenance.json').read_text());assert r['variant']==arm and r['bindingSHA256']==sha(P/'source-binding.json') and r['patchSHA256']==b['patchSHA256']
 assert r['run']['GITHUB_SHA']==os.environ['GITHUB_SHA'] and r['run']['GITHUB_RUN_ID']==os.environ['GITHUB_RUN_ID']
 assert r['sourceSHA256']==sha(root/'source-before.json') and r['nativeAcceptance'] is False
 files=inv(root/'runtime');expected=json.loads((root/'runtime-files.json').read_text());assert files=={k:v['sha256'] for k,v in expected.items()}
 flavors=derive(root,None);c['runtimes'][arm]={'files':files,'selectedWasmSHA256':flavors['flavors']['extensions']['sha256'],'flavorProof':flavors,'provenanceSHA256':sha(root/'provenance.json')}
old=json.loads((a.engines/'baseline/source-before.json').read_text());new=json.loads((a.engines/'candidate/source-before.json').read_text());assert old.keys()==new.keys()
assert [k for k in old if old[k]!=new[k]]==['render/src/utils.rs'],'Pair differs beyond reviewed product file'
a.output.write_text(json.dumps(c,sort_keys=True,indent=2)+'\n');print('PASS exact engine pair and loader-derived extensions identity')
