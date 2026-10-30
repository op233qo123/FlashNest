"""Derive packaged dual-WASM identity from sourcemaps AND compiled loader edges.
Fail closed if webpack representation changes. Does not imply execution.
"""
import argparse,hashlib,json,pathlib,re
sha=lambda b:hashlib.sha256(b).hexdigest()
def one(xs,label):
 assert len(xs)==1,(label,len(xs));return xs[0]
def derive(root,archive):
 root=pathlib.Path(root);rt=root/'runtime';main=(rt/'ruffle.js').read_text();mainmap=json.loads((rt/'ruffle.js.map').read_text());prov=json.loads((root/'provenance.json').read_text())
 flavors={}
 for path in sorted(rt.glob('core*.js.map')):
  sm=json.loads(path.read_text()); candidates=[(s,c) for s,c in zip(sm['sources'],sm['sourcesContent']) if re.search(r'/ruffle_web(?:-wasm_mvp)?\.js$',s)]
  s,c=one(candidates,'core mapped source');flavor='mvp' if s.endswith('ruffle_web-wasm_mvp.js') else 'extensions'
  assert flavor not in flavors
  chunkpath=path.with_suffix('');chunk=chunkpath.read_text();chunkid=int(one(re.findall(r'\.push\(\[\[(\d+)\]',chunk),'chunkID'))
  match=one(list(re.finditer(r'new URL\(([A-Za-z_$][\w$]*)\((\d+)\),\1\.b\)',chunk)),'compiled init URL');assetid=int(match[2])
  export=one(list(re.finditer(r'\b'+str(assetid)+r'\((\w+),(\w+),(\w+)\)\{\1\.exports=\3\.p\+"([a-zA-Z0-9._-]+\.wasm)"\}',main)),'main asset export');wasm=export[4];data=(rt/wasm).read_bytes()
  sourceurl=one(re.findall(r'new URL\([\'"]([^\'"]+\.wasm)[\'"],\s*import\.meta\.url\)',c),'source init URL')
  assert sourceurl==('ruffle_web-wasm_mvp_bg.wasm' if flavor=='mvp' else 'ruffle_web_bg.wasm')
  flavors[flavor]={'sourceMap':path.name,'sourceMapSHA256':sha(path.read_bytes()),'mappedSource':s,'mappedSourceSHA256':sha(c.encode()),'mappedSourceWasmURL':sourceurl,'coreChunk':chunkpath.name,'coreChunkSHA256':sha(chunkpath.read_bytes()),'chunkID':chunkid,'compiledInitURL':match[0],'compiledInitURLOffset':match.start(),'assetModuleID':assetid,'mainAssetExport':export[0],'mainAssetExportOffset':export.start(),'wasmPath':wasm,'sha256':sha(data),'bytes':len(data)}
 assert set(flavors)=={'mvp','extensions'}
 loader_s,loader=one([(s,c) for s,c in zip(mainmap['sources'],mainmap['sourcesContent']) if s.endswith('/load-ruffle.js')],'loader source')
 for requirement in ['bulkMemory(),','simd(),','saturatedFloatToInt(),','signExtensions(),','referenceTypes(),','import("./ruffle_web.js")','import("./ruffle_web-wasm_mvp.js")']:
  assert requirement in loader,requirement
 predicate=one(list(re.finditer(r'const (\w+)=\(await Promise\.all\(\[[^\]]+\]\)\)\.every\(Boolean\);',main)),'compiled feature predicate');v=predicate[1];a,b=flavors['extensions'],flavors['mvp']
 # Verify the SAME boolean drives both dynamic chunk selection and fetched WASM selection.
 pat=rf'await\({v}\?(\w+)\.e\({a["chunkID"]}\)\.then\(\(\)=>\1\({a["chunkID"]}\)\):\1\.e\({b["chunkID"]}\)\.then\(\(\)=>\1\({b["chunkID"]}\)\)\);let \w+;const (\w+)={v}\?new URL\(\1\({a["assetModuleID"]}\),\1\.b\):new URL\(\1\({b["assetModuleID"]}\),\1\.b\),\w+=await fetch\(\2\)'
 branch=one(list(re.finditer(pat,main)),'shipping branch')
 return {'mapping':{f['sha256']:name for name,f in flavors.items()},'flavors':flavors,'mainBundleSHA256':sha((rt/'ruffle.js').read_bytes()),'mainSourceMapSHA256':sha((rt/'ruffle.js.map').read_bytes()),'loaderMappedSource':loader_s,'loaderMappedSourceSHA256':sha(loader.encode()),'compiledPredicate':predicate[0],'compiledPredicateOffset':predicate.start(),'compiledShippingBranch':branch[0],'compiledShippingBranchOffset':branch.start(),'schemaVersion':1,'archiveSHA256':archive,'runID':int(prov['run']['GITHUB_RUN_ID']),'sourceCommit':prov['run']['GITHUB_SHA'],'runtimeInventorySHA256':sha((root/'runtime-files.json').read_bytes()),'provenanceSHA256':sha((root/'provenance.json').read_bytes()),'basis':'Exact packaged source maps + compiled core URL asset import + main webpack asset export + same-condition shipping branch; not filename order or size','runtimeExecutionClaim':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('archive_sha256');p.add_argument('output');a=p.parse_args();out=derive(a.root,a.archive_sha256);pathlib.Path(a.output).write_text(json.dumps(out,indent=2)+'\n');print('PASS independently derived',out['mapping'])
