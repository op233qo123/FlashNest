"""Execute only workflow's fixed classifier on synthetic logs; never xcodebuild."""
import json,pathlib,subprocess,sys,tempfile,textwrap,unittest
HERE=pathlib.Path(__file__).resolve().parent
WORKFLOW=(HERE/'observe-sigill-phase-ios18_2.yml').read_text()
CODE=textwrap.dedent(WORKFLOW.split('          import json,re,sys\n',1)[1].split('          PYBUILD',1)[0])
CODE='import json,re,sys\n'+CODE
class BuildStatusTests(unittest.TestCase):
 def classify(self,body,code=70):
  with tempfile.TemporaryDirectory()as t:
   path=pathlib.Path(t)/'PRIVATE_PATH-build.log'
   if body is not None:path.write_bytes(body)
   before=path.read_bytes()if path.exists()else None
   r=subprocess.run([sys.executable,'-',str(path),str(code)],input=CODE,text=True,capture_output=True,check=True)
   self.assertEqual(r.stderr,'');self.assertTrue(r.stdout.startswith('SIGILL_BUILD_STATUS '));self.assertEqual(len(r.stdout.splitlines()),1)
   self.assertNotIn('PRIVATE',r.stdout);self.assertEqual(path.read_bytes()if path.exists()else None,before)
   result=json.loads(r.stdout.split(' ',1)[1]);self.assertEqual(set(result),{'classification','exitCode'});self.assertEqual(result['exitCode'],code);return result['classification']
 def test_classifications_and_no_raw_log_payload(self):
  for body,want in [(b'xcodebuild: error: unsupported device specifier option PRIVATE_UDID','unsupported-destination-option'),(b'xcodebuild: error: Unable to find a destination matching the provided destination specifier PRIVATE_PATH','destination-unavailable'),(b'/PRIVATE_PATH/Example.swift:14:7: error: PRIVATE_GAME','compile-error'),(b'clang: error: PRIVATE_PATH','compile-error'),(b'PRIVATE_GAME unknown failure','unknown'),(None,'unknown'),(b'unsupported destination specifier PRIVATE_GAME','unknown')]:
   with self.subTest(want=want):self.assertEqual(self.classify(body),want)
 def test_bounded_tail_scan_does_not_modify_large_log(self):
  self.assertEqual(self.classify(b'PRIVATE_PREFIX\n'+b'x'*(5*1024*1024)+b'\nxcodebuild: error: Found no destinations for the scheme PRIVATE_NAME'), 'destination-unavailable')
 def test_exact_destination_and_compiler_flags_and_failure_exit(self):
  line=next(x.strip()for x in WORKFLOW.splitlines()if x.strip().startswith('xcodebuild build '))
  self.assertIn("-destination 'platform=iOS Simulator,id=${{ steps.simulator.outputs.device_id }}'",line)
  self.assertNotIn(',arch=',line);self.assertIn('ARCHS=arm64 ONLY_ACTIVE_ARCH=YES',line)
  self.assertIn('> "$RUNNER_TEMP/phase-build.log" 2>&1',line)
  self.assertIn('build_exit=$?',WORKFLOW);self.assertIn('exit "$build_exit"',WORKFLOW)
  self.assertIn('if [ "$build_exit" -ne 0 ]; then',WORKFLOW)
  self.assertNotIn('cat "$RUNNER_TEMP/phase-build.log"',WORKFLOW)
if __name__=='__main__':unittest.main()
