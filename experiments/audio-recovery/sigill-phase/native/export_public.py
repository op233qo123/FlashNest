"""Only publication boundary: explicit enums/numbers/hashes and validated journal rows.
Never copy raw logs, IPS, xcresult, app containers, simulator inventories or paths.
"""
import argparse,hashlib,json,math,re,os
from pathlib import Path
from collect import validate_journal
OUTCOMES={'crash-observed','launch-unconfirmed','process-exit-or-unconfirmed','evidence-incomplete','journal-identity-unconfirmed','registered-script-unconfirmed','native-failure','startup-not-ready','observation-window-incomplete','cleanup-unconfirmed','complete-no-crash-observed'}
def number(value):
 return value if type(value)in(int,float) and math.isfinite(value) and 0<=value<=1000000 else None
def digest(value):return value if isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) else None
def uint(value):
 return value if type(value)is int and 0<=value<=9007199254740991 else None
def fault_signature(body):
 # Deliberately omit symbols, paths, image base addresses and register contents.
 threads=body.get('threads');images=body.get('usedImages');index=body.get('faultingThread')
 threads=threads if isinstance(threads,list) else [];images=images if isinstance(images,list) else []
 index=index if type(index)is int and 0<=index<len(threads) and isinstance(threads[index],dict) else None
 thread=threads[index] if index is not None and isinstance(threads[index],dict) else {}
 frames=thread.get('frames');frames=frames if isinstance(frames,list) else []
 sanitized=[]
 for frame in frames[:8]:
  frame=frame if isinstance(frame,dict) else {};image_index=frame.get('imageIndex')
  image=images[image_index] if type(image_index)is int and 0<=image_index<len(images) and isinstance(images[image_index],dict) else {}
  name=image.get('name');path=image.get('path');image_class='unknown'
  if name in ('JavaScriptCore','WebCore','WebKit'):image_class=name
  elif isinstance(path,str) and '..'not in path.split('/') and path.startswith(('/System/Library/','/usr/lib/')):image_class='other-system'
  size=uint(image.get('size'));offset=uint(frame.get('imageOffset'))
  resolved=size is not None and size>0 and offset is not None and offset<size
  # An unresolved frame's "offset" may actually be its absolute fault address.
  # Publish offsets only when contained in a positive-sized indexed image.
  sanitized.append({'imageClass':image_class,'imageOffset':offset if resolved else None,
                    'imageSize':size,'imageResolved':resolved})
 architecture={'ARM-64':'arm64','ARM64':'arm64','arm64':'arm64','arm64e':'arm64e','X86-64':'x86_64','x86_64':'x86_64'}.get(body.get('cpuType'),'unknown') if isinstance(body.get('cpuType'),str) else 'unknown'
 return {'faultingThread':index,'architecture':architecture,'faultImageResolved':bool(sanitized and sanitized[0]['imageResolved']),
         'faultThreadFrames':sanitized,'faultThreadFramesOmitted':max(0,len(frames)-8)}
def crash_summary(path):
 raw=Path(path).read_bytes()
 if len(raw)>2*1024*1024:raise ValueError('Crash cap')
 body=json.loads(raw.split(b'\n',1)[1]);name=body.get('procName','')
 process={'AudioRecoveryDiagnostic':'diagnostic-host','com.apple.WebKit.WebContent':'WebContent','com.apple.WebKit.GPU':'GPU','SimMetalHost':'SimMetalHost'}.get(name,'other-allowed-report')
 ex=body.get('exception') or {};term=body.get('termination') or {}
 signal=ex.get('signal');kind=ex.get('type')
 return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'process':process,
  'signal':signal if signal in {'SIGILL','SIGTRAP','SIGABRT','SIGSEGV','SIGBUS','SIGKILL'} else None,
  'exceptionType':kind if kind in {'EXC_BAD_INSTRUCTION','EXC_BREAKPOINT','EXC_CRASH','EXC_BAD_ACCESS','EXC_RESOURCE','EXC_GUARD'} else None,
  'terminationCode':number(term.get('code')),**fault_signature(body)}
