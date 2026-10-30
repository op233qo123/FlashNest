#!/usr/bin/env python3
"""One unchanged synthetic WK test. Raw evidence stays runner-local."""
import json, os, re, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=Path(os.environ.get('RELEASE_RECIPE_PATH',str(HERE.parent/'native-release-ipa-156-build22'))).resolve()
sys.path.insert(0,str(BASE))
import package_checks as c
import run_selected_tests as original
EXPECTED=(('RuffleRuntimeTests','testZIPImportExecutesSecondaryMovieInWebKit'),)
SELECTOR='FlashNestTests/'+ '/'.join(EXPECTED[0])

def crash_events(log):
    events=[]; unmatched=0
    for line in log.splitlines():
        if not re.search(r'(?:reason=Crash|web process \d+ crash)',line):continue
        if not re.search(r'(?:WebProcessProxy|WebPageProxy|GPUProcessProxy)',line):continue
        pid=re.search(r'(?:\[PID=|\(pid |\bPID=)([1-9][0-9]{0,8})',line)
        if not pid:unmatched+=1;continue
        event={'pid':int(pid.group(1)),'reason':'Crash','kind':'GPU' if 'GPUProcessProxy' in line else 'WebContent'}
        if event not in events and len(events)<16:events.append(event)
    return events,unmatched

def preflight(dispatch=False):
    lock=c.load(HERE/'inputs.json')
    c.require(lock['diagnosticOnly'] is True and lock['selectedReleaseGatePassed'] is False,'Diagnostic-only scope required')
    c.require(c.digest((BASE/'inputs.json').read_bytes())==lock['baseInputsSHA256'],'Base recipe mismatch')
    for path,digest in lock['sourceFiles'].items():c.require(c.digest((HERE/path).read_bytes())==digest,'Diagnostic source mismatch')
    if dispatch:c.require(lock['dispatchAllowed'] is True,'Dispatch not authorized')
    return lock

def run(app,private_out,public_out):
    preflight(True)
    app=Path(app).resolve();private=Path(private_out).resolve();public=Path(public_out).resolve()
    c.require(private!=public and private not in public.parents and public not in private.parents,'Separate raw/public evidence roots required')
    private.mkdir(exist_ok=False);public.mkdir(exist_ok=False)
    baseline=c.load(BASE/'inputs.json')['candidateAppFiles'];c.verify_sources(app,baseline)
    run_id=os.environ.get('GITHUB_RUN_ID','');head=os.environ.get('GITHUB_SHA','')
    c.require(run_id.isdigit() and re.fullmatch('[0-9a-f]{40}',head),'Missing run identity')
    deadline=time.monotonic()+900;device=None;failure=None;start=None;end=None
    report={'schema':'single-wk-crash-diagnostic-v1','diagnosticOnly':True,'selectedReleaseGatePassed':False,
        'fullGatePassed':False,'physicalDeviceCertified':False,'selector':SELECTOR,'runID':int(run_id),'head':head,
        'unit15NotRun':True,'uiNotRun':True,'probeApplied':False,'methodSeconds':120,'result':'notRun'}
    def command(args,timeout,log=None):
        remaining=deadline-time.monotonic();c.require(remaining>0,'Diagnostic deadline exceeded')
        if log:
            with log.open('w') as stream:return subprocess.run(args,cwd=app,stdout=stream,stderr=subprocess.STDOUT,timeout=min(timeout,remaining),check=True)
        return subprocess.check_output(args,cwd=app,stderr=subprocess.STDOUT,timeout=min(timeout,remaining))
    try:
        device=command(['xcrun','simctl','create','FlashNestSingleWKDiagnostic','com.apple.CoreSimulator.SimDeviceType.iPhone-SE-3rd-generation','com.apple.CoreSimulator.SimRuntime.iOS-18-2'],60).decode().strip()
        c.require(re.fullmatch(r'[A-Fa-f0-9-]{36}',device),'Invalid simulator identifier')
        command(['xcrun','simctl','boot',device],60);command(['xcrun','simctl','bootstatus',device,'-b'],180)
        start=time.time();(private/'test-window.json').write_text(json.dumps({'startEpoch':start,'marker':'single-synthetic-wk-start'}))
        result=private/'test.xcresult';log=private/'test.log'
        args=['xcodebuild','test','-project','FlashNest.xcodeproj','-scheme','FlashNest','-configuration','Debug','-sdk','iphonesimulator',
            '-destination','platform=iOS Simulator,id='+device,'-derivedDataPath',str(private/'build'),'-resultBundlePath',str(result),
            '-disableAutomaticPackageResolution','-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1',
            '-test-timeouts-enabled','YES','-default-test-execution-time-allowance','120','-maximum-test-execution-time-allowance','120',
            '-only-testing:'+SELECTOR,'CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
        try:command(args,720,log)
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:failure=error
        end=time.time()
        (private/'test-window.json').write_text(json.dumps({'startEpoch':start,'endEpoch':end,'marker':'single-synthetic-wk-ended'}))
        text=log.read_text(errors='replace');events,unmatched=crash_events(text)
        report.update(crashEvents=events,unmatchedCrashLines=unmatched,startEpoch=start,endEpoch=end)
        # Reporting can arrive asynchronously. Never wait beyond 15s from test-command end.
        remaining=15-(time.time()-end)
        if remaining>0:time.sleep(remaining)
        from collect_crash import collect
        roots=[Path.home()/'Library/Logs/DiagnosticReports',Path.home()/'Library/Developer/CoreSimulator/Devices'/device/'data/Library/Logs/DiagnosticReports']
        report['crashReports']=collect(roots,public/'crashes',start,end+15,{e['pid'] for e in events})
        if result.exists():
            try:
                raw=command(['xcrun','xcresulttool','get','test-results','summary','--path',str(result)],45)
                (private/'summary.json').write_bytes(raw);summary=json.loads(raw)
                report['counts']={k:summary.get(k) if type(summary.get(k)) is int else None for k in ['totalTestCount','passedTests','failedTests','skippedTests','expectedFailures']}
                if failure is None:
                    original.verify(summary,text,EXPECTED,'FlashNestTests',device)
                    report['result']='passed-isolated-not-reproduced'
                else:report['result']='failed'
            except Exception as error:
                report['summaryValidationErrorType']=type(error).__name__;failure=failure or error;report['result']='failed'
        else:report['result']='no-result';failure=failure or RuntimeError('No xcresult')
        if report['crashReports'].get('exitCode') != 0:
            report['crashCollectionComplete']=False;failure=failure or RuntimeError('Crash report evidence incomplete')
        else:report['crashCollectionComplete']=True
    except Exception as error:
        failure=failure or error;report['executionErrorType']=type(error).__name__
    finally:
        try:c.verify_sources(app,baseline);report['original207SourceUnchanged']=True
        except Exception as error:failure=failure or error;report['original207SourceUnchanged']=False
        report['interpretation']='A pass only means this isolated run did not reproduce; sequence-dependent failure remains possible.'
        (public/'diagnostic-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
        if device:
            for action in ['shutdown','delete']:
                try:subprocess.run(['xcrun','simctl',action,device],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=False)
                except (subprocess.TimeoutExpired,OSError):pass
    if failure:raise SystemExit(1)
if __name__=='__main__':
    if sys.argv[1:]==['preflight']:preflight(True)
    else:run(*sys.argv[1:])
