#!/usr/bin/env python3
"""Offline integration tests for unchanged fetch and bundle gates with candidate metadata."""
import argparse,importlib.util,json,shutil,sys,tempfile
from pathlib import Path

def run(app):
 app=Path(app).resolve()
 with tempfile.TemporaryDirectory() as td:
  root=Path(td)/'app';web=root/'App/Resources/Web';web.parent.mkdir(parents=True)
  shutil.copytree(app/'App/Resources/Web',web);shutil.copytree(app/'scripts',root/'scripts')
  for n in ['runtime.lock.json','runtime.files.json','THIRD_PARTY_NOTICES.md']:shutil.copyfile(app/n,root/n)
  lock=json.loads((root/'runtime.lock.json').read_text());archive=root/lock['archivePath'];archive.parent.mkdir(parents=True);shutil.copyfile(app/lock['archivePath'],archive)
  sys.path.insert(0,str(root/'scripts'))
  import fetch_runtime as fetch
  import verify_bundled_runtime as bundled
  import composite_runtime as consumer
  manifest=json.loads((root/'runtime.files.json').read_text());identity=(web/'runtime-identity.json').read_bytes();raw=archive.read_bytes()
  out=consumer.verified_runtime(raw,lock,manifest,identity);assert len(out)==12
  bundled.verify_web(web,root);fetch.install_runtime(root);bundled.verify_web(web,root);fetch.install_runtime(root);bundled.verify_web(web,root)
  def reject(fn,label):
   try:fn()
   except (ValueError,FileNotFoundError):return
   raise AssertionError('Accepted invalid '+label)
  reject(lambda:consumer.verified_runtime(raw[:-1]+bytes([raw[-1]^1]),lock,manifest,identity),'archive hash')
  old=dict(lock,sha256='2cb4022b1859156f2e28dcb5d499ebf01cbf13b386acb8467d34c147ed22d28d',buildRunID=40998892881)
  reject(lambda:consumer.verified_runtime(raw,old,manifest,identity),'old-engine lock')
  f=web/'runtime/ruffle.js';original=f.read_bytes();f.write_bytes(original+b' ');reject(lambda:bundled.verify_web(web,root),'runtime hash');f.write_bytes(original)
  f.unlink();reject(lambda:bundled.verify_web(web,root),'missing asset');f.write_bytes(original)
  extra=web/'runtime/stale.js';extra.write_text('stale');reject(lambda:bundled.verify_web(web,root),'extra asset');extra.unlink()
  f.unlink();f.symlink_to(web/'runtime/package.json');reject(lambda:bundled.verify_web(web,root),'runtime symlink');f.unlink();f.write_bytes(original)
  archive.unlink();reject(lambda:fetch.install_runtime(root),'missing offline archive');archive.write_bytes(raw)
  archive.unlink();archive.symlink_to(root/'runtime.lock.json');reject(lambda:fetch.install_runtime(root),'archive symlink');archive.unlink();archive.write_bytes(raw)
  bundled.verify_web(web,root)
  print('PASS exact real archive consumer, unchanged bundle gate, twice offline install and eight negative cases')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--app',type=Path,required=True);run(p.parse_args().app)
