#!/usr/bin/env python3
"""Two bounded public synthetic CWS transitions, unchanged product/runtime, not acceptance."""
import importlib.util,json,shutil,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
SELECTORS=['FlashNestSamplingUITests/NativeSceneLoaderUITests/test01TinySceneTransition','FlashNestSamplingUITests/NativeSceneLoaderUITests/test02SizedSceneTransition']
TOTAL_SECONDS=1800;METHOD_SECONDS=180;COMPILE_SECONDS=900

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def execute_scene(runner,module):
 runner.preflight();b=runner.binding
 package=ROOT/'validation-harness/native-scene-cws-diagnostic';host_package=ROOT/'validation-harness/native-scene-loader-diagnostic'
 generated=runner.stage/'generated-scene-fixtures';module.require(not generated.exists(),'Fresh public fixture generation required')
 runner.command([sys.executable,package/'generate_fixtures.py','--out',generated],'scene-fixture-generation',timeout=120)
 fixture_manifest=generated/'manifest.json'
 module.require(module.sha(fixture_manifest)==module.sha(package/'fixture-manifest.json') and json.loads(fixture_manifest.read_text())==json.loads((package/'fixture-manifest.json').read_text()),'CI fixture output differs from independently frozen deterministic fixture manifest')
 module.require(sum(p.stat().st_size for p in generated.rglob('*') if p.is_file())<=128*1024*1024,'Generator disk budget exceeded')
 shutil.copyfile(fixture_manifest,runner.out/'scene-fixture-manifest.json')
 candidate_string={p:r['sha256'] for p,r in runner.candidate_map.items()}
 app=runner.copy_app('scene-loader-candidate',runner.args.candidate_engine/'runtime',candidate_string)
 module.dump(app/'NATIVE_VALIDATION_COPY.json',{'disposable':True,'sdk':'iphonesimulator'})
 repin=b['samplingAppManifests']['candidate'];repin_path=(runner.args.binding.parent/repin['path']).resolve()
 module.require(module.sha(repin_path)==repin['sha256'],'Approved candidate manifest differs')
 inv=module.sha(app/'runtime.files.json');freeze=runner.stage/'scene-candidate-freeze.json'
 module.dump(freeze,{'frozen':True,'releaseEquivalent':True,'runtimeInventorySHA256':inv,'approvedAppManifestSHA256':repin['sha256']})
 runner.command([sys.executable,module.SAMPLING/'scripts/prepare_overlay.py','--app',app,'--arm','candidate','--runtime-inventory-sha256',inv,'--approved-app-manifest',repin_path,'--approved-app-manifest-sha256',repin['sha256'],'--candidate-freeze',freeze],'scene-candidate-stage',timeout=120)
 before_app=module.inventory(app/'App');stage=load('scene_host_stage',host_package/'stage_scene_host.py')
 proof=stage.apply_overlay(app,module.SAMPLING,generated,package)
 module.require(proof['exactInverseVerified'] is True and module.inventory(app/'App')==before_app,'Extra scene overlay altered product App')
 module.dump(runner.out/'scene-host-overlay.json',proof)
 identity=json.loads((app/'NativeSamplingValidation/SamplingIdentity.json').read_text())
 module.dump(runner.out/'scene-expected-identity.json',identity)
 shutil.copyfile(app/'NativeSamplingValidation/staging-provenance.json',runner.out/'scene-base-staging-provenance.json')
 module.dump(runner.out/'scene-prelaunch-binding.json',{'diagnosticOnly':True,'nativeAcceptance':False,
  'identitySHA256':module.sha(runner.out/'scene-expected-identity.json'),'fixtureManifestSHA256':module.sha(fixture_manifest),
  'overlayProofSHA256':module.sha(runner.out/'scene-host-overlay.json'),'baseProvenanceSHA256':module.sha(runner.out/'scene-base-staging-provenance.json'),
  'engineSHA256':b['engine']['sha256'],'approvedAppFiles':b['appFiles'],'selectors':SELECTORS,
  'stageHelperSHA256':module.sha(host_package/'stage_scene_host.py'),'verifierSHA256':module.sha(package/'verify_phases.py')})
 cfg=module.lane('scene-loader-controls','FlashNestSamplingUI',SELECTORS,METHOD_SECONDS)
 module.require(cfg['expectedCount']==2 and len(set(SELECTORS))==2,'Exactly two scene cases required')
 runner.lanes['scene-loader-controls']=cfg;module.dump(runner.out/'scene-selection.json',cfg)
 project=runner.project(app,'scene-loader-candidate','FlashNestSamplingUI');device=runner.devices['2'];runner.reset(device,'scene-loader-controls')
 primary=None
 try:runner.test(app,project,device,'scene-loader-controls','scene-loader-controls')
 except Exception as exc:
  primary=exc;module.dump(runner.out/'scene-execution-error.json',{'error':str(exc),'nativeAcceptance':False})
 secondary=None
 try:
  module.require(module.inventory(runner.args.app)==b['appFiles'],'Immutable App input changed')
  runner.check_runtime(runner.args.candidate_engine/'runtime',runner.candidate_map)
  module.require(module.sha(app/'NativeSamplingValidation/Host/SamplingHost.swift')==identity['sceneDiagnostic']['hostSHA256'] and module.sha(app/'NativeSamplingValidation/UITests/NativeSamplingUITests.swift')==identity['sceneDiagnostic']['testsSHA256'],'Executed diagnostic source changed')
 except Exception as exc:
  secondary=exc;module.dump(runner.out/'scene-postcheck-error.json',{'error':str(exc),'primaryError':str(primary) if primary else None,'nativeAcceptance':False})
 if primary is not None:raise primary
 if secondary is not None:raise secondary
 module.require(len(runner.results)==1 and {r['runName']:r['tests'] for r in runner.results}=={'scene-loader-controls':2},'Exactly two real completed cases required')

