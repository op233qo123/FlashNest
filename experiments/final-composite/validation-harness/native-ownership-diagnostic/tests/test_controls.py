import copy, importlib.util, json, pathlib, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
stage=load('stage_controls');verify=load('verify_observations')
class Controls(unittest.TestCase):
 def test_source_and_inverse(self):
  source=pathlib.Path('renderer-policy-repair/full-v3-app/App/Views/PlayerView.swift').read_bytes()
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);(p/'App/Views').mkdir(parents=True);(p/'Tests').mkdir();(p/'App/Views/PlayerView.swift').write_bytes(source);(p/'Tests/existing.swift').write_text('unchanged')
   before=stage.filemap(p);proof=stage.apply_overlay(p);self.assertTrue(proof['exactInverseVerified']);(p/stage.TARGET).unlink();self.assertEqual(stage.filemap(p),before)
   (p/'App/Views/PlayerView.swift').write_bytes(source+b'\n')
   with self.assertRaises(AssertionError):stage.apply_overlay(p)
 def records(self):
  common=dict(schema='flashnest-restart-ownership-diagnostic-v1',diagnosticOnly=True,nativeAcceptance=False,renderHealthCertified=False,observationComplete=True)
  owner=dict(common,control='owners',bothOwnersAlive=True,containerOnlyAlive=True,explicitOwnerAfterDetachAlive=True,weakNilAfterAllOwnersDropped=True,observationWindowSeconds=3,gpuMemoryReclamationProven=False)
  result=[owner]
  for name in ('same-turn','rendered-nil'):
   samples=[dict(uptimeSeconds=10+i*.05,displayedCount=1,displayedOld=False,displayedReplacement=True,displayedForeign=False,modelIsReplacement=True,oldHasSuperview=False,newHasSuperview=True) for i in range(40)]
   result.append(dict(common,control=name,initialAttached=True,sourceCopyNotProductionView=True,oldStronglyHeldForIdentityComparison=True,identityMatches=True,nilRenderedBeforeReplacement=True if name=='rendered-nil' else None,samples=samples))
  return result
 def test_outcomes_not_health(self):
  r=self.records();verify.verify_records(r)
  r[0]['weakNilAfterAllOwnersDropped']=False;r[1]['identityMatches']=False
  for s in r[1]['samples']:s.update(displayedOld=True,displayedReplacement=False,oldHasSuperview=True,newHasSuperview=False)
  out=verify.verify_records(r);self.assertFalse(out['nativeAcceptance']);self.assertFalse(out['sameTurnIdentityMatches']);self.assertIn('inconclusive',out['weakReleaseOutcome'])
 def test_reject_invalid(self):
  for mutate in [lambda r:r.pop(),lambda r:r.append(r[0]),lambda r:r[0].update(bothOwnersAlive=False),lambda r:r[0].update(containerOnlyAlive=False),lambda r:r[1].update(identityMatches=False),lambda r:r[2].update(nilRenderedBeforeReplacement=False),lambda r:r[1]['samples'][2].update(uptimeSeconds=float('nan')),lambda r:r[1]['samples'][2].update(displayedForeign=True),lambda r:r[1]['samples'].pop(),lambda r:r[0].update(nativeAcceptance=True)]:
   r=self.records();mutate(r)
   with self.assertRaises(AssertionError):verify.verify_records(r)
 def test_swift_scope(self):
  s=(ROOT/'RestartOwnershipDiagnosticTests.swift').read_text()
  self.assertEqual(s.count('    func test'),3)
  for forbidden in ('saveAndRestart(','.load(','.loadHTMLString(','.evaluateJavaScript(','.id(', 'Mirror('):self.assertNotIn(forbidden,s)
  self.assertIn('executionTimeAllowance = 30',s)
  for block in json.loads((ROOT/'source-pins.json').read_text())['exactSourceBlocks']:self.assertEqual(s.count(block),1)
if __name__=='__main__':unittest.main()
