#!/usr/bin/env python3
"""Run bounded real Rust regressions; reject a successful zero-test invocation."""
import argparse,json,os,re,subprocess
from pathlib import Path
from stage import sha,need,dump
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
cases=[('bitmap-cache',['cargo','test','--locked','-p','ruffle_core','--lib','--features','jpegxr','bitmap_cache_release_preserves_live_handles_and_recreates','--','--nocapture']),('loader-events',['cargo','test','--locked','-p','tests','--test','tests','--features','jpegxr','--','avm2/loader_events','--exact','--nocapture'])]
cases.append(('loader-loadbytes-events',['cargo','test','--locked','-p','tests','--test','tests','--features','jpegxr','--','avm2/loader_loadbytes_events','--exact','--nocapture']))
results=[]
for name,cmd in cases:
 result=subprocess.run(cmd,cwd=a.source,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);log=a.out/(name+'.log');log.write_text(result.stdout);print(result.stdout,flush=True)
 need(result.returncode==0,'Core regression failed: '+name)
 counts=re.findall(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;',result.stdout)
 need(len(counts)==1 and tuple(map(int,counts[0]))==(1,0,0),'Expected exactly one executed passing test: '+name)
 results.append({'name':name,'command':cmd,'passed':1,'failed':0,'ignored':0,'logSHA256':sha(log)})
dump(a.out/'results.json',{'run':{k:os.environ[k] for k in ['GITHUB_SHA','GITHUB_RUN_ID']},'tests':results,'passed':True,'candidateSourceManifestSHA256':sha(Path(os.environ['STAGE_EVIDENCE'])/'candidate-source.json'),'privateInputs':False,'visualChecks':False,'flashConformanceClaim':False})
