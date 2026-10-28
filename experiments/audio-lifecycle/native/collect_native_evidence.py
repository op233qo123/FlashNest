#!/usr/bin/env python3
"""Retain only this original diagnostic app's bounded files, using actual XCTest device."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

BUNDLE = 'com.flashnest.audio-lifecycle.diagnostic'
MODES = {f'{arm}-{mode}' for arm in ('baseline', 'candidate')
         for mode in ('normal', 'start-first', 'start-second', 'synthetic-ended')}


def require(value, message):
    if not value:
        raise ValueError(message)


def actual_device(summary):
    devices = [row['device'] for row in summary['devicesAndConfigurations']]
    require(devices and all(d.get('osVersion') == '18.5' and d.get('platform') == 'iOS Simulator' for d in devices),
            'Unexpected actual XCTest platform')
    identifiers = {str(uuid.UUID(d['deviceId'])).upper() for d in devices}
    require(len(identifiers) == 1, 'Missing/ambiguous actual XCTest device')
    return identifiers.pop()


def copy_evidence(source, destination):
    require(source.is_dir() and not source.is_symlink(), 'Diagnostic Documents evidence is missing/linked')
    require(not destination.exists(), 'Refusing evidence overwrite')
    entries, total, suites = [], 0, list(source.iterdir())
    require(len(suites) == 1, 'Expected exactly one diagnostic suite')
    suite = suites[0]
    require(suite.is_dir() and not suite.is_symlink() and str(uuid.UUID(suite.name)) == suite.name,
            'Invalid diagnostic suite')
    for mode in sorted(suite.iterdir()):
        require(mode.name in MODES and mode.is_dir() and not mode.is_symlink(), 'Unexpected diagnostic mode')
        mode_files = sorted(mode.iterdir())
        require(len(mode_files) <= 93, 'Evidence file count bound')
        for file in mode_files:
            require(file.is_file() and not file.is_symlink(), 'Non-regular evidence')
            require(file.name in ('identity.json', 'host-summary.json', 'host-final-snapshot.json', 'host-final-window.json', 'page-terminal.json')
                    or re.fullmatch(r'case-(?:start-|receipt-)?[0-7]\.json', file.name)
                    or re.fullmatch(r'event-(?:chunk|receipt)-(?:[0-9]|[1-3][0-9])\.json', file.name), 'Unexpected evidence name')
            size = file.stat().st_size
            require(0 < size <= 2 * 1024 * 1024 and total + size <= 128 * 1024 * 1024, 'Evidence size bound')
            data = file.read_bytes(); require(len(data) == size, 'Evidence changed during collection')
            json.loads(data)
            relative = file.relative_to(source)
            target = destination / relative; target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
            entries.append({'file': relative.as_posix(), 'bytes': size, 'sha256': hashlib.sha256(data).hexdigest()})
            total += size
    require(entries, 'No original diagnostic evidence files')
    return entries



def timestamp():
    return datetime.now(timezone.utc).isoformat()


def recover_shutdown_device(actual, result, run):
    """After crash capture only: boot the same XCTest device, never launch an app."""
    response = run(['xcrun', 'simctl', 'list', 'devices', '--json'],
                   capture_output=True, text=True, timeout=20)
    result['stateLookupExitCode'] = response.returncode
    result['stateLookupStderr'] = response.stderr[:8192]
    require(response.returncode == 0 and len(response.stdout) <= 2 * 1024 * 1024,
            'Cannot inspect actual simulator state within bounds')
    devices = json.loads(response.stdout)['devices']
    matches = [row for rows in devices.values() for row in rows
               if row.get('udid', '').upper() == actual]
    require(len(matches) == 1, 'Actual simulator missing/ambiguous in device listing')
    device = matches[0]
    result['priorDeviceState'] = device.get('state')
    require(device.get('isAvailable') is True and device.get('state') == 'Shutdown',
            'Failed lookup is not an available Shutdown actual simulator')
    result['recovery'] = {'scope': 'same-device post-test evidence only; no app launch',
                          'device': actual, 'startedAt': timestamp()}
    for key, command, bound in [
        ('boot', ['xcrun', 'simctl', 'boot', actual], 30),
        ('bootstatus', ['xcrun', 'simctl', 'bootstatus', actual, '-b'], 90),
    ]:
        record = {'startedAt': timestamp(), 'timeoutSeconds': bound}
        result['recovery'][key] = record
        try:
            response = run(command, capture_output=True, text=True, timeout=bound)
            record.update(exitCode=response.returncode, stderr=response.stderr[:8192], endedAt=timestamp())
        except subprocess.TimeoutExpired:
            record.update(timedOut=True, endedAt=timestamp())
            raise
        require(response.returncode == 0, 'Same-device evidence recovery failed: ' + key)
    result['recovery']['endedAt'] = timestamp()


def collect(summary, selected, output, run=subprocess.run):
    require(output.is_dir() and not output.is_symlink(), 'Invalid output directory')
    receipt = output / 'raw-collection.json'
    require(not receipt.exists(), 'Refusing collection receipt overwrite')
    result = {'schemaVersion': 1, 'verified': False, 'bundleID': BUNDLE,
              'selectedDevice': str(uuid.UUID(selected)).upper(), 'files': [], 'startedAt': timestamp()}
    try:
        actual = actual_device(summary); result['actualDevice'] = actual
        command = ['xcrun', 'simctl', 'get_app_container', actual, BUNDLE, 'data']
        response = run(command, capture_output=True, text=True, timeout=20)
        result['lookupExitCode'] = response.returncode
        result['lookupStderr'] = response.stderr[:8192]
        if response.returncode != 0:
            # Do not mix any evidence-only boot reports into the test crash window.
            crashes = output / 'crashes/collection.json'
            require(crashes.is_file() and not crashes.is_symlink() and crashes.stat().st_size <= 65536,
                    'Crash collection must complete before evidence-only simulator boot')
            crash_bytes = crashes.read_bytes()
            require(isinstance(json.loads(crash_bytes).get('reports'), list), 'Invalid prior crash collection')
            result['priorCrashCollectionSHA256'] = hashlib.sha256(crash_bytes).hexdigest()
            result['priorCrashCollectionModifiedAt'] = crashes.stat().st_mtime
            recover_shutdown_device(actual, result, run)
            response = run(command, capture_output=True, text=True, timeout=20)
            result['recoveryLookupExitCode'] = response.returncode
            result['recoveryLookupStderr'] = response.stderr[:8192]
        require(response.returncode == 0, 'simctl could not resolve the actual diagnostic container')
        raw = response.stdout.strip()
        require(raw and '\n' not in raw and len(raw) <= 4096, 'Invalid diagnostic container path')
        container = Path(raw)
        require(container.is_absolute() and container.is_dir() and not container.is_symlink(), 'Invalid container root')
        source = container / 'Documents/audio-native-evidence'
        require(source.resolve().is_relative_to(container.resolve()), 'Evidence escapes diagnostic container')
        result['files'] = copy_evidence(source, output / 'raw')
        result['verified'] = True
    except Exception as error:
        result['error'] = str(error)[:8192]
    result['endedAt'] = timestamp()
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    require(result['verified'], result.get('error', 'Evidence unavailable'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--selected-device', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    collect(json.loads(args.summary.read_text()), args.selected_device, args.output)
