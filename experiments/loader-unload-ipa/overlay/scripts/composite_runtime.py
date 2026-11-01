"""Strict exact UNLOAD-candidate consumer. Legacy fetch and bundle gates remain mandatory."""
import hashlib,io,json,stat,zipfile
from pathlib import PurePosixPath
MAX_ARCHIVE=268435456
MAX_EXPANDED=402653184
MAX_FILE=67108864
EXPECTED_LOCK={'acceptedSourceLockSHA256': '7200650c24fe505844ea676c02c44a42dd2ee7bc484344e775e4458d84566494', 'archiveBytes': 15260480, 'archivePath': 'vendor/ruffle-unload-candidate-41318527222.zip', 'buildRunID': 41318527222, 'buildSourceCommit': '3b0ab52a334336e6e6474e840e9c487e3f666f1d', 'candidateDeltaSHA256': 'c086aea1ec0a4430f15a230cb7ab8fd9479d27a226719316d1cd368e20a73c16', 'checksumProvenance': 'Exact GitHub Actions artifact bytes, not publisher signature or independent reproducible build', 'effectiveSourceStageSHA256': '09348b4a2c3df8aed4fe9526ad9149270fb0c71dd9190bd8a940d170ebf477c3', 'experimentalVersionName': 'FlashNest composite experimental 2d7fbb4e26f7', 'identitySHA256': 'bf822afb0afa700b3c9662a10e1cf670bf12fdb825a0a430a8dd5ea189cde5e5', 'license': 'MIT OR Apache-2.0', 'name': 'FlashNest modified Ruffle', 'provenancePath': 'provenance.json', 'provenanceSHA256': '921142a9d848511f152a129a8c34d73577ef00c37c0423915afdc25f353a0011', 'runtimeInventorySHA256': 'db8878b9986c89e121d17e59ecebca6f6058bcecf20b97fa2861489c14c85e8b', 'runtimeKind': 'flashnest-composite-experimental', 'runtimePrefix': 'runtime/', 'schemaVersion': 4, 'sha256': 'dac0c326e29d2cfd354eb418000ac049fa7bdcfaa56b7693132f5799661d52c2', 'sourceLockRole': 'candidate-delta-with-accepted-base', 'sourceLockSHA256': 'c086aea1ec0a4430f15a230cb7ab8fd9479d27a226719316d1cd368e20a73c16', 'sourceSetSHA256': '2d7fbb4e26f75332ca226ea9f153f03eab48fc119fc9ea2b0d89c2eb1155abef', 'status': 'experimental-unload-candidate-native-acceptance-separate', 'upstreamSourceCommit': '89a7049965f3090e706265670df309a5128233ac', 'version': '0.7.1'}
EXPECTED_FILES={'36b3cbd33c368ba3e094.wasm': '65bfde20229c0ea07a944dbb6a61f8de438826ea8fa7c3dc98a7d5ab60cab685', '81a207f7dca57201d407.wasm': 'b65fd06f17f68b1c30417dc19cd406016f445c3ff7ff93c1ce9286527f65be7b', 'LICENSE_APACHE': '62c7a1e35f56406896d7aa7ca52d0cc0d272ac022b5d2796e7d6905db8a3636a', 'LICENSE_MIT': '4de9338a7879c68e911742a7d691f0797ff1ef8d8a6fb978b0c711e258fe959c', 'README.md': 'cdbeefd04e27a2fe80f735210fa4c054e376802eb43a16d9b6eeae78500f2bde', 'core.ruffle.b37b03400c42af4f2df8.js': '1643fa872c336e5a920a5ab5f0e89d8d0f19f6fe3af9dbd6812e94832d7c6c70', 'core.ruffle.b37b03400c42af4f2df8.js.map': '6908db6111d775763a979c772b54a2cb450a0d9ea24d1937f2ef006279928e0a', 'core.ruffle.b66cd8f7f9bc4f6102a5.js': '97583a8ea68de971dde69fd12c8aa86a3ac2c5e4556b29d675dec292cb840d1c', 'core.ruffle.b66cd8f7f9bc4f6102a5.js.map': '5b3fc8490d7714667d08fd2c7c59efb08425cfe7f0be847a4f9bd44a437e58ed', 'package.json': '822dd0fe6f6a84d4ab41351acd2a789aa9ef75b3fe454ab846c0858157c48d89', 'ruffle.js': '659463197f43c2232ee6047d078c2b19e094a3feb63c6e86534b7799dad9e552', 'ruffle.js.map': '5b01b95ac87730e011ef9cbc2793b48f2b5ac03102d6f234de6946e31f7c5144'}
IDENTITY_KEYS=['acceptedSourceLockSHA256', 'buildRunID', 'buildSourceCommit', 'candidateDeltaSHA256', 'effectiveSourceStageSHA256', 'experimentalVersionName', 'provenanceSHA256', 'runtimeInventorySHA256', 'runtimeKind', 'sourceLockRole', 'sourceLockSHA256', 'sourceSetSHA256', 'upstreamSourceCommit']

