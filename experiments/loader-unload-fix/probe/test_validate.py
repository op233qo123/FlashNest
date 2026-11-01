"""Synthetic evidence-validator tests; no runtime/Flash-reference execution."""
import unittest,copy
from make_probe import MODES
from validate import validate

def row(mode,expect):
    t=['MODE:'+mode];swfs=[mode+'.swf'];failures=[];rt=[]
    if mode in ('no-load','incomplete-load','failed-load'):
        if mode=='incomplete-load':swfs+=['delayed-first.swf'];failures=[{'name':'delayed-first.swf'}]
        if mode=='failed-load':swfs+=['missing.swf'];t+=['LOAD_ERROR HTTP404','FAILED_LOAD_OBSERVED'];rt=['load returned 404']
        t+=['UNLOAD_CALL_BEGIN','UNLOAD_CALL_RETURNED']
    elif mode=='added-before-init':
        swfs+=['first.swf'];t+=['PRE_ADDED_TARGET_PARENT_LOADER true','ADDED_BEFORE_UNLOAD','UNLOAD_CALL_BEGIN','UNLOAD_BEGIN','UNLOAD_INFO_MATCH true','UNLOAD_CONTENT_IS_HELD true','UNLOAD_END','UNLOAD_CALL_RETURNED']
    else:
        swfs+=['first.swf'];t+=['FIRST_CHILD_CONSTRUCTED','INIT_INFO_MATCH true','INIT','COMPLETE_INFO_MATCH true','FIRST_COMPLETE','PRE_CONTENT_PARENT_LOADER true','PRE_CONTENT_INFO_MATCH true','PRE_FIRST_TOKEN true']
        if mode.startswith('moved-'):t+=['PRE_CONTENT_PARENT_HOLDER true']
        t+=['TRANSITION_ENTER_FRAME']
        t+=['PRE_MOVED_PARENT_NULL true'] if mode.startswith('moved-removed') else ['PRE_MOVED_PARENT_HOLDER true'] if mode.startswith('moved-kept') else ['PRE_ATTACHED_CONTENT_PARENT_LOADER true']
        t+=['PRE_LOADER_PARENT_NULL true','UNLOAD_CALL_BEGIN']
        omitted=expect=='baseline' and mode.startswith('moved-')
        if not omitted:
            t+=['UNLOAD_BEGIN','UNLOAD_INFO_MATCH true','UNLOAD_CONTENT_IS_HELD true']
            if mode=='recursive-unload':
                t+=['NESTED_UNLOAD_BEGIN']
                if expect=='baseline':t+=['UNLOAD_BEGIN','UNLOAD_INFO_MATCH true','UNLOAD_CONTENT_IS_HELD true','UNLOAD_END']
                t+=['NESTED_UNLOAD_RETURNED']
            if mode.endswith(('-fresh','-same')):t+=['UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','FRESH_LOADER_CREATED' if mode.endswith('-fresh') else 'SAME_LOADER_REUSED','REQUEST next.swf','NEXT_LOAD_RETURNED']
            t+=['UNLOAD_END']
        t+=['UNLOAD_CALL_RETURNED']
        if mode=='repeated-unload':t+=['SECOND_UNLOAD_BEGIN','SECOND_UNLOAD_RETURNED']
        if mode=='retained-script':t+=['RETAINED_TOKEN true','RETAINED_REATTACHED true','RETAINED_GRAPHICS_CALL_RETURNED']
        if mode.startswith('moved-kept'):t+=['MOVED_KEPT_PARENT_PRESERVED true']
        if mode.endswith(('-fresh','-same')) and not omitted:
            swfs+=['next.swf'];t+=['NEXT_CHILD_CONSTRUCTED','INIT_INFO_MATCH true','INIT','COMPLETE_INFO_MATCH true','NEXT_COMPLETE','NEXT_CONTENT_PRESENT true','NEXT_PARENT_LOADER true','NEXT_INFO_MATCH true','NEXT_LOADER_CONTENT_MATCH true','NEXT_CHILD_COUNT_ONE true','OLD_CHILD_NOT_IN_LOADER true','NEXT_TOKEN true']
    responses=[{'name':x,'status':404 if x=='missing.swf' else 200} for x in swfs if x!='delayed-first.swf']
    return {'arm':mode,'snapshot':{'traces':[{'message':x} for x in t],'error':None,'overflow':False},'renderer':'webgl','errors':[],'runtimeErrors':rt,'remoteRequests':[],'requestFailures':failures,'requests':[{'name':x} for x in swfs],'responses':responses,'observationSecondsAfterUnloadReturn':5.5,'pixels':{'nextOrRetainedAt8x8':[230,30,90,255] if mode=='retained-script' else [30,60,230,255],'keptOldAt136x8':[230,30,90,255]},'screenshot':{}}
