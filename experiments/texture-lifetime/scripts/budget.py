import os,pathlib,sys
root=pathlib.Path(sys.argv[1]);size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
allowed=size<=67108864
if os.environ.get('GITHUB_OUTPUT'):
 with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('allowed='+str(allowed).lower()+'\n')
print({'bytes':size,'allowed':allowed});assert allowed
