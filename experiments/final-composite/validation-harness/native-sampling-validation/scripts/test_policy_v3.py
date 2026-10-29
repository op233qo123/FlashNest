"""Synthetic policy/negative-scope tests. No native execution or render certification."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw
import prepare_overlay as stage
import verify_results as v
from test_verifier import measurement

class PolicyContracts(unittest.TestCase):
    def test_new_auto_actual_load_and_backend_required(self):
        row,s=measurement();row['rendererPolicy']='automatic';s['measurement']['loadObservation']['rendererQuery']=None
        self.assertEqual(v.check_measurement(row,s,'candidate','baseline'),.25)
        for field,value in [('preferredRenderer',None),('hasPreferredRenderer',False),('rendererQuery','enhanced'),('count',2),('count',True),('hasQuality',True)]:
            bad=copy.deepcopy(s);bad['measurement']['loadObservation'][field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):v.check_measurement(row,bad,'candidate','baseline')
        bad=copy.deepcopy(s);bad['measurement']['renderer']='wgpu-webgl'
        with self.assertRaises(AssertionError):v.check_measurement(row,bad,'candidate','baseline')
    def test_candidate_executable_map_is_not_metadata_exception(self):
        base=stage.ROOT/'approved-app-source-manifest.json';new=stage.ROOT/'approved-candidate-app-source-manifest.json'
        oldmap={r['path']:r['sha256'] for r in json.loads(base.read_text())['files'] if r['path'].startswith('App/') and not r['path'].startswith('App/Resources/Web/runtime/')}
        newmap={r['path']:r['sha256'] for r in json.loads(new.read_text())['files']}
        with self.assertRaises(AssertionError):stage.resolve_app_manifest(oldmap,new,stage.sha(new))
        self.assertEqual(stage.sha(new),stage.APPROVED_CANDIDATE_APP_MANIFEST_SHA256)
        self.assertEqual(stage.resolve_app_manifest(newmap,new,stage.sha(new),stage.APPROVED_CANDIDATE_APP_MANIFEST_SHA256)[0],newmap)
    def enhanced(self,p):
        image=Image.new('RGB',(64,64),'white');image.save(p/'blank.png');h=hashlib.sha256((p/'blank.png').read_bytes()).hexdigest()
        identity={'arm':'candidate','rendererPolicyContract':'candidate-three-mode-v1'};records=[];boundaries=[]
        for dpr in (2,3):
            for label,t in [('ready',0),('after-5s',5),('after-15s',15)]:
                m={'dpr':dpr,'css':[0,0,375,602],'loadObservation':{'count':1,'rendererQuery':'enhanced','hasPreferredRenderer':False,'preferredRenderer':None,'hasQuality':False,'renderScale':1},'events':[],'overflow':False,'diagnosticOverflow':False,'sampledAtMs':1000+1000*t,'renderer':'wgpu-webgl','contextLost':True,'gl':[0,0]}
                s={'screenScale':dpr,'identity':identity,'os':'18.2','epoch':1,'gate':True,'requested':1,'failure':'','traceOverflow':False,'measurement':m,'traces':['DENSITY|READY|375|602|noScale|']}
                records.append({'snapshot':s,'label':label,'diagnosticOnly':True,'nativeAcceptance':False,'targetElapsedSeconds':t,'elapsedSeconds':t,'anchorUptimeSeconds':10,'observedUptimeSeconds':10+t,'captureFinishedUptimeSeconds':11+t,'cropSHA256':h,'observationError':''})
            before=copy.deepcopy(s);before['measurement']['sampledAtMs']+=100;failed=copy.deepcopy(s);failed.update(failure='real navigation failure',status='unknown',navigationEvents=['provisional-failure'])
            boundaries.append({'beforeFailure':before,'failed':failed,'diagnosticOnly':True,'nativeAcceptance':False,'beforeFailureUptimeSeconds':27,'failedUptimeSeconds':30})
        return records,boundaries,{h:p/'blank.png'},identity
    def test_enhanced_unhealthy_is_explicit_not_health_pass(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.enhanced(Path(d));r=v.verify_enhanced_boundary(*args)
            self.assertTrue(r['configurationAndErrorBoundaryVerified']);self.assertFalse(r['nativeAcceptance']);self.assertFalse(r['platformRenderHealthCertified'])
            self.assertTrue(all(x['observedOutcome']=='bounded-unhealthy' for x in r['observations']))
    def test_enhanced_wrong_forwarding_identity_timing_or_failure_visibility_rejected(self):
        for mutant in ('forced','identity','epoch','timing','failure','missing','input','callbacks','dpr','replacement','earlyboundary'):
            with self.subTest(mutant=mutant),tempfile.TemporaryDirectory() as d:
                records,bounds,pngs,identity=self.enhanced(Path(d));s=records[1]['snapshot'];m=s['measurement']
                if mutant=='forced':m['loadObservation']['hasPreferredRenderer']=True
                if mutant=='identity':s['identity']={'arm':'baseline'}
                if mutant=='epoch':s['epoch']=2
                if mutant=='timing':records[1]['elapsedSeconds']=80
                if mutant=='failure':bounds[0]['failed']['failure']=''
                if mutant=='missing':records.pop()
                if mutant=='input':m['events']=[{}]
                if mutant=='callbacks':s['traces'].append('DENSITY|MOTION|1')
                if mutant=='dpr':m['dpr']=7
                if mutant=='replacement':bounds[0]['beforeFailure']['epoch']=bounds[0]['failed']['epoch']=2
                if mutant=='earlyboundary':bounds[0]['beforeFailureUptimeSeconds']=1
                with self.assertRaises(AssertionError):v.verify_enhanced_boundary(records,bounds,pngs,identity)
if __name__=='__main__':unittest.main(verbosity=2)
