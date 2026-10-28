"""Read-only bounded exact installed-app postcondition for the selected simulator."""
import hashlib,os,plistlib,stat,uuid
from pathlib import Path
MAX_FILES=5000
MAX_BYTES=256*1024*1024

def inventory(root,bundle_id):
 root=Path(root)
 if not root.is_absolute() or root.is_symlink() or not root.is_dir():raise ValueError('Unsafe app root')
 files={};folded=set();total=0
 for directory,dirs,names in os.walk(root,followlinks=False):
  for name in dirs+names:
   path=Path(directory)/name
   key=path.relative_to(root).as_posix().casefold()
   if key in folded:raise ValueError('Case-colliding bundle paths')
   folded.add(key)
   kind=path.lstat().st_mode
   if stat.S_ISLNK(kind) or not (stat.S_ISDIR(kind) or stat.S_ISREG(kind)):raise ValueError('Nonregular bundle member')
  for name in sorted(names):
   path=Path(directory)/name;relative=path.relative_to(root).as_posix()
   if len(files)>=MAX_FILES:raise ValueError('Bundle file count cap')
   before=path.stat();total+=before.st_size
   if total>MAX_BYTES:raise ValueError('Bundle total byte cap')
   digest=hashlib.sha256();length=0
   fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
   with os.fdopen(fd,'rb') as stream:
    opened=os.fstat(stream.fileno())
    if (opened.st_dev,opened.st_ino,opened.st_size)!=(before.st_dev,before.st_ino,before.st_size):raise ValueError('Bundle file changed before read')
    while chunk:=stream.read(1024*1024):
     length+=len(chunk)
     if length>before.st_size:raise ValueError('Bundle file grew during read')
     digest.update(chunk)
   after=path.stat()
   if length!=before.st_size or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Bundle file changed during read')
   files[relative]={'bytes':length,'sha256':digest.hexdigest()}
 if 'Info.plist'not in files or files['Info.plist']['bytes']>65536:raise ValueError('Missing or oversized app Info.plist')
 info=plistlib.loads((root/'Info.plist').read_bytes());executable=info.get('CFBundleExecutable')
 if info.get('CFBundleIdentifier')!=bundle_id or not isinstance(executable,str) or '/'in executable or executable not in files:raise ValueError('Bundle identity/executable mismatch')
 return {'bundleIdentifier':bundle_id,'executable':executable,'totalBytes':total,'files':files}

def installed_path(raw,data_path,udid,app_name):
 path=Path(raw);data=Path(data_path)
 if not path.is_absolute() or not data.is_absolute() or data.name!='data' or data.parent.name!=udid or data.parent.parent.name!='Devices':raise ValueError('Wrong simulator data path')
 try:parts=path.relative_to(data).parts
 except ValueError:raise ValueError('Installed app outside selected simulator')
 if len(parts)!=5 or parts[:3]!=('Containers','Bundle','Application') or parts[-1]!=app_name:raise ValueError('Unexpected app container layout')
 try:uuid.UUID(parts[3])
 except ValueError:raise ValueError('Invalid bundle container identity')
 for parent in [data.parent.parent,data.parent,data,*[data.joinpath(*parts[:n]) for n in range(1,6)]]:
  if parent.is_symlink():raise ValueError('Symlink installed-app path')
 return path

def verify(built,installed,bundle_id,passive):
 expected=inventory(built,bundle_id);actual=inventory(installed,bundle_id)
 matches=expected==actual
 if passive and any(Path(name).name=='audio-recovery-injection.js' for name in actual['files']):raise ValueError('Passive installed app contains injector')
 return {'verified':matches,'builtIdentity':expected,'installedIdentity':actual,'claim':'installed bundle identity/code/all resource bytes match built app; not engine execution'}
