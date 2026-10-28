#!/usr/bin/env python3
"""Diagnostic-only Session overlay. Never edits the shipping source tree."""
import hashlib
import json
from pathlib import Path
import sys

SESSION = Path('App/Player/PlayerSession.swift')
EXPECTED = '517add7683716d98f17c82f3a2ab76b8354489c1fb0021cf68fe55351a0adc0f'
ANCHOR = '            let controller = WKUserContentController()\n'
INSERT = '''            // CI-only fault injection: this file is not a shipping App source.
            guard let injectionURL = Bundle.main.url(forResource: "audio-recovery-injection", withExtension: "js") else {
                throw PackageError.corrupt("Diagnostic audio injection resource missing")
            }
            controller.add(StartupJournal.shared.makeHandler(), name: "flashnestStartup")
            guard let startupURL = Bundle.main.url(forResource: "startup-journal", withExtension: "js"),
                  let resourcesURL = Bundle.main.url(forResource: "startup-resources", withExtension: "json") else {
                throw PackageError.corrupt("Diagnostic startup resources missing")
            }
            let startup = try String(contentsOf: startupURL, encoding: .utf8)
            let resources = try String(contentsOf: resourcesURL, encoding: .utf8)
            controller.addUserScript(WKUserScript(source: "window.__FlashNestStartupResources=" + resources + ";" + startup, injectionTime: .atDocumentStart, forMainFrameOnly: true))
            let injection = try String(contentsOf: injectionURL, encoding: .utf8)
            controller.addUserScript(WKUserScript(source: injection, injectionTime: .atDocumentStart, forMainFrameOnly: true))
'''

def stage(source_root, output, script, script_sha):
    source_root, output, script = map(lambda p: Path(p).resolve(), (source_root, output, script))
    if output == source_root or source_root in output.parents or output in source_root.parents:
        raise ValueError('Overlay must be separate from shipping source tree')
    if output.exists(): raise ValueError('Overlay destination must not exist')
    if len(script_sha) != 64 or any(c not in '0123456789abcdef' for c in script_sha):
        raise ValueError('Exact reviewed script SHA256 required')
    original = (source_root / SESSION).read_bytes()
    injected = script.read_bytes()
    if hashlib.sha256(original).hexdigest() != EXPECTED: raise ValueError('Session pin drift')
    if hashlib.sha256(injected).hexdigest() != script_sha: raise ValueError('Injection script pin drift')
    if not injected or len(injected) > 65536: raise ValueError('Injection script size invalid')
    text = original.decode('utf-8')
    if text.count(ANCHOR) != 1 or 'audio-recovery-injection' in text:
        raise ValueError('Session injection anchor drift')
    patched = text.replace(ANCHOR, ANCHOR + INSERT).encode()
    output.mkdir(parents=True)
    target = output / SESSION
    target.parent.mkdir(parents=True)
    target.write_bytes(patched)
    (output / 'audio-recovery-injection.js').write_bytes(injected)
    import difflib
    (output / 'session-injection.diff').write_text(''.join(difflib.unified_diff(
        text.splitlines(True), patched.decode().splitlines(True), fromfile=str(SESSION), tofile=str(SESSION))))
    evidence = {'shippingSessionSHA256': EXPECTED, 'overlaySessionSHA256': hashlib.sha256(patched).hexdigest(),
                'injectionSHA256': script_sha, 'shippingUnchanged': (source_root / SESSION).read_bytes() == original}
    (output / 'overlay-manifest.json').write_text(json.dumps(evidence, indent=2)+'\n')
    if not evidence['shippingUnchanged']: raise RuntimeError('Shipping source changed during staging')
    return evidence

if __name__ == '__main__':
    if len(sys.argv) != 5: raise SystemExit('source-root new-overlay-root reviewed-script script-sha256')
    print(json.dumps(stage(*sys.argv[1:])))
