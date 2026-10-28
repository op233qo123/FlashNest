#!/usr/bin/env python3
"""Bounded WebKit / SimMetalHost crash evidence from a dedicated, ephemeral macOS CI runner.
Only .ips reports newer than this test's marker are copied; no general logs.
"""
from pathlib import Path
import json
import re
import sys


def collect(marker, output, reports):
    output.mkdir(parents=True, exist_ok=True)
    copied = []
    skipped = 0
    total = 0
    if marker.is_file() and reports.is_dir():
        since = marker.stat().st_mtime
        for path in sorted(reports.rglob('*.ips')):
            allowed_process = ('WebKit' in path.name and ('GPU' in path.name or 'WebContent' in path.name)) or 'SimMetalHost' in path.name
            if path.is_symlink() or not allowed_process:
                continue
            try:
                info = path.stat()
                if info.st_mtime < since:
                    continue
                if len(copied) >= 10 or info.st_size > 2 * 1024 * 1024 or total + info.st_size > 10 * 1024 * 1024:
                    skipped += 1
                    continue
                text = path.read_text(errors='replace')
                text = re.sub(r'http://127\.0\.0\.1:\d+/[a-fA-F0-9]{32,}/', 'http://127.0.0.1/<capability>/', text)
                name = f'{len(copied):02d}-' + path.name
                (output / name).write_text(text)
                copied.append(name)
                total += info.st_size
            except OSError:
                skipped += 1
    (output / 'collection.json').write_text(json.dumps({'reports': copied, 'skipped': skipped, 'maximumReports': 10, 'maximumTotalBytes': 10 * 1024 * 1024}, indent=2) + '\n')
    print(f'Collected {len(copied)} test-time WebKit / SimMetalHost crash reports; skipped {skipped}')


if __name__ == '__main__':
    collect(Path(sys.argv[1]), Path(sys.argv[2]), Path.home() / 'Library/Logs/DiagnosticReports')
