"""Strict synthetic transition evidence; no native release acceptance or OOM inference."""
import math

def require(ok,message):
 if not ok:raise AssertionError(message)
def number(x):return type(x) in (int,float) and math.isfinite(x)
def verify_as(records,case):
 import importlib.util,pathlib
 spec=importlib.util.spec_from_file_location('retention_as_oracle',pathlib.Path(__file__).with_name('verify_as.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m.verify_as(records,case)

def verify_body(body,case,manifest):
 require(body['schema']=='flashnest-scene-body-observer-v1','Body schema')
 require(type(body['overflow']) is int and body['overflow']==0,'Body overflow')
 for p in ('promiseReactionsAdded','unhandledRejectionObservationChanged'):require(body[p] is True,'Observer limitation disclosure')
 for p in ('wasmCopyObservable','decompressionObservable'):require(body[p] is False,'Unobservable stage claimed')
 rows=body['records'];require(len(rows)==20,'Exactly five complete body operations')
 previous=-1;groups={}
 for i,r in enumerate(rows):
  require(type(r['sequence']) is int and r['sequence']==i+1,'Body sequence')
  require(number(r['timeMs']) and r['timeMs']>=previous,'Body time');previous=r['timeMs']
  require(type(r['id']) is int and r['id']>0,'Body request ID')
  require(r['asset'] in ('main-'+case+'.swf','prefix-a.swf','prefix-b.swf','old.swf','new.swf'),'Unexpected asset')
  groups.setdefault(r['id'],[]).append(r)
 require(len(groups)==5,'Request count')
 assets=[]
 for rows in groups.values():
  asset=rows[0]['asset'];assets.append(asset)
  require(all(r['asset']==asset for r in rows),'Request asset drift')
  require([r['phase'] for r in rows]==['request','headers','array-buffer-start','array-buffer-complete'],'Incomplete body stage')
  require(type(rows[1]['status']) is int and rows[1]['status']==200,'HTTP status')
  require(type(rows[3]['byteLength']) is int and rows[3]['byteLength']==manifest['files']['retention/'+asset]['compressedBytes'],'Actual body length')
 require(assets[0]=='main-'+case+'.swf' and set(assets[1:3])=={'prefix-a.swf','prefix-b.swf'} and assets[3:]==['old.swf','new.swf'],'Request asset order/set')
 return rows

def verify_cases(case_snapshots,expected_identity,fixture_manifest):
 report={'schema':'flashnest-native-retention-scene-verification-v1','diagnosticOnly':True,'nativeAcceptance':False,'renderHealthCertified':False,'cases':{},'errors':[],
 'wasmCopyObservable':False,'decompressionObservable':False,'cause':'unknown'}
 if set(case_snapshots)!={'retain','drop'}:report['errors'].append('Exact retain/drop cases required')
 for case in ('retain','drop'):
  snapshots=case_snapshots.get(case,[]);entry={'snapshots':snapshots,'errors':[],'lastASPhase':None,'lastBodyPhase':None};report['cases'][case]=entry
  # Diagnose from the latest available raw record even if validation fails earlier.
  if snapshots and isinstance(snapshots[-1],dict):
   last=snapshots[-1];entry['terminated']=last.get('terminated');entry['nativeFailure']=last.get('failure')
   if isinstance(last.get('measurement'),dict):
    entry['observedWASM']=last['measurement'].get('wasm');entry['observedRenderer']=last['measurement'].get('renderer')
   try:entry['lastASPhase']=last['asRecords'][-1]['phase']['phase']
   except (KeyError,IndexError,TypeError):pass
   try:entry['lastBodyPhase']=last['body']['records'][-1]['phase']
   except (KeyError,IndexError,TypeError):pass
  try:
   require(0<len(snapshots)<=42,'Snapshot count')
   wk=None;epoch=None;previous=-1;prior_as=[];prior_body=[];last_request=-1
   for snap in snapshots:
    require(snap['schema']=='flashnest-native-scene-snapshot-v1' and snap['case']==case,'Snapshot schema/case')
    require(snap['identity']==expected_identity,'External identity mismatch')
    require(number(snap['observedUptimeSeconds']) and snap['observedUptimeSeconds']>previous,'Snapshot monotonic');previous=snap['observedUptimeSeconds']
    require(type(snap['request']) is int and snap['request']>last_request,'Snapshot request monotonic');last_request=snap['request']
    if snap.get('wkID') is not None:
     require(type(snap['wkID']) is int and snap['wkID']>0,'WK scalar identity')
     if wk is None:wk=snap['wkID'];epoch=snap['epoch']
     require(snap['wkID']==wk and snap['epoch']==epoch and type(epoch) is int and epoch>0,'WK/epoch changed')
    require(snap['asOverflow'] is False,'AS overflow')
    require(snap['traceSuppressed'] is False,'Trace suppression')
    records=snap['asRecords'];require(len(records)<=64 and records[:len(prior_as)]==prior_as,'AS history rewritten');prior_as=records
    time=-1
    for row in records:require(number(row['nativeUptimeSeconds']) and time<=row['nativeUptimeSeconds']<=snap['observedUptimeSeconds'],'Native AS time');time=row['nativeUptimeSeconds']
    body=snap.get('body')
    if body:
     rows=body['records'];require(rows[:len(prior_body)]==prior_body,'Body history rewritten');prior_body=rows
    require(snap['terminated'] is False,'Current WK terminated')
    require(not snap['failure'],'Native failure')
   final=snapshots[-1];require(wk is not None and final['wkID']==wk,'Missing final WK')
   require(final['ready'] is True,'Not ready')
   require(final['epoch']==1,'Unexpected page epoch')
   require(type(final['transitionCount']) is int and final['transitionCount']==1,'Exactly one native Space pair')
   require(final['sameWK'] is True,'Not same WK')
   require(final['jsPending'] is False and final['jsCompletedForRequest']==final['request'],'Final JS result not fresh')
   require(final['os']=='18.2' and type(final['screenScale']) in (int,float) and final['screenScale']==2,'Exact approved device/DPR')
   m=final['measurement'];load=m['loadObservation']
   require(number(m['dpr']) and m['dpr']==2,'Actual CSS DPR')
   require(type(load['count']) is int and load['count']==1,'Actual load count')
   require(load['rendererQuery'] is None and load['hasPreferredRenderer'] is True and load['preferredRenderer']=='webgl','Actual Automatic config differs')
   require(load['hasQuality'] is False and number(load['renderScale']) and load['renderScale']==1,'Actual Original/default quality differs')
   require(isinstance(m['wasm'],list) and len(m['wasm'])==1 and m['wasm'][0] in expected_identity['runtimeFiles'],'Actual WASM branch unobserved/ambiguous')
   entry['actualWASM']=m['wasm'][0];entry['actualRenderer']=m.get('renderer')
   entry['phases']=verify_as([r['phase'] for r in final['asRecords']],case)
   verify_body(final['body'],case,fixture_manifest)
   entry['transitionComplete']=True
  except (AssertionError,KeyError,TypeError,ValueError) as e:
   entry['errors'].append(str(e));entry['transitionComplete']=False
  report['errors'] += [case+': '+e for e in entry['errors']]
 if not report['errors']:
  left,right=report['cases']['retain'],report['cases']['drop']
  if left.get('actualWASM')!=right.get('actualWASM') or left.get('actualRenderer')!=right.get('actualRenderer') or left.get('actualRenderer') not in ('webgl','wgpu-webgl','webgpu'):
   report['errors'].append('Actual engine branch/renderer differs or is unobserved across the pair')
 report['evidenceValid']=not report['errors'];report['transitionComplete']=report['evidenceValid']
 return report

def verify_native(out,expected_identity,fixture_manifest_path):
 import json,pathlib,hashlib
 out=pathlib.Path(out);manifest_path=pathlib.Path(fixture_manifest_path)
 grouped={'retain':[],'drop':[]}
 result={'diagnosticOnly':True,'nativeAcceptance':False,'renderHealthCertified':False,'errors':[],'observations':[],'caseSummaries':[]}
 try:
  raw=(out/'retention-scene-controls.log').read_text();require(len(raw.encode())<=16*1024*1024,'Log exceeds bound')
  observations=[];summaries=[]
  for line in raw.splitlines():
   for marker,target in [('FLASHNEST_SCENE_OBSERVATION_JSON ',observations),('FLASHNEST_SCENE_CASE_JSON ',summaries)]:
    if marker in line:
     payload=line.split(marker,1)[1];require(len(payload.encode())<=65536,'Record exceeds bound');target.append(json.loads(payload))
  result['observations']=observations;result['caseSummaries']=summaries
  require(len(observations)<=84 and len(summaries)==2,'Exact bounded case summary count')
  require({s['case'] for s in summaries}=={'retain','drop'},'Case summary roles')
  attachments=[]
  for p in (out/'attachments/retention-scene-controls').rglob('*.json'):
   if p.stat().st_size<=65536:
    try:attachments.append(json.loads(p.read_text()))
    except (ValueError,UnicodeError):pass
  for obs in observations:
   require(obs['schema']=='flashnest-native-scene-observation-v1','Observation schema')
   case=obs['case'];require(case in grouped and obs['identity']==expected_identity,'Observation identity')
   require(type(obs['index']) is int and obs['index']==len(grouped[case])+1,'Observation index')
   require(number(obs['nativeUptimeSeconds']),'Observation time')
   require(sum(a==obs for a in attachments)==1,'Observation attachment absent/duplicate')
   grouped[case].append(obs['snapshot'])
  for summary in summaries:
   require(summary['schema']=='flashnest-native-scene-case-v1' and summary['identity']==expected_identity,'Summary identity')
   require(sum(a==summary for a in attachments)==1,'Summary attachment absent/duplicate')
   require(summary['observationCount']==len(grouped[summary['case']]),'Summary count')
   require(summary['lastSnapshot']==grouped[summary['case']][-1],'Summary final snapshot')
   require(summary['parentDoneObserved'] is True and summary['terminated'] is False and not summary['error'],'Case did not complete in original deadline')
   for key in ('launchedAt','readyAt','activeFinishedAt','finishedAt'):require(number(summary[key]),'Case timing missing')
   require(summary['launchedAt']<=summary['readyAt']<=summary['activeFinishedAt']<=summary['finishedAt'],'Case timing order')
   require(summary['activeFinishedAt']-summary['launchedAt']<=165,'Case wall window exceeded165s')
   require(summary['finishedAt']-summary['activeFinishedAt']<=10,'Extra evidence exceeded10s')
  result['fixtureManifestSHA256']=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
 except (AssertionError,KeyError,TypeError,ValueError,OSError,IndexError,StopIteration) as error:
  result['errors'].append(str(error));result['evidenceValid']=False;result['transitionComplete']=False
 # Always compute partial last-phase summaries, including on missing-done/termination/errors.
 grouped={case:[o['snapshot'] for o in result['observations'] if isinstance(o,dict) and o.get('case')==case and isinstance(o.get('snapshot'),dict)] for case in ('retain','drop')}
 try:
  partial=verify_cases(grouped,expected_identity,json.loads(manifest_path.read_text()))
  prior_errors=result['errors'];result.update(partial);result['errors']=prior_errors+partial['errors']
  result['evidenceValid']=not result['errors'];result['transitionComplete']=result['evidenceValid']
 except (OSError,ValueError,TypeError) as error:
  result['errors'].append(str(error));result['evidenceValid']=False;result['transitionComplete']=False
 return result

# Keep base phase evidence before evaluating the independent visual/trigger gate.
_verify_phase_native = verify_native
def verify_native(out,expected_identity,fixture_manifest_path):
 import json,pathlib,importlib.util
 out=pathlib.Path(out);result=_verify_phase_native(out,expected_identity,fixture_manifest_path);result['visuals']=[];result['textureUploadCountMeasured']=False;result['gpuMemoryReclamationProven']=False
 try:
  spec=importlib.util.spec_from_file_location('bitmap_pixel_oracle',pathlib.Path(__file__).with_name('pixel_oracle.py'));oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
  rows=[]
  for line in (out/'retention-scene-controls.log').read_text().splitlines():
   marker='FLASHNEST_BITMAP_VISUAL_JSON '
   if marker in line:
    payload=line.split(marker,1)[1];require(len(payload.encode())<=65536,'Visual record bound');rows.append(json.loads(payload))
  result['visuals']=rows
  require(len(rows)==4,'Exact two old/new visual pairs')
  attachments=[];folder=out/'attachments/retention-scene-controls'
  for p in folder.rglob('*.json'):
   if p.stat().st_size<=65536:
    try:attachments.append(json.loads(p.read_text()))
    except (ValueError,UnicodeError):pass
  observations=result['observations'];snapshots=[o['snapshot'] for o in observations]
  checks=[]
  for row in rows:
   require(sum(a==row for a in attachments)==1,'Visual attachment absent/duplicate')
   require(row['snapshot'] in snapshots,'Visual snapshot not captured in bounded observation history')
   checks.append(oracle.verify_visual(row,folder,expected_identity))
  for case in ('retain','drop'):
   pair=[r for r in rows if r['snapshot']['case']==case]
   require(len(pair)==2 and [r['label'] for r in pair]==['old','new'],'Exact per-case old/new pair')
   old,new=pair;before=old['snapshot'];after=new['snapshot']
   require(before['wkID']==after['wkID'] and before['epoch']==after['epoch']==1,'Visual WK identity changed')
   require(type(before['transitionCount']) is int and before['transitionCount']==0 and before['transitionAt'] is None,'Transition occurred before old pixels')
   require(type(after['transitionCount']) is int and after['transitionCount']==1,'Repeated native transition')
   require(number(after['transitionAt']) and old['nativeUptimeSeconds']<after['transitionAt']<new['nativeUptimeSeconds'],'Pixel/trigger chronology')
   require(after['transitionAt']-old['nativeUptimeSeconds']>=1.1,'Trace-window pause not observed')
   require(oracle.draw_count(before)>0 and oracle.draw_count(after)>oracle.draw_count(before),'No actual old/new draw progress')
   oldphases=[r['phase']['phase'] for r in before['asRecords']]
   require('old.awaiting-space' in oldphases and 'transition.key' not in oldphases,'Old visual not before accepted transition')
   require(not any(r['asset']=='new.swf' for r in before['body']['records']),'New fetch preceded old pixel gate')
   newphases=[r['phase']['phase'] for r in after['asRecords']];require(newphases.count('transition.key')==1 and 'parent.done' in newphases,'New visual lacks completed single transition')
   summary=next(s for s in result['caseSummaries'] if s['case']==case);require(summary['visualCount']==2 and summary['transitionAttempted'] is True,'Summary visual/trigger mismatch')
   require(new['nativeUptimeSeconds']<=summary['activeFinishedAt'],'Visual after original active window')
  result['visualChecks']=checks;result['textureUploadCountMeasured']=False;result['gpuMemoryReclamationProven']=False
 except (AssertionError,KeyError,TypeError,ValueError,OSError,IndexError,StopIteration) as error:
  result['errors'].append('visual: '+str(error))
 result['evidenceValid']=not result['errors'];result['transitionComplete']=result['evidenceValid']
 return result
