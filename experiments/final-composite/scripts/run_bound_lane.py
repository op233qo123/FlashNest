#!/usr/bin/env python3
"""Sequential bounded execution of explicitly frozen argv; no shell interpolation."""
from pathlib import Path
import json,sys,subprocess,os
ROOT=Path(__file__).resolve().parents[1];lane=sys.argv[1]
subprocess.run([sys.executable,str(ROOT/'scripts/validate_binding.py'),lane],check=True)
lock=json.loads((ROOT/'validation-lock.json').read_text());cfg=lock['lanes'][lane]
for command in cfg['commands']+[cfg['verifier']]:
 subprocess.run(command,cwd=ROOT,check=True,timeout=cfg.get('perCommandTimeoutSeconds',1200))
# A lane command exit is insufficient on its own: independent verifier must
# emit this agreed structured receipt from actual xcresult/matrix evidence.
report=json.loads((ROOT/'evidence'/f'{lane}-acceptance.json').read_text())
if report.get('passed') is not True or report.get('skipped',1)!=0:raise SystemExit('Acceptance missing or skipped cases')
if report.get('engineSHA256')!=lock['engine']['sha256']:raise SystemExit('Evidence engine identity mismatch')
selected=report.get('selectedWasmSHA256')
if not isinstance(selected,str) or selected not in lock['engine'].get('wasmSHA256',[]):raise SystemExit('Missing actual fetched WASM identity')
if lane=='browser':
 paths=report.get('realLoaderPaths',[])
 if not paths or any(x not in ['extensions','mvp'] for x in paths) or len(paths)!=len(set(paths)):raise SystemExit('Invalid actual loader-path evidence')
 if report.get('rows')!=cfg['expectedRowsPerExecutedPath']*len(paths) or report.get('shippingSelectionExecuted') is not True:raise SystemExit('Incomplete shipping-path browser coverage')
 if 'mvp' not in paths and report.get('mvpSelectionStatus')!='not-executed-no-supported-route':raise SystemExit('MVP gap not explicitly recorded')
else:
 if report.get('evidenceKind')!='iOS simulator' or report.get('physicalDeviceCertified') is not False:raise SystemExit('Wrong evidence classification')
 policies=report.get('shippingPoliciesWithAllReductions',[])
 if report.get('shippingReductionRequirementMet') is not True or not policies or any(p not in ['automatic','webgl'] for p in policies):raise SystemExit('All-fallback or diagnostic-only rows cannot establish shipping functionality')
 if report.get('shippingDefaultAppliesAllTiers') is not ('automatic' in policies):raise SystemExit('Default policy claim differs from actual native geometry')
print('PASS bound lane; no IPA packaged')
