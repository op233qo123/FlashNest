"""Test-only one-file addition; never changes the product or existing tests."""
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
TARGET = 'Tests/RestartOwnershipDiagnosticTests.swift'
def sha(data): return hashlib.sha256(data).hexdigest()
def filemap(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink(): raise AssertionError('Symlink forbidden')
        if p.is_file(): result[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    return result

def apply_overlay(app):
    app = Path(app)
    pins = json.loads((ROOT/'source-pins.json').read_text())
    original = (app/'App/Views/PlayerView.swift').read_bytes()
    assert sha(original) == pins['playerViewSHA256'], 'Unapproved PlayerView source'
    source = (ROOT/'RestartOwnershipDiagnosticTests.swift').read_bytes()
    assert sha(source) == pins['testSHA256'], 'Diagnostic source drift'
    for block in pins['exactSourceBlocks']:
        assert original.decode().count(block) == 1 and source.decode().count(block) == 1, 'Source copy drift'
    before = filemap(app)
    assert TARGET not in before, 'Never overwrite an existing test'
    (app/TARGET).write_bytes(source)
    after = filemap(app)
    inverse = dict(after); del inverse[TARGET]
    assert inverse == before, 'Inverse source mismatch'
    assert set(after)-set(before) == {TARGET}
    return {'schema':'flashnest-ownership-test-overlay-v1', 'diagnosticOnly':True,
            'nativeAcceptance':False, 'exactInverseVerified':True, 'productAppUnchanged':True,
            'target':TARGET, 'beforeFiles':before, 'afterFiles':after,
            'testSHA256':sha(source), 'playerViewSHA256':sha(original)}
