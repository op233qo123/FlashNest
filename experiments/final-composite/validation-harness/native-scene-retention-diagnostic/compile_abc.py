import argparse,hashlib,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
ASC='4dc2aef13198cfa0692b2f2dda3cce10890277066d7c5aa2ac3e9c9f9a2c462e'
IMPORT='bacacb58df8390161c34e68f9e69406b9f1c9f6103bdacd3162034f42cce1eb3'
def compile(asc,imports,verify=True):
 asc=pathlib.Path(asc).resolve();imports=pathlib.Path(imports).resolve()
 assert hashlib.sha256(asc.read_bytes()).hexdigest()==ASC
 assert hashlib.sha256(imports.read_bytes()).hexdigest()==IMPORT
 with tempfile.TemporaryDirectory() as tmp:
  tmp=pathlib.Path(tmp)
  for name in ('SceneParent','SceneChild','PrefixChild'):
   (tmp/(name+'.as')).write_bytes((ROOT/'as'/(name+'.as')).read_bytes())
   extra=[]
   if name=='SceneChild':
    (tmp/'SceneBitmap.as').write_bytes((ROOT/'as/SceneBitmap.as').read_bytes());extra=['-in','SceneBitmap.as']
   subprocess.run(['java','-classpath',str(asc),'macromedia.asc.embedding.Main','-AS3','-md','-import',str(imports),'-optimize']+extra+[name+'.as'],cwd=tmp,check=True)
   data=(tmp/(name+'.abc')).read_bytes();dest=ROOT/'abc'/(name+'.abc')
   if verify: assert dest.read_bytes()==data, 'ABC regeneration differs'
   else: dest.write_bytes(data)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--asc',required=True);p.add_argument('--imports',required=True);p.add_argument('--write',action='store_true');a=p.parse_args();compile(a.asc,a.imports,not a.write)