def require(ok,message):
    if not ok:raise ValueError(message)
def digest(b):return hashlib.sha256(b).hexdigest()
def pairs(rows):
    d={}
    for k,v in rows:require(k not in d,'Duplicate JSON key');d[k]=v
    return d
def parse(b):return json.loads(b,object_pairs_hook=pairs)
def safe(name):
    require(isinstance(name,str) and name and not any(ord(c)<32 for c in name),'Invalid path')
    p=PurePosixPath(name);require(not p.is_absolute() and '\\' not in name and ':' not in name and '..' not in p.parts and p.as_posix()==name,'Unsafe path');return p

def verified_identity(lock,manifest,identity_bytes):
    # This consumer supports only this exact reviewed derivative, never a fallback.
    require(lock==EXPECTED_LOCK,'Not the exact supported unload-candidate lock')
    require(manifest==EXPECTED_FILES,'Candidate runtime manifest differs')
    require(digest(identity_bytes)==lock['identitySHA256'],'Candidate identity bytes differ')
    ident=parse(identity_bytes)
    require(ident['schemaVersion']==3 and ident['sourceLockRole']=='candidate-delta-with-accepted-base','Identity schema/role differs')
    for key in IDENTITY_KEYS:require(ident[key]==lock[key],'Identity correspondence differs: '+key)
    require(ident['artifactArchiveSHA256']==lock['sha256'] and ident['upstreamBaseVersion']==lock['version'],'Artifact/version mismatch')
    rows=ident['runtimeFiles'];require(len(rows)==12 and set(rows)==set(manifest),'Incomplete runtime inventory')
    for n,row in rows.items():require(len(safe(n).parts)==1 and set(row)=={'bytes','sha256'} and row['sha256']==manifest[n] and type(row['bytes']) is int and 0<row['bytes']<=MAX_FILE,'Invalid runtime entry')
    return ident

