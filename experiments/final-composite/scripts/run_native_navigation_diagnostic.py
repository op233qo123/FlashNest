#!/usr/bin/env python3
"""Single existing navigation method with retained synthetic timeout evidence, never acceptance."""
import importlib.util,json,shutil,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
SELECTOR='FlashNestSamplingUITests/NativeSamplingUITests/testActualInitialRedirectAndNavigationFailure'
MAX_SECONDS=1800

def load_runner():
    spec=importlib.util.spec_from_file_location('reviewed_native_runner',ROOT/'validation-harness/native-composite-runner/run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def execute_navigation(runner,module):
    runner.preflight() # Exact source/runtime/tool checks; never executes full selection.
    b=runner.binding;identities={};arms={};overlays={}
    candidate_string={p:r['sha256'] for p,r in runner.candidate_map.items()}
    for arm in ('candidate',):
        app=runner.copy_app('navigation-diagnostic-candidate',runner.args.candidate_engine/'runtime',candidate_string)
        module.dump(app/'NATIVE_VALIDATION_COPY.json',{'disposable':True,'sdk':'iphonesimulator'})
        repin=b['samplingAppManifests'][arm];repin_path=(runner.args.binding.parent/repin['path']).resolve()
        module.require(module.sha(repin_path)==repin['sha256'],'Per-arm reviewed App manifest differs')
        inv=module.sha(app/'runtime.files.json');freeze=runner.stage/(arm+'-freeze.json')
        module.dump(freeze,{'frozen':True,'releaseEquivalent':True,'runtimeInventorySHA256':inv,'approvedAppManifestSHA256':repin['sha256']})
        args=[sys.executable,module.SAMPLING/'scripts/prepare_overlay.py','--app',app,'--arm',arm,
            '--runtime-inventory-sha256',inv,'--approved-app-manifest',repin_path,'--approved-app-manifest-sha256',repin['sha256']]
        args+=['--candidate-freeze',freeze]
        runner.command(args,'navigation-'+arm+'-stage',timeout=120)
        target=app/'NativeSamplingValidation/UITests/NativeSamplingUITests.swift';original=target.read_bytes()
        anchor=b'        try attachJSON(last, name: "sampling-timeout"); throw Failure.invalid("Bounded native observation deadline")'
        replacement=b'        let diagnosticData = try JSONSerialization.data(withJSONObject: last, options: [.sortedKeys])\n        if diagnosticData.count <= 131072, let diagnosticText = String(data: diagnosticData, encoding: .utf8) { print("FLASHNEST_SYNTHETIC_TIMEOUT_JSON:" + diagnosticText) }\n'+anchor
        module.require(original==(module.SAMPLING/'UITests/NativeSamplingUITests.swift').read_bytes(),'Exact reviewed original UITests required')
        module.require(original.count(anchor)==1,'Exact original timeout anchor required')
        app_before=module.inventory(app/'App');changed=original.replace(anchor,replacement,1)
        module.require(changed.replace(replacement,anchor,1)==original,'Original UITest exact inverse required')
        target.write_bytes(changed);module.require(module.inventory(app/'App')==app_before,'Synthetic log hook altered staged App')
        fixture=app/'NativeSamplingValidation/SamplingFixtures/showAll-center.swf'
        module.require(module.sha(fixture)==module.sha(module.SAMPLING/'fixtures/showAll-center.swf'),'Exact synthetic fixture required')
        overlays[arm]={'originalSHA256':module.hashlib.sha256(original).hexdigest(),'stagedSHA256':module.sha(target),
            'fixtureSHA256':module.sha(fixture),'exactInverseVerified':True,'extraDiagnosticOverlayAppChanged':False,'timeoutLogMaximumBytes':131072}
        identities[arm]=json.loads((app/'NativeSamplingValidation/SamplingIdentity.json').read_text())
        module.require(identities[arm]['arm']==arm,'Staged identity arm differs')
        shutil.copyfile(app/'NativeSamplingValidation/staging-provenance.json',runner.out/(arm+'-staging-provenance.json'))
        arms[arm]=(app,runner.project(app,'navigation-'+arm,'FlashNestSamplingUI'))
    # Candidate source identity is frozen BEFORE the runtime launches.
    module.dump(runner.out/'navigation-expected-identities.json',identities)
    module.dump(runner.out/'navigation-test-overlay.json',{'diagnosticOnly':True,'nativeAcceptance':False,'arms':overlays})
    cfg=module.lane('navigation-diagnostic','FlashNestSamplingUI',[SELECTOR],900)
    module.require(cfg['expectedCount']==1 and cfg['selectors']==[SELECTOR],'Exactly one original diagnostic method')
    runner.lanes['navigation-diagnostic']=cfg;module.dump(runner.out/'navigation-selection.json',cfg)
    errors={};device=runner.devices['2']
    for arm,(app,project) in arms.items():
        name='navigation-'+arm
        try:
            runner.reset(device,name) # Verified exact iOS18.2 shutdown/erase/boot, never reuse failed state.
            runner.test(app,project,device,'navigation-diagnostic',name)
        except Exception as exc:
            errors[arm]=str(exc) # Preserve the original single-method failure.
            module.dump(runner.out/'navigation-execution-errors.json',errors)
    module.require(module.inventory(runner.args.app)==b['appFiles'],'Immutable candidate input changed')
    runner.check_runtime(runner.args.candidate_engine/'runtime',runner.candidate_map)
    module.dump(runner.out/'navigation-execution-errors.json',errors)
    if errors:raise ValueError('Navigation XCTest execution errors: '+json.dumps(errors,sort_keys=True))
    module.require(len(runner.results)==1 and {r['runName']:r['tests'] for r in runner.results}=={'navigation-candidate':1},'Exactly one original navigation method required')

def main():
    lock=json.loads((ROOT/'validation-lock.json').read_text())
    if lock.get('dispatchAllowed') is not True or lock.get('diagnosticOnly') is not True:raise ValueError('Explicit diagnostic-only binding required')
    module=load_runner();out=ROOT/'native-navigation-execution/results';final=ROOT/'evidence/native-navigation-diagnostic'
    module.require(not out.exists() and not out.with_name('results-staging').exists() and not final.exists(),'Fresh outputs required; inspect uncertain previous execution')
    args=SimpleNamespace(app=ROOT/'validation-app',candidate_engine=ROOT/'staged-engine',baseline=ROOT/'baseline-bundle',binding=ROOT/'validation-bindings/native-binding.json',output=out)
    runner=module.Runner(args);error=None;deadline=time.monotonic()+MAX_SECONDS;original_command=runner.command
    def bounded(argv,name,cwd=None,timeout=1200,allowed=(0,)):
        remaining=deadline-time.monotonic();module.require(remaining>0,'Navigation diagnostic total deadline expired')
        return original_command(argv,name,cwd,min(timeout,remaining),allowed)
    runner.command=bounded
    def timed_out(_signum,_frame):raise TimeoutError('Navigation diagnostic exceeded1800 seconds')
    old=signal.signal(signal.SIGALRM,timed_out);signal.alarm(MAX_SECONDS)
    try:execute_navigation(runner,module)
    except Exception as exc:error=exc
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old);observation=None;verification_error=None
        try:
            expected=json.loads((out/'navigation-expected-identities.json').read_text())['candidate']
            records=[]
            for line in (out/'navigation-candidate.log').read_text().splitlines():
                marker='FLASHNEST_SYNTHETIC_TIMEOUT_JSON:'
                if marker not in line:continue
                raw=line.split(marker,1)[1];module.require(len(raw.encode())<=131072,'Oversized timeout record')
                value=json.loads(raw);module.require(value.get('identity')==expected,'Timeout source identity mismatch');records.append(value)
            module.require(len(records)<=1,'Unexpected duplicate timeout records')
            observation={'diagnosticOnly':True,'nativeAcceptance':False,'timeoutSnapshots':records}
            module.dump(out/'navigation-timeout-evidence.json',observation)
            module.require(not records or error is not None,'Timeout record cannot be reported as passing XCTest')
        except Exception as exc:
            verification_error=str(exc)
            module.dump(out/'navigation-timeout-evidence-error.json',{'error':verification_error,'diagnosticOnly':True,'nativeAcceptance':False})
            if error is None:error=exc
        module.dump(out/'native-navigation-diagnostic.json',{'diagnosticOnly':True,'nativeAcceptance':False,'ipaBuilt':False,
            'selector':SELECTOR,'expectedMethods':1,'expectedArms':['candidate'],'requestedDPR':2,
            'observationPassed':error is None,'error':str(error) if error else None,'observationVerificationError':verification_error,
            'completedLanes':runner.results,'limitation':'One unchanged initial redirect/navigation failure method; original30s state assertion and900s XCTest bound remain; timeout log is synthetic evidence only, not full166/IPA acceptance.'})
        module.require(not (out/'native-acceptance.json').exists(),'Diagnostic must not emit final acceptance')
        runner.budget();final.parent.mkdir(exist_ok=True);shutil.copytree(out,final)
    if error:raise SystemExit('Navigation diagnostic failed; complete bounded evidence retained: '+str(error))
    print('Navigation diagnostic healthy; NOT full native acceptance')
if __name__=='__main__':main()
