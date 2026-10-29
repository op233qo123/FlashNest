import pathlib,importlib.util,json,unittest,struct,zlib,re,copy
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
g=load('generate_fixtures');v=load('verify_phases')
class Tests(unittest.TestCase):
 def test_deterministic_encoding(self):
  for size,entropy in [(65536,32768),(65537,0),(70000,65530)]:
   a=g.build('SceneChild',size,entropy,b'seed');self.assertEqual(a,g.build('SceneChild',size,entropy,b'seed'))
   self.assertEqual(g.inspect(a)['actualDecodedBytes'],size)
  for zeros in [0,1,257,258,259,515,516,517,1000]:
   prefix=b'head';tail=bytes(range(256));raw=prefix+bytes(zeros)+tail
   stream=g.deterministic_zlib(prefix,zeros,tail)+struct.pack('>I',zlib.adler32(raw)&0xffffffff)
   self.assertEqual(zlib.decompress(stream),raw)
 def test_actual_generated_sizes_and_tags(self):
  m=json.loads((ROOT/'generated-local/manifest.json').read_text())
  for path,expected in m['files'].items():self.assertEqual(g.inspect((ROOT/'generated-local'/path).read_bytes()),expected)
  self.assertEqual(m['files']['sized/new.swf']['actualDecodedBytes'],48*g.MIB)
  self.assertLess(abs(m['files']['sized/new.swf']['compressedBytes']-43*g.MIB),128*1024)
  self.assertLess(sum(x['compressedBytes'] for x in m['files'].values()),64*g.MIB)
 def test_reject_bad_swf_length(self):
  a=bytearray(g.build('SceneChild',65536,100,b'seed'));a[4:8]=struct.pack('<I',1)
  with self.assertRaises(AssertionError):g.inspect(bytes(a))
 def phases(self):
  log=(ROOT/'core-smoke.log').read_text();return [json.loads(line[len('<SCENE_PHASE '):]) for line in log.splitlines() if line.startswith('<SCENE_PHASE ')]
 def test_actual_core_phase_evidence(self):
  rows=self.phases();self.assertEqual(len(rows),15);v.verify_as(rows)
 def test_phase_negative_controls(self):
  for edit in [lambda r:r.pop(),lambda r:r[7].update(phase='new.init'),lambda r:r[3].update(sequence=77),lambda r:r[2].update(bytesLoaded=0),lambda r:r[5].update(timeMs=-1)]:
   rows=copy.deepcopy(self.phases());edit(rows)
   with self.assertRaises(AssertionError):v.verify_as(rows)
if __name__=='__main__':unittest.main()
