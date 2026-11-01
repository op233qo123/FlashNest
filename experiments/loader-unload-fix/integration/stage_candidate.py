#!/usr/bin/env python3
"""Validate complete same-run engine artifact, stage only its runtime closure."""
import argparse, hashlib, json, os, pathlib, stat, zipfile
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok: raise ValueError(msg)
def stage(archive, output, lock_output, receipt, delta, commit, run):
    archive=pathlib.Path(archive);output=pathlib.Path(output)
    require(not output.exists(),'Output must be fresh')
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        require(len(names)==len(set(names)),'Duplicate archive member')
        require(len(names)<20000 and sum(i.file_size for i in infos)<=268435456,'Archive budget exceeded')
        for i in infos:
            p=pathlib.PurePosixPath(i.filename);mode=i.external_attr>>16
            require(not i.is_dir() and not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename,'Unsafe member path')
            require(i.filename==p.as_posix() and p.parts and not i.flag_bits&1,'Noncanonical or encrypted member')
            require(stat.S_IFMT(mode) in (0,stat.S_IFREG),'Non-regular member')
        require(z.testzip() is None,'Archive CRC failure')
        files={n:z.read(n) for n in names}
    manifest=json.loads(files['artifact-files.json'])
    actual={n:{'sha256':sha(b),'bytes':len(b)} for n,b in files.items() if n!='artifact-files.json'}
    require(actual==manifest,'Complete artifact manifest mismatch')
    lock=json.loads(files['runtime-lock.json']);prov=json.loads(files['provenance.json'])
    require(lock['sourceCommit']==commit and str(lock['runID'])==str(run),'Candidate is not current source/run')
    require(prov['run']['GITHUB_SHA']==commit and str(prov['run']['GITHUB_RUN_ID'])==str(run),'Provenance source/run mismatch')
    require(lock['provenanceSHA256']==sha(files['provenance.json']),'Provenance hash mismatch')
    require(lock['flavorMapSHA256']==sha(files['flavor-map.json']),'Flavor map mismatch')
    require(lock['candidateDeltaSHA256']==sha(pathlib.Path(delta).read_bytes()),'Different reviewed delta')
    require(files['source-correspondence/candidate-delta/source-lock.json']==pathlib.Path(delta).read_bytes(),'Delta correspondence mismatch')
    require(lock['acceptedRecipeCommit']=='6d3e4322293972a28ab2cdf129ee6398f40f0f37','Wrong accepted baseline')
    require(prov['acceptedSourceLockSHA256']=='7200650c24fe505844ea676c02c44a42dd2ee7bc484344e775e4458d84566494','Wrong baseline lock')
    runtime={n[len('runtime/'):]:sha(b) for n,b in files.items() if n.startswith('runtime/')}
    require(runtime==lock['runtimeFiles'] and len(runtime)==12,'Runtime closure mismatch')
    require(all('/' not in n for n in runtime),'Unexpected nested runtime')
    require(runtime[lock['selectedWasm']]==lock['selectedWasmSHA256'],'Selected WASM mismatch')
    require(lock['runtimeAccepted'] is False and lock['ipaBuilt'] is False,'Unexpected acceptance claim')
    core=json.loads(files['core-tests/results.json'])
    require(core['passed'] is True and len(core['tests'])==3,'Missing core regression results')
    require({t['name'] for t in core['tests']}=={'bitmap-cache','loader-events','loader-loadbytes-events'},'Wrong core regression set')
    require(core['candidateSourceManifestSHA256']==sha(files['source-correspondence/staging/candidate-source.json']),'Core/source binding mismatch')
    require(files['full-source-before.json']==files['full-source-after.json']==files['source-correspondence/staging/candidate-source.json'],'Source changed during build')
    require(core['run']=={'GITHUB_SHA':commit,'GITHUB_RUN_ID':str(run)},'Wrong core source/run')
    for t in core['tests']:
        require((t['passed'],t['failed'],t['ignored'])==(1,0,0),'Core regression not executed')
        require(t['logSHA256']==sha(files['core-tests/'+t['name']+'.log']),'Core log hash mismatch')
    output.mkdir(parents=True)
    for n in runtime:(output/n).write_bytes(files['runtime/'+n])
    pathlib.Path(lock_output).write_bytes(files['runtime-lock.json'])
    result={'archiveSHA256':sha(archive.read_bytes()),'archiveBytes':archive.stat().st_size,'sourceCommit':commit,'runID':str(run),'runtimeFiles':runtime,'candidateDeltaSHA256':lock['candidateDeltaSHA256'],'provenanceSHA256':lock['provenanceSHA256'],'artifactFileCount':len(files),'coreTests':core,'applicationPass':False}
    pathlib.Path(receipt).write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('archive','output','lock-output','receipt','delta'):p.add_argument('--'+n,required=True)
    a=p.parse_args();stage(a.archive,a.output,a.lock_output,a.receipt,a.delta,os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID'])
