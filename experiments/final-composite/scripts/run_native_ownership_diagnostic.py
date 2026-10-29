#!/usr/bin/env python3
"""Three bounded synthetic ownership/identity controls; no game, product fix or acceptance."""
import importlib.util,json,re,shutil,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
SELECTORS=['FlashNestTests/RestartOwnershipDiagnosticTests/'+name for name in (
    'testBlankWebViewOwnersAndWeakRelease','testSourceCopySameTurnReplacementIdentity','testSourceCopyRenderedNilReplacementIdentity')]
MAX_SECONDS=1800
METHOD_SECONDS=30
COMPILE_INCLUSIVE_SECONDS=900

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def load_runner():return load_module('reviewed_native_runner',ROOT/'validation-harness/native-composite-runner/run.py')
def load_controls():return load_module('ownership_controls',ROOT/'validation-harness/native-ownership-diagnostic/stage_controls.py')

def execute_controls(runner,module):
    runner.preflight()
    controls=load_controls();app=runner.copy_app('ownership-diagnostic')
    before=module.inventory(app/'App');proof=controls.apply_overlay(app)
    module.require(proof.get('exactInverseVerified') is True,'Exact staged-only inverse required')
    module.require(before==module.inventory(app/'App'),'Ownership diagnostic must not alter product App')
    module.dump(runner.out/'ownership-test-overlay.json',proof)
    expected={'diagnosticOnly':True,'nativeAcceptance':False,'selectors':SELECTORS,'appFiles':runner.binding['appFiles'],
        'engineSHA256':runner.binding['engine']['sha256'],
        'playerViewSHA256':module.sha(app/'App/Views/PlayerView.swift'),
        'stagedTestsSHA256':module.sha(app/'Tests/RestartOwnershipDiagnosticTests.swift'),
        'stageProofSHA256':module.sha(runner.out/'ownership-test-overlay.json'),
        'helperSHA256':module.sha(ROOT/'validation-harness/native-ownership-diagnostic/stage_controls.py'),
        'observationVerifierSHA256':module.sha(ROOT/'validation-harness/native-ownership-diagnostic/verify_observations.py'),
        'selectionSHA256':module.sha(ROOT/'validation-harness/native-ownership-diagnostic/selection.json'),
        'sourcePinsSHA256':module.sha(ROOT/'validation-harness/native-ownership-diagnostic/source-pins.json')}
    selection=json.loads((ROOT/'validation-harness/native-ownership-diagnostic/selection.json').read_text())
    module.require(selection['selectors']==SELECTORS and selection['count']==3 and selection['methodDeadlineSeconds']==METHOD_SECONDS,'Exact diagnostic selection differs')
    # External source evidence is frozen before any control executes.
    module.dump(runner.out/'ownership-expected-binding.json',expected)
    cfg=module.lane('ownership-controls','FlashNest',SELECTORS,METHOD_SECONDS)
    module.require(cfg['expectedCount']==3 and len(set(SELECTORS))==3,'Exactly three source-copy control methods required')
    runner.lanes['ownership-controls']=cfg;module.dump(runner.out/'ownership-selection.json',cfg)
    project=runner.project(app,'ownership-controls','FlashNest');device=runner.devices['2']
    runner.reset(device,'ownership-controls')
    error=None
    try:runner.test(app,project,device,'ownership-controls','ownership-controls')
    except Exception as exc:
        error=exc;module.dump(runner.out/'ownership-execution-error.json',{'error':str(exc),'nativeAcceptance':False})
    # Preserve the initial XCTest error if immutable-input verification also fails.
    post_error=None
    try:
        module.require(module.inventory(runner.args.app)==runner.binding['appFiles'],'Immutable approved App input changed')
        runner.check_runtime(runner.args.candidate_engine/'runtime',runner.candidate_map)
        module.require(module.sha(app/'App/Views/PlayerView.swift')==expected['playerViewSHA256'] and module.sha(app/'Tests/RestartOwnershipDiagnosticTests.swift')==expected['stagedTestsSHA256'],'Executed source-copy bytes changed')
    except Exception as exc:
        post_error=exc;module.dump(runner.out/'ownership-postcheck-error.json',{'error':str(exc),'primaryError':str(error) if error else None,'nativeAcceptance':False})
    if error is not None:raise error
    if post_error is not None:raise post_error
    module.require(len(runner.results)==1 and {r['runName']:r['tests'] for r in runner.results}=={'ownership-controls':3},'Exactly three completed controls required')

