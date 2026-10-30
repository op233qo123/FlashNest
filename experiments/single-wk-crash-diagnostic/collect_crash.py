#!/usr/bin/env python3
"""Strict structured IPS allowlist. Raw crash reports never leave the runner."""
import datetime,json,re,stat,os
from pathlib import Path
MAX_REPORTS=3
MAX_BYTES=2*1024*1024
PROCESSES={'com.apple.WebKit.WebContent','com.apple.WebKit.GPU','WebContent','GPU'}
EXCEPTIONS={'EXC_BAD_ACCESS','EXC_BAD_INSTRUCTION','EXC_ARITHMETIC','EXC_EMULATION','EXC_SOFTWARE','EXC_BREAKPOINT','EXC_CRASH','EXC_RESOURCE','EXC_GUARD','EXC_CORPSE_NOTIFY'}
SIGNALS={'SIGILL','SIGTRAP','SIGABRT','SIGFPE','SIGBUS','SIGSEGV','SIGKILL','SIGSYS','SIGTERM','SIGQUIT','SIGPIPE'}
NAMESPACES={'SIGNAL','LIBSYSTEM','FRONTBOARD','RUNNINGBOARD','WEBKIT','SPRINGBOARD','CODESIGNING','DYLD','GUARD','ENDPOINTSECURITY','WATCHDOG','TCC','RESOURCE'}
UUID_PATTERN=r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
def number(value):return value if type(value) is int and 0<=value<=2**64-1 else None
def token(value):return value if isinstance(value,str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}',value) else None
def symbol(value):
 if not isinstance(value,str) or len(value)>512 or any(v in value for v in ('/','\\','://','"',"'",'`','@')):return None
 if re.search(UUID_PATTERN,value) or re.search(r'\b[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b',value):return None
 return value if re.fullmatch(r'[A-Za-z0-9_ .:$<>()[\]{}~*&,+!?=\-]{1,512}',value) else None
def basename(value):
 if not isinstance(value,str):return None
 value=value.replace('\\','/').rsplit('/',1)[-1]
 if re.search(UUID_PATTERN,value) or ('.' in value and not value.endswith('.dylib')):return None
 return value if re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}',value) else None
def parse(raw):
 text=raw.decode('utf-8');decoder=json.JSONDecoder();first,end=decoder.raw_decode(text.lstrip());rest=text.lstrip()[end:].strip()
 body=decoder.decode(rest) if rest else first
 if not isinstance(body,dict) or not isinstance(first,dict):raise ValueError('unsupported-object')
 if rest and str(first.get('bug_type',''))!='309':raise ValueError('unsupported-report-kind')
 return body

