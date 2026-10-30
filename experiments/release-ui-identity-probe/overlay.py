#!/usr/bin/env python3
"""Reversible, opt-in synthetic-test-only overlay; never a product fix."""
import argparse, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
PATHS=['App/Views/PlayerView.swift','App/Player/PlayerSession.swift','UITests/LifecyclePlayerUITests.swift']
NEW='App/Player/IdentityProbe.swift'
def inventory(app):
    return {p.relative_to(app).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(app.rglob('*')) if p.is_file() and not any(v in p.parts for v in ['build','.git'])}
def once(s,a,b):
    assert s.count(a)==1, a
    return s.replace(a,b)
def transform(path,s):
    if path==PATHS[0]:
        s=once(s,'PlayerWebView(webView: webView)','PlayerWebView(webView: webView, session: session)')
        s=once(s,'''    let webView: WKWebView
    func makeUIView(context: Context) -> WKWebView { webView }
    func updateUIView(_ uiView: WKWebView, context: Context) {}''','''    let webView: WKWebView
    let session: PlayerSession
#if DEBUG
    func makeCoordinator() -> IdentityProbe { IdentityProbe() }
#endif
    func makeUIView(context: Context) -> WKWebView {
#if DEBUG
        context.coordinator.observe(webView, session: session)
#endif
        return webView
    }
    func updateUIView(_ uiView: WKWebView, context: Context) {
#if DEBUG
        context.coordinator.observe(uiView, session: session)
#endif
    }''')
    elif path==PATHS[1]:
        s=once(s,'    private var processTerminated = false','''    private var processTerminated = false
#if DEBUG
    var identityProbeTerminated: Bool { processTerminated }
#endif''')
    else:
        s=once(s,'        let app = importFixture()','''        let app = importFixture()
        defer { identityEvidence(app, "final") }''')
        s=once(s,'        trace("LIFECYCLE_ROOT_READY:undefined", in: app)','''        trace("LIFECYCLE_ROOT_READY:undefined", in: app)
        identityEvidence(app, "baseline")
        let identity = app.staticTexts["identity-probe"].firstMatch
        XCTAssertTrue(identity.waitForExistence(timeout: 5), "Diagnostic probe must be observable before interpreting restart evidence")
        let identityJSON = identity.label.data(using: .utf8).flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        XCTAssertEqual(identityJSON?["schema"] as? Int, 1)
        XCTAssertEqual(identityJSON?["same"] as? Bool, true)
        XCTAssertEqual(identityJSON?["representedAttached"] as? Bool, true)''')
        s=once(s,'        reveal(restart, in: app); restart.tap()','''        reveal(restart, in: app)
        identityEvidence(app, "before-restart")
        restart.tap()
        identityEvidence(app, "after-restart-tap")''')
        s=once(s,'        XCTAssertTrue(play.waitForExistence(timeout: 60)); XCTAssertTrue(wait { play.isEnabled }); play.tap()','''        let appeared = play.waitForExistence(timeout: 60)
        if !appeared { identityEvidence(app, "play-timeout") }
        XCTAssertTrue(appeared); XCTAssertTrue(wait { play.isEnabled }); play.tap()''')
        s=once(s,'app.launchArguments = ["--flashnest-cross-container-ui-test",','app.launchArguments = ["--flashnest-identity-probe", "--flashnest-cross-container-ui-test",')
        s=once(s,'    private func startMovie(_ app: XCUIApplication) {','''    private func identityEvidence(_ app: XCUIApplication, _ phase: String) {
        let probe = app.staticTexts["identity-probe"].firstMatch
        let scalar = probe.exists ? String(probe.label.prefix(4096)) : "{\\"unavailable\\":true}"
        print("IDENTITY_UI phase=\\(phase) " + scalar)
        for (name, body) in [("scalar", scalar), ("AX", String(app.debugDescription.prefix(65536)))] {
            let evidence = XCTAttachment(string: body)
            evidence.name = "identity-" + phase + "-" + name
            evidence.lifetime = .keepAlways; add(evidence)
        }
        let image = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        image.name = "identity-" + phase + "-PNG"; image.lifetime = .keepAlways; add(image)
    }

    private func startMovie(_ app: XCUIApplication) {''')
    return s

def apply(app,state,source_map=None):
    assert not state.exists() and not (app/NEW).exists()
    original=inventory(app) if source_map is None else dict(source_map)
    assert all(not (app/p).is_symlink() and hashlib.sha256((app/p).read_bytes()).hexdigest()==h for p,h in original.items()), "Original source mismatch"
    assert set(PATHS).issubset(original)
    originals={p:(app/p).read_text() for p in PATHS}
    changed={p:transform(p,s) for p,s in originals.items()}
    expected={p:hashlib.sha256(s.encode()).hexdigest() for p,s in changed.items()}
    expected[NEW]=hashlib.sha256((HERE/'IdentityProbe.swift').read_bytes()).hexdigest()
    state.write_text(json.dumps({'inventory':original,'originals':originals,'overlayFiles':expected,'selectedInventory':source_map is not None},sort_keys=True))
    for p,s in changed.items(): (app/p).write_text(s)
    (app/NEW).write_bytes((HERE/'IdentityProbe.swift').read_bytes())
def restore(app,state):
    record=json.loads(state.read_text())
    for p,digest in record['overlayFiles'].items():
        assert hashlib.sha256((app/p).read_bytes()).hexdigest()==digest, 'Overlay changed before inverse: '+p
    for p,s in record['originals'].items(): (app/p).write_text(s)
    (app/NEW).unlink()
    restored=({p:hashlib.sha256((app/p).read_bytes()).hexdigest() for p in record['inventory']} if record.get('selectedInventory') else inventory(app))
    assert restored==record['inventory'], 'Exact inverse inventory mismatch'
    assert not (app/NEW).exists()
    state.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['apply','restore']); p.add_argument('--app',type=Path,required=True); p.add_argument('--state',type=Path,required=True)
    a=p.parse_args(); (apply if a.action=='apply' else restore)(a.app.resolve(),a.state.resolve())
