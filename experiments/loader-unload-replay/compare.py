#!/usr/bin/env python3
"""Close cross-runtime source/fixture binding after both real probe validations."""
import argparse,hashlib,json,os,pathlib
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--evidence',type=pathlib.Path,required=True);p.add_argument('--recipe',type=pathlib.Path,required=True);a=p.parse_args()
b=json.loads((a.evidence/'baseline.json').read_text());c=json.loads((a.evidence/'candidate.json').read_text());bs=json.loads((a.evidence/'baseline-stage.json').read_text());cs=json.loads((a.evidence/'candidate-stage.json').read_text())
for x,mode in [(b,'baseline'),(c,'candidate')]:
 assert x['validationPassed'] is True and x['applicationPass'] is False
 assert x['expect']==mode and x['head']==os.environ['GITHUB_SHA'] and str(x['runID'])==os.environ['GITHUB_RUN_ID']
 assert x['privateGameInputs'] is False and x['flashReferenceRun'] is False
replay=json.loads((a.recipe/'replay-lock.json').read_text())
assert b['fixtureFiles']==c['fixtureFiles']==replay['fixtureFiles']
for name,h in replay['stableProbeFiles'].items():
 assert sha(a.recipe/'probe'/name)==h and b['sourceFiles'][name]==c['sourceFiles'][name]==h
assert b['engineChanged'] is False and c['engineChanged'] is True
assert b['fixtureFiles']==c['fixtureFiles'] and b['sourceFiles']==c['sourceFiles']
assert b['runtimeFiles']==bs['runtimeFiles'] and c['runtimeFiles']==cs['runtimeFiles']
assert b['selectedWasmSHA256']!=c['selectedWasmSHA256'],'Candidate must execute actual different WASM'
assert cs['consumerHead']==os.environ['GITHUB_SHA'] and cs['consumerRunID']==os.environ['GITHUB_RUN_ID']
assert cs['engineBuildExecutedThisRun'] is False and cs['coreTestExecutionReused'] is True and cs['browserResultsReused'] is False
result={'engineBuildRun':replay['engineBuildRun'],'engineBuildHead':replay['engineBuildHead'],'browserConsumerHead':os.environ['GITHUB_SHA'],'browserConsumerRunID':os.environ['GITHUB_RUN_ID'],'replayLockSHA256':sha(a.recipe/'replay-lock.json'),'fixtureCoverageChanged':False,'engineReference':cs['engineReference'],'engineBuildExecutedThisRun':False,'coreTestsExecutedThisRun':False,'coreTestExecutionReused':True,'browserResultsReused':False,'schema':1,'head':os.environ['GITHUB_SHA'],'runID':os.environ['GITHUB_RUN_ID'],'baselineOutcome':b['mechanismOutcome'],'candidateOutcome':c['mechanismOutcome'],'baselineResultSHA256':sha(a.evidence/'baseline.json'),'candidateResultSHA256':sha(a.evidence/'candidate.json'),'identicalNeutralFixtureFiles':b['fixtureFiles'],'recipeFiles':{f.relative_to(a.recipe).as_posix():sha(f) for f in sorted(a.recipe.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and 'fixtures' not in f.parts},'neutralRegressionPassed':True,'applicationPass':False,'physicalDeviceTested':False,'flashReferenceRun':False,'gpuMemoryReclaimedMeasured':False}
(a.evidence/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS source-bound neutral baseline/candidate regression; not application/iOS acceptance')
