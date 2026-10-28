#!/usr/bin/env python3
"""Bind approved full runtime receipts; does not promote the source or tests."""
import argparse,json,pathlib
from contracts import ROOT,digest,bind,delivered_baseline,verify_baseline_entry
p=argparse.ArgumentParser();p.add_argument('--candidate-artifact',type=pathlib.Path,required=True);p.add_argument('--baseline',type=pathlib.Path,required=True);p.add_argument('--baseline-identity',type=pathlib.Path,required=True);p.add_argument('--expected-provenance-sha256',required=True);p.add_argument('--expected-baseline-identity-sha256',required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
c=a.candidate_artifact;assert digest(c/'provenance.json')==a.expected_provenance_sha256
assert digest(a.baseline_identity)==a.expected_baseline_identity_sha256
provenance=json.loads((c/'provenance.json').read_text());baseline=delivered_baseline(a.baseline_identity)
assert provenance['runtimeInventorySHA256']==digest(c/'runtime-files.json')
assert provenance['dualWasm'] and provenance['jpegxr'] and provenance['wasmOpt']
verify_baseline_entry(baseline)
contract={'schemaVersion':1,'finalComposite':True,'baselineRunID':40614335019,'fixtureManifestSHA256':digest(ROOT/'fixtures/manifest.json'),
'candidate':{'files':json.loads((c/'runtime-files.json').read_text()),'sourceIdentity':provenance['sourceSetSHA256'],'provenanceSHA256':digest(c/'provenance.json')},
'baseline':baseline}
bind(c/'runtime',contract['candidate']);bind(a.baseline,contract['baseline'])
a.out.write_text(json.dumps(contract,indent=2)+'\n');print(digest(a.out))
