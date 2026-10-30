#!/usr/bin/env python3
"""Pin observed candidate build outputs before actual focused browser execution."""
import argparse,hashlib,json,os
from pathlib import Path
from check_contract import ROOT,check,digest
from check_pipeline import check as check_pipeline
from derive_engine_flavors import derive
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
lock=check(ROOT,'engine');pipeline=check_pipeline();candidate=a.candidate.resolve();baseline=ROOT/'staged-engine'
def inventory(root):return {str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()}
receipt=json.loads((candidate/'provenance.json').read_text());identity=hashlib.sha256(json.dumps(lock['modifiedSourceFiles'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert receipt['sourceSetSHA256']==identity and receipt['sourceLockSHA256']==digest(ROOT/'source-lock.json')
assert receipt['run']['GITHUB_RUN_ID']==os.environ['GITHUB_RUN_ID'] and receipt['run']['GITHUB_SHA']==os.environ['GITHUB_SHA']
assert receipt['nativeAcceptance'] is False and receipt['runtimeValidated'] is False
for root in (baseline,candidate):
 inv=json.loads((root/'runtime-files.json').read_text());assert inventory(root/'runtime')=={p:r['sha256']for p,r in inv.items()}
 for p,r in inv.items():assert (root/'runtime'/p).stat().st_size==r['bytes']
base_lock=json.loads((ROOT/'validation-lock.json').read_text());old=json.loads((baseline/'provenance.json').read_text());assert digest(baseline/'provenance.json')==base_lock['engine']['provenanceSHA256'];assert old['run']['GITHUB_RUN_ID']==str(base_lock['engine']['runID'])
contract=json.loads((ROOT/'browser/contract.template.json').read_text());assert contract['dispatchAllowed'] is False
contract['dispatchAllowed']=True;contract['reason']='Explicitly authorized focused browser job; exact current build receipt and original baseline mirror verified; no native acceptance'
for arm,root,archive in [('baseline',baseline,base_lock['engine']['sha256']),('candidate',candidate,None)]:
 flavors=derive(root,archive);contract['runtimes'][arm]={'runID':int(json.loads((root/'provenance.json').read_text())['run']['GITHUB_RUN_ID']),'files':inventory(root/'runtime'),'selectedWasmSHA256':flavors['flavors']['extensions']['sha256'],'flavorProof':flavors}
contract['fixtures']=inventory(ROOT/'browser-fixtures');assert contract['fixtures']==pipeline['browserFixtures'];assert not a.output.exists();a.output.write_text(json.dumps(contract,sort_keys=True,indent=2)+'\n');print('Pinned both complete runtimes, compiled loader/extension WASM identity and exact public fixtures')
