import pathlib,sys,copy,json,unittest,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import verify_phases as v
class Native(unittest.TestCase):
 def setup_data(self):
  manifest=json.loads((ROOT/'generated-local/manifest.json').read_text())
  records=[json.loads(l[len('<SCENE_PHASE '):]) for l in (ROOT/'core-smoke.log').read_text().splitlines() if l.startswith('<SCENE_PHASE ')]
  identity={'arm':'candidate','exactSource':'synthetic-control','runtimeFiles':{'synthetic.wasm':'source-hash'}};cases={}
  for case in ('tiny','sized'):
   body=[]
   for idx,asset in enumerate(('main.swf','old.swf','new.swf'),1):
    for phase in ('request','headers','array-buffer-start','array-buffer-complete'):
     row=dict(sequence=len(body)+1,phase=phase,id=idx,asset=asset,timeMs=len(body)+1)
     if phase=='headers':row['status']=200
     if phase=='array-buffer-complete':row['byteLength']=manifest['files'][case+'/'+asset]['compressedBytes']
     body.append(row)
   snap=dict(schema='flashnest-native-scene-snapshot-v1',case=case,identity=identity,observedUptimeSeconds=100,request=1,epoch=1,wkID=1,sameWK=True,os='18.2',screenScale=2,measurement=dict(dpr=2,loadObservation=dict(count=1,rendererQuery=None,hasPreferredRenderer=True,preferredRenderer='webgl',hasQuality=False,renderScale=1),wasm=['synthetic.wasm'],renderer='webgl'),ready=True,terminated=False,failure='',asOverflow=False,traceSuppressed=False,jsPending=False,jsCompletedForRequest=1,asRecords=[dict(nativeUptimeSeconds=90+i*.1,phase=r) for i,r in enumerate(records)],body=dict(schema='flashnest-scene-body-observer-v1',records=body,overflow=0,promiseReactionsAdded=True,unhandledRejectionObservationChanged=True,wasmCopyObservable=False,decompressionObservable=False))
   cases[case]=[snap]
  return cases,identity,manifest
 def test_complete_and_negative_cases(self):
  cases,identity,manifest=self.setup_data();self.assertTrue(v.verify_cases(cases,identity,manifest)['transitionComplete'])
  for mutate in [lambda s:s.update(terminated=True),lambda s:s['measurement']['loadObservation'].update(count=True),lambda s:s['measurement'].update(wasm=['unknown.wasm']),lambda s:s.update(screenScale=3),lambda s:s.update(identity={}),lambda s:s.update(epoch=2),lambda s:s.update(sameWK=False),lambda s:s.update(asOverflow=True),lambda s:s.update(traceSuppressed=True),lambda s:s.update(jsPending=True),lambda s:s['body']['records'][-1].update(byteLength=1),lambda s:s['body'].update(decompressionObservable=True),lambda s:s['asRecords'].pop()]:
   c=copy.deepcopy(cases);mutate(c['sized'][0]);report=v.verify_cases(c,identity,manifest);self.assertFalse(report['evidenceValid']);self.assertEqual(report['cases']['sized']['snapshots'],c['sized'])
 def test_file_join_and_missing_attachment(self):
  cases,identity,manifest=self.setup_data()
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp);att=out/'attachments/scene-loader-controls';att.mkdir(parents=True);mp=out/'fixture.json';mp.write_text(json.dumps(manifest));lines=[]
   for case in cases:
    snapshot=cases[case][0];obs=dict(schema='flashnest-native-scene-observation-v1',case=case,index=1,nativeUptimeSeconds=101,identity=identity,snapshot=snapshot)
    summary=dict(schema='flashnest-native-scene-case-v1',case=case,identity=identity,launchedAt=1,readyAt=2,activeFinishedAt=101,finishedAt=102,observationCount=1,parentDoneObserved=True,terminated=False,error='',lastSnapshot=snapshot)
    for name,data,marker in [('obs',obs,'FLASHNEST_SCENE_OBSERVATION_JSON '),('case',summary,'FLASHNEST_SCENE_CASE_JSON ')]:
     lines.append(marker+json.dumps(data));(att/(case+name+'.json')).write_text(json.dumps(data))
   (out/'scene-loader-controls.log').write_text('\n'.join(lines));self.assertTrue(v.verify_native(out,identity,mp)['transitionComplete'])
   pristine=list(lines)
   for patch in ({'activeFinishedAt':123,'finishedAt':124},{'finishedAt':112}):
    timed=json.loads(pristine[-1].split('FLASHNEST_SCENE_CASE_JSON ',1)[1]);timed.update(patch)
    lines[-1]='FLASHNEST_SCENE_CASE_JSON '+json.dumps(timed);(att/'sizedcase.json').write_text(json.dumps(timed));(out/'scene-loader-controls.log').write_text('\n'.join(lines))
    self.assertFalse(v.verify_native(out,identity,mp)['evidenceValid'])
   lines=pristine;normal=json.loads(lines[-1].split('FLASHNEST_SCENE_CASE_JSON ',1)[1]);(att/'sizedcase.json').write_text(json.dumps(normal));(out/'scene-loader-controls.log').write_text('\n'.join(lines))
   # Failed summary must still contain both cases' last-stage diagnosis.
   original=list(lines);failed=json.loads(lines[-1].split('FLASHNEST_SCENE_CASE_JSON ',1)[1]);failed['error']='Original deadline failure';failed['parentDoneObserved']=False
   lines[-1]='FLASHNEST_SCENE_CASE_JSON '+json.dumps(failed);(att/'sizedcase.json').write_text(json.dumps(failed));(out/'scene-loader-controls.log').write_text('\n'.join(lines))
   bad=v.verify_native(out,identity,mp);self.assertFalse(bad['evidenceValid']);self.assertEqual(bad['cases']['sized']['lastASPhase'],'parent.done');self.assertEqual(bad['cases']['sized']['lastBodyPhase'],'array-buffer-complete')
   # Restore summary then prove absent attachment also preserves raw snapshots.
   lines=original;restored=json.loads(lines[-1].split('FLASHNEST_SCENE_CASE_JSON ',1)[1]);(att/'sizedcase.json').write_text(json.dumps(restored));(out/'scene-loader-controls.log').write_text('\n'.join(lines))
   (att/'tinyobs.json').unlink();bad=v.verify_native(out,identity,mp);self.assertFalse(bad['evidenceValid']);self.assertEqual(len(bad['observations']),2);self.assertEqual(bad['cases']['tiny']['lastASPhase'],'parent.done')
if __name__=='__main__':unittest.main()