def bounded_command(original,module,deadline,argv,name,cwd=None,timeout=1200,allowed=(0,)):
    remaining=deadline-time.monotonic();module.require(remaining>0,'Ownership diagnostic total deadline expired')
    if name=='ownership-controls':
        strings=list(map(str,argv))
        module.require(strings[:2]==['xcodebuild','test'] and timeout==METHOD_SECONDS*3+300,'Only the new diagnostic compile/test invocation may use its explicit compile-inclusive budget')
        module.require([x.removeprefix('-only-testing:') for x in strings if x.startswith('-only-testing:')]==SELECTORS,'Diagnostic selectors drift')
        for flag in ('-default-test-execution-time-allowance','-maximum-test-execution-time-allowance'):
            module.require(strings.count(flag)==1 and strings[strings.index(flag)+1]==str(METHOD_SECONDS),'Method30s limit changed')
        timeout=COMPILE_INCLUSIVE_SECONDS
    return original(argv,name,cwd,min(timeout,remaining),allowed)

def verify_evidence(out,expected,module):
    # Authenticated source/proof comes from staging before execution, not stdout claims.
    helper_root=ROOT/'validation-harness/native-ownership-diagnostic'
    for name,key in [('stage_controls.py','helperSHA256'),('verify_observations.py','observationVerifierSHA256'),('selection.json','selectionSHA256'),('source-pins.json','sourcePinsSHA256')]:
        module.require(module.sha(helper_root/name)==expected[key],'Diagnostic source/helper changed')
    module.require(expected['selectors']==SELECTORS and module.sha(out/'ownership-test-overlay.json')==expected['stageProofSHA256'],'External staged binding differs')
    proof=json.loads((out/'ownership-test-overlay.json').read_text())
    module.require(proof['beforeFiles']==expected['appFiles'] and proof['playerViewSHA256']==expected['playerViewSHA256'] and proof['testSHA256']==expected['stagedTestsSHA256'],'Staged source-copy proof differs')
    pins=json.loads((helper_root/'source-pins.json').read_text())
    module.require(expected['playerViewSHA256']==pins['playerViewSHA256'] and expected['stagedTestsSHA256']==pins['testSHA256'],'Exact approved source copy differs')
    log=out/'ownership-controls.log';module.require(log.is_file() and log.stat().st_size<=16*1024*1024,'Missing/oversize original XCTest log')
    marker='FLASHNEST_OWNERSHIP_JSON '
    lines=re.findall(re.escape(marker)+r'([^\r\n]+)',log.read_text(errors='replace'))
    module.require(len(lines)==3 and all(len(line.encode())<=32768 for line in lines),'Exactly three bounded control records required')
    records=[json.loads(line) for line in lines]
    module.require(all(isinstance(record,dict) for record in records),'Observation object required')
    attached={};folder=out/'attachments/ownership-controls'
    module.require(folder.is_dir(),'Original JSON attachments required')
    files=list(folder.rglob('*'));module.require(not any(path.is_symlink() for path in files),'Linked evidence forbidden')
    module.require(sum(path.stat().st_size for path in files if path.is_file())<=128*1024*1024,'Evidence exceeds original bound')
    for path in files:
        if path.is_file() and path.suffix.lower()=='.json' and path.stat().st_size<=32768:
            try:value=json.loads(path.read_text())
            except (ValueError,UnicodeError):continue
            if isinstance(value,dict) and value.get('schema')=='flashnest-restart-ownership-diagnostic-v1':
                control=value.get('control');module.require(control not in attached,'Duplicate observation attachment');attached[control]=value
    module.require(len(attached)==3 and len({record.get('control') for record in records})==3 and all(attached.get(record.get('control'))==record for record in records),'Stdout/attachment exact observations differ')
    report=load_module('ownership_observation_verifier',helper_root/'verify_observations.py').verify_records(records)
    report['externalBindingSHA256']=module.sha(out/'ownership-expected-binding.json')
    report['stageProofSHA256']=expected['stageProofSHA256'];report['sourcePlayerViewSHA256']=expected['playerViewSHA256'];report['executedTestSourceSHA256']=expected['stagedTestsSHA256']
    return report

