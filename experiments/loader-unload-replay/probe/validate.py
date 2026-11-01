"""Evidence contract; baseline failures are named mechanisms, never generic exceptions."""
import re
from make_probe import MODES

CANCEL_DIAGNOSTIC = '%cERROR%c web/src/navigator.rs:477%c Asynchronous error occurred: Load cancelled color: red; background: #444 color: gray; font-style: italic color: inherit'
MISSING_404_TEMPLATE = '%cERROR%c core/src/loader.rs:868%c Error during movie loading of "http://127.0.0.1:{port}/fixtures/missing.swf": HttpNotOk("Got Not Found", 404, false, 0) color: red; background: #444 color: gray; font-style: italic color: inherit'
CANCEL_MODES = ('incomplete-load','failed-load','added-before-init')

def expected_diagnostics(mode, errors):
    """Match only the pinned runtime's exact neutral-test diagnostics, not substrings."""
    assert isinstance(errors,list) and all(isinstance(x,str) for x in errors)
    cancel_count=errors.count(CANCEL_DIAGNOSTIC)
    assert cancel_count<=1 and (cancel_count==0 or mode in CANCEL_MODES),(mode,errors)
    missing=[]
    pattern=re.escape(MISSING_404_TEMPLATE).replace(r'\{port\}',r'([1-9][0-9]{0,4})')
    for error in errors:
        if error==CANCEL_DIAGNOSTIC:continue
        match=re.fullmatch(pattern,error)
        assert mode=='failed-load' and match and int(match.group(1))<=65535,(mode,error)
        missing.append(error)
    assert len(missing)==(1 if mode=='failed-load' else 0),(mode,errors)
    return {'expectedCancellationCount':cancel_count,'expectedNeutral404Count':len(missing)}


