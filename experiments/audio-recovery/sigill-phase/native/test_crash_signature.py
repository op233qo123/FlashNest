"""Synthetic IPS-signature projection; contains no real crash/user data."""
import json,unittest
from export_public import fault_signature
class SignatureTests(unittest.TestCase):
 def test_unresolved_fault_then_jsc_comparison_without_raw_address(self):
  body={'cpuType':'ARM-64','faultingThread':0,'threads':[{'name':'PRIVATE_GAME','registers':{'pc':999999},'frames':[
   {'imageIndex':0,'imageOffset':999999,'symbol':'PRIVATE_GAME'},
   {'imageIndex':1,'imageOffset':128,'symbol':'PRIVATE_GAME'}]}],
   'usedImages':[{'name':'???','size':0,'base':999999,'path':'PRIVATE_GAME'},
                 {'name':'JavaScriptCore','size':4096,'base':999999,'path':'PRIVATE_GAME'}]}
  got=fault_signature(body)
  self.assertEqual(got['faultingThread'],0);self.assertEqual(got['architecture'],'arm64');self.assertFalse(got['faultImageResolved'])
  self.assertEqual(got['faultThreadFrames'][0],{'imageClass':'unknown','imageOffset':None,'imageSize':0,'imageResolved':False})
  self.assertEqual(got['faultThreadFrames'][1],{'imageClass':'JavaScriptCore','imageOffset':128,'imageSize':4096,'imageResolved':True})
  text=json.dumps(got);self.assertNotIn('PRIVATE_GAME',text);self.assertNotIn('999999',text);self.assertNotIn('symbol',text);self.assertNotIn('base',text)
 def test_bounded_frames_and_allowlisted_image_classes(self):
  names=['JavaScriptCore','WebCore','WebKit','PRIVATE_GAME']
  images=[{'name':n,'size':1000,'path':'/System/Library/Frameworks/PRIVATE_GAME'}for n in names]
  frames=[{'imageIndex':i%4,'imageOffset':5,'symbol':'PRIVATE_GAME'}for i in range(20)]
  got=fault_signature({'cpuType':'x86_64','faultingThread':0,'threads':[{'frames':frames}],'usedImages':images})
  self.assertEqual(len(got['faultThreadFrames']),8);self.assertEqual(got['faultThreadFramesOmitted'],12);self.assertTrue(got['faultImageResolved'])
  self.assertEqual([f['imageClass']for f in got['faultThreadFrames'][:4]],['JavaScriptCore','WebCore','WebKit','other-system'])
  self.assertNotIn('PRIVATE_GAME',json.dumps(got))
 def test_bad_thread_indices_never_select_a_different_thread(self):
  for index in [None,-1,True,1,2**60,'0',{},[]]:
   got=fault_signature({'faultingThread':index,'threads':[{'frames':[{'imageIndex':0,'imageOffset':1}]}]})
   self.assertIsNone(got['faultingThread']);self.assertFalse(got['faultImageResolved']);self.assertEqual(got['faultThreadFrames'],[])
 def test_bad_offsets_and_images_are_unknown_not_addresses(self):
  for frame,image in [({'imageIndex':-1,'imageOffset':1},{'size':10}),({'imageIndex':True,'imageOffset':1},{'size':10}),({'imageIndex':0,'imageOffset':10},{'size':10}),({'imageIndex':0,'imageOffset':-1},{'size':10}),({'imageIndex':0,'imageOffset':True},{'size':10}),({'imageIndex':0,'imageOffset':2**60},{'size':2**61}),({'imageIndex':0,'imageOffset':1},{'size':'PRIVATE_GAME'}),({},None)]:
   got=fault_signature({'cpuType':{'private':'PRIVATE_GAME'},'faultingThread':0,'threads':[{'frames':[frame]}],'usedImages':[image]})
   self.assertEqual(got['architecture'],'unknown');self.assertFalse(got['faultImageResolved']);self.assertIsNone(got['faultThreadFrames'][0]['imageOffset']);self.assertNotIn('PRIVATE_GAME',json.dumps(got))
 def test_wrong_container_types_fail_closed_projection(self):
  for body in [{'threads':{},'usedImages':None,'faultingThread':0},{'threads':[None],'faultingThread':0},{'threads':[{'frames':{}}],'faultingThread':0}]:
   got=fault_signature(body);self.assertEqual(got['faultThreadFrames'],[]);self.assertFalse(got['faultImageResolved'])
if __name__=='__main__':unittest.main()