def bound_command(original,module,deadline,argv,name,cwd=None,timeout=1200,allowed=(0,)):
 remaining=deadline-time.monotonic();module.require(remaining>0,'Scene diagnostic1800s total deadline expired')
 if name=='scene-loader-controls':
  args=list(map(str,argv));module.require(args[:2]==['xcodebuild','test'] and timeout==2*METHOD_SECONDS+300,'Only exact two-case compile/test invocation can use explicit900s budget')
  module.require([a.removeprefix('-only-testing:') for a in args if a.startswith('-only-testing:')]==SELECTORS,'Scene selector drift')
  for flag in ('-default-test-execution-time-allowance','-maximum-test-execution-time-allowance'):
   module.require(args.count(flag)==1 and args[args.index(flag)+1]==str(METHOD_SECONDS),'Method180s limit differs')
  timeout=COMPILE_SECONDS
 return original(argv,name,cwd,min(timeout,remaining),allowed)

def verify_prelaunch(out,module):
 expected=json.loads((out/'scene-prelaunch-binding.json').read_text())
 pairs=[(out/'scene-expected-identity.json','identitySHA256'),(out/'scene-fixture-manifest.json','fixtureManifestSHA256'),(out/'scene-host-overlay.json','overlayProofSHA256'),(out/'scene-base-staging-provenance.json','baseProvenanceSHA256'),(ROOT/'validation-harness/native-scene-loader-diagnostic/stage_scene_host.py','stageHelperSHA256'),(ROOT/'validation-harness/native-scene-cws-diagnostic/verify_phases.py','verifierSHA256')]
 for path,key in pairs:module.require(module.sha(path)==expected[key],'Prelaunch binding changed: '+key)
 module.require(expected.get('diagnosticOnly') is True and expected.get('nativeAcceptance') is False and expected['selectors']==SELECTORS,'Prelaunch scope/selector drift')

