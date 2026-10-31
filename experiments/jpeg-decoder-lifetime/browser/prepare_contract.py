"""Pin already built runtime bytes. CI must separately prove source-to-output binding."""
import argparse,json,pathlib,hashlib
from run import inventory
p=argparse.ArgumentParser();p.add_argument('--baseline',type=pathlib.Path,required=True);p.add_argument('--candidate',type=pathlib.Path,required=True);p.add_argument('--baseline-wasm',required=True);p.add_argument('--candidate-wasm',required=True);p.add_argument('--source-set-sha256',required=True);p.add_argument('--patch',type=pathlib.Path,required=True);p.add_argument('--fixtures',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
def wasm(root,name):
 path=(root/name).resolve();assert path.is_relative_to(root.resolve()) and path.suffix=='.wasm';return hashlib.sha256(path.read_bytes()).hexdigest()
c={'schema':'image-memory-webgl-contract-v1','source':{'baselineSourceSetSHA256':a.source_set_sha256,'candidatePatchSHA256':hashlib.sha256(a.patch.read_bytes()).hexdigest(),'candidateReconstructed':True},'runtimes':{},'fixtures':inventory(a.fixtures)}
for arm in ['baseline','candidate']:
 root=getattr(a,arm);c['runtimes'][arm]={'files':inventory(root),'selectedWasmSHA256':wasm(root,getattr(a,arm+'_wasm'))}
a.output.write_text(json.dumps(c,indent=2)+'\n')
