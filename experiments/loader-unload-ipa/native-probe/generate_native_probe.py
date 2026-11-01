#!/usr/bin/env python3
"""Generate additive DEBUG test-target source; never write App/ or mutate runtime."""
import argparse,base64,hashlib,importlib.util,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--probe-root',type=pathlib.Path,required=True);p.add_argument('--runtime-lock',type=pathlib.Path,required=True);p.add_argument('--output-swift',type=pathlib.Path,required=True);p.add_argument('--receipt',type=pathlib.Path,required=True);a=p.parse_args()
    assert a.output_swift.name=='UnloadWKSmokeTests.swift' and a.output_swift.parent.name=='Tests','Only additive test-target output allowed'
    assert not a.output_swift.exists(),'Do not overwrite an existing test file'
    lock=json.loads(a.runtime_lock.read_text());files=lock['runtimeFiles'];assert len(files)==12 and all('/' not in n and len(h)==64 for n,h in files.items())
    probe=a.probe_root.resolve();sys.path.insert(0,str(probe));spec=importlib.util.spec_from_file_location('neutral_native_fixture',probe/'make_probe.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    generated=module.fixtures();names=('attached-fresh.swf','moved-removed-fresh.swf','first.swf','next.swf');fixtures={n:generated[n] for n in names}
    runtime_literal='[\n'+',\n'.join('        '+json.dumps(n)+': '+json.dumps(h) for n,h in sorted(files.items()))+'\n    ]'
    fixture_literal='[\n'+',\n'.join('        '+json.dumps(n)+': ('+json.dumps(base64.b64encode(b).decode())+', '+json.dumps(sha(b))+')' for n,b in fixtures.items())+'\n    ]'
    source=(ROOT/'UnloadWKSmokeTests.swift.in').read_text().replace('__RUNTIME_FILES__',runtime_literal).replace('__FIXTURES__',fixture_literal)
    a.output_swift.parent.mkdir(parents=True,exist_ok=True);a.output_swift.write_text(source)
    receipt={'schema':'neutral-wk-smoke-source-v1','sourcePath':'Tests/UnloadWKSmokeTests.swift','sourceSHA256':sha(source.encode()),'runtimeLockSHA256':sha(a.runtime_lock.read_bytes()),'runtimeFiles':files,'fixtureFiles':{n:sha(b) for n,b in fixtures.items()},'generatorFiles':{n:sha((ROOT/n).read_bytes()) for n in ('generate_native_probe.py','UnloadWKSmokeTests.swift.in')},'fixtureGeneratorFiles':{n:sha((probe/n).read_bytes()) for n in ('abc_fixture.py','make_probe.py')},'methods':[['UnloadWKSmokeTests','testAttachedLoaderUnloadsAndContinuesInWKWebView'],['UnloadWKSmokeTests','testMovedRemovedLoaderUnloadsAndContinuesInWKWebView']],'productSourcesChanged':False,'runtimeExecuted':False,'physicalDeviceCertified':False}
    a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
