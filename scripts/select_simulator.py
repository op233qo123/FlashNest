#!/usr/bin/env python3
"""Select an available iPhone matching the selected Xcode's simulator SDK.
Reads `xcrun simctl list devices available --json` on stdin. Never guesses names.
"""
import json, re, sys

def select(data, sdk):
    version=tuple(map(int,sdk.split('.')))
    candidates=[]
    for runtime, devices in data.get('devices',{}).items():
        match=re.fullmatch(r'com\.apple\.CoreSimulator\.SimRuntime\.iOS-(\d+)-(\d+)(?:-(\d+))?',runtime)
        if not match: continue
        runtime_version=tuple(int(x) for x in match.groups() if x is not None)
        if runtime_version[:2] != version[:2] or runtime_version[0] < 17: continue
        for device in devices:
            if device.get('isAvailable') and device.get('name','').startswith('iPhone'):
                candidates.append((device['name'],device['udid']))
    if not candidates:
        raise ValueError(f'No available iPhone for selected Xcode simulator SDK {sdk}; refusing untested runtime fallback')
    return sorted(candidates)[0][1]

if __name__=='__main__':
    try: print(select(json.load(sys.stdin),sys.argv[1]))
    except (ValueError,KeyError,IndexError) as error: sys.exit(str(error))
