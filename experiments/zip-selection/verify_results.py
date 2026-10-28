#!/usr/bin/env python3
"""No green-by-omission: exact XCTest counts, no skips, exact simulator OS."""
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
for name,expected,title in [('NativeTests',31,'Test - FlashNest'),('PickerTests',1,'Test - FlashNestUI')]:
 p=root/(name+'-summary.json')
 assert p.is_file(), 'Missing retained XCTest summary: '+name
 s=json.loads(p.read_text())
 assert s['result']=='Passed' and s['title']==title, (name,s.get('result'),s.get('title'))
 for key,value in [('totalTestCount',expected),('passedTests',expected),('failedTests',0),('skippedTests',0),('expectedFailures',0)]:
  assert type(s[key]) is int and s[key]==value,(name,key,s.get(key),value)
 assert s['testFailures']==[],name+' has test failures'
 configurations=s['devicesAndConfigurations']
 assert len(configurations)==1,name+' unexpected configurations'
 c=configurations[0];device=c['device']
 assert device['osVersion']=='18.2' and device['platform']=='iOS Simulator',device
 for key,value in [('passedTests',expected),('failedTests',0),('skippedTests',0),('expectedFailures',0)]:assert c[key]==value,(name,key)
 print(name+': exact '+str(expected)+' passed; zero skipped/failed/expected failures; iOS18.2 simulator')
copy=json.loads((root/'copy-verification.json').read_text())
assert all(copy[x] is True for x in ['originalsByteIdentical','privateCopiesByteIdentical','differentAppSandboxes'])
assert copy['committedPackages']==4 and copy['shapes']==['folder','swf','zip','zip']
print('PASS native32 total plus original/private-copy invariants; local Files provider scope only')
