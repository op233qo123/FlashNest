"""Stage one distinct phase-engine diagnostic; never shipping, never old candidate fallback."""
import argparse,hashlib,json,shutil,subprocess,tarfile,tempfile
from pathlib import Path
from apply_injection import stage as inject,SESSION
from apply_startup import transform
HERE=Path(__file__).resolve().parent
SOURCE='5862f8dbd414d9835f11872d3ebabd1eed315ffc'
ORIGINAL_INJECTOR='d495f538242dd49915810a33478c17da9c1e7a831a721524a9136c4f2628176b'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare(repo,output,runtime,approval):
 repo,output,runtime,approval=map(lambda x:Path(x).resolve(),(repo,output,runtime,approval))
 if output.exists() or output==repo or output.is_relative_to(repo):raise ValueError('New isolated stage required')
 a=json.loads(approval.read_text())
 if a['sourceCommit']!=SOURCE or a['kind']!='sigill-phase-diagnostic-not-shipping' or a['authorizedObservationCount']!=1:raise ValueError('Wrong immutable diagnostic approval')
 inventory=a['runtimes']['diagnostic']['files']
 actual={str(p.relative_to(runtime)):digest(p) for p in runtime.rglob('*') if p.is_file()}
 if any(p.is_symlink() for p in runtime.rglob('*')) or actual!=inventory:raise ValueError('Distinct runtime exact inventory mismatch')
 for name,sha in a['diagnosticFiles'].items():
  p=HERE/name
  if not p.resolve().is_relative_to(HERE) or p.is_symlink() or digest(p)!=sha:raise ValueError('Reviewed diagnostic source drift')
 required={'stage_one.py','run_one.py','verify_engine.py','export_public.py','collect.py','installed_bundle.py','apply_injection.py','apply_startup.py','project.yml','startup-journal.js','audio-recovery-injection.js','Host/AudioRecoveryHost.swift','Host/StartupJournal.swift'}
 if not required<=set(a['diagnosticFiles']):raise ValueError('Incomplete source approval')
 if digest(HERE/'audio-recovery-injection.js')!=ORIGINAL_INJECTOR:raise ValueError('Original injector correspondence lost')
 with tempfile.TemporaryDirectory() as tmp:
  tmp=Path(tmp);archive=tmp/'source.tar'
  with archive.open('wb') as f:subprocess.run(['git','-C',str(repo),'archive',SOURCE,'App','fixtures/lifecycle','Package.resolved'],stdout=f,check=True)
  shipping=tmp/'shipping';shipping.mkdir()
  with tarfile.open(archive) as tar:
   for m in tar.getmembers():
    if not(m.isfile() or m.isdir()) or Path(m.name).is_absolute() or '..'in Path(m.name).parts:raise ValueError('Unsafe source archive')
   tar.extractall(shipping,filter='data')
  overlay=tmp/'overlay';inject(shipping,overlay,HERE/'audio-recovery-injection.js',ORIGINAL_INJECTOR)
  output.mkdir();staged=output/'staged';staged.mkdir()
  shutil.copytree(shipping/'App',staged/'App');shutil.copyfile(overlay/SESSION,staged/SESSION)
  session=staged/SESSION;text=session.read_text()
  anchor='            controller.addUserScript(WKUserScript(source: "window.__FlashNestStartupResources=" + resources + ";" + startup, injectionTime: .atDocumentStart, forMainFrameOnly: true))\n'
  if text.count(anchor)!=1:raise ValueError('Registered journal anchor drift')
  text=text.replace(anchor,anchor+'            StartupJournal.shared.registeredScript(source: "window.__FlashNestStartupResources=" + resources + ";" + startup)\n')
  anchor='            controller.addUserScript(WKUserScript(source: injection, injectionTime: .atDocumentStart, forMainFrameOnly: true))\n'
  if text.count(anchor)!=1:raise ValueError('Registered injector anchor drift')
  session.write_text(text.replace(anchor,anchor+'            StartupJournal.shared.registeredScript(source: injection)\n'))
  shutil.copytree(shipping/'fixtures/lifecycle',staged/'lifecycle')
  for name in ['audio-recovery-injection.js','startup-journal.js']:shutil.copyfile(HERE/name,staged/name)
  (staged/'startup-resources.json').write_text(json.dumps(inventory,sort_keys=True))
  shell=staged/'App/Resources/Web/shell.js';patched,diff=transform(shell.read_bytes());shell.write_bytes(patched)
  (output/'startup-shell.diff').write_text(diff)
  shutil.rmtree(staged/'App/Resources/Web/runtime');shutil.copytree(runtime,staged/'App/Resources/Web/runtime')
  (output/'Host').mkdir()
  for name in ['AudioRecoveryHost.swift','StartupJournal.swift']:shutil.copyfile(HERE/'Host'/name,output/'Host'/name)
  shutil.copyfile(HERE/'project.yml',output/'project.yml')
  shutil.copyfile(shipping/'Package.resolved',output/'Package.resolved')
  source='window.__FlashNestStartupResources='+(staged/'startup-resources.json').read_text()+';'+(staged/'startup-journal.js').read_text()
  manifest={'schema':1,'sourceCommit':SOURCE,'kind':a['kind'],'arm':'diagnostic','runtime':a['runtimes']['diagnostic'],
   'instrumentationProfile':'instrumented','authorizedObservationCount':1,'registeredStartupScriptSHA256':hashlib.sha256(source.encode()).hexdigest(),
   'registeredScriptSHA256s':[hashlib.sha256(source.encode()).hexdigest(),ORIGINAL_INJECTOR],
   'originalInjectorSHA256':ORIGINAL_INJECTOR,'audioStateCoverage':'context-state-unknown-not-queried; phase-boundary-receipts-only; original-injector-preserved',
   'files':{str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file()}}
  (output/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 return output
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--output',required=True);p.add_argument('--runtime',required=True);p.add_argument('--approval',required=True);a=p.parse_args();prepare(a.repo,a.output,a.runtime,a.approval)
