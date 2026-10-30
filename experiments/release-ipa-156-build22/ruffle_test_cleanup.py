#!/usr/bin/env python3
"""One reversible test-only cleanup change. Production source is untouched."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
TARGET='Tests/RuffleRuntimeTests.swift'
def sha(b):return hashlib.sha256(b).hexdigest()
def transform(s):
    old='''    private func exerciseFixture(named name: String) async throws {
        executionTimeAllowance = 120
        let fixtures = try XCTUnwrap(Bundle(for: RuffleRuntimeTests.self).url(forResource: "fixtures", withExtension: nil))
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }'''
    new='''    private func exerciseFixture(named name: String) async throws {
        executionTimeAllowance = 120
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let cleanup = FixtureCleanup()
        var primaryError: Error?
        do { try await exerciseFixtureBody(named: name, root: root, cleanup: cleanup) }
        catch { primaryError = error }
        let cleanupError = await cleanup.finish(root: root)
        // Keep the original thrown failure; cleanup failures are independently
        // recorded by finish, so neither failure can mask the other.
        if let primaryError { throw primaryError }
        if let cleanupError { throw cleanupError }
    }

    @MainActor private final class FixtureCleanup {
        var session: PlayerSession?
        var window: UIWindow?
        var previousKeyWindow: UIWindow?

        func finish(root: URL) async -> Error? {
            var cleanupError: Error?
            var drained = false
            do {
                try await session?.closeWithoutSaving()
                drained = true
            } catch {
                cleanupError = error
                XCTFail("Synthetic runtime fixture cleanup did not confirm server drain")
            }
            // Explicitly release the fixture's UIKit ownership after shutdown.
            // This does not assert that WebContent/GPU memory was reclaimed.
            window?.rootViewController?.view.subviews.forEach { $0.removeFromSuperview() }
            window?.rootViewController = nil
            window?.isHidden = true
            previousKeyWindow?.makeKey()
            window = nil; previousKeyWindow = nil; session = nil
            // Do not delete assets while an unconfirmed listener may serve them.
            if drained && FileManager.default.fileExists(atPath: root.path) {
                do { try FileManager.default.removeItem(at: root) }
                catch {
                    cleanupError = error
                    XCTFail("Synthetic runtime fixture directory cleanup failed")
                }
            }
            return cleanupError
        }
    }

    private func exerciseFixtureBody(named name: String, root: URL, cleanup: FixtureCleanup) async throws {
        let fixtures = try XCTUnwrap(Bundle(for: RuffleRuntimeTests.self).url(forResource: "fixtures", withExtension: nil))'''
    assert s.count(old)==1;s=s.replace(old,new)
    old='''        let session = PlayerSession()
        // Ruffle''';new='''        let session = PlayerSession()
        cleanup.session = session
        // Ruffle''';assert s.count(old)==1;s=s.replace(old,new)
    old='''        defer {
            session.stop()
            window.isHidden = true
            previousKeyWindow?.makeKey()
        }''';new='''        cleanup.window = window
        cleanup.previousKeyWindow = previousKeyWindow''';assert s.count(old)==1;s=s.replace(old,new)
    return s

def apply(app,state,source_map):
    app=Path(app);state=Path(state);assert not state.exists()
    assert TARGET in source_map,'Target missing from original source map'
    assert all(sha((app/p).read_bytes())==h for p,h in source_map.items()),'Original source mismatch'
    original=(app/TARGET).read_bytes();modified=transform(original.decode()).encode()
    state.write_text(json.dumps({'originalSourceFiles':source_map,'target':TARGET,'original':original.decode(),'modifiedSHA256':sha(modified)},sort_keys=True))
    (app/TARGET).write_bytes(modified)

def restore(app,state):
    app=Path(app);state=Path(state);record=json.loads(state.read_text())
    assert sha((app/TARGET).read_bytes())==record['modifiedSHA256'],'Modified test changed before inverse'
    (app/TARGET).write_bytes(record['original'].encode())
    assert all(sha((app/p).read_bytes())==h for p,h in record['originalSourceFiles'].items()),'Exact original source restoration failed'
    state.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['apply','restore']);p.add_argument('--app',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--source-map',type=Path)
    a=p.parse_args()
    if a.action=='apply':apply(a.app,a.state,json.loads(a.source_map.read_text()))
    else:restore(a.app,a.state)
