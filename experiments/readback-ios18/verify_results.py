import json,re,sys
from pathlib import Path
NAMES=[('SharedObjectPersistenceTests','testConfirmedImportAppliesOnceAndNewerLiveFlushSurvivesMissedNativeCapture'),
('FrameOrderRuntimeTests','testNestedChildGotoPreservesParentTarget'),
('FrameOrderRuntimeTests','testControlPreservesRecordedFrameOrder')]
def verify(arm, summary, log, expected_os='18.2'):
    if expected_os != '18.2':raise ValueError('Unsupported exact OS choice')
    if arm not in ('baseline','candidate'):raise ValueError('Unknown arm')
    expected=NAMES
    if summary.get('result') != 'Passed' or summary.get('testFailures') != []:raise ValueError('Contradictory result/failures')
    if re.search(r"Test (?:Case|Suite).*failed|Test Case.*skipped|test execution time allowance|Exceeded.*time|Testing failed|\*\* TEST FAILED \*\*",log,re.I):raise ValueError('Failure/skip/timeout log evidence')
    if summary.get('passedTests')!=len(expected) or summary.get('totalTestCount')!=len(expected) or any(summary.get(k)!=0 for k in ['failedTests','skippedTests','expectedFailures']):raise ValueError('Unexpected raw results/counts')
    if not summary.get('devicesAndConfigurations') or any(x.get('device',{}).get('osVersion')!=expected_os for x in summary['devicesAndConfigurations']):raise ValueError('Wrong OS')
    devices=summary['devicesAndConfigurations']
    if len(devices)!=1 or any(x.get('device',{}).get('platform')!='iOS Simulator' or x.get('passedTests')!=len(expected) or any(x.get(k)!=0 for k in ['failedTests','skippedTests','expectedFailures']) for x in devices):raise ValueError('Contradictory per-device results')
    passed=re.findall(r"Test Case '-\[FlashNestTests\.(\w+) (\w+)\]' passed",log)
    if sorted(passed)!=sorted(expected):raise ValueError('Expected test names not exactly passed')
    if '** TEST SUCCEEDED **' not in log:raise ValueError('Missing native success')
    return {'arm':arm,'passed':passed,'skipped':0,'os':expected_os}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1],json.loads(Path(sys.argv[2]).read_text()),Path(sys.argv[3]).read_text(),sys.argv[4] if len(sys.argv)>4 else '18.2')))