def verified_runtime(archive,lock,manifest,identity_bytes):
    ident=verified_identity(lock,manifest,identity_bytes)
    require(len(archive)==lock['archiveBytes'] and digest(archive)==lock['sha256'],'Candidate archive identity mismatch')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist();names=set()
        require(len(infos)<5000 and sum(i.file_size for i in infos)<=MAX_EXPANDED,'Archive budget')
        for i in infos:
            safe(i.filename);require(i.filename not in names and not i.is_dir() and not i.flag_bits&1,'Duplicate/directory/encrypted archive member');names.add(i.filename)
            require(0<=i.file_size<=MAX_FILE and stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFREG),'Nonregular/oversized archive member')
        require(z.testzip() is None,'Archive CRC failure')
        files={n:z.read(n) for n in names};actual={n:{'sha256':digest(b),'bytes':len(b)} for n,b in files.items() if n!='artifact-files.json'}
        require(parse(files['artifact-files.json'])==actual,'Complete artifact file manifest differs')
        raw=files['provenance.json'];require(digest(raw)==lock['provenanceSHA256'],'Provenance differs');p=parse(raw)
        for field in ['acceptedSourceLockSHA256','candidateDeltaSHA256','sourceSetSHA256','runtimeInventorySHA256']:require(p[field]==lock[field],'Source provenance mismatch '+field)
        require(p['run']['GITHUB_SHA']==lock['buildSourceCommit'] and p['run']['GITHUB_RUN_ID']==str(lock['buildRunID']),'Build source/run differs')
        require(p['upstreamCommit']==lock['upstreamSourceCommit'] and p['dualWasm'] is True and p['jpegxr'] is True and p['wasmOpt'] is True,'Incomplete source/build recipe')
        require(p['versionSeal']['version_name']==lock['experimentalVersionName'] and p['versionSeal']['version_channel']==lock['runtimeKind'],'Version seal differs')
        cp='source-correspondence/'
        require({n[len(cp):]:actual[n] for n in files if n.startswith(cp)}==p['correspondence'],'Source correspondence differs')
        accepted=files[cp+'source-lock.json'];delta=files[cp+'candidate-delta/source-lock.json'];stage=files[cp+'staging/source-stage.json']
        require(digest(accepted)==lock['acceptedSourceLockSHA256'] and digest(delta)==lock['candidateDeltaSHA256']==lock['sourceLockSHA256'] and digest(stage)==lock['effectiveSourceStageSHA256'],'Accepted/delta/effective source proof mismatch')
        a=parse(accepted);d=parse(delta);s=parse(stage);modified=dict(a['modifiedSourceFiles'])
        require(set(d['modifiedSourceFiles'])=={'core/src/avm2/object/loaderinfo_object.rs'},'Unexpected product delta')
        for n,row in d['modifiedSourceFiles'].items():require(modified[n]==row['before'],'Delta preimage mismatch');modified[n]=row['after']
        require(s['modifiedSourceFiles']==modified and digest(json.dumps(modified,sort_keys=True,separators=(',',':')).encode())==lock['sourceSetSHA256'],'Effective source set mismatch')
        for patch in a['patches']:require(digest(files[cp+patch['path']])==patch['sha256'],'Inherited patch differs')
        require(digest(files[cp+'candidate-delta/'+d['patch']['path']])==d['patch']['sha256'],'Unload patch differs')
        full=files['full-source-before.json'];require(full==files['full-source-after.json']==files[cp+'staging/candidate-source.json'] and digest(full)==p['fullSourceManifestSHA256'],'Source changed during build')
        fs=parse(full);require(len(fs)==p['fullSourceFileCount'] and all(fs[n]==r for n,r in modified.items()),'Full source manifest differs')
        for n,r in modified.items():require(actual[cp+'source/'+n]==r,'Modified source correspondence differs')
        for n,h in a['locks'].items():require(actual[cp+'source/'+n]['sha256']==h,'Dependency lock differs')
        invraw=files['runtime-files.json'];require(digest(invraw)==lock['runtimeInventorySHA256'] and parse(invraw)==ident['runtimeFiles'],'Runtime inventory differs')
        require({n[8:] for n in files if n.startswith('runtime/')}==set(manifest),'Extra/missing runtime assets')
        output={n:files['runtime/'+n] for n in manifest}
        for n,b in output.items():require({'sha256':digest(b),'bytes':len(b)}==ident['runtimeFiles'][n],'Runtime bytes differ')
    require(parse(output['package.json'])['version']=='0.7.1','Package version differs')
    require(sum(n.endswith('.wasm') for n in output)==2,'Dual WASM missing')
    for n,b in output.items():
        if n.endswith('.wasm'):require(b[:4]==b'\0asm','Invalid WASM')
    for text in [lock['experimentalVersionName'],lock['runtimeKind'],lock['upstreamSourceCommit']]:require(text.encode() in output['ruffle.js'],'Sealed JS identity differs')
    return output
