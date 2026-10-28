"""Validate installed runtime against the reviewed full overlay, before XCTest."""
import json,sys
from pathlib import Path
from stage import SOURCE,PROMOTION,OVERLAY_SHA256,sha

def attest(root,arm,here=None):
 root=Path(root);here=Path(here or Path(__file__).parent)
 if arm not in ('baseline','candidate'):raise ValueError('Unknown arm')
 if sha(here/'overlay.json')!=OVERLAY_SHA256:raise ValueError('Overlay drift')
 overlay=json.loads((here/'overlay.json').read_text())
 receipt=json.loads((root/'readback-stage-receipt.json').read_text())
 if receipt['sourceCommit']!=SOURCE or receipt['arm']!=arm or receipt['promotionManifestSHA256']!=PROMOTION or receipt['shippingCheckoutUnchanged'] is not True:raise ValueError('Stage identity drift')
 for name in ['runtime.files.json','runtime.lock.json','App/Resources/Web/runtime-identity.json','Tests/FrameOrderRuntimeTests.swift']:
  entry=next(x for x in overlay['files'] if x['path']==name)
  expected=entry['sha256'] if arm=='candidate' else entry['originalSHA256']
  if sha(root/name)!=expected:raise ValueError('Source/runtime metadata drift: '+name)
 runtime=root/'App/Resources/Web/runtime'
 expected=json.loads((root/'runtime.files.json').read_text())
 actual={str(x.relative_to(runtime)):sha(x) for x in runtime.rglob('*') if x.is_file()}
 if any(x.is_symlink() for x in runtime.rglob('*')) or actual!=expected:raise ValueError('Installed runtime differs from locked inventory')
 return {'sourceCommit':SOURCE,'arm':arm,'os':'18.2','runtimeIdentitySHA256':sha(root/'App/Resources/Web/runtime-identity.json'),'runtimeFiles':actual,'stageReceipt':receipt}
if __name__=='__main__':print(json.dumps(attest(*sys.argv[1:]),indent=2))
