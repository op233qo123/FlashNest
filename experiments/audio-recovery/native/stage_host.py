#!/usr/bin/env python3
"""Stage only pinned production sources plus reviewed diagnostic host/overlay."""
import argparse, hashlib, json, shutil, subprocess, tarfile, tempfile
from pathlib import Path
from apply_injection import stage, SESSION
from apply_startup import transform
SOURCE = '5862f8dbd414d9835f11872d3ebabd1eed315ffc'
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def prepare(repo, output, arm, runtime, approval):
    repo, output, runtime, approval = map(lambda p: Path(p).resolve(), (repo,output,runtime,approval))
    if arm not in ['baseline','candidate']: raise ValueError('Unknown arm')
    if output.exists() or repo == output or repo in output.parents: raise ValueError('Use new separate output')
    approved=json.loads(approval.read_text())
    if approved['sourceCommit'] != SOURCE: raise ValueError('Wrong production source')
    inventory=approved['runtimes'][arm]['files']
    actual={str(p.relative_to(runtime)):digest(p) for p in runtime.rglob('*') if p.is_file()}
    if any(p.is_symlink() for p in runtime.rglob('*')) or actual != inventory: raise ValueError('Runtime exact inventory mismatch')
    here=Path(__file__).resolve().parent
    diagnostic_names={str(p.relative_to(here)) for p in here.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'approval.json'}
    if diagnostic_names != set(approved['diagnosticFiles']): raise ValueError('Diagnostic file inventory mismatch')
    for name, sha in approved['diagnosticFiles'].items():
        p=here/name
        if p.resolve().is_relative_to(here) is False or digest(p)!=sha: raise ValueError('Diagnostic source drift')
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp); archive=tmp/'source.tar'
        with archive.open('wb') as f:
            subprocess.run(['git','-C',str(repo),'archive',SOURCE,'App','fixtures/lifecycle','Package.resolved'],stdout=f,check=True)
        shipping=tmp/'shipping';shipping.mkdir()
        with tarfile.open(archive) as tar:
            for m in tar.getmembers():
                if not (m.isfile() or m.isdir()) or Path(m.name).is_absolute() or '..' in Path(m.name).parts:
                    raise ValueError('Unsafe pinned source archive member')
            tar.extractall(shipping,filter='data')
        script=here/'audio-recovery-injection.js'
        overlay=tmp/'overlay';stage(shipping,overlay,script,approved['diagnosticFiles']['audio-recovery-injection.js'])
        output.mkdir(parents=True)
        staged=output/'staged';staged.mkdir()
        shutil.copytree(shipping/'App',staged/'App')
        shutil.copyfile(overlay/SESSION,staged/SESSION)
        shutil.copytree(shipping/'fixtures/lifecycle',staged/'lifecycle')
        shutil.copyfile(script,staged/script.name)
        shutil.copyfile(here/'startup-journal.js',staged/'startup-journal.js')
        (staged/'startup-resources.json').write_text(json.dumps(inventory,sort_keys=True))
        shell=staged/'App/Resources/Web/shell.js'
        patched,shell_diff=transform(shell.read_bytes());shell.write_bytes(patched)
        (output/'startup-shell.diff').write_text(shell_diff)
        shutil.rmtree(staged/'App/Resources/Web/runtime')
        shutil.copytree(runtime,staged/'App/Resources/Web/runtime')
        for name in ['Host','UITests']:shutil.copytree(here/name,output/name)
        shutil.copyfile(here/'project.yml',output/'project.yml')
        shutil.copyfile(shipping/'Package.resolved',output/'Package.resolved')
        for name in ['overlay-manifest.json','session-injection.diff']:shutil.copyfile(overlay/name,output/name)
        evidence={'sourceCommit':SOURCE,'arm':arm,'runtime':approved['runtimes'][arm],
                  'files':{str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file()}}
        (output/'source-manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return output
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--output',required=True)
    p.add_argument('--arm',required=True);p.add_argument('--runtime',required=True);p.add_argument('--approval',required=True)
    a=p.parse_args();prepare(a.repo,a.output,a.arm,a.runtime,a.approval)
