#!/usr/bin/env python3
"""Overlay the reviewed probe into a disposable CI checkout; never a release build."""
import hashlib
from pathlib import Path
import shutil
import sys

BASE_SHA = 'ffe3cfd7047d85a9050a3da36958f1cdaa2b21c63a390aa63035ba6833c72f2b'


def transform(source):
    if hashlib.sha256(source).hexdigest() != BASE_SHA:
        raise ValueError('unexpected production PlayerSession; refusing probe overlay')
    text = source.decode()
    old = '        let started = Date()\n        NSLog("CACHE-CLEANUP-BEGIN supportedMask=%d", supported)'
    new = '''        let started = Date()
        let deadline = started.addingTimeInterval(15)
        let lease = CacheCleanupWarmLease(profile: profile)
        defer { lease.close() }
        try await lease.prepare(before: deadline)
        NSLog("CACHE-CLEANUP-BEGIN supportedMask=%d", supported)'''
    assert text.count(old) == 1
    text = text.replace(old, new)
    start = text.index('    static func clearPackageCaches(')
    end = text.index('    static func preparePackageRemoval(', start)
    section = text[start:end]
    old_sleep = 'try? await Task.sleep(nanoseconds: 15_000_000_000)'
    assert section.count(old_sleep) == 1
    section = section.replace(old_sleep, 'try? await Task.sleep(nanoseconds: UInt64(max(0, deadline.timeIntervalSinceNow) * 1_000_000_000))')
    return (text[:start] + section + text[end:]).encode()


def apply(root):
    target = root / 'App/Player/PlayerSession.swift'
    modified = transform(target.read_bytes())
    helper = root / 'experiments/cache-liveness/CacheCleanupWarmLease.swift'
    assert helper.is_file()
    target.write_bytes(modified)
    shutil.copyfile(helper, root / 'App/Player/CacheCleanupWarmLease.swift')
    print('CACHE-CLEANUP-PROBE source=' + BASE_SHA + ' patched=' + hashlib.sha256(modified).hexdigest())


if __name__ == '__main__':
    apply(Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve())
