#!/usr/bin/env python3
"""Fail closed before publishing a complete candidate engine artifact."""
import json,os,sys
from pathlib import Path
from stage import sha,need,dump,ACCEPTED,LOCK_SHA
root=Path(sys.argv[1]);files={};total=0
for p in sorted(root.rglob('*')):
 need(not p.is_symlink(),'Symlink in engine output')
 if p.is_file():
  name=p.relative_to(root).as_posix();need(p.suffix.lower() not in {'.ipa','.swf','.sol','.abc'},'Unexpected package/private fixture in engine artifact')
  files[name]={'sha256':sha(p),'bytes':p.stat().st_size};total+=p.stat().st_size
need(total<=268435456,'Engine artifact exceeds 256MiB review budget')
lock=json.loads((root/'runtime-lock.json').read_text());prov=json.loads((root/'provenance.json').read_text());core=json.loads((root/'core-tests/results.json').read_text())
need(lock['sourceCommit']==os.environ['GITHUB_SHA'] and lock['runID']==os.environ['GITHUB_RUN_ID'],'Wrong candidate build identity')
need(lock['acceptedRecipeCommit']==ACCEPTED and prov['acceptedSourceLockSHA256']==LOCK_SHA,'Wrong accepted baseline')
need(lock['provenanceSHA256']==sha(root/'provenance.json') and lock['flavorMapSHA256']==sha(root/'flavor-map.json'),'Runtime receipt mismatch')
need(core['run']=={k:os.environ[k] for k in ['GITHUB_SHA','GITHUB_RUN_ID']},'Core evidence wrong run')
need(core['passed'] is True and len(core['tests'])==3,'Incomplete bounded core regression evidence')
need({t['name'] for t in core['tests']}=={'bitmap-cache','loader-events','loader-loadbytes-events'},'Unexpected core regression names')
for t in core['tests']:
 need((t['passed'],t['failed'],t['ignored'])==(1,0,0),'Incomplete core test')
 need(t['logSHA256']==sha(root/'core-tests'/(t['name']+'.log')),'Core log changed')
staging=root/'source-correspondence/staging'
need(core['candidateSourceManifestSHA256']==sha(staging/'candidate-source.json'),'Core source binding changed')
need(sha(root/'full-source-before.json')==sha(root/'full-source-after.json')==sha(staging/'candidate-source.json'),'Full source identity changed')
actual={p.relative_to(root/'runtime').as_posix():sha(p) for p in (root/'runtime').rglob('*') if p.is_file()}
need(actual==lock['runtimeFiles'],'Runtime closure changed')
need(len([p for p in actual if p.endswith('.wasm')])==2,'Two WASM flavors required')
need(lock['selectedWasmSHA256']==actual[lock['selectedWasm']],'Selected WASM mismatch')
need(lock['runtimeAccepted'] is False and lock['ipaBuilt'] is False and prov['nativeAcceptance'] is False,'Forbidden acceptance claim')
for rel,entry in prov['correspondence'].items():need(files['source-correspondence/'+rel]==entry,'Source/license correspondence mismatch')
(root/'CANDIDATE-MODIFICATIONS.md').write_text('Experimental Loader unload lifecycle candidate.\n\nAccepted Ruffle upstream and six patches remain intact; one additional LoaderInfo lifecycle patch is included in source-correspondence/candidate-delta. Source and build provenance, licenses and notices accompany this artifact. This is not an IPA, release, physical-device acceptance or private-game compatibility result.\n')
files['CANDIDATE-MODIFICATIONS.md']={'sha256':sha(root/'CANDIDATE-MODIFICATIONS.md'),'bytes':(root/'CANDIDATE-MODIFICATIONS.md').stat().st_size}
dump(root/'artifact-files.json',files)
print('PASS complete bounded source-bound candidate engine artifact',len(files),total)