def main():
    lock=json.loads((ROOT/'validation-lock.json').read_text())
    if lock.get('dispatchAllowed') is not True or lock.get('diagnosticOnly') is not True:raise ValueError('Explicit ownership diagnostic-only binding required')
    module=load_runner();out=ROOT/'native-ownership-execution/results';final=ROOT/'evidence/native-ownership-diagnostic'
    module.require(not out.exists() and not out.with_name('results-staging').exists() and not final.exists(),'Fresh diagnostic outputs required')
    args=SimpleNamespace(app=ROOT/'validation-app',candidate_engine=ROOT/'staged-engine',baseline=ROOT/'baseline-bundle',binding=ROOT/'validation-bindings/native-binding.json',output=out)
    runner=module.Runner(args);error=None;deadline=time.monotonic()+MAX_SECONDS;original=runner.command
    runner.command=lambda argv,name,cwd=None,timeout=1200,allowed=(0,):bounded_command(original,module,deadline,argv,name,cwd,timeout,allowed)
    def timed_out(_signum,_frame):raise TimeoutError('Ownership diagnostic exceeded1800 seconds')
    old=signal.signal(signal.SIGALRM,timed_out);signal.alarm(MAX_SECONDS)
    try:execute_controls(runner,module)
    except Exception as exc:
        error=exc;module.dump(out/'ownership-primary-error.json',{'error':str(exc),'errorType':type(exc).__name__,'nativeAcceptance':False})
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old);observation=None;verification_error=None
        try:
            expected=json.loads((out/'ownership-expected-binding.json').read_text())
            observation=verify_evidence(out,expected,module)
            module.require(isinstance(observation,dict),'Structured ownership evidence required')
            module.dump(out/'ownership-observation-evidence.json',observation)
            module.require(observation.get('diagnosticOnly') is True and observation.get('nativeAcceptance') is False and observation.get('renderHealthCertified') is False,'Diagnostic scope differs')
            module.require(observation.get('observationComplete') is True,'Incomplete/invalid ownership evidence')
        except Exception as exc:
            verification_error=str(exc);module.dump(out/'ownership-observation-evidence-error.json',{'error':verification_error,'nativeAcceptance':False})
            if error is None:error=exc
        module.dump(out/'native-ownership-diagnostic.json',{'diagnosticOnly':True,'nativeAcceptance':False,'renderHealthCertified':False,'ipaBuilt':False,
            'expectedSelectors':SELECTORS,'expectedMethods':3,'requestedDPR':2,'methodExecutionAllowanceSeconds':METHOD_SECONDS,
            'compileInclusiveCommandSeconds':COMPILE_INCLUSIVE_SECONDS,'totalDiagnosticSeconds':MAX_SECONDS,
            'observationComplete':observation.get('observationComplete') if isinstance(observation,dict) else False,
            'weakReleaseOutcome':observation.get('weakReleaseOutcome') if isinstance(observation,dict) else None,
            'sameTurnIdentityMatches':observation.get('sameTurnIdentityMatches') if isinstance(observation,dict) else None,
            'renderedNilIdentityMatches':observation.get('renderedNilIdentityMatches') if isinstance(observation,dict) else None,
            'collectionCompleted':error is None,'error':str(error) if error else None,'observationVerificationError':verification_error,
            'completedLanes':runner.results,'limitation':'Blank WK ownership and exact source-copy representable controls only; not the production session, no game/GPU recovery. Bounded weak non-release is inconclusive, not a proven leak. Observed hierarchy mismatch is a synthetic control outcome, not a production verdict. No full198 acceptance.'})
        module.require(not (out/'native-acceptance.json').exists(),'Diagnostic must never emit native acceptance')
        try:runner.budget();final.parent.mkdir(exist_ok=True);shutil.copytree(out,final)
        except Exception as exc:
            module.dump(out/'ownership-evidence-copy-error.json',{'error':str(exc),'primaryError':str(error) if error else None,'nativeAcceptance':False})
            if error is None:error=exc
    if error:raise SystemExit('Ownership diagnostic collection failed; bounded evidence retained: '+str(error))
    print('Ownership observations collected; NOT product/session/render/native acceptance')
if __name__=='__main__':main()
