#!/usr/bin/env python3
"""Reconstruct accepted six-patch source first, then one narrowly scoped delta."""
import argparse, hashlib, importlib.util, json, os, subprocess
from pathlib import Path
ACCEPTED='6d3e4322293972a28ab2cdf129ee6398f40f0f37'
UPSTREAM='89a7049965f3090e706265670df309a5128233ac'
LOCK_SHA='7200650c24fe505844ea676c02c44a42dd2ee7bc484344e775e4458d84566494'
ALLOWED={'core/src/avm2/object/loaderinfo_object.rs'}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def row(p): return {'sha256':sha(p),'bytes':Path(p).stat().st_size}
def need(x,why):
 if not x: raise ValueError(why)
def git(p,*args): return subprocess.check_output(['git','-C',str(p),*args],text=True).strip()
def dump(p,v): Path(p).write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
def load_snapshot(recipe):
 spec=importlib.util.spec_from_file_location('accepted_source_snapshot',recipe/'scripts/source_snapshot.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.snapshot

def stage(source,accepted,engine,out):
 source=source.resolve();accepted=accepted.resolve();engine=engine.resolve();out=out.resolve()
 need(git(accepted,'rev-parse','HEAD')==ACCEPTED and not git(accepted,'status','--porcelain'),'Accepted recipe checkout must be clean/pinned')
 recipe=accepted/'experiments/lazy-graphic-engine';lock=json.loads((recipe/'source-lock.json').read_text())
 need(sha(recipe/'source-lock.json')==LOCK_SHA,'Accepted source lock identity')
 need(git(source,'rev-parse','HEAD')==UPSTREAM and not git(source,'status','--porcelain'),'Upstream checkout must be clean/pinned')
 subprocess.run(['python3',str(recipe/'scripts/check_pipeline.py')],cwd=accepted,check=True)
 subprocess.run(['python3',str(recipe/'scripts/stage_engine.py'),str(source),'--engine-gate'],cwd=accepted,check=True)
 snapshot=load_snapshot(recipe);before=snapshot(source,lock['modifiedSourceFiles'])
 delta=json.loads((engine/'source-lock.json').read_text());mods=delta['modifiedSourceFiles']
 need(delta['acceptedBuildSourceCommit']==ACCEPTED and delta['acceptedSourceLockSHA256']==LOCK_SHA and delta['upstreamCommit']==UPSTREAM,'Delta baseline identity mismatch')
 need(all(delta[k] is False for k in ['browserAcceptance','engineBuildExecuted','flashReferenceCertified','ipaBuildAllowed']),'Forbidden candidate declaration')
 need(set(mods)==ALLOWED,'Only reviewed unload product file allowed')
 need(delta['patch']['path']=='unload-lifecycle.patch','Unexpected delta patch path')
 patch=engine/delta['patch']['path'];need(not patch.is_symlink() and sha(patch)==delta['patch']['sha256'],'Delta patch hash')
 for rel,m in mods.items(): need(row(source/rel)==m['before']==lock['modifiedSourceFiles'][rel],'Delta preimage mismatch: '+rel)
 subprocess.run(['git','-C',str(source),'apply','--check',str(patch)],check=True)
 subprocess.run(['git','-C',str(source),'apply',str(patch)],check=True)
 expected=dict(lock['modifiedSourceFiles'])
 for rel,m in mods.items():
  need(row(source/rel)==m['after'],'Delta postimage mismatch: '+rel);expected[rel]=m['after']
 after=snapshot(source,expected)
 need({p for p in before if before[p]!=after[p]}==ALLOWED,'Unexpected source delta')
 for rel,h in lock['locks'].items(): need(sha(source/rel)==h,'Dependency lock changed')
 out.mkdir(parents=True,exist_ok=False)
 dump(out/'accepted-source.json',before);dump(out/'candidate-source.json',after)
 dump(out/'source-stage.json',{'schema':1,'acceptedRecipeCommit':ACCEPTED,'upstreamCommit':UPSTREAM,'acceptedSourceLockSHA256':LOCK_SHA,'candidateDeltaSHA256':sha(engine/'source-lock.json'),'candidatePatchSHA256':sha(patch),'acceptedSourceManifestSHA256':sha(out/'accepted-source.json'),'candidateSourceManifestSHA256':sha(out/'candidate-source.json'),'modifiedSourceFiles':expected,'deltaFiles':mods,'dependencyLocks':lock['locks'],'run':{k:os.environ.get(k) for k in ['GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT']},'runtimeAccepted':False,'ipaBuilt':False})
 print('PASS exact accepted six-patch source + bounded candidate delta')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--accepted',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();stage(a.source,a.accepted,a.engine,a.out)
