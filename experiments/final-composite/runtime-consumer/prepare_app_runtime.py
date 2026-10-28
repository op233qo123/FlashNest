#!/usr/bin/env python3
"""Bind verified final engine to disposable App staging; never enables sampling gate."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile,io
import composite_runtime as c
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--acceptance',type=Path,required=True);p.add_argument('--app',type=Path,required=True);a=p.parse_args()
proof=c.parse(a.acceptance.read_bytes());c.require(proof.get('engineAccepted') is True,'No independent engine acceptance')
raw=a.archive.read_bytes();c.require(len(raw)==proof['bytes'] and c.digest(raw)==proof['sha256'],'Archive differs from accepted artifact')
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 receipt_raw=z.read(c.PREFIX+'provenance.json');c.require(c.digest(receipt_raw)==proof['provenanceSHA256'],'Receipt differs');receipt=c.parse(receipt_raw)
 invraw=z.read(c.PREFIX+'runtime-files.json');c.require(c.digest(invraw)==proof['runtimeInventorySHA256'],'Runtime inventory differs');inventory=c.parse(invraw)
 c.require(receipt['run']['GITHUB_SHA']==proof['sourceCommit'] and receipt['run']['GITHUB_RUN_ID']==str(proof['runID']) and receipt['sourceSetSHA256']==proof['sourceSetSHA256'],'Accepted source/run differs')
lock={'schemaVersion':4,'runtimeKind':c.KIND,'runtimePrefix':c.PREFIX+'runtime/','provenancePath':c.PREFIX+'provenance.json','archiveBytes':len(raw),'archivePath':f"vendor/ruffle-composite-{proof['runID']}.zip",'sha256':c.digest(raw),'identitySHA256':None,'provenanceSHA256':c.digest(receipt_raw),'sourceLockSHA256':receipt['sourceLockSHA256'],'sourceSetSHA256':receipt['sourceSetSHA256'],'runtimeInventorySHA256':receipt['runtimeInventorySHA256'],'upstreamSourceCommit':receipt['upstreamCommit'],'buildSourceCommit':proof['sourceCommit'],'buildRunID':proof['runID'],'version':'0.7.1','experimentalVersionName':receipt['versionSeal']['version_name'],'name':'FlashNest modified Ruffle','license':'MIT OR Apache-2.0','status':'experimental-test-candidate-native-acceptance-separate','checksumProvenance':'Exact GitHub Actions artifact bytes, not publisher signature or independent reproducible build'}
ident={key:lock[key] for key in ('runtimeKind','experimentalVersionName','upstreamSourceCommit','buildSourceCommit','buildRunID','provenanceSHA256','sourceLockSHA256','sourceSetSHA256','runtimeInventorySHA256')}
ident.update(schemaVersion=3,artifactArchiveSHA256=lock['sha256'],upstreamBaseVersion='0.7.1',runtimeFiles=inventory)
def encoded(v):return (json.dumps(v,indent=2,sort_keys=True)+'\n').encode()
identity_bytes=encoded(ident);lock['identitySHA256']=c.digest(identity_bytes);manifest={k:v['sha256'] for k,v in inventory.items()}
files=c.verified_runtime(raw,lock,manifest,identity_bytes)
app=a.app.resolve();web=app/'App/Resources/Web';c.require(app.is_dir() and web.is_dir() and not app.is_symlink() and not web.is_symlink(),'Regular staged App required')
c.require('static let runtimeValidated = false' in (app/'App/Player/RenderSamplingSettings.swift').read_text(),'Do not activate sampling during engine staging')
target=web/'runtime';c.require(not target.is_symlink(),'Linked runtime forbidden')
if target.exists():
 c.require({f.name for f in target.iterdir()}<={'LICENSE_MIT','LICENSE_APACHE'},'Only license-only pending runtime staging accepted')
 for f in target.iterdir():c.require(f.is_file() and not f.is_symlink(),'Nonregular initial runtime')
else:target.mkdir()
# Rebind the existing frame-order test to the exact final identity; test logic unchanged.
old_identity_sha=c.digest((web/'runtime-identity.json').read_bytes())
frame_test=app/'Tests/FrameOrderRuntimeTests.swift'
old_pin='private static let identitySHA256 = "'+old_identity_sha+'"'
new_pin='private static let identitySHA256 = "'+lock['identitySHA256']+'"'
frame_text=frame_test.read_text();c.require(frame_text.count(old_pin)==1,'Original frame-order identity pin drift')
licenses=c.parse((web/'licenses.manifest.json').read_bytes())
for name in ('LICENSE_MIT','LICENSE_APACHE'):
 c.require(c.digest(files[name])==licenses['runtime/'+name],'Upstream license text changed')
archivepath=app/lock['archivePath'];c.require(not archivepath.exists(),'No overwrite of prior vendor archive')
# All checks completed before runtime/test writes. No unknown files removed.
for name,data in files.items():(target/name).write_bytes(data)
frame_test.write_text(frame_text.replace(old_pin,new_pin))
(web/'runtime-identity.json').write_bytes(identity_bytes);(app/'runtime.lock.json').write_bytes(encoded(lock));(app/'runtime.files.json').write_bytes(encoded(manifest))
archivepath.parent.mkdir(exist_ok=True);archivepath.write_bytes(raw)
(app/'FINAL_ENGINE_STAGING.json').write_bytes(encoded({'engineAccepted':True,'engine':proof,'runtimeLockSHA256':c.digest(encoded(lock)),'identitySHA256':lock['identitySHA256'],'samplingGateEnabled':False,'nativeAccepted':False,'ipaBuilt':False}))
print('Staged exact composite engine; sampling gate remains false, native/IPA acceptance pending')