def sanitize(body,start,end,pids):
 if body.get('procName') not in PROCESSES or type(body.get('pid')) is not int or body['pid'] not in pids:return None
 capture=body.get('captureTime')
 if not isinstance(capture,str):raise ValueError('missing-capture-time')
 dt=datetime.datetime.fromisoformat(capture)
 if dt.tzinfo is None:raise ValueError('unqualified-capture-time')
 if not start<=dt.timestamp()<=end:return None
 exception=body.get('exception',{});termination=body.get('termination',{})
 if not isinstance(exception,dict) or not isinstance(termination,dict):raise ValueError('unsupported-exception')
 ex={}
 for k,allowed in [('type',EXCEPTIONS),('signal',SIGNALS)]:
  value=exception.get(k)
  if isinstance(value,str) and value in allowed:ex[k]=value
 codes=exception.get('rawCodes')
 if isinstance(codes,list) and len(codes)<=8 and all(number(v) is not None for v in codes):ex['rawCodes']=codes
 term={k:number(termination.get(k)) for k in ('code','flags')};term={k:v for k,v in term.items() if v is not None}
 namespace=termination.get('namespace')
 if isinstance(namespace,str) and namespace in NAMESPACES:term['namespace']=namespace
 index=body.get('faultingThread');threads=body.get('threads');images=body.get('usedImages')
 if type(index) is not int or not isinstance(threads,list) or not 0<=index<len(threads) or not isinstance(images,list):raise ValueError('unsupported-faulting-thread')
 thread=threads[index]
 if not isinstance(thread,dict) or not isinstance(thread.get('frames'),list):raise ValueError('unsupported-frames')
 frames=[]
 for f in thread['frames'][:128]:
  if not isinstance(f,dict):raise ValueError('unsupported-frame')
  row={};offset=number(f.get('imageOffset'));location=number(f.get('symbolLocation'))
  if offset is not None:row['imageOffset']=offset
  if location is not None:row['symbolOffset']=location
  sym=symbol(f.get('symbol'))
  if sym is not None:row['symbol']=sym
  elif 'symbol' in f:row['symbolOmitted']=True
  image_index=f.get('imageIndex')
  if type(image_index) is int and 0<=image_index<len(images) and isinstance(images[image_index],dict):
   image=images[image_index];name=basename(image.get('name') or image.get('path'))
   if name is not None:row['imageBasename']=name
   uid=image.get('uuid')
   if isinstance(uid,str) and re.fullmatch(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',uid):row['imageUUID']=uid.lower()
  frames.append(row)
 return {'processRole':'WebContent' if 'WebContent' in body['procName'] else 'GPU','matchedPID':body['pid'],'captureOffsetMilliseconds':round((dt.timestamp()-start)*1000),'exception':ex,'termination':term,'faultingThreadIndex':index,'frames':frames,'framesOmitted':max(0,len(thread['frames'])-128)}

def collect(raw_roots,out,start_epoch,end_epoch,allowed_pids):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 if not (start_epoch<=end_epoch and all(type(p) is int and p>0 for p in allowed_pids)):raise ValueError('invalid-window-or-pids')
 result={'schema':'flashnest-sanitized-crash-v1','status':'notfound','reports':[],'unsupported':0,'omitted':0,'nonMatching':0,'rawReportsUploaded':False,'selectedReleaseGatePassed':False}
 if not allowed_pids:
  result.update(reason='no-correlated-pid',exitCode=2)
  (out/'collection.json').write_text(json.dumps(result,indent=2)+'\n')
  return result
 candidates=[];seen=set()
 for root in raw_roots:
  root=Path(root)
  if not root.is_dir() or root.is_symlink():continue
  for p in sorted(root.glob('*.ips')):
   if p in seen:continue
   seen.add(p)
   try:st=p.lstat()
   except OSError:continue
   if not stat.S_ISREG(st.st_mode) or not any(v in p.name for v in ('WebContent','GPU')):continue
   if start_epoch-2<=st.st_mtime<=end_epoch+15:candidates.append((p,st.st_size))
 consumed=0;read_count=0
 for p,size in candidates:
  if size>MAX_BYTES or size<=0 or read_count>=MAX_REPORTS or consumed+size>MAX_REPORTS*MAX_BYTES:result['omitted']+=1;continue
  read_count+=1;consumed+=size
  try:
   fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
   with os.fdopen(fd,'rb') as file:
    current=os.fstat(file.fileno())
    if not stat.S_ISREG(current.st_mode) or current.st_size!=size:raise ValueError('report-changed')
    raw=file.read(MAX_BYTES+1)
   if len(raw)!=size or len(raw)>MAX_BYTES:result['omitted']+=1;continue
   row=sanitize(parse(raw),start_epoch,end_epoch,set(allowed_pids))
   if row is None:result['nonMatching']+=1;continue
   name='crash-'+str(len(result['reports'])+1)+'.json';(out/name).write_text(json.dumps(row,indent=2)+'\n');result['reports'].append({'path':name,'frames':len(row['frames'])})
  except (OSError,UnicodeError,ValueError,TypeError,KeyError,OverflowError):result['unsupported']+=1
 if result['omitted']:result['status']='omitted'
 elif result['unsupported']:result['status']='unsupported'
 elif result['reports']:result['status']='collected'
 result['exitCode']=0 if result['status']=='collected' else 2
 (out/'collection.json').write_text(json.dumps(result,indent=2)+'\n')
 return result
