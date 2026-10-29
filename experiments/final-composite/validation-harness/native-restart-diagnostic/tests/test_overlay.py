import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('diag',ROOT/'stage_restart_diagnostic.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class Contracts(unittest.TestCase):
 def model(self,p,available=False):
  identity={'arm':'candidate','runtimeSHA256':'a'*64};folder=p/'attachments/restart-candidate';folder.mkdir(parents=True);png=folder/'raw.png';Image.new('RGB',(32,48),'white').save(png);h=v.sha(png)
  state={'identity':identity,'screenScale':2,'os':'18.2','epoch':1,'request':10,'failure':'Actual save/restart failed' if not available else '', 'restartObservation':{'saveReady':False,'saveFailure':'Save failed' if not available else '', 'restartFailure':'Save failed' if not available else '', 'restartRequired':False,'hasWebView':True,'restartPhase':'returned-false' if not available else 'attached','processTerminated':None,'preservationStage':None,'privateFieldAvailability':'not-exposed-by-product'}}
  records=[]
  for label in v.LABELS:
   r={'schema':'flashnest-restart-observation-v1','identity':identity,'row':'candidate-dpr2-webgl-showAll-quarter-shipping-default-quality','label':label,'diagnosticOnly':True,'nativeAcceptance':False,'observedUptimeSeconds':100+len(records)}
   if label=='after-restart-wait-raw':r.update(restartPlayAvailable=available,originalPNGSHA256=h,cachedAXValue=json.dumps(state),cachedAXSanitized=True,cachedAXParseFailed=False)
   else:
    s=copy.deepcopy(state)
    if label=='after-restart-wait-refreshed':s['request']=11;r['restartPlayAvailable']=available
    r['snapshot']=s
   records.append(r)
  return identity,records
 def write(self,p,records):
  (p/'restart-candidate.log').write_text('\n'.join(v.MARKER+json.dumps(r) for r in records))
  for r in records:(p/'attachments/restart-candidate'/('obs-'+r['label']+'.json')).write_text(json.dumps(r))
 def test_complete_failure_observation_does_not_claim_health(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);identity,records=self.model(p);self.write(p,records);r=v.verify_evidence(p,identity)
   self.assertTrue(r['observationComplete'],r['errors']);self.assertTrue(r['hasFailure']);self.assertFalse(r['restartPlayAvailable']);self.assertFalse(r['nativeAcceptance']);self.assertFalse(r['renderHealthCertified'])
 def test_success_observation_is_not_render_certification(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);identity,records=self.model(p,True);self.write(p,records);r=v.verify_evidence(p,identity);self.assertTrue(r['observationComplete'],r['errors']);self.assertTrue(r['restartPlayAvailable']);self.assertFalse(r['renderHealthCertified'])
 def test_missing_duplicate_identity_png_private_or_unsafe_errors_rejected(self):
  for mutation in ('missing','duplicate','identity','png','private','url','token','stale','timing','epoch','error-type'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    p=Path(d);identity,records=self.model(p)
    if mutation=='missing':records.pop()
    if mutation=='duplicate':records.append(records[0])
    if mutation=='identity':records[0]['identity']={}
    if mutation=='png':records[2]['originalPNGSHA256']='missing'
    if mutation=='private':records[3]['snapshot']['restartObservation']['processTerminated']=False
    if mutation=='url':records[3]['snapshot']['failure']='bad https://example.test/cap'
    if mutation=='token':records[3]['snapshot']['failure']='cap '+'Z'*64
    if mutation=='stale':records[3]['snapshot']['request']=10
    if mutation=='timing':records[3]['observedUptimeSeconds']=99
    if mutation=='epoch':records[1]['snapshot']['epoch']=2
    if mutation=='error-type':records[3]['snapshot']['restartObservation']['saveFailure']=False
    self.write(p,records);self.assertFalse(v.verify_evidence(p,identity)['evidenceValid'])
 def test_apply_exact_two_files_inverse_and_no_product_change(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);app=p/'app';approved=p/'sampling';(app/'App').mkdir(parents=True);(app/'App/product').write_text('original product')
   for name,rel in v.TARGETS.items():
    for root in (approved,app/'NativeSamplingValidation'):(root/rel).parent.mkdir(parents=True,exist_ok=True);(root/rel).write_bytes((ROOT/'base'/name).read_bytes())
   proof=v.apply_overlay(app,approved);self.assertTrue(proof['exactInverseVerified']);self.assertTrue(proof['productAppUnchanged']);self.assertEqual(len(proof['changedFiles']),2)
   with self.assertRaises(ValueError):v.apply_overlay(app,approved)
 def test_original_wait_input_and_private_boundary_source(self):
  source=(ROOT/'overlay/NativeSamplingUITests.swift').read_text();host=(ROOT/'overlay/SamplingHost.swift').read_text()
  self.assertIn('let restartPlayAvailable = play.waitForExistence(timeout: 90)',source);self.assertIn('XCTAssertTrue(restartPlayAvailable); XCTAssertTrue(wait { play.isEnabled && play.isHittable }); play.tap()',source)
  self.assertLess(source.index('let bytes = XCUIScreen.main.screenshot().pngRepresentation'),source.index('let observed = try snapshot(app, allowingFailure: true)'))
  self.assertEqual(host.count('await session.saveAndRestart()'),1);self.assertNotIn('session.processTerminated',host);self.assertNotIn('session.preservationStage',host);self.assertNotIn('Mirror(',host)
  self.assertIn('if key == "identity" { result[key] = entry; continue }',source)
  original=(ROOT/'base/NativeSamplingUITests.swift').read_text();self.assertEqual(source.split('    private func lifecycle(')[0],original.split('    private func lifecycle(')[0])
if __name__=='__main__':unittest.main(verbosity=2)
