import json,tempfile,unittest
from pathlib import Path
import collect_evidence as c
SECRET='PRIVATE_SENTINEL'
def fail():return {'schema':1,'step':'restartPlay','source':'LifecyclePlayerUITests.swift','line':128,'kind':'assertion','message':SECRET,'url':'https://'+SECRET}
def ax():return {'schema':1,'step':'restartPlay','webViewPresent':True,'controls':[{'id':i,'exists':True,'enabled':False,'label':SECRET} for i in c.IDS],'hierarchy':SECRET}
class Collector(unittest.TestCase):
 def test_markers_retain_line_without_attachments_and_strip_values(self):
  text='FINAL_UI_STEP restartPlay\nFINAL_UI_FAILURE '+json.dumps(fail())+'\nFINAL_UI_AX '+json.dumps(ax())+'\n'+SECRET
  observed=c.parse_markers(text);self.assertEqual(observed['failures'][0]['line'],128);self.assertNotIn(SECRET,json.dumps(observed));self.assertEqual(len(observed['safeAX'][0]['controls']),6)
 def test_unknown_enum_source_or_identifier_rejected(self):
  for key,value in [('step',SECRET),('source','/Users/'+SECRET),('line',True),('kind',SECRET)]:
   row=fail();row[key]=value;self.assertIsNone(c.failure(row))
  row=ax();row['controls'][0]['id']=SECRET;self.assertIsNone(c.safe_ax(row))
 def test_only_whitelisted_manifest_test_and_names_are_retained(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);private=root/'private';private.mkdir();exported=private/'exported-final-ui';exported.mkdir();file='11111111-1111-1111-1111-111111111111.txt';(exported/file).write_text(json.dumps(fail()));(exported/'manifest.json').write_text(json.dumps([{'testIdentifier':c.TEST,'attachments':[{'suggestedHumanReadableName':'final-ui-failure_0_11111111-1111-1111-1111-111111111111.txt','exportedFileName':file},{'suggestedHumanReadableName':'Home raw debug_0_11111111-1111-1111-1111-111111111111.txt','exportedFileName':file}]}]));(private/'ui.log').write_text(SECRET);(private/'ui-summary.json').write_text(json.dumps({'failedTests':1,'message':SECRET}));out=root/'public';c.collect(private,out);alltext=''.join(p.read_text() for p in out.iterdir());self.assertNotIn(SECRET,alltext);observed=json.loads((out/'safe-ui-observation.json').read_text());self.assertTrue(observed['failureLocationAvailable']);self.assertEqual(observed['counts'],{'failedTests':1});self.assertFalse((out/'ui.log').exists())
 def test_unsafe_export_filename_not_opened(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);private=root/'private';private.mkdir();exported=private/'exported-final-ui';exported.mkdir();(exported/'manifest.json').write_text(json.dumps([{'testIdentifier':c.TEST,'attachments':[{'suggestedHumanReadableName':'final-ui-failure_0_11111111-1111-1111-1111-111111111111.txt','exportedFileName':'../../private.txt'}]}]));out=root/'public';c.collect(private,out);self.assertFalse(json.loads((out/'safe-ui-observation.json').read_text())['failureLocationAvailable'])
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);private=root/'private';private.mkdir();(private/'ui.log').write_text('FINAL_UI_FAILURE '+json.dumps(dict(fail(),source='unknown',line=0)));out=root/'public';c.collect(private,out);row=json.loads((out/'safe-ui-observation.json').read_text());self.assertTrue(row['failureMarkerAvailable']);self.assertFalse(row['failureLocationAvailable'])
 def test_bounds_and_no_release_workflow(self):
  text='\n'.join('FINAL_UI_FAILURE '+json.dumps(dict(fail(),line=i)) for i in range(20));self.assertEqual(len(c.parse_markers(text)['failures']),3)
  flow=Path(__file__).with_name('workflow.yml').read_text()
  for forbidden in ('-configuration Release','package_unsigned.sh','run_selected_tests.py release-package/app','path: ui-private'):
   self.assertNotIn(forbidden,flow)
if __name__=='__main__':unittest.main()
