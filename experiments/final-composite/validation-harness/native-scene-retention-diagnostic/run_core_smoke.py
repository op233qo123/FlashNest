"""Local-only null-renderer smoke; wrapper preserves selected parent URL. Not Flash/native acceptance."""
import hashlib,json,os,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));import generate_fixtures as g
from compile_abc import ASC,IMPORT
from verify_as import verify_as

def run(binary,asc,imports):
 binary,asc,imports=map(lambda p:pathlib.Path(p).resolve(),(binary,asc,imports))
 assert hashlib.sha256(binary.read_bytes()).hexdigest()=='fc15ee30b578a1c479bcb168d68fd4f61489b62036597b927725e196d5508bfc'
 assert hashlib.sha256(asc.read_bytes()).hexdigest()==ASC and hashlib.sha256(imports.read_bytes()).hexdigest()==IMPORT
 work=ROOT/'core-smoke';wrapper_hashes={}
 for case in ('retain','drop'):
  out=work/'tests/swfs'/('retention_main-'+case+'.swf');out.mkdir(parents=True,exist_ok=True)
  (out/'test.toml').write_text('num_frames = 180\n');(out/'output.txt').write_text('')
  (out/'input.json').write_text(json.dumps([{'type':'Wait'}]*90+[{'type':'KeyDown','key':{'Char':' '}},{'type':'KeyUp','key':{'Char':' '}}]))
  for name in ['prefix-a','prefix-b','old','new','main-'+case]:
   dest=out/(name+'.swf')
   if dest.exists():dest.unlink()
   os.link(ROOT/'generated-local/retention'/(name+'.swf'),dest)
  source='package { import flash.display.Sprite; import flash.display.Loader; import flash.net.URLRequest; import flash.events.Event; public class SmokeRoot extends Sprite { private var child:Loader=new Loader();private var frame:int=0; public function SmokeRoot() { addChild(child);child.load(new URLRequest("main-'+case+'.swf"));addEventListener(Event.ENTER_FRAME,tick); } private function tick(e:Event):void { if(++frame==60) { removeChild(child);addChild(child);removeEventListener(Event.ENTER_FRAME,tick); } } } }'
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);(p/'SmokeRoot.as').write_text(source)
   subprocess.run(['java','-classpath',str(asc),'macromedia.asc.embedding.Main','-AS3','-md','-import',str(imports),'-optimize','SmokeRoot.as'],cwd=p,check=True)
   abc=(p/'SmokeRoot.abc').read_bytes();raw=g.rect()+g.struct.pack('<HH',24*256,1)+g.tag(69,g.struct.pack('<I',8))+g.tag(82,g.struct.pack('<I',1)+b'\0'+abc)+g.tag(76,g.struct.pack('<HH',1,0)+b'SmokeRoot\0')+g.tag(1)+g.tag(0)
   swf=b'FWS\x0f'+g.struct.pack('<I',len(raw)+8)+raw
   (out/'test.swf').unlink(missing_ok=True);(out/'test.swf').write_bytes(swf)
   wrapper_hashes[case]={'sourceSHA256':hashlib.sha256(source.encode()).hexdigest(),'abcSHA256':hashlib.sha256(abc).hexdigest(),'swfSHA256':hashlib.sha256(swf).hexdigest()}
 env=dict(os.environ,RUFFLE_TEST_OPTS='--compile-mode use-precompiled')
 proc=subprocess.run([str(binary),'retention_main','--nocapture'],cwd=work,env=env,capture_output=True,text=True)
 log=proc.stdout+proc.stderr;(ROOT/'core-smoke.log').write_text(log)
 assert proc.returncode==101,'Expected intentional empty-golden mismatch, inspect changed harness behavior'
 cases={}
 for case in ('retain','drop'):
  block=log.split('---- retention_main-'+case+'.swf ----',1)[1].split('\n---- ',1)[0]
  records=[json.loads(line[len('<SCENE_PHASE '):]) for line in block.splitlines() if line.startswith('<SCENE_PHASE ')]
  verify_as(records,case);cases[case]={'phases':records,'singleSyntheticSpacePair':True}
 proof={'originalOutcome':'FAILED: intentionally empty Flash golden','semanticVerificationPassed':True,'nullRendererNotNativePixelProof':True,'physicalReleaseObservable':False,'rootURLWrapperRequired':True,'secondAddedToStageControl':True,'wrapperHashes':wrapper_hashes,'binarySHA256':hashlib.sha256(binary.read_bytes()).hexdigest(),'logSHA256':hashlib.sha256(log.encode()).hexdigest(),'cases':cases}
 (ROOT/'local-core-evidence.json').write_text(json.dumps(proof,indent=2)+'\n');print('Two controlled null-core semantic cases verified; not native or Flash-golden pass.')
if __name__=='__main__':run(*sys.argv[1:])