def validate(rows,expect):
    assert expect in ('baseline','candidate')
    assert [r['arm'] for r in rows]==list(MODES),'Incomplete/order-different suite'
    outcomes=[]
    for row in rows:
        mode=row['arm'];t=[x['message'] for x in row['snapshot']['traces']]
        count=t.count
        def once(marker):assert count(marker)==1,(mode,marker,t)
        def before(left,right):assert t.index(left)<t.index(right),(mode,left,right,t)
        def requests():return [x['name'] for x in row['requests'] if x['name'].endswith('.swf')]
        def responses():return [x['name'] for x in row['responses'] if x['name'].endswith('.swf') and x['status']==200]
        assert not row['snapshot']['error'] and not row['snapshot']['overflow']
        assert row['renderer'] in ('webgl','webgl2','experimental-webgl')
        assert not row['errors'] and not row['remoteRequests'],(mode,row['errors'])
        runtime_errors=row.get('runtimeErrors',[])
        baseline_edge=expect=='baseline' and mode=='attached-same'
        if mode in CANCEL_MODES:row['expectedRuntimeDiagnostics']=expected_diagnostics(mode,runtime_errors)
        elif baseline_edge:assert CANCEL_DIAGNOSTIC not in runtime_errors,'Cancellation diagnostic is not allowed in this arm'
        else:assert not runtime_errors,(mode,runtime_errors)
        assert row['observationSecondsAfterUnloadReturn']>=5
        once('MODE:'+mode);once('UNLOAD_CALL_BEGIN');once('UNLOAD_CALL_RETURNED');before('UNLOAD_CALL_BEGIN','UNLOAD_CALL_RETURNED')
        assert not any(x.endswith(' false') and (x.startswith('PRE_') or (not baseline_edge and x.startswith(('INIT_INFO_MATCH','COMPLETE_INFO_MATCH','UNLOAD_INFO_MATCH')))) for x in t),(mode,t)
        if mode=='added-before-init':
            once('FIRST_CHILD_CONSTRUCTED');once('REQUEST first.swf');before('FIRST_CHILD_CONSTRUCTED','ADDED_BEFORE_UNLOAD')
            once('PRE_ADDED_TARGET_PARENT_LOADER true');once('ADDED_BEFORE_UNLOAD');once('UNLOAD_BEGIN');once('UNLOAD_END');once('UNLOAD_INFO_MATCH true')
            assert not row['requestFailures'] and not any(x.startswith('LOAD_ERROR') for x in t)
            for left,right in zip(['ADDED_BEFORE_UNLOAD','UNLOAD_CALL_BEGIN','UNLOAD_BEGIN','UNLOAD_END'],['UNLOAD_CALL_BEGIN','UNLOAD_BEGIN','UNLOAD_END','UNLOAD_CALL_RETURNED']):before(left,right)
            row['unloadContentObservations']=[x for x in t if x.startswith('UNLOAD_CONTENT_IS_HELD ')]
            assert len(row['unloadContentObservations'])==1
            assert count('INIT')==count('FIRST_COMPLETE')==count('NEXT_COMPLETE')==0
            assert requests()==responses()==[mode+'.swf','first.swf']
            outcomes.append({'mode':mode,'outcome':'control-pass'});continue
        if mode in ('no-load','incomplete-load','failed-load'):
            assert count('UNLOAD_BEGIN')==count('UNLOAD_END')==count('INIT')==count('FIRST_COMPLETE')==count('NEXT_COMPLETE')==0,(mode,t)
            assert 'first.swf' not in requests() and 'next.swf' not in requests()
            if mode=='no-load':assert requests()==[mode+'.swf'] and not row['requestFailures']
            if mode=='incomplete-load':
                once('REQUEST delayed-first.swf');before('REQUEST delayed-first.swf','UNLOAD_CALL_BEGIN')
                assert count('FIRST_CHILD_CONSTRUCTED')==0
                assert all(x['name']=='delayed-first.swf' for x in row['requestFailures'])
                assert requests() in ([mode+'.swf'],[mode+'.swf','delayed-first.swf'])
                assert not any(x.startswith('LOAD_ERROR') for x in t),'Canceled-load error event unexpectedly delivered'
            if mode=='failed-load':
                once('REQUEST missing.swf');once('FAILED_LOAD_OBSERVED');once('LOAD_ERROR Movie loader error');assert sum(x.startswith('LOAD_ERROR') for x in t)==1
                before('REQUEST missing.swf','FAILED_LOAD_OBSERVED');before('FAILED_LOAD_OBSERVED','UNLOAD_CALL_BEGIN')
                assert not row['requestFailures']
                assert sum(x['name']=='missing.swf' and x['status']==404 for x in row['responses'])==1
                assert requests()==[mode+'.swf','missing.swf'] and any(x['name']=='missing.swf' and x['status']==404 for x in row['responses'])
            outcomes.append({'mode':mode,'outcome':'control-pass'});continue
        if not baseline_edge:
            assert not row['requestFailures'];assert not any(x.startswith('LOAD_ERROR') for x in t)
        for x in ('FIRST_CHILD_CONSTRUCTED','FIRST_COMPLETE','TRANSITION_ENTER_FRAME','PRE_CONTENT_PARENT_LOADER true','PRE_CONTENT_INFO_MATCH true','PRE_FIRST_TOKEN true','PRE_LOADER_PARENT_NULL true'):once(x)
        before('FIRST_CHILD_CONSTRUCTED','INIT');before('INIT','FIRST_COMPLETE');before('FIRST_COMPLETE','TRANSITION_ENTER_FRAME');before('TRANSITION_ENTER_FRAME','UNLOAD_CALL_BEGIN')
        if mode.startswith('moved-'):
            once('PRE_CONTENT_PARENT_HOLDER true')
            once('PRE_MOVED_PARENT_NULL true' if mode.startswith('moved-removed') else 'PRE_MOVED_PARENT_HOLDER true')
        else:once('PRE_ATTACHED_CONTENT_PARENT_LOADER true')
        def pixel(key,color):
            value=row['pixels'][key]
            assert isinstance(value,list) and len(value)==4 and all(type(v) is int and 0<=v<=255 for v in value),(mode,key,value)
            assert all(abs(a-b)<=2 for a,b in zip(value,color)),(mode,key,row['pixels'])
        if mode.startswith('moved-kept'):
            once('MOVED_KEPT_PARENT_PRESERVED true');pixel('keptOldAt136x8',(230,30,90,255))
        if mode=='retained-script':pixel('nextOrRetainedAt8x8',(230,30,90,255))
        if expect=='baseline' and mode.startswith('moved-'):
            assert count('UNLOAD_BEGIN')==count('UNLOAD_END')==0
            assert not any(x in t for x in ('NEXT_BEGIN','REQUEST next.swf','NEXT_COMPLETE','FRESH_LOADER_CREATED','SAME_LOADER_REUSED'))
            assert requests()==responses()==[mode+'.swf','first.swf']
            assert count('INIT')==count('INIT_INFO_MATCH true')==count('COMPLETE_INFO_MATCH true')==1
            outcomes.append({'mode':mode,'outcome':'expected-baseline-unload-omission'});continue
        if baseline_edge:
            # Observation-only edge lane: initial load/control prerequisites remain strict.
            # Do not assume which old-engine reentrant failure will occur.
            initial=t[:t.index('TRANSITION_ENTER_FRAME')]
            assert initial.count('INIT_INFO_MATCH true')==initial.count('COMPLETE_INFO_MATCH true')==1
            assert not any(x.endswith(' false') and '_INFO_MATCH' in x for x in initial)
            for marker in ('UNLOAD_BEGIN','UNLOAD_INFO_MATCH true','UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','SAME_LOADER_REUSED','REQUEST next.swf'):once(marker)
            for left,right in zip(['UNLOAD_CALL_BEGIN','UNLOAD_BEGIN','UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','SAME_LOADER_REUSED'],['UNLOAD_BEGIN','UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','SAME_LOADER_REUSED','REQUEST next.swf']):before(left,right)
            assert requests()[:2]==[mode+'.swf','first.swf'] and all(x=='next.swf' for x in requests()[2:])
            assert responses()[:2]==[mode+'.swf','first.swf'] and all(x=='next.swf' for x in responses()[2:])
            assert all(x['name']=='next.swf' for x in row['requestFailures'])
            row['unloadContentObservations']=[x for x in t if x.startswith('UNLOAD_CONTENT_IS_HELD ')]
            if runtime_errors or any(x.startswith('LOAD_ERROR') for x in t):outcome='baseline-reentrant-error-observed'
            elif 'NEXT_COMPLETE' not in t:outcome='baseline-reentrant-incomplete-observed'
            elif 'NEXT_CONTENT_PRESENT false' in t:outcome='baseline-reentrant-content-clobber-observed'
            elif all(count(x)==1 for x in ('NEXT_CONTENT_PRESENT true','NEXT_PARENT_LOADER true','NEXT_INFO_MATCH true','NEXT_LOADER_CONTENT_MATCH true','NEXT_CHILD_COUNT_ONE true','OLD_CHILD_NOT_IN_LOADER true','NEXT_TOKEN true')):outcome='baseline-reentrant-final-state-observed'
            else:outcome='baseline-reentrant-partial-final-state-observed'
            outcomes.append({'mode':mode,'outcome':outcome,'engineCorrectnessPassed':False});continue
        expected_unloads=count('UNLOAD_BEGIN') if expect=='baseline' and mode=='recursive-unload' else 1
        if expect=='baseline' and mode=='recursive-unload':assert expected_unloads in (1,2)
        assert count('UNLOAD_BEGIN')==count('UNLOAD_END')==count('UNLOAD_INFO_MATCH true')==expected_unloads,(mode,t)
        observation=[x for x in t if x.startswith('UNLOAD_CONTENT_IS_HELD ')]
        assert len(observation)==expected_unloads
        row['unloadContentObservations']=observation
        before('UNLOAD_CALL_BEGIN','UNLOAD_BEGIN');before('UNLOAD_END','UNLOAD_CALL_RETURNED')
        if mode=='recursive-unload':once('NESTED_UNLOAD_BEGIN');once('NESTED_UNLOAD_RETURNED')
        if mode=='repeated-unload':once('SECOND_UNLOAD_BEGIN');once('SECOND_UNLOAD_RETURNED');before('UNLOAD_CALL_RETURNED','SECOND_UNLOAD_BEGIN')
        if mode=='retained-script':
            for x in ('RETAINED_TOKEN true','RETAINED_REATTACHED true','RETAINED_GRAPHICS_CALL_RETURNED'):once(x)
        if mode.endswith(('-fresh','-same')):
            for x in ('UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','NEXT_LOAD_RETURNED'):once(x)
            once('FRESH_LOADER_CREATED' if mode.endswith('-fresh') else 'SAME_LOADER_REUSED')
            assert requests()==responses()==[mode+'.swf','first.swf','next.swf']
            for left,right in zip(['UNLOAD_BEGIN','UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','REQUEST next.swf','NEXT_LOAD_RETURNED','UNLOAD_END','UNLOAD_CALL_RETURNED','NEXT_CHILD_CONSTRUCTED'],['UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','REQUEST next.swf','NEXT_LOAD_RETURNED','UNLOAD_END','UNLOAD_CALL_RETURNED','NEXT_CHILD_CONSTRUCTED','NEXT_COMPLETE']):before(left,right)
            assert count('INIT')==count('INIT_INFO_MATCH true')==count('COMPLETE_INFO_MATCH true')==2
            inits=[i for i,x in enumerate(t) if x=='INIT'];completes=[i for i,x in enumerate(t) if x=='COMPLETE_INFO_MATCH true']
            assert t.index('NEXT_CHILD_CONSTRUCTED')<inits[1]<completes[1]<t.index('NEXT_COMPLETE')
            if expect=='baseline' and mode=='attached-same' and 'NEXT_CONTENT_PRESENT false' in t:
                # Only this exact post-COMPLETE content-clobber signature is accepted.
                once('NEXT_COMPLETE');once('NEXT_CHILD_CONSTRUCTED');once('NEXT_CONTENT_PRESENT false')
                assert not runtime_errors
                outcomes.append({'mode':mode,'outcome':'expected-baseline-reentrant-content-clobber'});continue
            assert not runtime_errors,(mode,runtime_errors)
            for x in ('NEXT_CHILD_CONSTRUCTED','NEXT_COMPLETE','NEXT_CONTENT_PRESENT true','NEXT_PARENT_LOADER true','NEXT_INFO_MATCH true','NEXT_LOADER_CONTENT_MATCH true','NEXT_CHILD_COUNT_ONE true','OLD_CHILD_NOT_IN_LOADER true','NEXT_TOKEN true'):once(x)
            before('NEXT_CHILD_CONSTRUCTED','NEXT_COMPLETE')
            pixel('nextOrRetainedAt8x8',(30,60,230,255))
            row['screenshot']['renderedFrameAssertion']=True
            assert count('INIT')==count('INIT_INFO_MATCH true')==count('COMPLETE_INFO_MATCH true')==2
        else:
            assert requests()==responses()==[mode+'.swf','first.swf']
            assert count('INIT')==count('INIT_INFO_MATCH true')==count('COMPLETE_INFO_MATCH true')==1
        outcomes.append({'mode':mode,'outcome':('baseline-recursive-duplicate-observed' if expected_unloads==2 else 'baseline-recursive-one-shot-observed') if expect=='baseline' and mode=='recursive-unload' else 'control-pass'})
    return outcomes
