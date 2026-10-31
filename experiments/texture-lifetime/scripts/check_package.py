import hashlib,json,pathlib
root=pathlib.Path(__file__).resolve().parents[1]
manifest=json.loads((root/'manifest.json').read_text())
actual={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p!=root/'manifest.json' and '__pycache__' not in p.parts}
assert actual==manifest['files'],'Package changed after review'
assert manifest['productChanges']==False
lock=json.loads((root/'engine-lock.json').read_text());assert lock['baselineProvenance']['variant']=='baseline'
print('Pinned diagnostic-only package verified',len(actual))
