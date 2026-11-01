#!/usr/bin/env python3
"""Validate the pinned existing IPA artifact; extract only the unchanged runtime."""
import argparse, hashlib, io, json, os, re, stat, zipfile
from pathlib import Path, PurePosixPath
ROOT = Path(__file__).resolve().parent
PREFIX = 'Payload/FlashNest.app/Web/runtime/'
def need(value, message):
    if not value: raise ValueError(message)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def checked_zip(raw, max_total, allow_directories):
    z = zipfile.ZipFile(io.BytesIO(raw)); entries = z.infolist()
    need(len(entries) <= 1000 and len({r.filename for r in entries}) == len(entries), 'Duplicate/too many members')
    need(sum(r.file_size for r in entries) <= max_total, 'Oversized ZIP payload')
    for row in entries:
        name = row.filename; clean = name[:-1] if row.is_dir() else name; p = PurePosixPath(clean)
        need(clean and not p.is_absolute() and '..' not in p.parts and '.' not in p.parts and '\\' not in name
             and ':' not in name and not any(ord(c) < 32 for c in name) and str(p) == clean, 'Unsafe ZIP member')
        mode = stat.S_IFMT(row.external_attr >> 16)
        need(mode in ((0, stat.S_IFDIR) if row.is_dir() else (0, stat.S_IFREG)), 'Nonregular ZIP member')
        need(allow_directories or not row.is_dir(), 'Unexpected ZIP directory')
        need(row.file_size <= 64 * 1024 * 1024 and not row.flag_bits & 1, 'Oversized/encrypted ZIP member')
    need(z.testzip() is None, 'ZIP CRC mismatch')
    return z

def stage(archive, output, receipt):
    raw_manifest = (ROOT / 'runtime-source.json').read_bytes(); x = json.loads(raw_manifest)
    need(x['schema'] == 1 and x['runtimeChanged'] is False and x['privateGameDataIncluded'] is False, 'Wrong source contract')
    expected = x['runtimeFiles']
    need(len(expected) == 12 and all(re.fullmatch(r'[A-Za-z0-9_.-]+', n) and re.fullmatch(r'[0-9a-f]{64}', h)
        for n,h in expected.items()), 'Invalid runtime inventory')
    raw = archive.read_bytes()
    need(len(raw) == x['archiveBytes'] and sha(raw) == x['archiveSHA256'], 'Artifact bytes/hash mismatch')
    name = x['ipaFilename']
    with checked_zip(raw, 32 * 1024 * 1024, False) as outer:
        need(set(outer.namelist()) == {name, name + '.sha256', 'case-compatible-ipa-provenance.json'}, 'Unexpected outer payload')
        ipa = outer.read(name); provenance_raw = outer.read('case-compatible-ipa-provenance.json')
        need(len(ipa) == x['ipaBytes'] and sha(ipa) == x['ipaSHA256'], 'IPA bytes/hash mismatch')
        checksum_raw = outer.read(name + '.sha256')
        need(sha(checksum_raw) == x['checksumFileSHA256'], 'Checksum sidecar bytes differ')
        checksum = checksum_raw.decode().strip().split()
        # This historical sidecar names its CI absolute path; validate, never use it for I/O.
        need(len(checksum) == 2 and checksum[0] == x['ipaSHA256'] and PurePosixPath(checksum[1]).name == name, 'IPA checksum file differs')
        need(sha(provenance_raw) == x['provenanceSHA256'], 'Provenance bytes differ')
        provenance = json.loads(provenance_raw)
    need(provenance['packagingCommit'] == x['artifactHead'] and str(provenance['packagingRunID']) == str(x['artifactRunID']), 'Provenance build identity differs')
    need(provenance['ipaFilename'] == name and provenance['ipaBytes'] == len(ipa) and provenance['ipaSHA256'] == sha(ipa), 'Provenance IPA differs')
    need(provenance['runtimeFiles'] == expected and provenance['runtimeChanged'] is False
        and provenance['productFrameRateChanged'] is False, 'Provenance runtime differs')
    with checked_zip(ipa, 128 * 1024 * 1024, True) as inner:
        runtime_names = {n for n in inner.namelist() if n.startswith(PREFIX) and not n.endswith('/')}
        need(runtime_names == {PREFIX + n for n in expected}, 'IPA runtime closure differs')
        identity_raw = inner.read('Payload/FlashNest.app/Web/runtime-identity.json')
        need(sha(identity_raw) == x['runtimeIdentitySHA256'], 'Engine identity hash differs')
        identity = json.loads(identity_raw)
        need(identity == x['runtimeIdentity'] and {n:r['sha256'] for n,r in identity['runtimeFiles'].items()} == expected, 'Engine source identity differs')
        files = {n: inner.read(PREFIX + n) for n in expected}
        for n, data in files.items():
            need(sha(data) == expected[n] and len(data) == identity['runtimeFiles'][n]['bytes'], 'Runtime bytes differ: ' + n)
            need(provenance['packagedBundleFiles']['Web/runtime/' + n] == expected[n], 'Bundle manifest mismatch')
    # Every archive, identity, and runtime check completes before writing any file.
    need(not output.exists(), 'Fresh runtime output directory required')
    output.mkdir(parents=True)
    for n,data in files.items(): (output/n).write_bytes(data)
    need({p.name: sha(p.read_bytes()) for p in output.iterdir() if p.is_file()} == expected, 'Staged runtime mismatch')
    result = {'schema': 'flashnest-loader-probe-runtime-stage-v1', 'runtimeVerified': True,
        'sourceManifestSHA256': sha(raw_manifest), 'sourceArtifact': {k:x[k] for k in ('repository','artifactID','artifactRunID','artifactHead','archiveBytes','archiveSHA256','ipaBytes','ipaSHA256','provenanceSHA256')},
        'runtimeFiles': expected, 'runtimeIdentity': identity, 'runtimeChanged': False,
        'newIPABuilt': False, 'privateGameDataIncluded': False, 'head': os.environ.get('GITHUB_SHA'),
        'runID': os.environ.get('GITHUB_RUN_ID'), 'scope': 'Only the 12 verified existing runtime files extracted; no App reconstruction, engine patch or IPA build'}
    receipt.parent.mkdir(parents=True, exist_ok=True); receipt.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print('Verified and staged 12 unchanged runtime files; no IPA built')

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args();stage(a.archive,a.output,a.receipt)