def export(private,output,approval):
 private,output=Path(private),Path(output)
 if output.exists() or private==output or output.is_relative_to(private) or private.is_relative_to(output):raise ValueError('Separate new public destination required')
 a=json.loads(Path(approval).read_text());resources=a['runtimes']['diagnostic']['files']
 if a.get('kind')!='sigill-phase-diagnostic-not-shipping' or a.get('authorizedObservationCount')!=1:raise ValueError('Wrong one-shot approval')
 if not re.fullmatch('[0-9a-f]{40}',a['buildCommit']) or not digest(a['archiveSHA256']) or any(type(a[k])is not int or a[k]<=0 for k in ['runID','artifactID']):raise ValueError('Unsafe public identity fields')
 result={'schema':1,'kind':'one-shot-phase-observation-not-fix','authorizedObservationCount':1,'expectedOS':'18.2','actualOS':None,'attempts':[],
  'privacy':'allowlisted diagnostics only; no raw logs/IPS/xcresult/user data','claim':'observed report is not proof of reproducing original SIGILL or owning shared WebContent','rawRetention':'private raw command/crash receipts ephemeral until runner teardown; no unified-log collection','input':{'expectedProductionSourceCommit':'5862f8dbd414d9835f11872d3ebabd1eed315ffc','expectedOriginalInjectorSHA256':'d495f538242dd49915810a33478c17da9c1e7a831a721524a9136c4f2628176b','nativeWorkflowCommit':os.environ.get('GITHUB_SHA') if re.fullmatch('[0-9a-f]{40}',os.environ.get('GITHUB_SHA','')) else None,'buildCommit':a['buildCommit'],'runID':a['runID'],'artifactID':a['artifactID'],'archiveSHA256':a['archiveSHA256']},'crashes':[]}
 path=private/'control-results.json'
 if path.is_file():
  receipt=json.loads(path.read_text());entries=receipt.get('attempts',[])
  result['actualOS']='18.2' if receipt.get('actualOS')=='18.2' else None
  result['hostArchitecture']='arm64' if receipt.get('hostArchitecture')=='arm64' else 'unconfirmed'
  result['simulatorArchitecture']='arm64' if receipt.get('simulatorArchitecture')=='arm64' else 'unconfirmed'
  result['audioStateCoverage']='unknown-not-queried; phase-boundary-receipts-only'
  if len(entries)>1:raise ValueError('More than one attempt: publication rejected')
  for e in entries:
   if e.get('attempt')!=1:raise ValueError('Wrong attempt ordinal')
   rows=[]
   for journal in e.get('journalsBeforeTermination',[]):
    rows.extend(validate_journal(json.dumps(journal['rows']).encode(),resources))
   if len(rows)>100:raise ValueError('Unexpected journal merging')
   result['attempts'].append({'attempt':1,'outcome':e.get('outcome') if e.get('outcome')in OUTCOMES else 'evidence-incomplete',
    'freshPID':e.get('freshPID')is True,'readyAtSeconds':number(e.get('readyAtSeconds')),
    'observedPostReadySeconds':number(e.get('observedPostReadySeconds')),'observationElapsedSeconds':number(e.get('observationElapsedSeconds')),
    'cleanupConfirmed':e.get('explicitTermination',{}).get('returncode')==0,'journal':rows,
    'collectionIncomplete':e.get('collectionIncomplete') is True,'crashDigests':[d for d in e.get('crashesCapturedDuringObservation',[]) if digest(d)],
    'crashAssociations':[{'sha256':c['sha256'],'association':c['association']} for c in e.get('associatedCrashRecords',[]) if digest(c.get('sha256')) and c.get('association')in {'native-host-PID-and-time','shared-process-time-only-not-proven-ownership'}]})
  result['singleObservationComplete']=receipt.get('singleObservationComplete')is True
 else:result['singleObservationComplete']=False
 reports=private/'crashes'
 if reports.exists():
  paths=sorted(reports.glob('*.ips'))
  if len(paths)>10:raise ValueError('Crash count cap')
  for path in paths:
   if path.is_symlink() or not re.fullmatch(r'[0-9a-f]{64}\.ips',path.name):raise ValueError('Unsafe crash receipt')
   result['crashes'].append(crash_summary(path))
 output.mkdir(parents=True);data=(json.dumps(result,indent=2)+'\n').encode()
 (output/'observation.json').write_bytes(data)
 (output/'publication-manifest.json').write_text(json.dumps({'schema':1,'files':{'observation.json':{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}}},indent=2)+'\n')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--private',required=True);p.add_argument('--output',required=True);p.add_argument('--approval',required=True);a=p.parse_args();export(a.private,a.output,a.approval)
