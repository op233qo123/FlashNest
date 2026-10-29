"""Synthetic DAG/transport negative controls. No native or remote execution."""
import copy,hashlib,importlib.util,io,json,os,stat,tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
RECIPE=HERE.parents[1]
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
r=load('multi_runner',HERE/'run.py');j=load('job_transfer',RECIPE/'scripts/job_evidence.py')
class Contracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name);self.env={'GITHUB_REPOSITORY':'op233qo123/FlashNest','GITHUB_RUN_ID':'1000','GITHUB_RUN_ATTEMPT':'2','GITHUB_SHA':'a'*40}
 def tearDown(self):self.tmp.cleanup()
 def identity(self,role):return {**self.env,'jobID':{'dpr2':2,'dpr3':3,'functional':4}[role],'jobName':'native-sampling-'+role if role!='functional' else 'native-functional','role':role}
 def rows(self):return [{'name':self.identity(role)['jobName'],'id':self.identity(role)['jobID'],'run_id':1000,'run_attempt':2,'head_sha':'a'*40,'status':'completed','conclusion':'success'} for role in ('dpr2','dpr3')]
 def test_job_metadata_rejects_other_attempt_head_run_duplicate_failure(self):
  with patch.dict(os.environ,self.env,clear=True):
   self.assertEqual(j.job_identity('dpr2',self.rows(),True),self.identity('dpr2'))
   missing=self.rows();missing[0].pop('run_attempt');paths=[]
   def api(path):paths.append(path);return io.BytesIO(json.dumps({'total_count':2,'jobs':missing}).encode())
   fake=SimpleNamespace(api=api,read_limited=lambda response,cap:response.read(cap))
   with patch.object(j,'transport',return_value=fake):self.assertEqual(j.job_identity('dpr2',completed=True),self.identity('dpr2'))
   self.assertEqual(paths,['actions/runs/1000/attempts/2/jobs?per_page=100'])
   for field,value in [('run_id',999),('run_attempt',1),('head_sha','b'*40),('status','in_progress'),('conclusion','failure')]:
    rows=self.rows();rows[0][field]=value
    with self.subTest(field=field),self.assertRaises(ValueError):j.job_identity('dpr2',rows,True)
   for rows in ([],self.rows()+[self.rows()[0]]):
    with self.assertRaises(ValueError):j.job_identity('dpr2',rows,True)
 def test_manifest_fullmap_rejects_tamper_extra_missing_link_and_false_acceptance(self):
  out=self.p/'leaf';out.mkdir();(out/'raw.json').write_text('raw')
  rec={'schema':1,'fullGeometryPending':True,'job':self.identity('dpr2'),'nativeAcceptance':False,'samplingJobPassed':True}
  j.freeze_leaf(out,rec);self.assertEqual(j.verify_leaf(out,rec['job']),rec)
  original=(out/'raw.json').read_bytes()
  (out/'raw.json').write_text('tamper')
  with self.assertRaises(ValueError):j.verify_leaf(out,rec['job'])
  (out/'raw.json').write_bytes(original);(out/'extra').write_text('extra')
  with self.assertRaises(ValueError):j.verify_leaf(out,rec['job'])
  (out/'extra').unlink();(out/'link').symlink_to(out/'raw.json')
  with self.assertRaises(ValueError):j.verify_leaf(out,rec['job'])
  (out/'link').unlink();(out/'raw.json').unlink()
  with self.assertRaises(ValueError):j.verify_leaf(out,rec['job'])
 def fixture(self):
  root=self.p/'runner';root.mkdir();sampling=self.p/'sampling';sampling.mkdir();incoming=self.p/'incoming';incoming.mkdir();out=self.p/'out';out.mkdir()
  (root/'helper-lock.json').write_text('exact helpers');(root/'selection-contract-v4.json').write_text('exact selection');(sampling/'method-map-v4.json').write_text('exact tier partition');binding=self.p/'binding.json';binding.write_text('exact binding')
  runner=object.__new__(r.Runner);runner.args=SimpleNamespace(sampling_input=incoming,binding=binding);runner.out=out;runner.results=[];runner.binding={'engine':{'sha256':'engine'},'appFiles':{'App/source.swift':'source'}}
  runner.selection_contract={'runs':[]};downloads={}
  for role in ('dpr2','dpr3'):
   leaf=incoming/role;leaf.mkdir();results=[]
   for lane,count in [('sampling-baseline',2),('sampling-candidate',23),('enhanced-boundary',1)]:
    name=lane+'-'+role;results.append({'runName':name,'tests':count});runner.selection_contract['runs'].append({'runName':name,'expectedCount':count})
    folder=leaf/'attachments'/name;folder.mkdir(parents=True);(folder/'synthetic.json').write_text('{}')
   r.dump(leaf/'sampling-expected-identities.json',{'baseline':{'engine':'old'},'candidate':{'engine':'new'}})
   receipt={'schema':1,'samplingJobPassed':True,'nativeAcceptance':False,'dpr':int(role[-1]),'job':self.identity(role),'bindingSHA256':r.sha(binding),'selectionContractSHA256':r.sha(root/'selection-contract-v4.json'),'methodMapSHA256':r.sha(sampling/'method-map-v4.json'),'helperLockSHA256':r.sha(root/'helper-lock.json'),'engineSHA256':'engine','appFiles':runner.binding['appFiles'],'results':results,'expectedIdentitiesSHA256':r.sha(leaf/'sampling-expected-identities.json'),'fullGeometryPending':True}
   j.freeze_leaf(leaf,receipt)
   downloads[role]={'job':self.identity(role),'artifactID':20+int(role[-1]),'artifactName':'fixture','archiveSHA256':'a'*64,'archiveBytes':100,'manifestSHA256':r.sha(leaf/'sampling-job-manifest.json'),'receiptSHA256':r.sha(leaf/'sampling-job-receipt.json')}
  r.dump(incoming/'download-receipt.json',downloads)
  return runner,root,sampling,incoming
 def import_fixture(self,runner,root,sampling):
  with patch.object(r,'ROOT',root),patch.object(r,'SAMPLING',sampling),patch.object(r,'load_module',return_value=j),patch.object(j,'job_identity',side_effect=lambda role,*a,**k:self.identity(role)):
   return runner.import_sampling_jobs()
 def test_both_leaves_preserve_independent_prefix_and_manifest(self):
  runner,root,sampling,incoming=self.fixture();self.import_fixture(runner,root,sampling)
  self.assertEqual(sum(x['tests'] for x in runner.results),52);self.assertEqual(len(runner.results),6)
  self.assertEqual({x['evidencePrefix'] for x in runner.results},{'sampling-jobs/dpr2','sampling-jobs/dpr3'})
  for role in ('dpr2','dpr3'):j.verify_leaf(runner.out/'sampling-jobs'/role,self.identity(role))
  self.assertFalse((runner.out/'attachments').exists());self.assertEqual(len(list((runner.out/'sampling-jobs').glob('*/attachments/*'))),6)
 def test_self_consistent_wrong_dependency_rejected(self):
  # Re-freeze each adversarial leaf to distinguish source/role checks from hash checks.
  for field,value in [('dpr',3),('bindingSHA256','bad'),('helperLockSHA256','bad'),('selectionContractSHA256','bad'),('methodMapSHA256','bad'),('engineSHA256','bad'),('appFiles',{}),('results',[{'runName':'sampling-candidate-dpr2','tests':26}])]:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
    old=self.p;self.p=Path(d);runner,root,sampling,incoming=self.fixture();self.p=old
    leaf=incoming/'dpr2';rec=json.loads((leaf/'sampling-job-receipt.json').read_text());rec[field]=value;(leaf/'sampling-job-manifest.json').unlink();j.freeze_leaf(leaf,rec)
    downloads=json.loads((incoming/'download-receipt.json').read_text());downloads['dpr2']['manifestSHA256']=r.sha(leaf/'sampling-job-manifest.json');downloads['dpr2']['receiptSHA256']=r.sha(leaf/'sampling-job-receipt.json');r.dump(incoming/'download-receipt.json',downloads)
    with self.assertRaises(ValueError):self.import_fixture(runner,root,sampling)
 def test_missing_slice_blocks_before_any_gate(self):
  runner,root,sampling,incoming=self.fixture();d=json.loads((incoming/'download-receipt.json').read_text());d.pop('dpr3');r.dump(incoming/'download-receipt.json',d)
  with self.assertRaises(ValueError):self.import_fixture(runner,root,sampling)
  self.assertEqual(runner.results,[])
 def test_geometry_failure_prevents_all_functional_execution(self):
  runner=object.__new__(r.Runner);runner.args=SimpleNamespace(role='functional');runner.out=self.p;runner.binding={};runner.preflight=lambda:None;runner.import_sampling_jobs=lambda:{'baseline':{'runtimeInventorySHA256':'old'},'candidate':{'runtimeInventorySHA256':'new'}};calls=[]
  def command(argv,name,**kw):
   calls.append(name)
   if name=='sampling-geometry-verifier':raise ValueError('real combined geometry failed')
  runner.command=command;runner.reset=lambda *a: self.fail('Functional simulator must not start')
  with self.assertRaises(ValueError):runner.execute()
  self.assertEqual(calls,['legacy-automatic-known-negative','sampling-geometry-verifier'])
 def test_transport_safe_archives_and_metadata(self):
  def archive(role,attack=None):
   receipt={'schema':1,'fullGeometryPending':True,'job':self.identity(role),'nativeAcceptance':False,'samplingJobPassed':True}
   raw=(json.dumps(receipt)+'\n').encode();manifest={'schema':1,'job':receipt['job'],'nativeAcceptance':False,'files':{'sampling-job-receipt.json':hashlib.sha256(raw).hexdigest()}}
   b=io.BytesIO()
   with zipfile.ZipFile(b,'w') as z:
    z.writestr('sampling-job-receipt.json',raw);z.writestr('sampling-job-manifest.json',json.dumps(manifest))
    if attack=='symlink':
     info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'target')
    elif attack:z.writestr(attack,'hostile')
   return b.getvalue()
  for attack in (None,'../escape','/absolute','a\\b','symlink','unmanifested'):
   with self.subTest(attack=attack):
    blobs={role:archive(role,attack if role=='dpr2' else None) for role in ('dpr2','dpr3')}
    metas=[{'id':2+i,'name':'FlashNest-native-sampling-'+role+'-attempt-2','expired':False,'digest':'sha256:'+hashlib.sha256(blobs[role]).hexdigest(),'size_in_bytes':len(blobs[role])} for i,role in enumerate(('dpr2','dpr3'))]
    fake=SimpleNamespace(api=lambda path:io.BytesIO(json.dumps({'total_count':2,'artifacts':metas}).encode()),read_limited=lambda response,cap:response.read(cap),fetch=lambda identity:blobs['dpr'+str(identity['artifactID'])])
    with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,self.env,clear=True),patch.object(j,'transport',return_value=fake),patch.object(j,'jobs',return_value=self.rows()):
     if attack is None:self.assertEqual(set(j.fetch_leaves(Path(d)/'download')),{'dpr2','dpr3'})
     else:
      with self.assertRaises(ValueError):j.fetch_leaves(Path(d)/'download')
  for field,value in [('expired',True),('digest',''),('name','wrong-attempt'),('size_in_bytes',j.CAP+1)]:
   with self.subTest(field=field):
    changed=copy.deepcopy(metas);changed[0][field]=value
    fake=SimpleNamespace(api=lambda path:io.BytesIO(json.dumps({'total_count':2,'artifacts':changed}).encode()),read_limited=lambda response,cap:response.read(cap),fetch=lambda identity:self.fail('Invalid metadata must fail before download'))
    with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,self.env,clear=True),patch.object(j,'transport',return_value=fake),patch.object(j,'jobs',return_value=self.rows()),self.assertRaises(ValueError):j.fetch_leaves(Path(d)/'download')
 def test_generated_plist_source_tool_and_unique_audio_exception(self):
  app=self.p/'app';(app/'App').mkdir(parents=True);out=self.p/'out';out.mkdir()
  (app/'project.yml').write_text('approved project');(out/'tool-receipt.json').write_text('actual tool');(app/'App/source.swift').write_text('unchanged')
  # Synthetic raw bytes: only the hash function for these TWO files is mocked.
  # This tests the narrow binding logic, not a claim to execute XcodeGen locally.
  generated=app/'App/Info.plist';raw=out/'main-gate-on-generated-Info.plist';generated.write_text('synthetic plist');raw.write_text('synthetic plist')
  expected='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f';original_sha=r.sha
  rec={'files':{'App/Info.plist':expected},'artifact':raw.name,'projectSpecificationPath':'project.yml','projectSpecificationSHA256':r.sha(app/'project.yml'),'toolReceiptSHA256':r.sha(out/'tool-receipt.json')}
  def synthetic_sha(p):return expected if Path(p) in (raw,generated) else original_sha(p)
  r.dump(out/'main-gate-on-generated-app-files.json',rec)
  with patch.object(r,'sha',side_effect=synthetic_sha):
   self.assertEqual(r.gate_on_source_app_map(app,out),{'source.swift':original_sha(app/'App/source.swift')})
   for field,value in [('projectSpecificationSHA256','wrong'),('toolReceiptSHA256','wrong'),('artifact','other.plist'),('files',{'App/Info.plist':expected,'App/extra':expected})]:
    bad=copy.deepcopy(rec);bad[field]=value;r.dump(out/'main-gate-on-generated-app-files.json',bad)
    with self.subTest(field=field),self.assertRaises(ValueError):r.gate_on_source_app_map(app,out)
   r.dump(out/'main-gate-on-generated-app-files.json',rec);(app/'App/extra.swift').write_text('unexpected')
   with self.assertRaises(ValueError):r.require(r.gate_on_source_app_map(app,out)=={'source.swift':original_sha(app/'App/source.swift')},'Audio App exact map')
  with self.assertRaises(ValueError):r.gate_on_source_app_map(app,out) # Actual synthetic raw SHA is rejected.
 def test_project_rejects_wrong_real_generated_bytes_before_resolution(self):
  runner=object.__new__(r.Runner);runner.out=self.p/'out';runner.out.mkdir();runner.xcodegen='synthetic-tool';app=self.p/'app';(app/'App').mkdir(parents=True);(app/'project.yml').write_text('project')
  calls=[]
  def command(argv,name,*a,**k):calls.append(name);(app/'App/Info.plist').write_text('wrong raw bytes')
  runner.command=command
  with self.assertRaises(ValueError):runner.project(app,'sampling-candidate','FlashNestSamplingUI')
  self.assertEqual(calls,['sampling-candidate-xcodegen'])
 def test_original_waits_budget_and_gate_order(self):
  source=Path(r.__file__).read_text()
  self.assertIn('timeout=600',source);self.assertIn('seconds*cfg[\'expectedCount\']+300',source)
  self.assertLess(source.index("geometry['matrixPassed']"),source.index("main=self.copy_app('main-gate-off')"))
  self.assertLess(source.index("main=self.copy_app('main-gate-off')"),source.index("main=self.copy_app('main-gate-on')"))
if __name__=='__main__':unittest.main(verbosity=2)
