#!/usr/bin/env python3
"""Recheck complete raw results; no authored checks count as runtime evidence."""
import argparse,json,pathlib,hashlib,io
from contracts import app_policy,ROOT,matrix,key,verify_measure,near,digest,verify_baseline_entry
from pixel_checks import compare

def verify(path,contract_path):
 from PIL import Image
 result=json.loads(path.read_text());contract=json.loads(contract_path.read_text());verify_baseline_entry(contract['baseline'])
 assert contract['appRendererPolicy']==app_policy()
 assert result['passed'] is True and result['runtimeBindingSHA256']==digest(contract_path)
 preflight=json.loads((path.parent/'browser-preflight.json').read_text())
 assert preflight['passed'] is True and result['preflightSHA256']==digest(path.parent/'browser-preflight.json')
 assert result['browserVersion']==preflight['browserVersion'] and preflight['playwright']=='1.64.1' and preflight['chromiumSandbox'] is True
 assert result['selection']=='unmodified-shipping-default'
 assert result['mvpExecution']=='not-established'
 expected=matrix();assert len(result['rows'])==290
 refs={};shots={};counts={'rows':290,'phases':0,'screenshots':0,'trustedClicks':0,'domEvents':0,'fallbackPhases':0,'reducedPhases':0}
 for row,want in zip(result['rows'],expected):
  assert all(row[k]==v for k,v in want.items()),'Missing/reordered matrix row'
  wasm=row['fetchedWasm'];assert len(wasm)==1
  file=wasm[0];assert contract[row['arm']]['files'][file['path']]=={k:file[k] for k in ['sha256','bytes']}
  w,h=row['viewport'];assert len(row['phases'])==3
  restored=[]
  for phase,(name,pw,ph) in zip(row['phases'],[('initial',w,h),('resized',h,w),('restored',w,h)]):
   assert phase['phase']==name
   status=verify_measure(row,phase['canvas'],pw,ph);assert phase['status']==status
   file=(path.parent/phase['screenshot']).resolve();assert file.is_relative_to(path.parent.resolve())
   assert digest(file)==phase['screenshotSHA256']
   img=Image.open(file).convert('RGB');assert img.size==(pw*row['dpr'],ph*row['dpr'])
   k=(key(row),name)
   if row['arm']=='baseline':shots[k]=img.copy()
   elif status['appliedScale']==1:assert img.tobytes()==shots[k].tobytes()
   assert json.loads(json.dumps(compare(img,shots[k],pw)))==phase['pixelComparison']
   if name in ['initial','restored']:restored.append(img.tobytes())
   points=[(round(pw*x),round(ph*y)) for x,y in [(.05,.05),(.95,.05),(.05,.95),(.95,.95),(.5,.5)]]
   events=phase['pointerEvents'];assert len(events)==10
   for i,e in enumerate(events):
    assert e['trusted'] is True and e['type']==['pointerdown','pointerup'][i%2]
    assert [e['x'],e['y']]==list(points[i//2]) and e['button']==0
    assert any(t['tag']=='CANVAS' for t in e['path'])
   counts['phases']+=1;counts['screenshots']+=1;counts['trustedClicks']+=5;counts['domEvents']+=10
   counts['fallbackPhases']+=int(status['fallback']);counts['reducedPhases']+=int(status['appliedScale']<1)
  assert restored[0]==restored[1]
  assert len(row['down'])==len(row['up'])==15
  if row['arm']=='baseline':refs[key(row)]=(row['down'],row['up'])
  else:near(row['down'],refs[key(row)][0]);near(row['up'],refs[key(row)][1])
 assert counts['phases']==870 and counts['trustedClicks']==4350 and counts['domEvents']==8700
 assert counts['reducedPhases']>0,'Only fallback tested'
 assert {arm:result['runtimeInventories'][arm] for arm in ['baseline','candidate']}=={arm:contract[arm]['files'] for arm in ['baseline','candidate']}
 counts['actualFetchedWasm']={arm:sorted({r['fetchedWasm'][0]['path'] for r in result['rows'] if r['arm']==arm}) for arm in ['baseline','candidate']}
 return counts
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('result',type=pathlib.Path);p.add_argument('contract',type=pathlib.Path);a=p.parse_args();print(json.dumps(verify(a.result,a.contract),indent=2))
