"""Synthetic receipt validator tests only. These do not execute Ruffle."""
import copy,unittest
from run import validate

FIRST=['FIRST_CHILD_CONSTRUCTED','INIT_INFO_MATCH true','INIT','COMPLETE_INFO_MATCH true','FIRST_COMPLETE','PRE_CONTENT_PARENT_LOADER true','PRE_CONTENT_INFO_MATCH true']
CONTINUATION=['UNLOAD_BEGIN','UNLOAD_LISTENER_REMOVED','NEXT_BEGIN','FRESH_LOADER_CREATED','REQUEST next.swf','NEXT_LOAD_RETURNED','UNLOAD_END']
NEXT=['NEXT_CHILD_CONSTRUCTED','INIT_INFO_MATCH true','INIT','COMPLETE_INFO_MATCH true','NEXT_COMPLETE']

def row(arm,traces,swfs):
    return {'arm':arm,'snapshot':{'traces':[{'message':x} for x in traces],'error':None,'overflow':False},
        'observationSecondsAfterUnloadReturn':5.5,'renderer':'webgl','errors':[],'remoteRequests':[],'requestFailures':[],
        'responses':[{'name':x} for x in swfs],'requests':[{'name':x} for x in swfs]}
def fixture(delivered=False):
    control=FIRST+['TRANSITION_ENTER_FRAME','PRE_ATTACHED_CONTENT_PARENT_LOADER true','PRE_LOADER_PARENT_NULL true','UNLOAD_CALL_BEGIN']+CONTINUATION+['UNLOAD_CALL_RETURNED']+NEXT
    moved=FIRST+['PRE_CONTENT_PARENT_HOLDER true','TRANSITION_ENTER_FRAME','PRE_MOVED_PARENT_NULL true','PRE_HOLDER_EMPTY true','PRE_LOADER_PARENT_NULL true','UNLOAD_CALL_BEGIN']+(CONTINUATION if delivered else [])+['UNLOAD_CALL_RETURNED']+(NEXT if delivered else [])
    return [row('attached-control',control,['attached-control.swf','first.swf','next.swf']),row('moved-removed',moved,['moved-removed.swf','first.swf']+(['next.swf'] if delivered else []))]

class ValidatorTests(unittest.TestCase):
    def rejected(self,rows):
        with self.assertRaises(AssertionError):validate(rows)
    def test_valid_omission(self):self.assertEqual(validate(fixture()),'reproduced-unload-omission-after-content-removal')
    def test_valid_delivery(self):self.assertEqual(validate(fixture(True)),'unload-omission-not-reproduced')
    def test_control_missing_events(self):
        for marker in ('UNLOAD_BEGIN','NEXT_COMPLETE','INIT_INFO_MATCH true','COMPLETE_INFO_MATCH true'):
            rows=fixture();rows[0]['snapshot']['traces'].remove({'message':marker});self.rejected(rows)
    def test_false_or_missing_moved_preconditions(self):
        for marker in ('PRE_CONTENT_PARENT_LOADER true','PRE_CONTENT_INFO_MATCH true','PRE_CONTENT_PARENT_HOLDER true','PRE_MOVED_PARENT_NULL true','PRE_HOLDER_EMPTY true','COMPLETE_INFO_MATCH true'):
            for false in (False,True):
                rows=fixture();traces=rows[1]['snapshot']['traces'];traces.remove({'message':marker})
                if false:traces.append({'message':marker.replace('true','false')})
                self.rejected(rows)
    def test_short_window(self):
        rows=fixture();rows[1]['observationSecondsAfterUnloadReturn']=4.99;self.rejected(rows)
    def test_next_request_without_response(self):
        rows=fixture();rows[1]['requests'].append({'name':'next.swf'});self.rejected(rows)
    def test_request_failure(self):
        rows=fixture();rows[1]['requestFailures'].append({'name':'first.swf','failure':'network'});self.rejected(rows)
    def test_unexpected_continuation_without_unload(self):
        for marker in ('NEXT_BEGIN','REQUEST next.swf','NEXT_LOAD_RETURNED','NEXT_COMPLETE'):
            rows=fixture();rows[1]['snapshot']['traces'].append({'message':marker});self.rejected(rows)
    def test_partial_delivered_chain(self):
        for marker in ('UNLOAD_END','UNLOAD_LISTENER_REMOVED','NEXT_COMPLETE','NEXT_CHILD_CONSTRUCTED','COMPLETE_INFO_MATCH true','INIT_INFO_MATCH true'):
            rows=fixture(True);rows[1]['snapshot']['traces'].remove({'message':marker});self.rejected(rows)
    def test_bad_synchronous_order(self):
        rows=fixture(True);traces=rows[1]['snapshot']['traces'];traces.remove({'message':'UNLOAD_END'});traces.append({'message':'UNLOAD_END'});self.rejected(rows)
    def test_canvas_is_not_webgl(self):
        rows=fixture();rows[0]['renderer']='2d';self.rejected(rows)
if __name__=='__main__':unittest.main()
