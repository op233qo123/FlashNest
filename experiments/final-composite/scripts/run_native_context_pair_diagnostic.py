#!/usr/bin/env python3
"""Two isolated runtime/policy arms, bounded context+rotation diagnosis, never acceptance."""
import importlib.util,json,shutil,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
SELECTOR='FlashNestSamplingUITests/NativeSamplingUITests/testDiagnosticContextPairWindowAndRotation'
MAX_SECONDS=1800

def load_runner():
    spec=importlib.util.spec_from_file_location('reviewed_native_runner',ROOT/'validation-harness/native-composite-runner/run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def execute_pair(runner,module):
    runner.preflight() # Exact source/runtime/tool checks; never executes full selection.
    b=runner.binding;identities={};arms={};overlays={}
    candidate_string={p:r['sha256'] for p,r in runner.candidate_map.items()}
    for arm in ('baseline','candidate'):
        runtime=runner.args.baseline/'sampling/runtime' if arm=='baseline' else runner.args.candidate_engine/'runtime'
        mapping=runner.sampling_map if arm=='baseline' else candidate_string
        app=runner.copy_app('context-pair-'+arm,runtime,mapping)
        if arm=='baseline':
            shutil.copyfile(runner.args.baseline/'sampling/runtime.files.json',app/'runtime.files.json')
            module.dump(runner.out/'baseline-legacy-source-restore.json',module.restore_legacy_source(app))
            runner.metadata_overlay(app,runner.args.baseline/'sampling/app-metadata',b['samplingBaselineMetadata'])
        module.dump(app/'NATIVE_VALIDATION_COPY.json',{'disposable':True,'sdk':'iphonesimulator'})
        repin=b['samplingAppManifests'][arm];repin_path=(runner.args.binding.parent/repin['path']).resolve()
        module.require(module.sha(repin_path)==repin['sha256'],'Per-arm reviewed App manifest differs')
        inv=module.sha(app/'runtime.files.json');freeze=runner.stage/(arm+'-freeze.json')
        module.dump(freeze,{'frozen':True,'releaseEquivalent':True,'runtimeInventorySHA256':inv,'approvedAppManifestSHA256':repin['sha256']})
        args=[sys.executable,module.SAMPLING/'scripts/prepare_overlay.py','--app',app,'--arm',arm,
            '--runtime-inventory-sha256',inv,'--approved-app-manifest',repin_path,'--approved-app-manifest-sha256',repin['sha256']]
        if arm=='candidate':args+=['--candidate-freeze',freeze]
        runner.command(args,'pair-'+arm+'-stage',timeout=120)
        target=app/'NativeSamplingValidation/UITests/NativeSamplingUITests.swift';original=target.read_bytes()
        fragment_path=ROOT/'diagnostics/native-context-pair/ContextPair.fragment.swift';fragment=fragment_path.read_bytes();anchor=b'    private func matrix('
        module.require(original==(module.SAMPLING/'UITests/NativeSamplingUITests.swift').read_bytes(),'Exact frozen original UITests required')
        app_before=module.inventory(app/'App')
        module.require(original.count(anchor)==1 and fragment not in original,'Exact staged-only insertion anchor required')
        changed=original.replace(anchor,fragment+anchor,1)
        module.require(changed.replace(fragment,b'',1)==original,'All original UITests must restore exactly')
        target.write_bytes(changed);module.require(module.inventory(app/'App')==app_before,'Extra method altered staged App')
        fixture=app/'NativeSamplingValidation/SamplingFixtures/noScale-center.swf'
        module.require(module.sha(fixture)=='49239943a9dc7388b171cc0d3fecf249a7fcac1ec1c277bfc8d91ee8cb7eac6e','Exact synthetic noScale fixture differs')
        overlays[arm]={'originalSHA256':module.hashlib.sha256(original).hexdigest(),'fragmentSHA256':module.sha(fragment_path),
            'stagedSHA256':module.sha(target),'fixtureSHA256':module.sha(fixture),'exactInverseVerified':True,'extraDiagnosticOverlayAppChanged':False}
        identities[arm]=json.loads((app/'NativeSamplingValidation/SamplingIdentity.json').read_text())
        module.require(identities[arm]['arm']==arm,'Staged identity arm differs')
        shutil.copyfile(app/'NativeSamplingValidation/staging-provenance.json',runner.out/(arm+'-staging-provenance.json'))
        arms[arm]=(app,runner.project(app,'pair-'+arm,'FlashNestSamplingUI'))
    # Both source identities are frozen BEFORE either runtime launches.
    module.dump(runner.out/'pair-expected-identities.json',identities)
    module.dump(runner.out/'pair-test-overlay.json',{'diagnosticOnly':True,'nativeAcceptance':False,'arms':overlays})
    cfg=module.lane('context-pair','FlashNestSamplingUI',[SELECTOR],900)
    module.require(cfg['expectedCount']==1 and cfg['selectors']==[SELECTOR],'Exactly one diagnostic method per arm')
    runner.lanes['context-pair']=cfg;module.dump(runner.out/'pair-selection.json',cfg)
    errors={};device=runner.devices['2']
    for arm,(app,project) in arms.items():
        name='pair-'+arm
        try:
            runner.reset(device,name) # Verified exact iOS18.2 shutdown/erase/boot, never reuse failed state.
            runner.test(app,project,device,'context-pair',name)
        except Exception as exc:
            errors[arm]=str(exc) # Preserve first arm failure while collecting the second bounded control.
            module.dump(runner.out/'pair-execution-errors.json',errors)
    module.require(module.inventory(runner.args.app)==b['appFiles'],'Immutable candidate input changed')
    runner.check_runtime(runner.args.candidate_engine/'runtime',runner.candidate_map)
    module.dump(runner.out/'pair-execution-errors.json',errors)
    if errors:raise ValueError('Paired XCTest execution errors: '+json.dumps(errors,sort_keys=True))
    module.require(len(runner.results)==2 and {r['runName']:r['tests'] for r in runner.results}=={'pair-baseline':1,'pair-candidate':1},'Exactly two separate arm executions required')

def main():
    lock=json.loads((ROOT/'validation-lock.json').read_text())
    if lock.get('dispatchAllowed') is not True or lock.get('diagnosticOnly') is not True:raise ValueError('Explicit diagnostic-only binding required')
    module=load_runner();out=ROOT/'native-context-pair-execution/results';final=ROOT/'evidence/native-context-pair-diagnostic'
    module.require(not out.exists() and not out.with_name('results-staging').exists() and not final.exists(),'Fresh outputs required; inspect uncertain previous execution')
    args=SimpleNamespace(app=ROOT/'validation-app',candidate_engine=ROOT/'staged-engine',baseline=ROOT/'baseline-bundle',binding=ROOT/'validation-bindings/native-binding.json',output=out)
    runner=module.Runner(args);error=None;deadline=time.monotonic()+MAX_SECONDS;original_command=runner.command
    def bounded(argv,name,cwd=None,timeout=1200,allowed=(0,)):
        remaining=deadline-time.monotonic();module.require(remaining>0,'Paired diagnostic total deadline expired')
        return original_command(argv,name,cwd,min(timeout,remaining),allowed)
    runner.command=bounded
    def timed_out(_signum,_frame):raise TimeoutError('Paired diagnostic exceeded1800 seconds')
    old=signal.signal(signal.SIGALRM,timed_out);signal.alarm(MAX_SECONDS)
    try:execute_pair(runner,module)
    except Exception as exc:error=exc
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old);observation=None;verification_error=None
        try:
            verifier=module.load_module('context_pair_verifier',ROOT/'diagnostics/native-context-pair/verify_context_pair.py')
            observation=verifier.verify(out/'attachments',module.SAMPLING/'scripts/verify_results.py',out/'pair-expected-identities.json')
            module.dump(out/'pair-observation-verification.json',observation)
            module.require(observation.get('diagnosticHealthy') is True,'Paired context/geometry diagnostic unhealthy; full report preserved')
        except Exception as exc:
            verification_error=str(exc)
            if observation is None:module.dump(out/'pair-observation-verification.json',{'diagnosticOnly':True,'nativeAcceptance':False,'diagnosticHealthy':False,'error':verification_error})
            if error is None:error=exc
        module.dump(out/'native-context-pair-diagnostic.json',{'diagnosticOnly':True,'nativeAcceptance':False,'ipaBuilt':False,
            'selector':SELECTOR,'expectedMethods':2,'expectedArms':['baseline','candidate'],'requestedDPR':2,
            'observationPassed':error is None,'error':str(error) if error else None,'observationVerificationError':verification_error,
            'completedLanes':runner.results,'limitation':'Two isolated noScale/Original context windows plus one same-player rotation per arm; not full166 or physical-device acceptance; context loss never becomes healthy because static pixels remain visible.'})
        module.require(not (out/'native-acceptance.json').exists(),'Diagnostic must not emit final acceptance')
        runner.budget();final.parent.mkdir(exist_ok=True);shutil.copytree(out,final)
    if error:raise SystemExit('Paired diagnostic failed; complete bounded evidence retained: '+str(error))
    print('Paired diagnostic healthy; NOT full native acceptance')
if __name__=='__main__':main()