def rows(expect):return [row(mode,expect) for mode in MODES]
def pick(rs,mode):return next(r for r in rs if r['arm']==mode)
class ValidatorTests(unittest.TestCase):
    def reject(self,rs,expect='candidate'):
        with self.assertRaises((AssertionError,ValueError)):validate(rs,expect)
    def test_all_candidate(self):self.assertEqual(len(validate(rows('candidate'),'candidate')),len(MODES))
    def test_baseline_named_failures(self):self.assertEqual(len(validate(rows('baseline'),'baseline')),len(MODES))
    def test_candidate_missing_event_rejected(self):
        rs=rows('candidate');r=pick(rs,'moved-removed-fresh');r['snapshot']['traces']=[x for x in r['snapshot']['traces'] if x['message']!='UNLOAD_BEGIN'];self.reject(rs)
    def test_next_identity_state_rejected(self):
        for marker in ('NEXT_TOKEN true','NEXT_CHILD_COUNT_ONE true','NEXT_LOADER_CONTENT_MATCH true','OLD_CHILD_NOT_IN_LOADER true'):
            rs=rows('candidate');r=pick(rs,'attached-same');r['snapshot']['traces'].remove({'message':marker});self.reject(rs)
    def test_second_init_order_rejected(self):
        rs=rows('candidate');t=pick(rs,'attached-fresh')['snapshot']['traces'];t.pop(next(i for i in range(len(t)-1,-1,-1) if t[i]['message']=='INIT'));t.append({'message':'INIT'});self.reject(rs)
    def test_missing_window_rejected(self):
        rs=rows('candidate');pick(rs,'moved-kept-fresh')['observationSecondsAfterUnloadReturn']=4.9;self.reject(rs)
    def test_retained_bitmap_must_render(self):
        rs=rows('candidate');pick(rs,'moved-kept-fresh')['pixels']['keptOldAt136x8']=[30,60,230,255];self.reject(rs)
    def test_empty_pixel_cannot_pass(self):
        rs=rows('candidate');pick(rs,'moved-kept-fresh')['pixels']['keptOldAt136x8']=[];self.reject(rs)
    def test_added_request_failure_rejected(self):
        rs=rows('candidate');pick(rs,'added-before-init')['requestFailures']=[{'name':'first.swf'}];self.reject(rs)
    def test_repeated_duplicate_unload_rejected(self):
        rs=rows('candidate');pick(rs,'repeated-unload')['snapshot']['traces'].append({'message':'UNLOAD_BEGIN'});self.reject(rs)
    def test_no_load_event_rejected(self):
        rs=rows('candidate');pick(rs,'no-load')['snapshot']['traces'].append({'message':'UNLOAD_BEGIN'});self.reject(rs)
    def test_added_late_init_rejected(self):
        rs=rows('candidate');pick(rs,'added-before-init')['snapshot']['traces'].append({'message':'INIT'});self.reject(rs)
    def test_baseline_next_request_not_omission(self):
        rs=rows('baseline');pick(rs,'moved-removed-same')['requests'].append({'name':'next.swf'});self.reject(rs,'baseline')
    def test_named_baseline_null_content_only(self):
        rs=rows('baseline');r=pick(rs,'attached-same');t=r['snapshot']['traces'];start=next(i for i,x in enumerate(t) if x['message']=='NEXT_CONTENT_PRESENT true');r['snapshot']['traces']=t[:start]+[{'message':'NEXT_CONTENT_PRESENT false'}]
        self.assertTrue(any(x['outcome']=='baseline-reentrant-content-clobber-observed' for x in validate(rs,'baseline')))
        self.reject(copy.deepcopy(rs),'candidate')
    def test_baseline_incomplete_is_observation_only(self):
        rs=rows('baseline');r=pick(rs,'attached-same');t=r['snapshot']['traces'];r['snapshot']['traces']=t[:next(i for i,x in enumerate(t) if x['message']=='NEXT_CHILD_CONSTRUCTED')];r['responses']=[x for x in r['responses'] if x['name']!='next.swf']
        out=validate(rs,'baseline');self.assertTrue(any(x['outcome']=='baseline-reentrant-incomplete-observed' and x['engineCorrectnessPassed'] is False for x in out))
    def test_unknown_runtime_error_rejected(self):
        rs=rows('candidate');pick(rs,'attached-same')['runtimeErrors']=['unknown panic'];self.reject(rs,'candidate')
if __name__=='__main__':unittest.main()
