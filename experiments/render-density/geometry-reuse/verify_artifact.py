#!/usr/bin/env python3
"""Verify/reuse one immutable experimental CI build; never promote a runtime."""
import argparse, hashlib, json, os, re, shutil, stat, zipfile
from pathlib import Path, PurePosixPath
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def safe_extract(archive, output):
    if output.exists(): raise ValueError('Refuse existing extraction directory')
    with zipfile.ZipFile(archive) as z:
        rows=z.infolist(); names=set()
        if len(rows)>1000 or sum(x.file_size for x in rows)>300*1024*1024: raise ValueError('Archive size bound exceeded')
        for x in rows:
            p=PurePosixPath(x.filename); mode=x.external_attr>>16
            if not x.filename or p.is_absolute() or '..' in p.parts or '\\' in x.filename or x.filename in names or stat.S_ISLNK(mode): raise ValueError('Unsafe archive entry')
            if stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR) or x.file_size>64*1024*1024: raise ValueError('Unsafe entry type/size')
            names.add(x.filename)
        output.mkdir(parents=True)
        try:
            for x in rows:
                target=output.joinpath(*PurePosixPath(x.filename).parts)
                if x.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(x) as source, target.open('xb') as dest: shutil.copyfileobj(source,dest)
        except BaseException:
            shutil.rmtree(output); raise

def validate(archive, output, metadata=None):
    lock=read(HERE/'build-lock.json')
    assert archive.stat().st_size==lock['artifactBytes'] and sha(archive)==lock['artifactSHA256'], 'Wrong immutable artifact ZIP'
    if metadata:
        run=read(metadata/'run.json'); artifact=read(metadata/'artifact.json'); jobs=read(metadata/'jobs.json')['jobs']
        assert run['id']==lock['runID'] and run['head_sha']==lock['buildCommit'] and run['status']=='completed' and run['conclusion']=='failure'
        assert run['repository']['full_name']==lock['repository'] and run['run_attempt']==1
        assert artifact['id']==lock['artifactID'] and artifact['name']==lock['artifactName'] and not artifact['expired']
        assert artifact['size_in_bytes']==lock['artifactBytes'] and artifact['digest']=='sha256:'+lock['artifactSHA256']
        assert artifact['workflow_run']['id']==lock['runID'] and artifact['workflow_run']['head_sha']==lock['buildCommit']
        assert len(jobs)==1 and jobs[0]['id']==lock['jobID'] and jobs[0]['conclusion']=='failure'
        steps={x['name']:x['conclusion'] for x in jobs[0]['steps']}
        for name in lock['successfulBuildSteps']: assert steps.get(name)=='success', name
        for name in ['Browser matrix - WebGL','Browser matrix - WGPU WebGL']: assert steps.get(name)=='failure'
    safe_extract(archive,output)
    candidate=output/'render-density-engine-candidate'; evidence=output/'render-density-engine-evidence'; baseline=output/'render-density-guard-baseline'
    for name,digest in lock['evidenceSHA256'].items(): assert sha(output/name)==digest, name
    build=read(candidate/'provenance.json'); current=read(ROOT/'experiments/render-density/engine-build/build-inputs.json')
    assert build['upstreamCommit']==lock['upstreamCommit'] and build['phase']=='density' and build['status']=='experimental-unpromoted'
    assert build['experiment']['GITHUB_SHA']==lock['buildCommit'] and build['experiment']['GITHUB_RUN_ID']==str(lock['runID'])
    assert build['patches']==current['patches'] and build['patchSetSHA256']==lock['patchSetSHA256']
    for row in build['patches']: assert sha(ROOT/row['path'])==row['sha256']
    actual={str(p.relative_to(candidate)) for p in candidate.rglob('*') if p.is_file()}-{'provenance.json'}
    assert actual==set(build['files']), 'Candidate inventory changed'
    for name,row in build['files'].items():
        assert sha(candidate/name)==row['sha256'] and (candidate/name).stat().st_size==row['bytes'], name
    for folder in (candidate,baseline):
        expected=read(folder/'runtime.browser-manifest.json')
        actual={str(p.relative_to(folder/'runtime')):sha(p) for p in (folder/'runtime').rglob('*') if p.suffix in ('.js','.wasm')}
        assert actual==expected and len([n for n in actual if n.endswith('.wasm')])==2
    identity=read(baseline/'baseline-identity.json')
    assert identity['archiveSHA256']==current['baselineArchiveSHA256'] and identity['provenanceSHA256']==current['baselineProvenanceSHA256']
    suite=read(ROOT/'experiments/frame-order/engine-build/adjacent-tests.json'); selected=suite['tests']+suite['knownFailureTests']
    for phase in ('baseline','patched'):
        summary=read(evidence/phase/'upstream-goldens/summary.json')
        assert summary['allPassed'] is True and summary['suiteComplete'] is True and summary['completedCount']==summary['expectedCount']==31
        assert summary['strictReferenceCount']==29 and summary['knownFailurePreservationCount']==2 and summary['sourceCommit']==lock['upstreamCommit']
        assert [x['name'] for x in summary['tests']]==selected
        for row in summary['tests']:
            assert row['passed'] is True and row['returncode']==0
            log=(evidence/phase/'upstream-goldens'/row['log']).read_text()
            assert re.search(r'test result: ok\. 1 passed; 0 failed; 0 ignored;',log)
        assert re.search(r'test result: ok\. 2 passed; 0 failed; 0 ignored;',(evidence/f'{phase}-original.log').read_text())
        for fixture,golden in [('nested-child-goto','nested-repair-target'),('control-no-child-goto','control')]:
            assert (evidence/phase/'original'/f'{fixture}.trace.txt').read_bytes()==(ROOT/'experiments/frame-order/engine-patch/expectations'/f'{golden}.txt').read_bytes()
    js=read(candidate/'core-js-summary.json')
    assert js['allPassed'] is True and js['stats']['tests']==js['stats']['passes']==63 and js['stats']['pending']==js['stats']['failures']==0
    assert js['expectedOriginalTests']==59 and js['expectedNewConfigTests']==4
    for name,digest in lock['correctedHarnessSHA256'].items(): assert sha(ROOT/name)==digest,name
    result={'verified':True,'runtimeBuildCommit':lock['buildCommit'],'runtimeBuildRun':lock['runID'],'artifactID':lock['artifactID'],'artifactSHA256':lock['artifactSHA256'],'patchSetSHA256':build['patchSetSHA256'],'currentHarnessCommit':os.environ.get('GITHUB_SHA'),'inheritedGates':{'originalPerPhase':2,'adjacentPerPhase':31,'coreJS':63},'previousGeometry':'failed original fixture; zero completed cases; not reused as a passing gate','correctedHarnessSHA256':lock['correctedHarnessSHA256']}
    (output/'reuse-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('output',type=Path);p.add_argument('--metadata',type=Path);a=p.parse_args()
    print(json.dumps(validate(a.archive,a.output,a.metadata),indent=2))