def main():
 lock=json.loads((ROOT/'validation-lock.json').read_text())
 if lock.get('dispatchAllowed') is not True or lock.get('diagnosticOnly') is not True:raise ValueError('Explicit scene diagnostic-only binding required')
 module=load('pinned_native_runner',ROOT/'validation-harness/native-composite-runner/run.py')
 out=ROOT/'native-scene-execution/results';final=ROOT/'evidence/native-scene-loader-diagnostic'
 module.require(not out.exists() and not out.with_name('results-staging').exists() and not final.exists(),'Fresh diagnostic output required')
 args=SimpleNamespace(app=ROOT/'validation-app',candidate_engine=ROOT/'staged-engine',baseline=ROOT/'baseline-bundle',binding=ROOT/'validation-bindings/native-binding.json',output=out)
 runner=module.Runner(args);error=None;deadline=time.monotonic()+TOTAL_SECONDS;original=runner.command
 runner.command=lambda argv,name,cwd=None,timeout=1200,allowed=(0,):bound_command(original,module,deadline,argv,name,cwd,timeout,allowed)
 def expire(_signum,_frame):raise TimeoutError('Scene diagnostic exceeded1800 seconds')
 old=signal.signal(signal.SIGALRM,expire);signal.alarm(TOTAL_SECONDS)
 try:execute_scene(runner,module)
 except Exception as exc:
  error=exc;module.dump(out/'scene-primary-error.json',{'error':str(exc),'errorType':type(exc).__name__,'nativeAcceptance':False})
 finally:
  signal.alarm(0);signal.signal(signal.SIGALRM,old);observation=None;verification_error=None
  try:
   verify_prelaunch(out,module)
   expected=json.loads((out/'scene-expected-identity.json').read_text())
   verifier=load('scene_verifier',ROOT/'validation-harness/native-scene-cws-diagnostic/verify_phases.py')
   observation=verifier.verify_native(out,expected,out/'scene-fixture-manifest.json')
   module.require(isinstance(observation,dict),'Structured scene observation required')
   module.dump(out/'scene-observation-verification.json',observation) # Keep partial data before any strict assertion.
   module.require(observation.get('diagnosticOnly') is True and observation.get('nativeAcceptance') is False and observation.get('renderHealthCertified') is False,'Scene diagnostic scope differs')
   module.require(observation.get('evidenceValid') is True and observation.get('transitionComplete') is True,'Scene transition incomplete or invalid; last observed boundary retained')
  except Exception as exc:
   verification_error=str(exc);module.dump(out/'scene-observation-verification-error.json',{'error':verification_error,'nativeAcceptance':False})
   if error is None:error=exc
  module.dump(out/'native-scene-loader-diagnostic.json',{'diagnosticOnly':True,'nativeAcceptance':False,'physicalDeviceCertified':False,'renderHealthCertified':False,'ipaBuilt':False,
   'cases':['tiny','sized'],'selectors':SELECTORS,'methodSeconds':METHOD_SECONDS,'activeObservationSeconds':120,'maximumSnapshotsPerCase':32,
   'compileInclusiveCommandSeconds':COMPILE_SECONDS,'maximumTotalSeconds':TOTAL_SECONDS,'requestedPolicy':'automatic','requestedSampling':'original','requestedDPR':2,
   'diagnosticPassed':error is None,'error':str(error) if error else None,'verificationError':verification_error,'completedLanes':runner.results,
   'limitations':['Public synthetic DefineBinaryData CWS only, not the private game or equal RAM pressure','Single same-WK Loader unload→new; unload does not prove reclamation','ArrayBuffer fulfillment is observable; Rust copy/decompression intervals are not','Web process termination does not identify OOM','No full198 acceptance or production repair']})
  module.require(not (out/'native-acceptance.json').exists(),'Diagnostic cannot emit full native acceptance')
  try:runner.budget();final.parent.mkdir(exist_ok=True);shutil.copytree(out,final)
  except Exception as exc:
   module.dump(out/'scene-evidence-copy-error.json',{'error':str(exc),'primaryError':str(error) if error else None,'nativeAcceptance':False})
   if error is None:error=exc
 if error:raise SystemExit('Scene diagnostic failed/incomplete; bounded evidence retained: '+str(error))
 print('Two synthetic scene transitions observed; NOT private-game/full-native/IPA acceptance')
if __name__=='__main__':main()
