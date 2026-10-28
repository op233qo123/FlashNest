#!/usr/bin/env python3
"""One explicitly diagnostic native baseline case; never writes acceptance."""
import importlib.util, json, shutil, signal, sys, time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
SELECTOR='FlashNestSamplingUITests/NativeSamplingUITests/testShippingWebGLShowAll'
MAX_SECONDS=1800

def load_runner():
    path=ROOT/'validation-harness/native-composite-runner/run.py'
    spec=importlib.util.spec_from_file_location('reviewed_native_runner',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def execute_one(runner, module):
    runner.preflight() # Original full source/runtime/helper/tool checks; no test execution here.
    b=runner.binding;baseline=runner.args.baseline/'sampling';runtime=baseline/'runtime'
    app=runner.copy_app('sampling-baseline-drag-diagnostic',runtime,runner.sampling_map)
    shutil.copyfile(baseline/'runtime.files.json',app/'runtime.files.json')
    module.dump(app/'NATIVE_VALIDATION_COPY.json',{'disposable':True,'sdk':'iphonesimulator'})
    runner.metadata_overlay(app,baseline/'app-metadata',b['samplingBaselineMetadata'])
    repin=b['samplingAppManifests']['baseline'];repin_path=(runner.args.binding.parent/repin['path']).resolve()
    module.require(module.sha(repin_path)==repin['sha256'],'Baseline App manifest differs')
    inventory_hash=module.sha(app/'runtime.files.json')
    runner.command([sys.executable,module.SAMPLING/'scripts/prepare_overlay.py','--app',app,'--arm','baseline',
        '--runtime-inventory-sha256',inventory_hash,'--approved-app-manifest',repin_path,
        '--approved-app-manifest-sha256',repin['sha256']],'sampling-baseline-diagnostic-stage',timeout=120)
    shutil.copyfile(app/'NativeSamplingValidation/staging-provenance.json',runner.out/'sampling-baseline-staging-provenance.json')
    project=runner.project(app,'sampling-baseline-diagnostic','FlashNestSamplingUI')
    device=runner.devices['2'];runner.reset(device,'sampling-baseline-dpr2-diagnostic')
    key='single-baseline-drag-diagnostic'
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
        module.dump(out/'native-drag-diagnostic.json',{'diagnosticOnly':True,'finalAcceptance':False,'ipaBuilt':False,
            'selector':SELECTOR,'expectedMethods':1,'arm':'delivered155-baseline','requestedDPR':2,
            'methodPassed':error is None,'error':str(error) if error else None,'completedLanes':runner.results,
            'limitation':'No candidate sampling, full native matrix, product fix or final acceptance is established'})
        module.require(not (out/'native-acceptance.json').exists(),'Diagnostic must not emit native acceptance')
        runner.budget();final.parent.mkdir(exist_ok=True);shutil.copytree(out,final) # Full xcresult remains outside evidence.
    if error:raise SystemExit('Single diagnostic failed; preserved bounded pre-drag evidence: '+str(error))
    print('Single diagnostic method passed; NOT final native acceptance')
if __name__=='__main__':main()
