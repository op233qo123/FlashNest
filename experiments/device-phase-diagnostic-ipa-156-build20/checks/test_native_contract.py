import pathlib, unittest, os, json, hashlib
ROOT=pathlib.Path(os.environ['PHASE_APP'])
class NativeContract(unittest.TestCase):
 def test_guards_and_optin(self):
  source=(ROOT/'App/Player/PlayerSession.swift').read_text()
  self.assertIn('loadingPhaseDiagnosticsEnabled && !storageOnly',source)
  self.assertIn('self.generation == attempt, !self.processTerminated',source)
  self.assertIn('snapshot.session == generation',source)
  self.assertIn('source === active, !processTerminated',source)
  self.assertIn('phaseSession',source)
 def test_bounds_and_atomic(self):
  source=(ROOT/'App/Player/LoadingPhaseDiagnostics.swift').read_text()
  for token in ['65_536','snapshots.count <= 2','events.count <= 32','eventCount < 256 || event.phase == .webProcessTerminated','options: .atomic','attributesOfItem(atPath: url.path)','clock=hostProcessingTime','eventCapReached=']:
   self.assertIn(token,source)
 def test_save_code_unchanged(self):
  baseline=json.loads((pathlib.Path(__file__).resolve().parents[1]/'inputs.json').read_text())['appGateOffFiles']
  for relative in ['Models/SaveStore.swift','Models/RawSOLImport.swift']:
   self.assertEqual(hashlib.sha256((ROOT/'App'/relative).read_bytes()).hexdigest(),baseline['App/'+relative])
 def test_no_raw_trace_persistence(self):
  source=(ROOT/'App/Player/LoadingPhaseDiagnostics.swift').read_text()
  for token in ['body["message"]','body["url"]','body["trace"]','body["save"]']:
   self.assertNotIn(token,source)
if __name__=='__main__': unittest.main()
