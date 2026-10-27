#!/usr/bin/env python3
"""CI-only renderer preference isolation; never changes the installed App default."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
def load_base(root):
    spec = importlib.util.spec_from_file_location('transition_base', Path(root)/'experiments/transition-stress/harness.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

SHELL = 'App/Resources/Web/shell.js'
ARMS = {'default': 'wgpu-webgl', 'webgl': 'webgl'}
FIELDS = {'backend','context','lost','width','height','nativeDPR','lossEvents','bannerCount'}

def instrument(shell, observer, arm):
    if arm not in ARMS: raise ValueError('Unknown renderer arm')
    # Fail closed on drift; never use a locally staged render-density shell.
    if 'preferredRenderer' in shell or 'FlashNestRendering' in shell: raise ValueError('Unexpected existing renderer override')
    for anchor in ["logLevel:'warn'", 'function reportTrace(', 'function watchRenderer() {', 'movieLoaded = true;']:
        if shell.count(anchor) != 1: raise ValueError('Missing/duplicate shell anchor: '+anchor)
    shell = shell.replace("logLevel:'warn'", "logLevel:'info'" + (", preferredRenderer:'webgl'" if arm == 'webgl' else ''))
    # reportTrace has one simple parameter in the reviewed source; inject only
    # at the body entry, leaving all runtime trace semantics unchanged.
    shell, count = re.subn(r'(function reportTrace\([^{}]*\) \{)', r'\1\n    window.FlashNestRendererDiagnostic.sample(player);', shell)
    if count != 1: raise ValueError('Unexpected trace observer function')
    shell = shell.replace('function watchRenderer() {', 'function watchRenderer() {\n    window.FlashNestRendererDiagnostic.sample(player);')
    shell = shell.replace('movieLoaded = true;', 'movieLoaded = true;\n      window.FlashNestRendererDiagnostic.sample(player);')
    return observer + '\n' + shell

def prepare(driver, output, evidence):
    driver,output,evidence=map(lambda x:Path(x).resolve(),(driver,output,evidence))
    base=load_base(driver)
    base.prepare(driver,output,evidence,'18.5')
    observer=(driver/'experiments/transition-renderers/renderer-observer.js').read_text()
    ui=driver/'experiments/transition-renderers/TransitionStressUITests.swift'
    guard_source=base.git(driver,'show',base.GUARD+':'+base.SESSION)
    if base.sha(guard_source)!=base.HASHES['guarded']: raise ValueError('Guarded Session pin mismatch')
    inventories={}
    for old,arm in [('baseline','default'),('guarded','webgl')]:
        tree=output/arm
        subprocess.run(['git','-C',str(driver),'worktree','move',str(output/old),str(tree)],check=True)
        (tree/base.SESSION).write_bytes(guard_source)
        shell=(tree/SHELL).read_text()
        (tree/SHELL).write_text(instrument(shell,observer,arm))
        shutil.copyfile(ui,tree/'UITests/TransitionStressUITests.swift')
        inventories[arm]=base.inventory(tree)
        (evidence/(arm+'-source-sha256.json')).write_text(json.dumps(inventories[arm],indent=2,sort_keys=True)+'\n')
        (evidence/(arm+'-shell.js')).write_bytes((tree/SHELL).read_bytes())
    if inventories['default'].keys()!=inventories['webgl'].keys(): raise ValueError('Different source inventories')
    differences=[p for p in inventories['default'] if inventories['default'][p]!=inventories['webgl'][p]]
    if differences != [SHELL]: raise ValueError('Unexpected renderer comparison source delta: '+repr(differences))
    default=(output/'default'/SHELL).read_text(); webgl=(output/'webgl'/SHELL).read_text()
    if webgl != default.replace("logLevel:'info'", "logLevel:'info', preferredRenderer:'webgl'",1): raise ValueError('Source delta exceeds one renderer preference')
    original=json.loads((evidence/'comparison.json').read_text())
    (evidence/'session-staging-comparison.json').write_text(json.dumps(original,indent=2)+'\n')
    (evidence/'comparison.json').write_text(json.dumps({'driverCommit':original['driverCommit'],'guardedSessionCommit':base.GUARD,
      'guardedSessionSHA256':base.HASHES['guarded'],'expectedSimulatorOS':'18.5','order':['default','webgl'],
      'requestedRenderer':{'default':None,'webgl':'webgl'},'requiredActualRenderer':ARMS,
      'onlyChangedFile':SHELL,'onlyArmDelta':"preferredRenderer:'webgl'",'fixture':original['fixture'],
      'observerSHA256':base.sha(observer.encode()),'uiSHA256':base.sha(ui.read_bytes()),
      'cyclesPerArm':3,'resetSameSimulatorBetweenArms':True,'configuration':'Debug'},indent=2)+'\n')

def verify(summary, log, root, arm):
    if arm not in ARMS: raise ValueError('Unknown renderer arm')
    result=load_base(root).verify(summary,log,root,'18.5')
    normalized=log.replace('FLASHNEST_RENDERER_STATE','\nFLASHNEST_RENDERER_STATE')
    rows=re.findall(r'^FLASHNEST_RENDERER_STATE phase=([a-z-]+) (\{[^\r\n]*\})$',normalized,re.M)
    phases=['startup','initial-input']
    for cycle in range(1,4):
        phases += ['scene-ready','after-landscape','after-background','after-portrait']
        if cycle==2: phases.append('after-paused-background')
    if [phase for phase,_ in rows]!=phases: raise ValueError('Missing/duplicate/out-of-order renderer observations')
    for phase,raw in rows:
        def unique_fields(pairs):
            data=dict(pairs)
            if len(data)!=len(pairs): raise ValueError('Duplicate renderer field')
            return data
        data=json.loads(raw,object_pairs_hook=unique_fields)
        if set(data)!=FIELDS or data['backend']!=ARMS[arm]: raise ValueError('Wrong actual renderer or fields')
        if data['context'] not in ('webgl','webgl2','experimental-webgl') or data['lost'] is not False: raise ValueError('No live actual WebGL context')
        for key in ['width','height']:
            if type(data[key]) is not int or not 0<data[key]<=32768: raise ValueError('Invalid drawing buffer')
        if type(data['nativeDPR']) not in (int,float) or not 0<data['nativeDPR']<=10: raise ValueError('Invalid device DPR')
        if type(data['bannerCount']) is not int or data['bannerCount']!=1: raise ValueError('Unexpected runtime instance count')
        if type(data['lossEvents']) is not int or data['lossEvents']!=0: raise ValueError('Observed context loss')
    return dict(result,actualRenderer=ARMS[arm],rendererObservations=len(rows))

if __name__=='__main__':
    parser=argparse.ArgumentParser(); subs=parser.add_subparsers(dest='action',required=True)
    p=subs.add_parser('prepare'); p.add_argument('driver');p.add_argument('output');p.add_argument('evidence')
    p=subs.add_parser('verify');p.add_argument('summary');p.add_argument('log');p.add_argument('root');p.add_argument('--arm',choices=ARMS,required=True)
    args=parser.parse_args()
    if args.action=='prepare': prepare(args.driver,args.output,args.evidence)
    else: print(json.dumps(verify(json.loads(Path(args.summary).read_text()),Path(args.log).read_text(),args.root,args.arm)))
