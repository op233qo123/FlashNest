#!/usr/bin/env python3
import argparse,os,shutil,tempfile
from pathlib import Path
from reuse_engine import reuse,BUILD,DELTA
p=argparse.ArgumentParser()
for n in ['archive','metadata','original']:p.add_argument('--'+n,required=True)
a=p.parse_args()
with tempfile.TemporaryDirectory() as td:
 root=Path(td);original=root/'original';source=Path(a.original)
 for folder,names in [('build',BUILD),('engine',DELTA),('integration',{'stage_candidate.py'})]:
  for name in names:
   dest=original/folder/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/folder/name,dest)
 def run(label,archive=a.archive):return reuse(archive,a.metadata,original,root/label,root/(label+'.lock'),root/(label+'.receipt'),os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID'])
 ok=run('valid');assert ok['coreTestExecutionReused'] and not ok['engineBuildExecutedThisRun'];assert ok['sourceCommit']!=ok['consumerHead']
 for folder,name in [('build','build.sh'),('engine','DESIGN.md'),('integration','stage_candidate.py')]:
  f=original/folder/name;old=f.read_bytes();f.write_bytes(old+b'\n')
  try:run(folder)
  except ValueError:pass
  else:raise AssertionError('Changed source accepted '+folder)
  f.write_bytes(old)
 bad=root/'bad.zip';data=bytearray(Path(a.archive).read_bytes());data[-1]^=1;bad.write_bytes(data)
 try:run('bad',bad)
 except ValueError:pass
 else:raise AssertionError('Changed archive accepted')
print('PASS exact engine reuse plus four negative source/archive cases')
