#!/usr/bin/env python3
"""Single existing quarter WebGL showAll method with retained restart evidence, never acceptance."""
import importlib.util,json,shutil,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
SELECTOR='FlashNestSamplingUITests/NativeSamplingUITests/testShippingWebGLShowAllQuarter'
MAX_SECONDS=1800

def load_runner():
    spec=importlib.util.spec_from_file_location('reviewed_native_runner',ROOT/'validation-harness/native-composite-runner/run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def load_overlay():
    spec=importlib.util.spec_from_file_location('restart_diagnostic_overlay',ROOT/'validation-harness/native-restart-diagnostic/stage_restart_diagnostic.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def execute_restart(runner,module):
    runner.preflight() # Exact source/runtime/tool checks; never executes full selection.
    b=runner.binding;identities={};arms={};overlays={}
    candidate_string={p:r['sha256'] for p,r in runner.candidate_map.items()}
    for arm in ('candidate',):
        app=runner.copy_app('restart-diagnostic-candidate',runner.args.candidate_engine/'runtime',candidate_string)
        module.dump(app/'NATIVE_VALIDATION_COPY.json',{'disposable':True,'sdk':'iphonesimulator'})
        repin=b['samplingAppManifests'][arm];repin_path=(runner.args.binding.parent/repin['path']).resolve()
        module.require(module.sha(repin_path)==repin['sha256'],'Per-arm reviewed App manifest differs')
        inv=module.sha(app/'runtime.files.json');freeze=runner.stage/(arm+'-freeze.json')
        module.dump(freeze,{'frozen':True,'releaseEquivalent':True,'runtimeInventorySHA256':inv,'approvedAppManifestSHA256':repin['sha256']})
        args=[sys.executable,module.SAMPLING/'scripts/prepare_overlay.py','--app',app,'--arm',arm,
            '--runtime-inventory-sha256',inv,'--approved-app-manifest',repin_path,'--approved-app-manifest-sha256',repin['sha256']]
        args+=['--candidate-freeze',freeze]
        runner.command(args,'restart-'+arm+'-stage',timeout=120)
        hook=load_overlay()
        app_before=module.inventory(app/'App')
        overlays[arm]=hook.apply_overlay(app,module.SAMPLING)
        module.require(overlays[arm].get('exactInverseVerified') is True,'Staged-only exact inverse proof required')
        module.require(module.inventory(app/'App')==app_before,'Restart diagnostic overlay altered App')
        fixture=app/'NativeSamplingValidation/SamplingFixtures/showAll-center.swf'
        module.require(module.sha(fixture)==module.sha(module.SAMPLING/'fixtures/showAll-center.swf'),'Exact synthetic fixture required')
        overlays[arm]['fixtureSHA256']=module.sha(fixture)
        overlays[arm]['extraDiagnosticOverlayAppChanged']=False
        identities[arm]=json.loads((app/'NativeSamplingValidation/SamplingIdentity.json').read_text())
        module.require(identities[arm]['arm']==arm,'Staged identity arm differs')
        shutil.copyfile(app/'NativeSamplingValidation/staging-provenance.json',runner.out/(arm+'-staging-provenance.json'))
        arms[arm]=(app,runner.project(app,'restart-'+arm,'FlashNestSamplingUI'))
    # Candidate source identity is frozen BEFORE the runtime launches.
    module.dump(runner.out/'restart-expected-identities.json',identities)
    module.dump(runner.out/'restart-test-overlay.json',{'diagnosticOnly':True,'nativeAcceptance':False,'arms':overlays})
    cfg=module.lane('restart-diagnostic','FlashNestSamplingUI',[SELECTOR],900)
    module.require(cfg['expectedCount']==1 and cfg['selectors']==[SELECTOR],'Exactly one original diagnostic method')
    runner.lanes['restart-diagnostic']=cfg;module.dump(runner.out/'restart-selection.json',cfg)
    errors={};device=runner.devices['2']
    for arm,(app,project) in arms.items():
        name='restart-'+arm
        try:
            runner.reset(device,name) # Verified exact iOS18.2 shutdown/erase/boot, never reuse failed state.
            runner.test(app,project,device,'restart-diagnostic',name)
        except Exception as exc:
            errors[arm]=str(exc) # Preserve the original single-method failure.
            module.dump(runner.out/'restart-execution-errors.json',errors)
    module.require(module.inventory(runner.args.app)==b['appFiles'],'Immutable candidate input changed')
    runner.check_runtime(runner.args.candidate_engine/'runtime',runner.candidate_map)
    module.dump(runner.out/'restart-execution-errors.json',errors)
    if errors:raise ValueError('Restart XCTest execution errors: '+json.dumps(errors,sort_keys=True))
    module.require(len(runner.results)==1 and {r['runName']:r['tests'] for r in runner.results}=={'restart-candidate':1},'Exactly one original restart method required')

def main():
    lock=json.loads((ROOT/'validation-lock.json').read_text())
    if lock.get('dispatchAllowed') is not True or lock.get('diagnosticOnly') is not True:raise ValueError('Explicit diagnostic-only binding required')
    module=load_runner();out=ROOT/'native-restart-execution/results';final=ROOT/'evidence/native-restart-diagnostic'
    module.require(not out.exists() and not out.with_name('results-staging').exists() and not final.exists(),'Fresh outputs required; inspect uncertain previous execution')
    args=SimpleNamespace(app=ROOT/'validation-app',candidate_engine=ROOT/'staged-engine',baseline=ROOT/'baseline-bundle',binding=ROOT/'validation-bindings/native-binding.json',output=out)
    runner=module.Runner(args);error=None;deadline=time.monotonic()+MAX_SECONDS;original_command=runner.command
    def bounded(argv,name,cwd=None,timeout=1200,allowed=(0,)):
        remaining=deadline-time.monotonic();module.require(remaining>0,'Restart diagnostic total deadline expired')
        return original_command(argv,name,cwd,min(timeout,remaining),allowed)
    runner.command=bounded
    def timed_out(_signum,_frame):raise TimeoutError('Restart diagnostic exceeded1800 seconds')
    old=signal.signal(signal.SIGALRM,timed_out);signal.alarm(MAX_SECONDS)
    try:execute_restart(runner,module)
    except Exception as exc:
        error=exc;module.dump(out/'restart-primary-error.json',{'error':str(exc),'errorType':type(exc).__name__,'nativeAcceptance':False})
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old);observation=None;verification_error=None
        try:
            expected=json.loads((out/'restart-expected-identities.json').read_text())['candidate']
            observation=load_overlay().verify_evidence(out,expected)
            module.require(isinstance(observation,dict),'Structured restart evidence required')
            module.dump(out/'restart-observation-evidence.json',observation)
            module.require(observation.get('diagnosticOnly') is True and observation.get('nativeAcceptance') is False,'Diagnostic evidence scope differs')
            module.require(observation.get('evidenceValid') is True and observation.get('observationComplete') is True,'Restart evidence invalid or incomplete')
            module.require(observation.get('renderHealthCertified') is False,'Restart observation must not certify rendering')
            module.require(type(observation.get('restartPlayAvailable')) is bool,'Explicit observed Play availability required')
            module.require(observation['restartPlayAvailable'] is True or error is not None,'Missing restart Play cannot be reported as passing XCTest')
        except Exception as exc:
            verification_error=str(exc)
            module.dump(out/'restart-observation-evidence-error.json',{'error':verification_error,'diagnosticOnly':True,'nativeAcceptance':False})
            if error is None:error=exc
        module.dump(out/'native-restart-diagnostic.json',{'diagnosticOnly':True,'nativeAcceptance':False,'ipaBuilt':False,
            'renderHealthCertified':False,'restartPlayAvailable':observation.get('restartPlayAvailable') if isinstance(observation,dict) else None,
            'observedFailure':observation.get('hasFailure') if isinstance(observation,dict) else None,
            'selector':SELECTOR,'expectedMethods':1,'expectedArms':['candidate'],'requestedDPR':2,
            'observationPassed':error is None,'error':str(error) if error else None,'observationVerificationError':verification_error,
            'completedLanes':runner.results,'limitation':'One unchanged candidate quarter WebGL showAll method, original three phases and same-player lifecycle; original90s restart Play wait and900s XCTest bound remain. Synthetic failure capture only; not full198 or IPA acceptance.'})
        module.require(not (out/'native-acceptance.json').exists(),'Diagnostic must not emit final acceptance')
        try:
            runner.budget();final.parent.mkdir(exist_ok=True);shutil.copytree(out,final)
        except Exception as exc:
            module.dump(out/'restart-evidence-copy-error.json',{'error':str(exc),'primaryError':str(error) if error else None,'nativeAcceptance':False})
            if error is None:error=exc
    if error:raise SystemExit('Restart diagnostic failed; complete bounded evidence retained: '+str(error))
    print('Restart single-method diagnostic completed; NOT full native acceptance')
if __name__=='__main__':main()
