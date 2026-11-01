#!/usr/bin/env python3
"""Bounded experimental source overlay; never packages an IPA or changes the engine."""
import argparse, hashlib, json, os, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
BASE = 'cc6c4bf285a201d9c1a827140662c54606027d10'
SOURCE = '9bc000e37695696f2427b25fe08efe4993bf22e5'
RECIPE = 'experiments/longrun-ipa-156-build23'
def need(value, message):
    if not value: raise ValueError(message)
def sha(data): return hashlib.sha256(data).hexdigest()
def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        need(not path.is_symlink(), 'Unexpected source symlink')
        if path.is_file(): result[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    return result
def read(path): return json.loads(path.read_text())
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
def config():
    c = read(ROOT/'inputs.json')
    need(c['baselineCommit']==BASE and c['sourceCommit']==SOURCE, 'Wrong source identity')
    need(c['ipaBuildAllowed'] is False and c['runtimeChanged'] is False, 'Wrong experiment scope')
    need(set(c['overlay'])=={'App/Server/HTTPProtocol.swift','App/Server/LoopbackServer.swift'}, 'Unexpected product changes')
    need(inventory(ROOT/'overlay')=={p:r['after'] for p,r in c['overlay'].items()}, 'Overlay bytes differ')
    actual = inventory(ROOT)
    need({p:h for p,h in actual.items() if p!='inputs.json'} == c['recipeFiles'], 'Recipe closure differs')
    return c
def verify(app, expected):
    # Generated Xcode/SwiftPM/build output is outside App. All original source bytes remain bound.
    for name, digest in expected.items():
        p=app/name
        need(p.is_file() and not p.is_symlink() and sha(p.read_bytes())==digest, 'Source changed: '+name)
    actual=inventory(app/'App'); expected_app={p[4:]:h for p,h in expected.items() if p.startswith('App/')}
    if 'Info.plist' in actual and 'Info.plist' not in expected_app:
        raw=(app/'App/Info.plist').read_bytes()
        anchor=b'<key>CFBundleVersion</key>\n\t<string>23</string>'
        need(raw.count(anchor)==1 and sha(raw.replace(anchor,b'<key>CFBundleVersion</key>\n\t<string>19</string>'))=='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f', 'Generated Info.plist differs')
        del actual['Info.plist']
    need(actual==expected_app, 'App closure changed')
def stage(baseline, source, output):
    c=config(); baseline=baseline.resolve(); source=source.resolve(); output=output.resolve()
    for root, commit in [(baseline,BASE),(source,SOURCE)]:
        need(subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==commit, 'Checkout identity mismatch')
    x=read(baseline/RECIPE/'inputs.json')
    need(sha((baseline/RECIPE/'inputs.json').read_bytes())==c['baselineInputsSHA256'], 'Baseline manifest differs')
    subprocess.run(['python3',str(baseline/RECIPE/'package.py'),'stage','--source-checkout',str(source),'--recipe-checkout',str(baseline),'--output',str(output)],check=True)
    app=output/'app'; prior=read(output/'staging.json')
    expected=dict(x['baselineAppFiles']); expected.update({p:r['after'] for p,r in x['overlay'].items()})
    need(prior['diagnosticSourceFiles']==expected and inventory(app)==expected, 'Not exact diagnostic v2 source')
    original=dict(expected)
    for name,row in c['overlay'].items():
        need(expected[name]==row['before'], 'Unexpected prior source: '+name)
        (app/name).write_bytes((ROOT/'overlay'/name).read_bytes()); expected[name]=row['after']
    need(inventory(app)==expected, 'Extra/missing candidate source')
    need(inventory(app/'App/Resources/Web/runtime')==x['runtimeFiles'] and len(x['runtimeFiles'])==12,'Runtime changed')
    write(output/'case-staging.json',{'baselineCommit':BASE,'sourceCommit':SOURCE,'baselineSourceFiles':original,'effectiveSourceFiles':expected,'runtimeFiles':x['runtimeFiles'],'overlay':c['overlay'],'recipeFiles':c['recipeFiles'],'diagnosticOptInDefault':False,'runtimeChanged':False,'ipaBuilt':False,'fullGatePassed':False,'physicalDeviceCertified':False,'speedRootCauseEstablished':False,'head':os.environ.get('GITHUB_SHA'),'runID':os.environ.get('GITHUB_RUN_ID')})
    print('Exact build23 diagnostic v2 staged; two server-source changes only; no IPA')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','stage','verify']);p.add_argument('--baseline-checkout',type=Path);p.add_argument('--source-checkout',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.action=='preflight':config()
    elif a.action=='stage':stage(a.baseline_checkout,a.source_checkout,a.output)
    else: verify(a.output/'app',read(a.output/'case-staging.json')['effectiveSourceFiles'])
