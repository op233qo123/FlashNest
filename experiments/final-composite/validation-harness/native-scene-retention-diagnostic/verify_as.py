"""Logical fixture-owned references only; neither garbage collection nor physical memory."""
import math

def require(ok,message):
 if not ok:raise AssertionError(message)
def number(x):return type(x) in (int,float) and math.isfinite(x)
def verify_as(records,case):
 require(case in ('retain','drop'),'Case')
 require(0<len(records)<=64,'AS record count')
 phases=[];previous=-1
 for i,r in enumerate(records):
  require(type(r['sequence']) is int and r['sequence']==i+1,'AS sequence')
  require(number(r['timeMs']) and r['timeMs']>=previous,'AS monotonic time');previous=r['timeMs']
  require(number(r['bytesLoaded']) and number(r['bytesTotal']),'AS byte types')
  phases.append(r['phase'])
 branch='prefixes.retained' if case=='retain' else 'prefixes.references-dropped'
 required=['parent.ready','prefixes.ready',branch,'old.open','old.init','old.complete','old.first-frame','old.awaiting-space','transition.key','before-unload','old.unload-event','returned-unload','new.open','new.init','new.complete','new.first-frame','parent.done']
 required += [p+'.'+event for p in ('prefix-a','prefix-b') for event in ('init','complete','first-frame')]
 require(all(phases.count(p)==1 for p in required),'Missing or duplicate required AS phase')
 require(set(phases)<=set(required+['old.progress-end','new.progress-end']),'Unexpected AS phase')
 for p in ('old.progress-end','new.progress-end'):require(phases.count(p)<=1,'Repeated progress marker')
 index=lambda p:phases.index(p)
 require(index('parent.ready')==0 and index('parent.done')==len(phases)-1,'Parent endpoints')
 for prefix in ('prefix-a','prefix-b'):
  for phase in ('init','complete','first-frame'):require(index(prefix+'.'+phase)<index('prefixes.ready'),'Prefix readiness')
 require(index('prefixes.ready')<index('old.open'),'Old before prefix readiness')
 for stage in ('old','new'):
  require(index(stage+'.open')<min(index(stage+'.init'),index(stage+'.complete'),index(stage+'.first-frame')),'Loader start ordering')
  for phase in ('init','complete','first-frame'):
   require(index(stage+'.'+phase)<index('old.awaiting-space' if stage=='old' else 'parent.done'),'Scene readiness')
 require(index('old.awaiting-space')<index('transition.key')<index(branch)<index('before-unload'),'Boundary branch ordering')
 require(index('before-unload')<index('old.unload-event')<index('returned-unload')<index('new.open'),'Unload ordering')
 expected_ready={'liveLoaderRefs':2,'liveContentRefs':2,'attachedPrefixLoaders':2,'unloadCalls':0,'removeCalls':0,'unsubscribeCalls':0,'nullAssignments':0}
 expected_branch=expected_ready if case=='retain' else {'liveLoaderRefs':0,'liveContentRefs':0,'attachedPrefixLoaders':0,'unloadCalls':2,'removeCalls':2,'unsubscribeCalls':8,'nullAssignments':4}
 for phase,expected in [('prefixes.ready',expected_ready),(branch,expected_branch)]:
  record=records[index(phase)]
  for key,value in expected.items():require(type(record.get(key)) is int and record[key]==value,'Invalid logical reference/operation oracle '+key)
 for row in records:
  if row['phase'].endswith('progress-end'):require(row['bytesLoaded']==row['bytesTotal'] and row['bytesTotal']>0,'Progress completion')
 return phases
