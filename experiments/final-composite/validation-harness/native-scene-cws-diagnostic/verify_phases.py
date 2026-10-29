"""Strict synthetic transition evidence; no native release acceptance or OOM inference."""
import math

def require(ok,message):
 if not ok:raise AssertionError(message)
def number(x):return type(x) in (int,float) and math.isfinite(x)
def verify_as(records):
 require(0<len(records)<=32,'AS record count')
 phases=[];previous=-1
 for i,r in enumerate(records):
  require(type(r['sequence']) is int and r['sequence']==i+1,'AS sequence')
  require(number(r['timeMs']) and r['timeMs']>=previous,'AS monotonic time');previous=r['timeMs']
  require(number(r['bytesLoaded']) and number(r['bytesTotal']),'AS bytes types')
  phases.append(r['phase'])
 required=['parent.ready','old.open','old.init','old.complete','old.first-frame','before-unload','old.unload-event','returned-unload','new.open','new.init','new.complete','new.first-frame','parent.done']
 require(all(phases.count(p)==1 for p in required),'Missing or duplicate required AS phase')
 require(set(phases)<=set(required+['old.progress-end','new.progress-end']),'Unexpected AS phase')
 for p in ('old.progress-end','new.progress-end'):require(phases.count(p)<=1,'Repeated progress marker')
 index=lambda p:phases.index(p)
 require(index('parent.ready')==0 and index('parent.done')==len(phases)-1,'Parent endpoints')
 for stage in ('old','new'):
  require(index(stage+'.open')<min(index(stage+'.init'),index(stage+'.complete'),index(stage+'.first-frame')),'Loader start ordering')
  for p in [stage+'.init',stage+'.complete',stage+'.first-frame']:
   require(index(p)<index('before-unload' if stage=='old' else 'parent.done'),'Transition before full stage evidence')
 require(index('before-unload')<index('old.unload-event')<index('returned-unload')<index('new.open'),'Unload ordering')
 for r in records:
  if r['phase'].endswith('progress-end'):require(r['bytesLoaded']==r['bytesTotal'] and r['bytesTotal']>0,'Progress completion')
 return phases

def verify_body(body,case,manifest):
 require(body['schema']=='flashnest-scene-body-observer-v1','Body schema')
 require(type(body['overflow']) is int and body['overflow']==0,'Body overflow')
 for p in ('promiseReactionsAdded','unhandledRejectionObservationChanged'):require(body[p] is True,'Observer limitation disclosure')
 for p in ('wasmCopyObservable','decompressionObservable'):require(body[p] is False,'Unobservable stage claimed')
 rows=body['records'];require(len(rows)==12,'Exactly three complete body operations')
 previous=-1;groups={}
 for i,r in enumerate(rows):
  require(type(r['sequence']) is int and r['sequence']==i+1,'Body sequence')
  require(number(r['timeMs']) and r['timeMs']>=previous,'Body time');previous=r['timeMs']
  require(type(r['id']) is int and r['id']>0,'Body request ID')
  require(r['asset'] in ('main.swf','old.swf','new.swf'),'Unexpected asset')
  groups.setdefault(r['id'],[]).append(r)
 require(len(groups)==3,'Request count')
 assets=[]
 for rows in groups.values():
  asset=rows[0]['asset'];assets.append(asset)
  require(all(r['asset']==asset for r in rows),'Request asset drift')
  require([r['phase'] for r in rows]==['request','headers','array-buffer-start','array-buffer-complete'],'Incomplete body stage')
  require(type(rows[1]['status']) is int and rows[1]['status']==200,'HTTP status')
  require(type(rows[3]['byteLength']) is int and rows[3]['byteLength']==manifest['files'][case+'/'+asset]['compressedBytes'],'Actual body length')
 require(assets==['main.swf','old.swf','new.swf'],'Request asset order')
 return rows

def verify_cases(case_snapshots,expected_identity,fixture_manifest):
 report={'schema':'flashnest-native-scene-verification-v1','diagnosticOnly':True,'nativeAcceptance':False,'renderHealthCertified':False,'cases':{},'errors':[],
 'wasmCopyObservable':False,'decompressionObservable':False,'cause':'unknown'}
 if set(case_snapshots)!={'tiny','sized'}:report['errors'].append('Exact tiny+sized cases required')
 for case in ('tiny','sized'):
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
   require(0<len(snapshots)<=32,'Snapshot count')
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
    records=snap['asRecords'];require(len(records)<=32 and records[:len(prior_as)]==prior_as,'AS history rewritten');prior_as=records
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
   entry['phases']=verify_as([r['phase'] for r in final['asRecords']])
   verify_body(final['body'],case,fixture_manifest)
   entry['transitionComplete']=True
  except (AssertionError,KeyError,TypeError,ValueError) as e:
   entry['errors'].append(str(e));entry['transitionComplete']=False
  report['errors'] += [case+': '+e for e in entry['errors']]
 report['evidenceValid']=not report['errors'];report['transitionComplete']=report['evidenceValid']
 return report

def verify_native(out,expected_identity,fixture_manifest_path):
 import json,pathlib,hashlib
 out=pathlib.Path(out);manifest_path=pathlib.Path(fixture_manifest_path)
 grouped={'tiny':[],'sized':[]}
 result={'diagnosticOnly':True,'nativeAcceptance':False,'renderHealthCertified':False,'errors':[],'observations':[],'caseSummaries':[]}
 try:
  raw=(out/'scene-loader-controls.log').read_text();require(len(raw.encode())<=16*1024*1024,'Log exceeds bound')
  observations=[];summaries=[]
  for line in raw.splitlines():
   for marker,target in [('FLASHNEST_SCENE_OBSERVATION_JSON ',observations),('FLASHNEST_SCENE_CASE_JSON ',summaries)]:
    if marker in line:
     payload=line.split(marker,1)[1];require(len(payload.encode())<=65536,'Record exceeds bound');target.append(json.loads(payload))
  result['observations']=observations;result['caseSummaries']=summaries
  require(len(observations)<=64 and len(summaries)==2,'Exact bounded case summary count')
  require({s['case'] for s in summaries}=={'tiny','sized'},'Case summary roles')
  attachments=[]
  for p in (out/'attachments/scene-loader-controls').rglob('*.json'):
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
   require(summary['activeFinishedAt']-summary['readyAt']<=120,'Active window exceeded120s')
   require(summary['finishedAt']-summary['activeFinishedAt']<=10,'Extra evidence exceeded10s')
  result['fixtureManifestSHA256']=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
 except (AssertionError,KeyError,TypeError,ValueError,OSError,IndexError) as error:
  result['errors'].append(str(error));result['evidenceValid']=False;result['transitionComplete']=False
 # Always compute partial last-phase summaries, including on missing-done/termination/errors.
 grouped={case:[o['snapshot'] for o in result['observations'] if isinstance(o,dict) and o.get('case')==case and isinstance(o.get('snapshot'),dict)] for case in ('tiny','sized')}
 try:
  partial=verify_cases(grouped,expected_identity,json.loads(manifest_path.read_text()))
  prior_errors=result['errors'];result.update(partial);result['errors']=prior_errors+partial['errors']
  result['evidenceValid']=not result['errors'];result['transitionComplete']=result['evidenceValid']
 except (OSError,ValueError,TypeError) as error:
  result['errors'].append(str(error));result['evidenceValid']=False;result['transitionComplete']=False
 return result
