#!/usr/bin/env python3
"""Only classification may differ from the original browser execution recipe."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parent
lock=json.loads((root/'replay-lock.json').read_text())
assert lock['engineBuildRun']==41318527222 and lock['engineBuildHead']=='3b0ab52a334336e6e6474e840e9c487e3f666f1d'
assert len(lock['fixtureFiles'])==14 and set(lock['stableProbeFiles'])=={'abc_fixture.py','make_probe.py','probe.html','run.py','runtime-lock.json'}
for name,h in lock['stableProbeFiles'].items():
 for path in [root/'probe'/name,a.original/'probe'/name]:
  assert not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==h, name
assert lock['onlyClassificationChanged'] is True and lock['newFixtureCoverageClaim'] is False
print('PASS unchanged neutral fixture generation, browser runner, runtime selection and page')
