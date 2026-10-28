"""Authenticate one separately approved diagnostic engine archive; no fallback."""
import hashlib,json,stat,zipfile
from pathlib import Path
UPSTREAM='89a7049965f3090e706265670df309a5128233ac'
def sha(data):return hashlib.sha256(data).hexdigest()
def verify(root,approval):
 root=Path(root);a=json.loads(Path(approval).read_text())
 if a['repository']!='op233qo123/FlashNest' or a['kind']!='sigill-phase-diagnostic-not-shipping' or a['authorizedObservationCount']!=1:raise ValueError('Wrong approval')
 run=json.loads((root/'run.json').read_text());artifact=json.loads((root/'artifact.json').read_text())
 if run['id']!=a['runID'] or run['head_sha']!=a['buildCommit'] or run['status']!='completed' or run['conclusion']!='success':raise ValueError('Build identity/status mismatch')
 if artifact['id']!=a['artifactID'] or artifact['workflow_run']['id']!=a['runID'] or artifact['name']!='FlashNest-sigill-phase-diagnostic-engine' or artifact['expired']:raise ValueError('Distinct artifact identity mismatch')
 archive=root/'runtime.zip'
 if not 0<a['archiveBytes']<=128*1024*1024 or archive.stat().st_size!=a['archiveBytes'] or artifact['size_in_bytes']!=a['archiveBytes']:raise ValueError('Archive size mismatch')
 if sha(archive.read_bytes())!=a['archiveSHA256']:raise ValueError('Archive hash mismatch')
 dest=root/'extracted'
 if dest.exists():raise ValueError('Existing extraction forbidden')
 with zipfile.ZipFile(archive) as z:
  names=set();total=0
  for e in z.infolist():
   p=Path(e.filename);total+=e.file_size;kind=(e.external_attr>>16)&0o170000
   if not p.parts or p.is_absolute() or '..'in p.parts or '\\'in e.filename or e.filename.casefold()in names or kind not in(0,stat.S_IFREG,stat.S_IFDIR):raise ValueError('Unsafe member')
   names.add(e.filename.casefold())
  if total>128*1024*1024 or len(names)>512 or z.testzip()is not None:raise ValueError('Archive bounds/CRC')
  z.extractall(dest)
 provenance=dest/'provenance.json'
 if sha(provenance.read_bytes())!=a['provenanceSHA256']:raise ValueError('Reviewed provenance hash mismatch')
 p=json.loads(provenance.read_text())
 if p['schema']!=1 or p['kind']!=a['kind'] or p['status']!='diagnostic-only-unpromoted' or p['upstreamCommit']!=UPSTREAM:raise ValueError('Engine provenance kind/base')
 if p['experiment']['GITHUB_SHA']!=a['buildCommit'] or p['experiment']['GITHUB_RUN_ID']!=str(a['runID']):raise ValueError('Provenance build correspondence')
 actual={str(x.relative_to(dest)):{'sha256':sha(x.read_bytes()),'bytes':x.stat().st_size} for x in dest.rglob('*') if x.is_file() and x!=provenance}
 if actual!=p['files']:raise ValueError('Complete artifact inventory mismatch')
 runtime_manifest=json.loads((dest/'runtime-manifest.json').read_text())
 expected=a['runtimes']['diagnostic']
 if expected['directory']!='runtime' or {k:v['sha256'] for k,v in runtime_manifest.items()}!=expected['files']:raise ValueError('Approved runtime inventory mismatch')
 actual_runtime={str(x.relative_to(dest/'runtime')):{'sha256':sha(x.read_bytes()),'bytes':x.stat().st_size} for x in(dest/'runtime').rglob('*') if x.is_file()}
 if actual_runtime!=runtime_manifest:raise ValueError('Actual runtime bytes mismatch')
 return dest
if __name__=='__main__':
 import sys
 verify(*sys.argv[1:])
