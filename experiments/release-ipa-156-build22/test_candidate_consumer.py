"""Offline checks against the actual candidate artifact; no network or source edits."""
import copy,hashlib,json,pathlib,sys,unittest,os,zipfile,io
ROOT=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import candidate_composite_runtime as c
ACTUAL=ROOT.parent/'native-lazy-graphic-diagnostic/actual-40998892881'
ENGINE=ACTUAL/'engine/lazy-graphic-engine'

class CandidateConsumer(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.archive=pathlib.Path(os.environ.get('CANDIDATE_ARCHIVE',str(ACTUAL/'engine.zip'))).read_bytes();z=zipfile.ZipFile(io.BytesIO(cls.archive));cls.receipt=c.parse(z.read(c.PREFIX+'provenance.json'))
  r=cls.receipt;rows=c.parse(z.read(c.PREFIX+'runtime-files.json'))
  cls.manifest={k:v['sha256'] for k,v in rows.items()}
  cls.lock=dict(schemaVersion=4,runtimeKind=c.KIND,runtimePrefix=c.PREFIX+'runtime/',provenancePath=c.PREFIX+'provenance.json',archiveBytes=len(cls.archive),sha256=c.digest(cls.archive),provenanceSHA256=c.digest(z.read(c.PREFIX+'provenance.json')),upstreamSourceCommit=r['upstreamCommit'],buildSourceCommit=r['run']['GITHUB_SHA'],buildRunID=int(r['run']['GITHUB_RUN_ID']),version='0.7.1',experimentalVersionName=r['versionSeal']['version_name'],sourceLockSHA256=r['sourceLockSHA256'],sourceSetSHA256=r['sourceSetSHA256'],runtimeInventorySHA256=r['runtimeInventorySHA256'])
  identity={k:cls.lock[k] for k in ['runtimeKind','experimentalVersionName','upstreamSourceCommit','buildSourceCommit','buildRunID','provenanceSHA256','sourceLockSHA256','sourceSetSHA256','runtimeInventorySHA256']}
  identity.update(schemaVersion=3,artifactArchiveSHA256=cls.lock['sha256'],upstreamBaseVersion='0.7.1',runtimeFiles=rows)
  cls.identity=json.dumps(identity,sort_keys=True,separators=(',',':')).encode();cls.lock['identitySHA256']=c.digest(cls.identity)
  cp=c.PREFIX+'source-correspondence/';cls.source=c.parse(z.read(cp+'source-lock.json'));cls.policy=c.parse(z.read(cp+cls.source['productionGcReview']['path']))
  cls.base=z.read(cp+'base-source-lock.json');cls.base_review=z.read(cp+'reviews/base-touch-engine-source-eligibility.json')
 def verify_policy(self,source=None,policy=None,base=None,review=None,corr=None):
  c.verified_candidate_policy(source or self.source,policy or self.policy,self.base if base is None else base,self.base_review if review is None else review,self.receipt['correspondence'] if corr is None else corr,self.lock['sourceSetSHA256'])
 def test_actual_archive_strict_acceptance(self):
  output=c.verified_runtime(self.archive,self.lock,self.manifest,self.identity)
  self.assertEqual(set(output),set(self.manifest))
  self.assertFalse(self.policy['productionAccepted']);self.assertTrue(self.policy['candidateDiagnosticBuildReviewed'])
 def test_policy_no_production_or_test_hook_promotion(self):
  self.verify_policy()
  for key,value in [('productionAccepted',True),('candidateDiagnosticBuildReviewed',False),('strongMigrationRootsPresent',True),('testOnlyReleaseHooksEnabled',True),('nativeAcceptance',True)]:
   policy=copy.deepcopy(self.policy);policy[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.verify_policy(policy=policy)
 def test_only_graphic_delta_allowed(self):
  for path in ['core/src/player.rs','web/src/lib.rs']:
   source=copy.deepcopy(self.source);source['modifiedSourceFiles'][path]['sha256']='0'*64
   with self.subTest(path=path),self.assertRaises(ValueError):self.verify_policy(source=source)
  source=copy.deepcopy(self.source);source['modifiedSourceFiles'].pop(c.GRAPHIC)
  with self.assertRaises(ValueError):self.verify_policy(source=source)
 def test_inherited_contract_and_bytes_locked(self):
  for key,value in [('runtimeValidated',True),('releaseEligible',True),('nativeAcceptance',True),('finalRuntimeBrowserAcceptance',True),('requiredFeatures',[])]:
   source=copy.deepcopy(self.source);source[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.verify_policy(source=source)
  with self.assertRaises(ValueError):self.verify_policy(base=self.base+b' ')
  with self.assertRaises(ValueError):self.verify_policy(review=self.base_review+b' ')
  corr=copy.deepcopy(self.receipt['correspondence']);corr.pop('base-source-lock.json')
  with self.assertRaises(ValueError):self.verify_policy(corr=corr)
 def test_patch_and_delta_binding(self):
  source=copy.deepcopy(self.source);source['patches'][0]['sha256']='0'*64
  with self.assertRaises(ValueError):self.verify_policy(source=source)
  for key in ['beforeSHA256','afterSHA256','patchSHA256','path']:
   policy=copy.deepcopy(self.policy);policy['productDelta'][key]='bad'
   with self.subTest(key=key),self.assertRaises(ValueError):self.verify_policy(policy=policy)
 def test_archive_identity_and_runtime_extras_fail(self):
  with self.assertRaises(ValueError):c.verified_runtime(self.archive+b'changed',self.lock,self.manifest,self.identity)
  manifest=dict(self.manifest,unexpected='0'*64)
  with self.assertRaises(ValueError):c.verified_runtime(self.archive,self.lock,manifest,self.identity)
  lock=dict(self.lock,runtimePrefix='final-composite-engine/runtime/')
  with self.assertRaises(ValueError):c.verified_runtime(self.archive,lock,self.manifest,self.identity)
if __name__=='__main__':unittest.main()
