#!/usr/bin/env python3
"""Fail-closed isolated diagnostic reconstruction; never accepts shipping approval."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent

def sha(b):return hashlib.sha256(b).hexdigest()
def run(args,cwd):return subprocess.check_output(args,cwd=cwd,stderr=subprocess.STDOUT).decode().strip()
def config():
 if not __debug__:raise RuntimeError('Python optimization forbidden for provenance gates')
 m=json.loads((HERE/'inputs.json').read_text())
 assert m['kind']=='sigill-phase-diagnostic-not-shipping'
 assert m['upstreamCommit']=='89a7049965f3090e706265670df309a5128233ac'
 for r in m['patches']:assert sha((HERE/r['path']).read_bytes())==r['sha256']
 for r in m['proposal']:assert sha((HERE/'phase'/r['path']).read_bytes())==r['afterSHA256']
 return m

def expected(source,m):
 paths={r['path']:r for r in m['historicalModifiedSources']}
 with tempfile.TemporaryDirectory(prefix='sigill-source-') as td:
  t=Path(td)
  for path,r in paths.items():
   if r['originalSHA256'] is not None:
    b=subprocess.check_output(['git','show',m['upstreamCommit']+':'+path],cwd=source)
    assert sha(b)==r['originalSHA256'];p=t/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
  for r in m['patches']:
   subprocess.run(['git','apply','--check',str(HERE/r['path'])],cwd=t,check=True)
   subprocess.run(['git','apply',str(HERE/r['path'])],cwd=t,check=True)
  assert {str(p.relative_to(t)) for p in t.rglob('*') if p.is_file()}==set(paths)
  for path,r in paths.items():assert sha((t/path).read_bytes())==r['modifiedSHA256']
  result={p:(t/p).read_bytes() for p in paths}
  for r in m['proposal']:
   path=r['path']
   if r['beforeSHA256'] is not None:
    before=result.get(path)
    if before is None:before=subprocess.check_output(['git','show',m['upstreamCommit']+':'+path],cwd=source)
    assert sha(before)==r['beforeSHA256'],path
   else:
    assert path not in result
    assert subprocess.run(['git','cat-file','-e',m['upstreamCommit']+':'+path],cwd=source,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
   result[path]=(HERE/'phase'/path).read_bytes()
  return result

def verify(source,m,exp):
 assert run(['git','rev-parse','HEAD'],source)==m['upstreamCommit']
 assert not run(['git','diff','--cached','--name-only'],source),'Staged modifications forbidden'
 tracked={p for p in exp if subprocess.run(['git','cat-file','-e',m['upstreamCommit']+':'+p],cwd=source,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0}
 assert set(run(['git','diff','HEAD','--name-only'],source).splitlines())==tracked,'Unexpected tracked diff'
 allowed=set(exp)-tracked|{'web/version_seal.json'}
 assert set(run(['git','ls-files','--others','--exclude-standard'],source).splitlines())<=allowed,'Unexpected untracked source'
 for p,b in exp.items():assert (source/p).read_bytes()==b,p
 for p,h in m['locks'].items():assert sha((source/p).read_bytes())==h,p
 return {p:{'sha256':sha(b),'bytes':len(b)} for p,b in sorted(exp.items())}

def inventory(root):return {str(p.relative_to(root)):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file()}

def main():
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['reconstruct','prepare','verify','package']);a.add_argument('source',type=Path);a.add_argument('output',type=Path);x=a.parse_args();s=x.source.resolve();o=x.output.resolve();m=config()
 assert run(['git','rev-parse','HEAD'],s)==m['upstreamCommit']
 e=expected(s,m)
 if x.mode=='reconstruct':
  assert not run(['git','status','--porcelain'],s),'Fresh upstream checkout required'
  # Exact historical recovery source is reconstructed and independently checked before phase overlay.
  for p,b in e.items():(s/p).parent.mkdir(parents=True,exist_ok=True);(s/p).write_bytes(b)
 rows=verify(s,m,e)
 if x.mode in ['reconstruct','verify']:
  o.parent.mkdir(parents=True,exist_ok=True);o.write_text(json.dumps({'kind':m['kind'],'inputsSHA256':sha((HERE/'inputs.json').read_bytes()),'modifiedSources':rows},indent=2)+'\n');return
 if x.mode=='prepare':
  assert not o.exists(),'Refuse reused output';o.mkdir(parents=True)
  seal={'version_number':'0.7.1','version_name':'FlashNest SIGILL phase diagnostic (NOT shipping)','version_channel':'flashnest-sigill-phase-diagnostic','build_date':datetime.fromtimestamp(m['sourceDateEpoch'],timezone.utc).isoformat().replace('+00:00','Z'),'commitHash':m['upstreamCommit'],'version4':'0.7.1.0','firefox_extension_id':'flashnest-sigill-phase-diagnostic'}
  (s/'web/version_seal.json').write_text(json.dumps(seal,sort_keys=True)+'\n')
  p={'schema':1,'kind':m['kind'],'status':'diagnostic-only-unpromoted','upstreamCommit':m['upstreamCommit'],'inputsSHA256':sha((HERE/'inputs.json').read_bytes()),'modifiedSources':rows,'versionSeal':seal,'sourceDateEpoch':m['sourceDateEpoch'],'experiment':{k:os.environ.get(k) for k in ['GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT']}}
  (o/'provenance.json').write_text(json.dumps(p,indent=2)+'\n');print(m['sourceDateEpoch']);return
 p=json.loads((o/'provenance.json').read_text());assert p['kind']==m['kind'] and p['modifiedSources']==rows and p['inputsSHA256']==sha((HERE/'inputs.json').read_bytes())
 assert (s/'web/version_seal.json').read_text()==json.dumps(p['versionSeal'],sort_keys=True)+'\n'
 dist=s/'web/packages/selfhosted/dist';assert (dist/'ruffle.js').is_file() and len(list(dist.glob('*.wasm')))==2
 # Copy every generated resource recursively, not a hardcoded old 12-file inventory.
 assert not any(q.is_symlink() for q in dist.rglob('*'))
 shutil.copytree(dist,o/'runtime');(o/'runtime-manifest.json').write_text(json.dumps(inventory(o/'runtime'),indent=2)+'\n')
 # Inline wasm-bindgen JS becomes generated snippet modules, then bundled selfhosted JS.
 snippets=[]
 for q in sorted((s/'web/packages/core').rglob('snippets/**/*.js')):
  if 'node_modules' in q.parts:continue
  if b'flashnestStartupPhase' in q.read_bytes():
   rel=q.relative_to(s);dest=o/'generated-snippets'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(q,dest);snippets.append(str(rel))
 assert snippets,'Missing generated inline-JS phase snippet'
 assert any(b'engine-second-start-return' in q.read_bytes() and b'engine-initial-tick-return' in q.read_bytes() for q in dist.rglob('*.js')),'Missing bundled fixed phase strings'
 for rel in sorted(set(e)|set(m['locks'])|{'LICENSE.md','web/version_seal.json','web/packages/selfhosted/LICENSE_MIT','web/packages/selfhosted/LICENSE_APACHE'}):
  dest=o/'source-correspondence'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s/rel,dest)
 shutil.copytree(HERE,o/'build-recipe',ignore=shutil.ignore_patterns('__pycache__'))
 p['toolVersions']={k:run(v,s) for k,v in {'rustc':['rustc','-vV'],'cargo':['cargo','--version'],'node':['node','--version'],'npm':['npm','--version'],'wasmBindgen':['wasm-bindgen','--version'],'binaryen':['wasm-opt','--version'],'java':['java','-version'],'clang':['clang-18','--version']}.items()}
 p['generatedInlineSnippetSources']=snippets;p['completedUTC']=datetime.now(timezone.utc).isoformat();p['files']=inventory(o);p['files'].pop('provenance.json');(o/'provenance.json').write_text(json.dumps(p,indent=2)+'\n')
if __name__=='__main__':main()
