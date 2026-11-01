#!/usr/bin/env python3
"""Exact diagnostic source reconstruction plus one verified experimental runtime."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE='cc6c4bf285a201d9c1a827140662c54606027d10'
SOURCE='9bc000e37695696f2427b25fe08efe4993bf22e5'
CASE='c4cad276f1a79caffd012bcfcb6eb260a9e3492f'
RECIPE='experiments/longrun-ipa-156-build23'
CASE_RECIPE='experiments/case-compatible-assets-build23'
CASE_INPUT_SHA='8c7b6aafcbcfbfa961d24c645f8d9e290a6ea5407b7c8d9948d879a6800b911c'
def need(x,message):
 if not x:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,sort_keys=True,indent=2)+'\n')
def inventory(root):
 out={}
 for p in sorted(Path(root).rglob('*')):
  need(not p.is_symlink(),'Source symlink forbidden')
  if p.is_file():out[p.relative_to(root).as_posix()]=sha(p.read_bytes())
 return out
def git_head(p):return subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def config():
 c=read(ROOT/'inputs.json');need(c['caseCommit']==CASE and c['baselineCommit']==BASE and c['sourceCommit']==SOURCE,'Recipe lineage mismatch')
 need(c['ipaBuildAllowed'] is True and c['runtimeChanged'] is True,'Candidate integration not declared')
 actual=inventory(ROOT);need({p:h for p,h in actual.items() if p!='inputs.json'}==c['recipeFiles'],'Recipe closure mismatch')
 need(sha((ROOT/'case-inputs-reference.json').read_bytes())==CASE_INPUT_SHA,'Case input reference changed')
 need(set(read(ROOT/'resource-overlay.json'))=={'App/Resources/Web/Ruffle-MODIFICATIONS.md','App/Resources/Web/licenses.manifest.json'},'Notice-only overlay scope')
 need(inventory(ROOT/'overlay')=={p:r['after'] for p,r in read(ROOT/'resource-overlay.json').items()},'Notice overlay mismatch')
 need(sha((ROOT/'candidate-runtime-reference.json').read_bytes())=='c449305e9ee292e4d2d7d255163e2fdf46ad5dac80dd41f9eab4c8236e7e49c6','Candidate runtime lock bytes')
 runtime=read(ROOT/'candidate-runtime-reference.json')
 need(runtime['sourceCommit']=='3b0ab52a334336e6e6474e840e9c487e3f666f1d' and runtime['runID']=='41318527222' and runtime['ipaBuilt'] is False and runtime['runtimeAccepted'] is False,'Candidate producer identity/claims')
 return c
def inherited(baseline):
 c=read(ROOT/'case-inputs-reference.json');need(git_head(baseline)==BASE,'Baseline checkout identity')
 raw=(baseline/RECIPE/'inputs.json').read_bytes();need(sha(raw)==c['baselineInputsSHA256'],'Baseline input identity')
 x=json.loads(raw);original=dict(x['baselineAppFiles']);original.update({p:r['after'] for p,r in x['overlay'].items()})
 expected=dict(original)
 for p,r in c['overlay'].items():need(expected[p]==r['before'],'Server preimage mismatch');expected[p]=r['after']
 return x,original,expected

def effective_inventory(case_expected):
 expected={p:h for p,h in case_expected.items() if not p.startswith('App/Resources/Web/runtime/')}
 runtime=read(ROOT/'candidate-runtime-reference.json')['runtimeFiles'];need(len(runtime)==12,'Candidate runtime closure')
 expected.update({'App/Resources/Web/runtime/'+p:h for p,h in runtime.items()})
 for p,r in read(ROOT/'resource-overlay.json').items():
  need(case_expected[p]==r['before'],'Notice preimage mismatch');expected[p]=r['after']
 cfg=read(ROOT/'inputs.json')
 for p,h in cfg['additionalFiles'].items():need(p.startswith('Tests/') and p not in expected,'Test-only addition scope');expected[p]=h
 return expected,runtime

def verify(app,expected):
 for name,digest in expected.items():
  p=app/name;need(p.is_file() and not p.is_symlink() and sha(p.read_bytes())==digest,'Source changed: '+name)
 actual=inventory(app/'App');wanted={p[4:]:h for p,h in expected.items() if p.startswith('App/')}
 if 'Info.plist' in actual and 'Info.plist' not in wanted:
  raw=(app/'App/Info.plist').read_bytes();anchor=b'<key>CFBundleVersion</key>\n\t<string>23</string>'
  need(raw.count(anchor)==1 and sha(raw.replace(anchor,b'<key>CFBundleVersion</key>\n\t<string>19</string>'))=='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f','Generated Info.plist differs');del actual['Info.plist']
 need(actual==wanted,'App closure changed')
 for folder in ('Tests','UITests'):
  need(inventory(app/folder)=={p[len(folder)+1:]:h for p,h in expected.items() if p.startswith(folder+'/')},'Test source closure differs')

def validate_stage(app,receipt,baseline):
 cfg=config();s=read(receipt);x,original,case_expected=inherited(baseline);effective,runtime=effective_inventory(case_expected)
 need(s['baselineCommit']==BASE and s['sourceCommit']==SOURCE and s['caseCommit']==CASE,'Stage lineage')
 need(s['caseSourceFiles']==case_expected and s['effectiveSourceFiles']==effective and s['runtimeFiles']==runtime,'Stage source inventory')
 need(s['recipeFiles']==cfg['recipeFiles'] and s['additionalNativeTests']==cfg['additionalNativeTests'] and s['additionalTestSourceFiles']==cfg['additionalTestSourceFiles'],'Stage recipe/test inventory')
 need(s['head']==os.environ.get('GITHUB_SHA') and s['runID']==os.environ.get('GITHUB_RUN_ID'),'Stage current run')
 need(s['runtimeChanged'] is True and s['diagnosticOptInDefault'] is False and s['ipaBuilt'] is False and s['physicalDeviceCertified'] is False,'Stage claim mismatch')
 parent=Path(receipt).parent
 need(sha((parent/'case-staging.json').read_bytes())==s['caseStagingSHA256'],'Case staging proof changed')
 cadence=(parent/'cadence-inputs.json').read_bytes();need(sha(cadence)==s['cadenceInputsSHA256'],'Cadence input proof changed')
 cadence=json.loads(cadence);need(cadence['runtimeFiles']==runtime and cadence['head']==s['head'] and cadence['runID']==s['runID'],'Cadence current runtime/source mismatch')
 reuse=read(parent/'engine-reuse.json')
 need(sha((Path(receipt).parent/'engine-reuse.json').read_bytes())==s['engineReuseSHA256'] and reuse['runtimeFiles']==runtime,'Engine reuse proof changed')
 need(reuse['consumerHead']==s['head'] and reuse['consumerRunID']==s['runID'] and reuse['engineBuildExecutedThisRun'] is False,'Engine reuse provenance')
 verify(app,effective);return s,effective,x

def stage(baseline,source,case,archive,metadata,output):
 cfg=config();baseline=baseline.resolve();source=source.resolve();case=case.resolve();output=output.resolve()
 need(git_head(case)==CASE and git_head(source)==SOURCE,'Frozen case/source checkout identity')
 case_recipe=case/CASE_RECIPE
 need((case_recipe/'inputs.json').read_bytes()==(ROOT/'case-inputs-reference.json').read_bytes(),'Case recipe manifest differs')
 subprocess.run(['python3',str(case_recipe/'experiment.py'),'stage','--baseline-checkout',str(baseline),'--source-checkout',str(source),'--output',str(output)],check=True)
 x,original,case_expected=inherited(baseline);app=output/'app';prior=read(output/'case-staging.json');need(prior['effectiveSourceFiles']==case_expected and inventory(app)==case_expected,'Case source reconstruction mismatch')
 helper=case/'experiments/loader-unload-replay/reuse_engine.py'
 need(sha(helper.read_bytes())==cfg['reuseHelperSHA256'],'Frozen reuse helper differs')
 reuse=module('frozen_unload_reuse',helper)
 reuse.reuse(archive,metadata,case/'experiments/loader-unload-fix',output/'candidate-runtime',output/'candidate-runtime-lock.json',output/'engine-reuse.json',os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID'])
 need((output/'candidate-runtime-lock.json').read_bytes()==(ROOT/'candidate-runtime-reference.json').read_bytes(),'Actual candidate lock differs')
 shutil.rmtree(app/'App/Resources/Web/runtime');shutil.copytree(output/'candidate-runtime',app/'App/Resources/Web/runtime')
 for p in read(ROOT/'resource-overlay.json'):(app/p).write_bytes((ROOT/'overlay'/p).read_bytes())
 with tempfile.TemporaryDirectory() as temp:
  temp=Path(temp);generated=temp/'Tests/UnloadWKSmokeTests.swift';manifest=temp/'source-manifest.json'
  subprocess.run(['python3',str(ROOT/'native-probe/generate_native_probe.py'),'--probe-root',str(case/'experiments/loader-unload-fix/probe'),'--runtime-lock',str(ROOT/'candidate-runtime-reference.json'),'--output-swift',str(generated),'--receipt',str(manifest)],check=True)
  need(generated.read_bytes()==(ROOT/'native-probe/UnloadWKSmokeTests.swift').read_bytes() and manifest.read_bytes()==(ROOT/'native-probe/source-manifest.json').read_bytes(),'Native probe generation identity mismatch')
 for p,h in cfg['additionalFiles'].items():
  src=ROOT/'native-probe'/Path(p).name;need(sha(src.read_bytes())==h,'Additional test source mismatch');dest=app/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(src.read_bytes())
 effective,runtime=effective_inventory(case_expected);need(inventory(app)==effective,'Unexpected staged source closure')
 write(output/'cadence-inputs.json',{'schema':'candidate-cadence-runtime-v1','runtimeFiles':runtime,'candidateRuntimeLockSHA256':sha((ROOT/'candidate-runtime-reference.json').read_bytes()),'head':os.environ['GITHUB_SHA'],'runID':os.environ['GITHUB_RUN_ID']})
 s={'baselineCommit':BASE,'sourceCommit':SOURCE,'caseCommit':CASE,'baselineSourceFiles':original,'caseSourceFiles':case_expected,'effectiveSourceFiles':effective,'runtimeFiles':runtime,'recipeFiles':cfg['recipeFiles'],'additionalNativeTests':cfg['additionalNativeTests'],'additionalTestSourceFiles':cfg['additionalTestSourceFiles'],'engineReuseSHA256':sha((output/'engine-reuse.json').read_bytes()),'caseStagingSHA256':sha((output/'case-staging.json').read_bytes()),'cadenceInputsSHA256':sha((output/'cadence-inputs.json').read_bytes()),'runtimeChanged':True,'diagnosticOptInDefault':False,'ipaBuilt':False,'fullGatePassed':False,'physicalDeviceCertified':False,'speedRootCauseEstablished':False,'head':os.environ['GITHUB_SHA'],'runID':os.environ['GITHUB_RUN_ID']}
 write(output/'unload-staging.json',s);validate_stage(app,output/'unload-staging.json',baseline)
 print('PASS exact diagnostic case-compatible source with candidate runtime and test-only native smoke')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','verify','preflight'])
 for n in ['baseline-checkout','source-checkout','case-checkout','engine-archive','engine-metadata','output']:p.add_argument('--'+n,type=Path)
 a=p.parse_args()
 if a.action=='preflight':config()
 elif a.action=='stage':stage(a.baseline_checkout,a.source_checkout,a.case_checkout,a.engine_archive,a.engine_metadata,a.output)
 else:validate_stage(a.output/'app',a.output/'unload-staging.json',a.baseline_checkout)
