#!/usr/bin/env python3
"""Final cross-binding on independently verified lane output, not test-process exit."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];lane=sys.argv[1]
assert lane in ('browser','native')
lock=json.loads((ROOT/'validation-lock.json').read_text());assert lock['dispatchAllowed'] is True
report=json.loads((ROOT/'evidence'/f'{lane}-acceptance.json').read_text());engine=lock['engine']
assert report['passed'] is True and type(report['skipped']) is int and report['skipped']==0
assert report['engineSHA256']==engine['sha256'] and report['selectedWasmSHA256'] in engine['wasmSHA256']
if lane=='browser':
 assert report['rows']==290 and report['shippingSelectionExecuted'] is True
 assert report['realLoaderPaths']==[engine['wasmFlavorBySHA256'][report['selectedWasmSHA256']]]
 assert report['verification']['rows']==290 and report['verification']['phases']==870 and report['verification']['trustedClicks']==4350
 assert report['physicalDeviceCertified'] is False
else:
 assert report['evidenceKind']=='iOS simulator' and report['physicalDeviceCertified'] is False
 assert report['nativeMethods']==161 and report['samplingRows']==52 and report['samplingPhases']==156
 assert sum(r['tests'] for r in report['results'])==161
 assert report['shippingReductionRequirementMet'] is True and report['shippingPoliciesWithAllReductions']
 assert set(report['shippingPoliciesWithAllReductions']) <= {'automatic','webgl'}
 assert report['shippingDefaultAppliesAllTiers']==('automatic' in report['shippingPoliciesWithAllReductions'])
 geometry=json.loads((ROOT/'evidence/native/sampling-geometry.json').read_text())
 assert geometry['matrixPassed'] is True and geometry['shippingReductionRequirementMet'] is True
 assert geometry['actualShippingReductionPolicies']==report['shippingPoliciesWithAllReductions']
 assert report['audibleOutputProven'] is False and report['privateProviderReproduced'] is False and report['ipaBuilt'] is False
print('PASS final lane receipt cross-binding',lane)
