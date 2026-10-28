"""Final browser matrix contract. Source checks and actual execution are separate."""
import hashlib,json,math,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def digest(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
DELIVERED_IPA_SHA256='b67e084a74537fd95c2e90a560210e73858071da860d7e62f637e55b974e7c42'
DELIVERED_RECEIPT_SHA256='4f6c0ce66c2287ecaf64246e92b9b72b4e5d354fdaafdbe2b4c48243eaf5d3b4'
def delivered_baseline(receipt_path):
 receipt_path=pathlib.Path(receipt_path)
 assert digest(receipt_path)==DELIVERED_RECEIPT_SHA256,'Not the reviewed primary delivered-IPA receipt'
 receipt=json.loads(receipt_path.read_text());identity=receipt['runtime_identity']
 assert receipt['ipa_sha256']==DELIVERED_IPA_SHA256
 assert identity['buildRunID']==40614335019
 assert receipt['files']==identity['runtimeFiles'] and len(receipt['files'])==12
 assert {k:v['sha256'] for k,v in receipt['files'].items() if k.endswith('.wasm')}=={
  '4b85d6e32912d24cca47.wasm':'2074371e1d8402b083207709e9b6f1fc3285a6845eaa850cdc545a390b5744b9',
  '90aa6311b211f13e3cb5.wasm':'24d962eb2d975cada92a6db46b70ea5e331070a4746b5650ab95c4ab5e839ea7'}
 return {'files':receipt['files'],'sourceIdentity':identity['buildSourceCommit'],
  'identitySHA256':DELIVERED_RECEIPT_SHA256,'deliveredIPASHA256':DELIVERED_IPA_SHA256,
  'role':'delivered-1.5.5-build18-audio-recovery-candidate'}
def verify_baseline_entry(entry):
 expected=delivered_baseline(ROOT/'provenance/delivered-155-runtime.json')
 assert entry==expected,'Browser baseline must be exact delivered155, not historical fatal-audio arm'
 return expected
def inventory(root):
 root=pathlib.Path(root).resolve();out={}
 for p in sorted(root.rglob('*')):
  assert not p.is_symlink(),'Runtime symlink forbidden'
  if p.is_file():out[str(p.relative_to(root))]={'sha256':digest(p),'bytes':p.stat().st_size}
 return out
def bind(root,entry):
 actual=inventory(root)
 assert entry['files']==actual,'Entire runtime file set/bytes mismatch'
 assert len([p for p in actual if p.endswith('.wasm')])==2
 assert len([p for p in actual if p.endswith('.js.map')])>=3
 assert all(p in actual for p in ['ruffle.js','LICENSE_MIT','LICENSE_APACHE'])
 assert isinstance(entry['sourceIdentity'],str) and len(entry['sourceIdentity'])>=40
 return actual
def matrix():
 plan=json.loads((ROOT/'matrix-plan.json').read_text())
 rows=[r for r in plan['rows'] if r['loader']=='regular']
 assert len(rows)==290 and len({json.dumps(r,sort_keys=True) for r in rows})==290
 assert {g:sum(r['group']==g for r in rows) for g in {r['group'] for r in rows}}=={'replay':160,'production-controls':50,'alignment-controls':80}
 return [{**r,"loader":"shipping-default"} for r in rows]
def key(r):return tuple(json.dumps(r[k],sort_keys=True) for k in ['group','renderer','quality','dpr','viewport','mode','align'])
def resolved_quality(row,m):
 return row['quality'] if row['quality'] is not None else ('low' if m['mobileQualityBranch'] else 'high')
def expected_scale(row,m):
 renderer=m['actualRenderer'];assert renderer in ['webgl','wgpu-webgl','webgpu','canvas'],renderer
 samples=[v[0] for v in m['storage'] if len(v)==3 and v[1]>0 and v[2]>0]
 msaa=max(samples,default=1)
 if row['renderer']!='auto':assert renderer==row['renderer'],(row,renderer)
 if row['quality'] is None:assert 'quality' not in m['launchConfig'],'Default quality was overwritten'
 else:assert m['launchConfig']['quality']==row['quality']
 if row['renderer']=='auto':assert 'preferredRenderer' not in m['launchConfig']
 assert not m['allocationOverflow'],'Allocator observation overflow'
 # Custom allocator samples—not gl.SAMPLES—prove the direct WebGL2 MSAA path.
 if row['group']=='production-controls' and renderer=='webgl' and resolved_quality(row,m) in ['high','medium']:
  assert m['backend']=='webgl2' and msaa>1,'MSAA control unavailable; cannot count as covered'
 if row['group']=='production-controls' and renderer in ['wgpu-webgl','webgpu'] and resolved_quality(row,m)=='high':
  assert msaa>1,'WGPU High multisample allocation not observed'
 if row['arm']=='baseline':return 1,msaa
 if renderer=='canvas' or (renderer=='webgl' and m['backend']=='webgl2' and msaa>1):return 1,msaa
 return row['scale'],msaa
def verify_measure(row,m,w,h):
 applied,msaa=expected_scale(row,m);dpr=row['dpr']
 physical=[max(1,math.floor(v*dpr*applied+.5)) for v in [w,h]]
 assert m['dpr']==dpr and m['css']==[0,0,w,h] and m['client']==[w,h],m
 assert [m['width'],m['height']]==physical,m
 if m['actualRenderer']=='canvas':assert m['backend']=='2d' and m['gl'] is None,m
 elif m['actualRenderer']=='webgpu':assert m['backend']=='webgpu' and m['texture']==physical and m['gl'] is None,m
 else:assert m['gl']==physical,m
 if row['arm']=='candidate':
  a=m['attributes'];assert float(a['data-flashnest-render-scale'])==applied
  assert float(a['data-flashnest-render-request'])==row['scale']
  assert [int(a['data-flashnest-viewport-width']),int(a['data-flashnest-viewport-height'])]==[w*dpr,h*dpr]
  assert a['data-flashnest-renderer']==m['actualRenderer']
 return {'appliedScale':applied,'customMaxSamples':msaa,'resolvedLaunchQuality':resolved_quality(row,m),'fallback':applied!=row['scale']}
def near(rows,expected):
 assert len(rows)==len(expected)
 for row,ref in zip(rows,expected):
  assert len(row)==len(ref)
  for x,y in zip(row,ref):
   try:assert abs(float(x)-float(y))<=.1,(x,y)
   except ValueError:assert x==y,(x,y)
