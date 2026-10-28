"""CI-stage-only startup profile. Never used by the three-case recovery workflow."""
import argparse,difflib,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'native'))
from apply_injection import SESSION,EXPECTED,ANCHOR,INSERT
ROLES=('instrumented','passive-only')
FAULT_GUARD='''            guard let injectionURL = Bundle.main.url(forResource: "audio-recovery-injection", withExtension: "js") else {
                throw PackageError.corrupt("Diagnostic audio injection resource missing")
            }
'''
FAULT_INSTALL='''            let injection = try String(contentsOf: injectionURL, encoding: .utf8)
            controller.addUserScript(WKUserScript(source: injection, injectionTime: .atDocumentStart, forMainFrameOnly: true))
'''
STARTUP_INSTALL='''            controller.addUserScript(WKUserScript(source: "window.__FlashNestStartupResources=" + resources + ";" + startup, injectionTime: .atDocumentStart, forMainFrameOnly: true))
'''
PASSIVE_INSTALL='''            let startupSource = "window.__FlashNestStartupResources=" + resources + ";" + startup
            controller.addUserScript(WKUserScript(source: startupSource, injectionTime: .atDocumentStart, forMainFrameOnly: true))
            StartupJournal.shared.registeredScript(source: startupSource)
'''
RESOURCE='''      - path: staged/audio-recovery-injection.js
        buildPhase: resources
'''
def sha(data):return hashlib.sha256(data).hexdigest()
def apply(stage,profile,approval):
 if profile not in ROLES:raise ValueError('Unknown startup instrumentation profile')
 stage=Path(stage);approved=json.loads(Path(approval).read_text());mp=stage/'source-manifest.json';source=json.loads(mp.read_text())
 if 'instrumentationProfile'in source:raise ValueError('Profile already applied')
 for name,digest in source['files'].items():
  p=stage/name
  if p.is_symlink() or not p.is_file() or sha(p.read_bytes())!=digest:raise ValueError('Staged source drift')
 session=stage/'staged'/SESSION;text=session.read_text()
 if text.count(ANCHOR+INSERT)!=1:raise ValueError('Exact reviewed injection overlay required')
 original=text.replace(ANCHOR+INSERT,ANCHOR)
 if sha(original.encode())!=EXPECTED:raise ValueError('Production Session pin drift')
 project=stage/'project.yml';project_text=project.read_text()
 if sha(project.read_bytes())!=approved['diagnosticFiles']['project.yml']:raise ValueError('Project source drift')
 if project_text.count(RESOURCE)!=1:raise ValueError('Fault resource stanza drift')
 startup=stage/'staged/startup-journal.js';resources=stage/'staged/startup-resources.json'
 actual_script='window.__FlashNestStartupResources='+resources.read_text()+';'+startup.read_text()
 source['instrumentationProfile']=profile
 source['registeredStartupScriptSHA256']=sha(actual_script.encode())
 source['audioStateCoverage']='unavailable-without-fault-injector' if profile=='passive-only' else 'existing-injector-context-observer'
 source['faultInjectorBundled']=profile=='instrumented'
 if profile=='passive-only':
  insert=INSERT
  for old,new in [(FAULT_GUARD,''),(FAULT_INSTALL,''),(STARTUP_INSTALL,PASSIVE_INSTALL)]:
   if insert.count(old)!=1:raise ValueError('Profile transform anchor drift')
   insert=insert.replace(old,new)
  insert=insert.replace('// CI-only fault injection: this file is not a shipping App source.','// CI-only passive startup journal; no fault injector installed.')
  patched=original.replace(ANCHOR,ANCHOR+insert)
  session.write_text(patched);project.write_text(project_text.replace(RESOURCE,''))
  (stage/'staged/audio-recovery-injection.js').unlink()
  source['files'].pop('staged/audio-recovery-injection.js')
  (stage/'startup-profile.diff').write_text(''.join(difflib.unified_diff(text.splitlines(True),patched.splitlines(True),fromfile='instrumented/PlayerSession.swift',tofile='passive-only/PlayerSession.swift')))
 else:(stage/'startup-profile.diff').write_text('No change: existing instrumented profile.\n')
 overlay=stage/'overlay-manifest.json';previous=overlay.read_bytes();(stage/'instrumented-overlay-manifest.json').write_bytes(previous)
 evidence=json.loads(previous);evidence.update(instrumentationProfile=profile,overlaySessionSHA256=sha(session.read_bytes()),injectionSHA256=sha((stage/'staged/audio-recovery-injection.js').read_bytes()) if profile=='instrumented' else None,registeredStartupScriptSHA256=source['registeredStartupScriptSHA256'])
 overlay.write_text(json.dumps(evidence,indent=2)+'\n');source['files']['instrumented-overlay-manifest.json']=sha(previous)
 source['files']={name:sha((stage/name).read_bytes()) for name in source['files']}
 source['files']['startup-profile.diff']=sha((stage/'startup-profile.diff').read_bytes())
 mp.write_text(json.dumps(source,indent=2)+'\n')
 return source
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--profile',choices=ROLES,required=True);p.add_argument('--approval',required=True);a=p.parse_args();apply(a.stage,a.profile,a.approval)
