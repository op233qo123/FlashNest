#!/usr/bin/env python3
"""Fail-closed LOCAL draft contract. No downloads, builds or mutation."""
import argparse,hashlib,json,re
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def safe(value):
 p=PurePosixPath(value)
 if not value or p.is_absolute() or '..' in p.parts or '\\' in value:raise ValueError('Unsafe relative path')
 return value
def check(root,mode='source'):
 lock=json.loads((root/'source-lock.json').read_text())
 base_path=root/'base-source-lock.json'
 if digest(base_path)!='98a0fae33b42a94ea037742e7458ff119facd8f5e4ad4f62ef9c9434cbfef97b':raise ValueError('Accepted engine source lock changed')
 base=json.loads(base_path.read_text());graphic='core/src/display_object/graphic.rs'
 if set(lock['modifiedSourceFiles'])!=set(base['modifiedSourceFiles']) or {k for k in base['modifiedSourceFiles'] if lock['modifiedSourceFiles'][k]!=base['modifiedSourceFiles'][k]}!={graphic}:raise ValueError('Only Graphic product delta allowed')
 if lock['patches'][:-1]!=base['patches'] or lock['patches'][-1]['path']!='patches/lazy-graphic-registration.patch':raise ValueError('Accepted patch chain changed')
 for key in ['locks','toolchain','forbiddenProductionFeatures']:
  if lock[key]!=base[key]:raise ValueError('Accepted dependency/toolchain/feature policy changed')
 if lock.get('nativeAcceptance') is not False or lock.get('finalRuntimeBrowserAcceptance') is not False:raise ValueError('Candidate cannot claim runtime acceptance')

 if lock['upstreamCommit']!='89a7049965f3090e706265670df309a5128233ac':raise ValueError('Unexpected upstream')
 for row in lock['patches']:
  path=root/safe(row['path'])
  if path.is_symlink() or digest(path)!=row['sha256']:raise ValueError('Patch identity mismatch')
 for path,row in lock['modifiedSourceFiles'].items():
  safe(path)
  if not re.fullmatch('[0-9a-f]{64}',row['sha256']) or row['bytes']<=0:raise ValueError('Invalid source identity')
 if lock['requiredFeatures']!=['jpegxr'] or lock['requiredWasmFlavors']!=['extensions','mvp'] or lock['wasmOptRequired'] is not True:raise ValueError('Incomplete release recipe')
 if mode=='engine':
  if lock.get('engineBuildEligible') is not True or lock.get('workflowDispatchAllowed') is not True:raise ValueError('Engine dispatch blocked: final production GC/source eligibility not established')
  review=lock.get('productionGcReview')
  if not isinstance(review,dict):raise ValueError('Missing production GC review')
  report=root/safe(review['path'])
  if digest(report)!=review['sha256']:raise ValueError('GC review identity mismatch')
  data=json.loads(report.read_text())
  if data.get('candidateDiagnosticBuildReviewed') is not True or data.get('productionAccepted') is not False or data.get('strongMigrationRootsPresent') is not False or data.get('testOnlyReleaseHooksEnabled') is not False:raise ValueError('Candidate diagnostic source review absent or false production acceptance')
  expected=hashlib.sha256(json.dumps(lock['modifiedSourceFiles'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
  if data.get('modifiedSourceSetSHA256')!=expected:raise ValueError('GC review belongs to a different source set')
 return lock
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--mode',choices=['source','engine'],default='source');a=p.parse_args()
 try:lock=check(a.root,a.mode)
 except (ValueError,KeyError,FileNotFoundError) as e:raise SystemExit(str(e))
 print('PASS exact source contract',a.mode,'; runtime/native acceptance is separate')
