#!/usr/bin/env python3
"""One explicitly diagnostic native candidate automatic case; never writes acceptance."""
import importlib.util, json, shutil, signal, sys, time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
SELECTOR='FlashNestSamplingUITests/NativeSamplingUITests/testDiagnosticCandidateAutomaticContextWindow'
MAX_SECONDS=1800

def load_runner():
    path=ROOT/'validation-harness/native-composite-runner/run.py'
    spec=importlib.util.spec_from_file_location('reviewed_native_runner',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def execute_one(runner, module):
    runner.preflight() # Original full source/runtime/helper/tool checks; no test execution here.
    b=runner.binding
    app=runner.copy_app('sampling-candidate-automatic-diagnostic')
    module.dump(app/'NATIVE_VALIDATION_COPY.json',{'disposable':True,'sdk':'iphonesimulator'})
    repin=b['samplingAppManifests']['candidate'];repin_path=(runner.args.binding.parent/repin['path']).resolve()
    module.require(module.sha(repin_path)==repin['sha256'],'Candidate App manifest differs')
    inventory_hash=module.sha(app/'runtime.files.json')
    freeze=runner.stage/'sampling-candidate-freeze.json'
    module.dump(freeze,{'frozen':True,'releaseEquivalent':True,'runtimeInventorySHA256':inventory_hash,
        'approvedAppManifestSHA256':repin['sha256']})
    runner.command([sys.executable,module.SAMPLING/'scripts/prepare_overlay.py','--app',app,'--arm','candidate',
        '--runtime-inventory-sha256',inventory_hash,'--approved-app-manifest',repin_path,
        '--approved-app-manifest-sha256',repin['sha256'],'--candidate-freeze',freeze],
        'sampling-candidate-diagnostic-stage',timeout=120)
    shutil.copyfile(app/'NativeSamplingValidation/staging-provenance.json',runner.out/'sampling-candidate-staging-provenance.json')
    # One extra diagnostic method exists only in this disposable staged UITest copy.
    target=app/'NativeSamplingValidation/UITests/NativeSamplingUITests.swift'
    original=target.read_bytes()
    staged_app_before=module.inventory(app/'App')
    module.require(original==(module.SAMPLING/'UITests/NativeSamplingUITests.swift').read_bytes(),
        'Diagnostic starts from exact frozen original UITest source')
    fragment_path=ROOT/'diagnostics/native-candidate-context/method.swift'
    fragment=fragment_path.read_bytes()
    anchor=b'    private func matrix('
    module.require(original.count(anchor)==1 and fragment not in original,'Exact diagnostic insertion anchor required')
    changed=original.replace(anchor,fragment+anchor,1)
    module.require(changed.replace(fragment,b'',1)==original,'Diagnostic inverse must restore every original byte')
    target.write_bytes(changed)
    module.require(module.inventory(app/'App')==staged_app_before,'Extra diagnostic overlay changed staged App')
    module.dump(runner.out/'diagnostic-test-overlay.json',{'diagnosticOnly':True,'extraDiagnosticOverlayAppChanged':False,
        'target':'NativeSamplingValidation/UITests/NativeSamplingUITests.swift',
        'originalSHA256':module.hashlib.sha256(original).hexdigest(),'fragmentSHA256':module.sha(fragment_path),
        'diagnosticSHA256':module.sha(target),'exactInverseVerified':True,'fullMatrixAcceptance':False})
    shutil.copyfile(app/'NativeSamplingValidation/SamplingIdentity.json',runner.out/'diagnostic-expected-identity.json')
    project=runner.project(app,'sampling-candidate-diagnostic','FlashNestSamplingUI')
    device=runner.devices['2'];runner.reset(device,'sampling-candidate-dpr2-diagnostic')
    key='single-candidate-automatic-diagnostic'
    runner.lanes[key]=module.lane(key,'FlashNestSamplingUI',[SELECTOR],900)
    module.require(runner.lanes[key]['expectedCount']==1 and runner.lanes[key]['selectors']==[SELECTOR],'Exactly one diagnostic method required')
    module.dump(runner.out/'diagnostic-selection.json',runner.lanes[key])
    runner.test(app,project,device,key)
    module.require(len(runner.results)==1 and runner.results[0]['tests']==1,'Exactly one diagnostic native test must execute')
    module.require(module.inventory(runner.args.app)==b['appFiles'],'Immutable App input changed')
    runner.check_runtime(runner.args.candidate_engine/'runtime',runner.candidate_map)

def main():
    lock=json.loads((ROOT/'validation-lock.json').read_text())
    if lock.get('dispatchAllowed') is not True:raise ValueError('Unapproved validation binding')
    module=load_runner();out=ROOT/'native-drag-execution/results';final=ROOT/'evidence/native-drag-diagnostic'
    module.require(not out.exists() and not out.with_name('results-staging').exists() and not final.exists(),'Fresh diagnostic directories required')
    args=SimpleNamespace(app=ROOT/'validation-app',candidate_engine=ROOT/'staged-engine',baseline=ROOT/'baseline-bundle',binding=ROOT/'validation-bindings/native-binding.json',output=out)
    runner=module.Runner(args);error=None
    deadline=time.monotonic()+MAX_SECONDS
    original_command=runner.command
    def deadline_command(argv,name,cwd=None,timeout=1200,allowed=(0,)):
        remaining=deadline-time.monotonic()
        module.require(remaining>0,'Single diagnostic total deadline expired; no further subprocesses')
        return original_command(argv,name,cwd,min(timeout,remaining),allowed)
    runner.command=deadline_command # Also bounds any xcresult cleanup attempted after a test timeout.
    def timeout(_signum,_frame):raise TimeoutError('Single native diagnostic exceeded1800 seconds')
    old=signal.signal(signal.SIGALRM,timeout);signal.alarm(MAX_SECONDS)
    try:execute_one(runner,module)
    except Exception as exc:error=exc
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old)
        verification_error=None;observation=None
        try:
            verifier=module.load_module('candidate_context_verifier',ROOT/'diagnostics/native-candidate-context/verify_context_window.py')
            observation=verifier.verify(out/'attachments/single-candidate-automatic-diagnostic',module.SAMPLING/'scripts/verify_results.py',out/'diagnostic-expected-identity.json')
            module.dump(out/'diagnostic-observation-verification.json',observation)
            module.require(observation.get('diagnosticHealthy') is True,'Candidate context/pixel diagnostic unhealthy; full report preserved')
        except Exception as exc:
            verification_error=str(exc)
            if observation is None:
                module.dump(out/'diagnostic-observation-verification.json',{'diagnosticOnly':True,
                    'nativeAcceptance':False,'diagnosticHealthy':False,'error':verification_error})
            if error is None:error=exc
        module.dump(out/'native-drag-diagnostic.json' ,{'diagnosticOnly':True,'finalAcceptance':False,'ipaBuilt':False,
            'selector':SELECTOR,'expectedMethods':1,'arm':'candidate-touch-contact-engine','requestedDPR':2,
            'observationPassed':error is None,'error':str(error) if error else None,'observationVerificationError':verification_error,'completedLanes':runner.results,
            'limitation':'Only candidate Automatic/noScale/Original initial same-player observation window; no fixture input, rotation, full matrix, product fix or final acceptance is established'})
        module.require(not (out/'native-acceptance.json').exists(),'Diagnostic must not emit native acceptance')
        runner.budget();final.parent.mkdir(exist_ok=True);shutil.copytree(out,final) # Full xcresult remains outside evidence.
    if error:raise SystemExit('Single diagnostic failed; preserved bounded automatic renderer evidence: '+str(error))
    print('Single diagnostic method passed; NOT final native acceptance')
if __name__=='__main__':main()
