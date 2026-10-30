#!/usr/bin/env python3
"""Reversible XCTest-only fixed-step failure evidence. No product instrumentation."""
import hashlib,json
from pathlib import Path
TARGET='UITests/LifecyclePlayerUITests.swift'
def sha(b):return hashlib.sha256(b).hexdigest()
STEPS=('import','firstPlay','childInput','backgroundRunning','backgroundPaused','directSave','managementCancel','restartOptions','restartTap','restartPlay','restoredTrace','postRestartAssertions','complete')
HELPER=r'''
    private var diagnosticStep = "import"
    private var diagnosticRecording = false
    private var diagnosticFailureCount = 0
    private func diagnosticMark(_ step: String) {
        diagnosticStep = step
        print("FINAL_UI_STEP " + step)
    }
    override func record(_ issue: XCTIssue) {
        guard !diagnosticRecording && diagnosticFailureCount < 3 else {
            super.record(issue); return
        }
        do {
            diagnosticRecording = true; diagnosticFailureCount += 1
            let location = issue.sourceCodeContext.location
            let basename = location?.fileURL.lastPathComponent ?? "unknown"
            let source = ["LifecyclePlayerUITests.swift", "LibraryNavigation.swift"].contains(basename) ? basename : "unknown"
            let rawLine = location?.lineNumber ?? 0
            let line = source == "LifecyclePlayerUITests.swift" ? (diagnosticOriginalLines[rawLine] ?? 0) : (source == "unknown" ? 0 : rawLine)
            let body: [String: Any] = ["schema": 1, "step": diagnosticStep, "source": source,
                "line": line, "kind": issue.type == .assertionFailure ? "assertion" : "other"]
            if let data = try? JSONSerialization.data(withJSONObject: body, options: [.sortedKeys]),
               let text = String(data: data, encoding: .utf8) {
                print("FINAL_UI_FAILURE " + text)
                let evidence = XCTAttachment(string: text)
                evidence.name = "final-ui-failure"; evidence.lifetime = .keepAlways; add(evidence)
            }
            // Record the original failure BEFORE further accessibility queries.
            // If XCTest aborts here, the fixed failure marker above still exists.
            super.record(issue)
            // Fixed identifier snapshots only: no labels, hierarchy text, URLs,
            // save values, filenames, or arbitrary exception descriptions.
            let app = XCUIApplication()
            let ids = ["player-menu", "player-resume", "player-saves", "save-entry-direct", "save-entry-restart", "save-management-cancel"]
            var controls: [[String: Any]] = []
            for id in ids {
                let element = app.buttons[id].firstMatch
                let exists = element.exists
                controls.append(["id": id, "exists": exists, "enabled": exists && element.isEnabled])
            }
            let ax: [String: Any] = ["schema": 1, "step": diagnosticStep, "controls": controls,
                "webViewPresent": app.webViews.firstMatch.exists]
            if let data = try? JSONSerialization.data(withJSONObject: ax, options: [.sortedKeys]),
               let text = String(data: data, encoding: .utf8) {
                let evidence = XCTAttachment(string: text)
                evidence.name = "final-ui-safe-ax"; evidence.lifetime = .keepAlways; add(evidence)
                print("FINAL_UI_AX " + text)
            }
            // Never capture the Files picker/import phase or SpringBoard.
            // Only the fixed synthetic test App after successful import.
            if diagnosticFailureCount == 1 && !(["import", "backgroundRunning", "backgroundPaused"].contains(diagnosticStep)) && app.state == .runningForeground {
                let screenshot = XCTAttachment(screenshot: app.screenshot())
                screenshot.name = "final-ui-synthetic-app"; screenshot.lifetime = .keepAlways; add(screenshot)
            }
            diagnosticRecording = false
        }
    }
'''
def transform(source):
    anchors={
      '        let app = importFixture()':'import',
      '        startMovie(app)':'firstPlay',
      '        let menu = app.buttons["player-menu"].firstMatch':'childInput',
      '        showHomeAndRequireBackground(app, phase: "Running child")':'backgroundRunning',
      '        showHomeAndRequireBackground(app, phase: "Paused menu")':'backgroundPaused',
      '        app.buttons["player-saves"].firstMatch.tap()':'directSave',
      '        let manage = app.buttons["save-entry-manage"].firstMatch':'managementCancel',
      '        menu.tap(); setSwitch("controls-visible", enabled: false, in: app)':'restartOptions',
      '        reveal(restart, in: app); restart.tap()':'restartTap',
      '        trace("LIFECYCLE_ROOT_READY:420", in: app)':'restoredTrace',
      '        let stage = app.webViews.firstMatch':'postRestartAssertions',
      '        capture("Save and restart returns to same game with written save")':'complete',
    }
    rows=source.splitlines(True);assert rows[-1]=='}\n'
    output=[];line_map={};seen={};play=0
    for number,line in enumerate(rows[:-1],1):
        key=line.rstrip('\n')
        if key in anchors:
            step=anchors[key]
            if key=='        startMovie(app)':
                play+=1;step='firstPlay' if play==1 else 'restartPlay'
            seen[key]=seen.get(key,0)+1
            output.append(f'        diagnosticMark("{step}")\n')
        line_map[len(output)+1]=number;output.append(line)
    assert set(seen)==set(anchors) and play==2 and all(v==(2 if k=='        startMovie(app)' else 1) for k,v in seen.items()),'Unexpected original test layout'
    mapping=', '.join(f'{k}: {v}' for k,v in line_map.items())
    output.append('    private let diagnosticOriginalLines: [Int: Int] = ['+mapping+']\n')
    output.append(HELPER);output.append('}\n')
    return ''.join(output)

def apply(app,state,source_map):
    app=Path(app);state=Path(state);assert not state.exists() and TARGET in source_map
    assert all(sha((app/p).read_bytes())==h for p,h in source_map.items()),'Original source mismatch'
    original=(app/TARGET).read_bytes();modified=transform(original.decode()).encode()
    state.write_text(json.dumps({'originalSourceFiles':source_map,'target':TARGET,'original':original.decode(),'modifiedSHA256':sha(modified)},sort_keys=True))
    (app/TARGET).write_bytes(modified)
def restore(app,state):
    app=Path(app);state=Path(state);record=json.loads(state.read_text())
    assert sha((app/TARGET).read_bytes())==record['modifiedSHA256'],'Overlay changed before inverse'
    (app/TARGET).write_bytes(record['original'].encode())
    assert all(sha((app/p).read_bytes())==h for p,h in record['originalSourceFiles'].items()),'Exact inverse failed'
    state.unlink()
