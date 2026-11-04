#!/usr/bin/env python3
"""Explicit recovered source baseline. Never impersonates successful legacy staging."""
import argparse, hashlib, importlib.util, json, os, re, subprocess, sys
from pathlib import Path, PurePosixPath
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PINS={'baseline':'cc6c4bf285a201d9c1a827140662c54606027d10','source':'9bc000e37695696f2427b25fe08efe4993bf22e5','case':'c4cad276f1a79caffd012bcfcb6eb260a9e3492f','delivered':'9a93ade1c7dd79382a06ddcb7925282a2e7c5ea8'}
REMOVED={'vendor/ruffle-audio-recovery-40614335019.zip':'3befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a'}
def need(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def encoded(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def write(path,value):Path(path).write_bytes(encoded(value))
def head(path):return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
def safe_file(root,name):
    p=PurePosixPath(name)
    need(p.as_posix()==name and not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name,'Unsafe source path')
    f=Path(root)
    for part in p.parts:
        f=f/part;need(not f.is_symlink(),'Source symlink forbidden: '+name)
    need(f.is_file(),'Missing regular source: '+str(f));return f

def expected(baseline,delivered):
    """Independently derive all 230 prior hashes, then the one explicit removal."""
    manifest=read(ROOT/'recovery-manifest.json')
    need(manifest['schema']=='flashnest-explicit-recovered-source-v1' and manifest['removedFiles']==REMOVED,'Recovery declaration differs')
    for key,digest in manifest['inputPins'].items():
        role,path=key.split(':',1);root={'baseline':baseline,'delivered':delivered}[role]
        need(sha(safe_file(root,path).read_bytes())==digest,'Frozen manifest differs: '+key)
    d=Path(delivered)/'experiments/loader-unload-ipa'
    baseline_inputs=read(Path(baseline)/'experiments/longrun-ipa-156-build23/inputs.json')
    prior=dict(baseline_inputs['baselineAppFiles'])
    prior.update({p:r['after'] for p,r in baseline_inputs['overlay'].items()})
    for p,row in read(d/'case-inputs-reference.json')['overlay'].items():
        need(prior[p]==row['before'],'Case overlay preimage: '+p);prior[p]=row['after']
    runtime=read(d/'candidate-runtime-reference.json')['runtimeFiles']
    prior={p:h for p,h in prior.items() if not p.startswith('App/Resources/Web/runtime/')}
    prior.update({'App/Resources/Web/runtime/'+p:h for p,h in runtime.items()})
    for p,row in read(d/'resource-overlay.json').items():
        need(prior[p]==row['before'],'Resource overlay preimage: '+p);prior[p]=row['after']
    replacement=read(d/'archive-replacement.json')
    need(prior.pop(replacement['oldPath'])==replacement['before'],'Old current-engine archive mismatch')
    prior[replacement['newPath']]=replacement['after']
    for p,h in read(d/'inputs.json')['additionalFiles'].items():need(p not in prior,'Duplicate native probe');prior[p]=h
    for p,row in read(ROOT/'inputs.json')['overlay'].items():
        need(prior.get(p)==row['before'],'Current overlay preimage: '+p);prior[p]=row['after']
    need(len(prior)==230 and prior==manifest['originalEffectiveSourceFiles'],'Original frozen source closure differs')
    for p,h in REMOVED.items():need(prior.get(p)==h,'Removed historical archive identity differs')
    effective={p:h for p,h in prior.items() if p not in REMOVED}
    need(len(effective)==229 and effective==manifest['effectiveSourceFiles'] and set(manifest['materials'])==set(effective),'Explicit recovered closure differs')
    return manifest,effective,runtime

def material_bytes(row,recipe,runtime,archive):
    kind=row['kind']
    if kind=='engine-runtime':return safe_file(runtime,row['path']).read_bytes()
    if kind=='engine-archive':return Path(archive).read_bytes()
    if kind=='canonical-json':return encoded(row['value'])
    need(row.get('checkout')=='recipe','Unapproved source checkout')
    raw=safe_file(recipe,row['path']).read_bytes()
    need(sha(raw)==row['sourceSHA256'],'Source preimage mismatch: '+row['path'])
    if kind=='repository':return raw
    if kind=='append':return raw+row['suffix'].encode()
    need(kind=='replace','Unknown material transformation')
    for old,new in row['replacements']:
        old=old.encode();need(raw.count(old)==1,'Replacement anchor differs: '+row['path']);raw=raw.replace(old,new.encode())
    return raw

def verify_app(app,effective):
    actual={}
    for f in Path(app).rglob('*'):
        need(not f.is_symlink(),'App symlink forbidden')
        if f.is_file():actual[f.relative_to(app).as_posix()]=sha(f.read_bytes())
    need(actual==effective,'Recovered complete source closure mismatch')

def stage(baseline,source,case,delivered,archive,metadata,output):
    roots={k:Path(v).resolve() for k,v in [('baseline',baseline),('source',source),('case',case),('delivered',delivered)]}
    for role,path in roots.items():need(head(path)==PINS[role],'Wrong fixed checkout: '+role)
    consumer=os.environ['GITHUB_SHA'];run=os.environ['GITHUB_RUN_ID']
    need(re.fullmatch('[0-9a-f]{40}',consumer) and run.isdigit() and head(REPO)==consumer,'Current consumer identity differs')
    manifest,effective,runtime=expected(roots['baseline'],roots['delivered'])
    d=roots['delivered']/'experiments/loader-unload-ipa'
    need((roots['case']/'experiments/case-compatible-assets-build23/inputs.json').read_bytes()==(d/'case-inputs-reference.json').read_bytes(),'Frozen case manifest differs')
    output=Path(output).resolve();need(not output.exists(),'Refuse to overwrite recovery staging');output.mkdir(parents=True)
    helper=roots['case']/'experiments/loader-unload-replay/reuse_engine.py'
    need(sha(helper.read_bytes())==read(d/'inputs.json')['reuseHelperSHA256'],'Original reuse helper differs')
    spec=importlib.util.spec_from_file_location('recovery_original_engine_reuse',helper);reuse=importlib.util.module_from_spec(spec);spec.loader.exec_module(reuse)
    reuse.reuse(Path(archive),Path(metadata),roots['case']/'experiments/loader-unload-fix',output/'candidate-runtime',output/'candidate-runtime-lock.json',output/'engine-reuse.json',consumer,run)
    need((output/'candidate-runtime-lock.json').read_bytes()==(d/'candidate-runtime-reference.json').read_bytes(),'Executed engine lock differs')
    # Re-run the original native fixture generator and retain its exact evidence.
    subprocess.run([sys.executable,str(d/'native-probe/generate_native_probe.py'),'--probe-root',str(roots['case']/'experiments/loader-unload-fix/probe'),'--runtime-lock',str(d/'candidate-runtime-reference.json'),'--output-swift',str(output/'native-probe/Tests/UnloadWKSmokeTests.swift'),'--receipt',str(output/'native-probe-source-manifest.json')],check=True)
    need((output/'native-probe/Tests/UnloadWKSmokeTests.swift').read_bytes()==(d/'native-probe/UnloadWKSmokeTests.swift').read_bytes() and (output/'native-probe-source-manifest.json').read_bytes()==(d/'native-probe/source-manifest.json').read_bytes(),'Original native probe generation differs')
    app=output/'app';app.mkdir()
    for name,digest in effective.items():
        raw=material_bytes(manifest['materials'][name],REPO,output/'candidate-runtime',archive)
        need(sha(raw)==digest,'Recovered material mismatch: '+name)
        p=PurePosixPath(name);need(not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name,'Unsafe output path')
        dest=app/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    verify_app(app,effective)
    write(output/'cadence-inputs.json',{'schema':'candidate-cadence-runtime-v1','runtimeFiles':runtime,'candidateRuntimeLockSHA256':sha((d/'candidate-runtime-reference.json').read_bytes()),'head':consumer,'runID':run})
    receipt={'schema':'flashnest-explicit-recovered-source-v1','kind':'EXPLICIT-RECOVERED-SOURCE-BASELINE','legacyStageExecuted':False,'originalEffectiveSourceFiles':manifest['originalEffectiveSourceFiles'],'effectiveSourceFiles':effective,'removedFiles':REMOVED,'materialSources':manifest['materials'],'recoveryManifestSHA256':sha((ROOT/'recovery-manifest.json').read_bytes()),'recoveryScriptSHA256':sha(Path(__file__).read_bytes()),'sourceCheckouts':PINS,'runtimeFiles':runtime,'engineReuseSHA256':sha((output/'engine-reuse.json').read_bytes()),'cadenceInputsSHA256':sha((output/'cadence-inputs.json').read_bytes()),'runtimeChanged':False,'engineBuildExecutedThisRun':False,'nativeExecutedThisRun':False,'ipaBuilt':False,'formalRelease':False,'fullGatePassed':False,'physicalDeviceCertified':False,'head':consumer,'runID':run}
    write(output/'recovery-staging.json',receipt)
    return receipt

def reconstruct(a):
    return stage(a.baseline_checkout,a.source_checkout,a.case_checkout,Path(os.environ['FLASHNEST_DELIVERED_CHECKOUT']),a.engine_archive,a.engine_metadata,a.output)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['baseline-checkout','source-checkout','case-checkout','engine-archive','engine-metadata','output']:parser.add_argument('--'+name,type=Path,required=True)
    reconstruct(parser.parse_args())
