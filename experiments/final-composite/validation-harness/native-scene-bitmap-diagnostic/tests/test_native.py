import pathlib,sys,json,copy,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import verify_phases as v
from test_bitmap import Bitmap
class Native(unittest.TestCase):
 def bundle(self,out):
  folder=out/'attachments/bitmap-scene-controls';folder.mkdir(parents=True)
  helper=Bitmap();old,identity=helper.make_visual(folder,'old');new,_=helper.make_visual(folder,'new');records=helper.phases();manifest=json.loads((ROOT/'fixture-manifest.json').read_text())
  full_as=[dict(nativeUptimeSeconds=30+i if i<7 else 70+i,phase=r) for i,r in enumerate(records)]
  body=[]
  for idx,asset in enumerate(('main.swf','old.swf','new.swf'),1):
   for phase in ('request','headers','array-buffer-start','array-buffer-complete'):
    row=dict(sequence=len(body)+1,phase=phase,id=idx,asset=asset,timeMs=len(body)+1)
    if phase=='headers':row['status']=200
    if phase=='array-buffer-complete':row['byteLength']=manifest['files']['sized-bitmap/'+asset]['compressedBytes']
    body.append(row)
  snapshots=[]
  for label,visual,request,at in [('old',old,1,45),('new',new,2,95)]:
   s=visual['snapshot'];s.update(schema='flashnest-native-scene-snapshot-v1',os='18.2',request=request,jsCompletedForRequest=request,observedUptimeSeconds=at,wkID=1,ready=True,terminated=False,failure='',asOverflow=False,traceSuppressed=False,asRecords=copy.deepcopy(full_as[:7] if label=='old' else full_as),transitionCount=0 if label=='old' else 1,transitionAt=None if label=='old' else 60)
   s['measurement'].update(loadObservation=dict(count=1,rendererQuery=None,hasPreferredRenderer=True,preferredRenderer='webgl',hasQuality=False,renderScale=1),wasm=['synthetic.wasm'],renderer='webgl')
   s['measurement']['renderCalls']={'drawElements':2 if label=='old' else 4}
   s['body']=dict(schema='flashnest-scene-body-observer-v1',records=copy.deepcopy(body[:8] if label=='old' else body),overflow=0,promiseReactionsAdded=True,unhandledRejectionObservationChanged=True,wasmCopyObservable=False,decompressionObservable=False)
   visual['nativeUptimeSeconds']=50 if label=='old' else 100;snapshots.append(s)
  final=copy.deepcopy(snapshots[-1]);final.update(request=3,jsCompletedForRequest=3,observedUptimeSeconds=110);snapshots.append(final)
  obs=[dict(schema='flashnest-native-scene-observation-v1',case='sized-bitmap',index=i+1,nativeUptimeSeconds=s['observedUptimeSeconds']+1,identity=identity,snapshot=s) for i,s in enumerate(snapshots)]
  summary=dict(schema='flashnest-native-scene-case-v1',case='sized-bitmap',identity=identity,launchedAt=0,readyAt=10,activeFinishedAt=105,finishedAt=112,observationCount=3,parentDoneObserved=True,terminated=False,error='',lastSnapshot=final,transitionAttempted=True,visualCount=2)
  return identity,obs,summary,[old,new]
 def write(self,out,obs,summary,visuals):
  rows=[('FLASHNEST_SCENE_OBSERVATION_JSON ',x) for x in obs]+[('FLASHNEST_SCENE_CASE_JSON ',summary)]+[('FLASHNEST_BITMAP_VISUAL_JSON ',x) for x in visuals]
  for p in (out/'attachments/bitmap-scene-controls').glob('*.json'):p.unlink()
  for i,(_,row) in enumerate(rows):(out/'attachments/bitmap-scene-controls'/f'{i}.json').write_text(json.dumps(row))
  (out/'bitmap-scene-controls.log').write_text('\n'.join(marker+json.dumps(row) for marker,row in rows))
 def test_complete_join(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp);identity,obs,summary,visuals=self.bundle(out);self.write(out,obs,summary,visuals)
   report=v.verify_native(out,identity,ROOT/'fixture-manifest.json');self.assertTrue(report['evidenceValid'],report['errors']);self.assertFalse(report['textureUploadCountMeasured'])
 def test_partial_and_trigger_draw_negatives(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp);identity,obs,summary,visuals=self.bundle(out)
   for mutation in [lambda o,s,w:w[0].update(nativeUptimeSeconds=65),lambda o,s,w:w[1]['snapshot']['measurement'].update(renderCalls={'drawElements':2}),lambda o,s,w:w[0]['snapshot']['measurement'].update(renderCalls={}),lambda o,s,w:w[0]['snapshot'].update(transitionCount=1),lambda o,s,w:s.update(error='original failure'),lambda o,s,w:w.pop(),lambda o,s,w:w[1]['geometry'].update(cropRectPixels=[0,91,750,1220])]:
    a,b,c=copy.deepcopy((obs,summary,visuals));mutation(a,b,c);self.write(out,a,b,c);report=v.verify_native(out,identity,ROOT/'fixture-manifest.json');self.assertFalse(report['evidenceValid']);self.assertIn('cases',report);self.assertTrue(report['observations'])
if __name__=='__main__':unittest.main()
