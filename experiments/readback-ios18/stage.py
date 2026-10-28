"""CI-only full promotion overlay; never mutate checkout or promote runtime."""
import argparse,hashlib,json,subprocess,tarfile,tempfile,shutil
from pathlib import Path
SOURCE='faa2b5fff98f81044de17f17eec23ddd9a9847e0'
OVERLAY_SHA256='c32d8c71d0e79a224512d6bd7736edb95cd65c3b87fef7d4233ecd1e44efb69c'
PROMOTION='3bcbcc205b84887b0b2e8bacc371277d4318b63c99aca7181faea3a0c9aae5c7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validated_inputs(here, archive):
 manifest=here/'overlay.json'
 if manifest.is_symlink() or sha(manifest)!=OVERLAY_SHA256:raise ValueError('Unreviewed overlay manifest')
 a=json.loads(manifest.read_text())
 if a.get('schema')!=1:raise ValueError('Unsupported overlay schema')
 if a['baseRef']!=SOURCE or a['promotionManifestSHA256']!=PROMOTION or len(a['files'])!=18:raise ValueError('Wrong source/promotion scope')
 seen=set()
 for x in a['files']:
  if not isinstance(x.get('path'),str) or type(x.get('bytes')) is not int or not 0<=x['bytes']<=128*1024*1024:raise ValueError('Invalid file fields')
  p=Path(x['path'])
  if p.is_absolute() or '..' in p.parts or p.as_posix()!=x['path'] or '\\' in x['path'] or str(p) in seen:raise ValueError('Unsafe duplicate path')
  seen.add(str(p));source=archive if p.suffix=='.zip' else here/'payload'/p
  if p.suffix!='.zip' and any(q.is_symlink() for q in [here/'payload',*[(here/'payload').joinpath(*p.parts[:i]) for i in range(1,len(p.parts)+1)]]):raise ValueError('Symlink payload')
  if source.is_symlink() or source.stat().st_size!=x['bytes'] or sha(source)!=x['sha256']:raise ValueError('Input hash/size mismatch: '+str(p))
 return a

def stage(repo, output, arm, archive, here=None):
 if Path(archive).is_symlink():raise ValueError('Symlink archive')
 repo,output,archive=map(lambda x:Path(x).resolve(),(repo,output,archive));here=Path(here or Path(__file__).parent).resolve()
 if arm not in ('baseline','candidate') or output.exists() or output==repo or repo in output.parents:raise ValueError('Require new separate output and known arm')
 a=validated_inputs(here,archive)
 with tempfile.TemporaryDirectory() as tmp:
  tarpath=Path(tmp)/'source.tar'
  with tarpath.open('wb') as f:subprocess.run(['git','-C',str(repo),'archive',SOURCE],stdout=f,check=True)
  shipping=Path(tmp)/'shipping';shipping.mkdir()
  with tarfile.open(tarpath) as tar:
   for m in tar.getmembers():
    if not (m.isfile() or m.isdir()) or Path(m.name).is_absolute() or '..' in Path(m.name).parts:raise ValueError('Unsafe source member')
   tar.extractall(shipping,filter='data')
  for x in a['files']:
   p=shipping/x['path'];before=x['originalSHA256']
   if (before is None and p.exists()) or (before is not None and (not p.is_file() or sha(p)!=before)):raise ValueError('Pinned original drift: '+x['path'])
  shutil.copytree(shipping,output)
  if arm=='candidate':
   for x in a['files']:
    p=output/x['path'];p.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(archive if p.suffix=='.zip' else here/'payload'/x['path'],p)
  receipt={'sourceCommit':SOURCE,'arm':arm,'promotionManifestSHA256':PROMOTION,'shippingCheckoutUnchanged':True,
   'overlay':a['files'] if arm=='candidate' else [],'sourceRuntimeIdentitySHA256':sha(output/'App/Resources/Web/runtime-identity.json')}
  (output/'readback-stage-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return output
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--output',required=True);p.add_argument('--arm',choices=['baseline','candidate'],required=True);p.add_argument('--archive',required=True)
 a=p.parse_args();stage(a.repo,a.output,a.arm,a.archive)
