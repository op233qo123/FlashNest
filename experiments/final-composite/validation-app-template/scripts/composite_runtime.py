"""Strict schema-4 composite consumer; legacy schema-3 remains separately supported."""
import hashlib, io, json, re, stat, zipfile
from pathlib import PurePosixPath
MAX_ARCHIVE = 268435456
MAX_EXPANDED = 402653184
MAX_FILE = 67108864
KIND = 'flashnest-composite-experimental'
PREFIX = 'final-composite-engine/'

def require(condition, message):
    if not condition: raise ValueError(message)
def digest(data): return hashlib.sha256(data).hexdigest()
def pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result
def parse(data): return json.loads(data, object_pairs_hook=pairs)
def valid_hash(value): return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None
def safe(name):
    require(isinstance(name, str) and name and not any(ord(c)<32 for c in name), 'Invalid path')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '\\' not in name and ':' not in name and '..' not in p.parts and p.as_posix()==name, 'Unsafe path: '+name)
    return p

def inventory(rows, allow_empty=False):
    require(isinstance(rows, dict) and rows, 'Missing inventory')
    for name, row in rows.items():
        safe(name)
        require(isinstance(row, dict) and set(row)=={'sha256','bytes'} and valid_hash(row['sha256']) and type(row['bytes']) is int and (0 if allow_empty else 1)<=row['bytes']<=MAX_FILE, 'Invalid inventory entry: '+name)

def verified_identity(lock, manifest, raw):
    require(lock.get('schemaVersion')==4 and type(lock['schemaVersion']) is int, 'Not composite schema4')
    require(lock.get('runtimeKind')==KIND and lock.get('runtimePrefix')==PREFIX+'runtime/' and lock.get('provenancePath')==PREFIX+'provenance.json', 'Composite kind/prefix mismatch')
    require(type(lock.get('archiveBytes')) is int and 0<lock['archiveBytes']<=MAX_ARCHIVE, 'Invalid archive size')
    for key in ('sha256','identitySHA256','provenanceSHA256','sourceLockSHA256','sourceSetSHA256','runtimeInventorySHA256'):
        require(valid_hash(lock.get(key)), 'Invalid identity digest: '+key)
    for key in ('upstreamSourceCommit','buildSourceCommit'):
        require(isinstance(lock.get(key),str) and re.fullmatch('[0-9a-f]{40}',lock[key]), 'Invalid commit')
    require(lock['upstreamSourceCommit']=='89a7049965f3090e706265670df309a5128233ac', 'Unexpected upstream')
    require(type(lock.get('buildRunID')) is int and lock['buildRunID']>0, 'Invalid build run')
    require(lock.get('version')=='0.7.1' and lock.get('experimentalVersionName')=='FlashNest composite experimental '+lock['sourceSetSHA256'][:12], 'Invalid composite version seal')
    require(digest(raw)==lock['identitySHA256'], 'Identity digest mismatch')
    ident=parse(raw)
    require(type(ident.get('schemaVersion')) is int and ident['schemaVersion']==3, 'Invalid identity schema')
    for key in ('runtimeKind','experimentalVersionName','upstreamSourceCommit','buildSourceCommit','buildRunID','provenanceSHA256','sourceLockSHA256','sourceSetSHA256','runtimeInventorySHA256'):
        require(ident.get(key)==lock[key], 'Identity differs: '+key)
    require(ident.get('artifactArchiveSHA256')==lock['sha256'] and ident.get('upstreamBaseVersion')==lock['version'], 'Artifact/version differs')
    rows=ident.get('runtimeFiles'); inventory(rows)
    require(isinstance(manifest,dict) and set(manifest)==set(rows), 'Runtime manifest file set differs')
    for name,row in rows.items():
        require(len(safe(name).parts)==1 and manifest[name]==row['sha256'], 'Runtime flat manifest differs')
    require(sum(n.endswith('.wasm') for n in rows)==2 and sum(n.endswith('.js.map') for n in rows)>=3 and {'ruffle.js','package.json','LICENSE_MIT','LICENSE_APACHE'}<=set(rows), 'Incomplete dual runtime/maps/licenses')
    return ident

def verified_runtime(archive, lock, manifest, identity_bytes):
    ident=verified_identity(lock,manifest,identity_bytes)
    require(len(archive)==lock['archiveBytes'] and digest(archive)==lock['sha256'], 'Archive identity mismatch')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist(); names=set()
        require(len(infos)<=5000 and sum(i.file_size for i in infos)<=MAX_EXPANDED, 'Oversized archive')
        for i in infos:
            safe(i.filename); require(i.filename not in names,'Duplicate archive member'); names.add(i.filename)
            require(0<=i.file_size<=MAX_FILE and stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFREG), 'Nonregular/oversized member')
        raw=z.read(lock['provenancePath']); require(digest(raw)==lock['provenanceSHA256'],'Provenance digest mismatch'); receipt=parse(raw)
        require(receipt.get('schemaVersion')==1 and receipt.get('status')=='ENGINE_ONLY_NATIVE_AND_VISUAL_GATES_PENDING','Unexpected engine receipt status')
        for field,key in [('sourceLockSHA256','sourceLockSHA256'),('sourceSetSHA256','sourceSetSHA256'),('runtimeInventorySHA256','runtimeInventorySHA256'),('upstreamCommit','upstreamSourceCommit')]:
            require(receipt.get(field)==lock[key],'Receipt identity differs: '+field)
        require(receipt.get('dualWasm') is True and receipt.get('jpegxr') is True and receipt.get('wasmOpt') is True,'Incomplete build recipe')
        require(receipt.get('run',{}).get('GITHUB_SHA')==lock['buildSourceCommit'] and receipt['run'].get('GITHUB_RUN_ID')==str(lock['buildRunID']),'Wrong actual build commit/run')
        seal=receipt.get('versionSeal',{})
        require(seal.get('version_name')==lock['experimentalVersionName'] and seal.get('version_channel')==KIND and seal.get('commitHash')==lock['upstreamSourceCommit'],'Wrong actual seal')
        invraw=z.read(PREFIX+'runtime-files.json'); require(digest(invraw)==lock['runtimeInventorySHA256'] and parse(invraw)==ident['runtimeFiles'],'Full runtime inventory differs')
        correspondence=receipt.get('correspondence'); inventory(correspondence)
        cprefix=PREFIX+'source-correspondence/'
        require({n[len(cprefix):] for n in names if n.startswith(cprefix)}==set(correspondence),'Correspondence extra/missing files')
        for name,row in correspondence.items():
            data=z.read(cprefix+name); require(len(data)==row['bytes'] and digest(data)==row['sha256'],'Correspondence bytes differ: '+name)
        slraw=z.read(cprefix+'source-lock.json'); require(digest(slraw)==lock['sourceLockSHA256'],'Source contract differs'); source=parse(slraw)
        require(source.get('engineBuildEligible') is True and source.get('workflowDispatchAllowed') is True,'Ineligible source build')
        modified=source.get('modifiedSourceFiles'); inventory(modified)
        require(digest(json.dumps(modified,sort_keys=True,separators=(',',':')).encode())==lock['sourceSetSHA256'],'Modified source set differs')
        review=source.get('productionGcReview',{});safe(review.get('path'));require(correspondence.get(review['path'],{}).get('sha256')==review.get('sha256'),'Missing reviewed GC policy')
        policy=parse(z.read(cprefix+review['path']))
        require(policy.get('productionAccepted') is True and policy.get('strongMigrationRootsPresent') is False and policy.get('testOnlyReleaseHooksEnabled') is False and policy.get('modifiedSourceSetSHA256')==lock['sourceSetSHA256'],'Ineligible shipping GC policy')
        fullraw=z.read(PREFIX+'full-source-before.json');require(digest(fullraw)==receipt.get('fullSourceManifestSHA256'),'Full source manifest mismatch')
        require(z.read(PREFIX+'full-source-after.json')==fullraw,'Source changed during build')
        full=parse(fullraw);inventory(full,allow_empty=True);require(len(full)==receipt.get('fullSourceFileCount') and all(full.get(k)==v for k,v in modified.items()),'Full source set lacks modified files')
        for path,row in modified.items(): require(correspondence.get('source/'+path)==row,'Modified source missing: '+path)
        patches=source.get('patches'); require(isinstance(patches,list) and len(patches)>=4,'Missing original and composite patches')
        originals=['de0acabdf957fccbc11966b67defd0a7f577cdc5a147db949e0a4f0e56c6331f','89dfadc1b9d113adb01f08582237559c71a5c0e04fe712cb0e31d80f077b07b9','631027394ab35c7ff5b8bd1da1402a649c38e913dd2b788d1a9ef514fc6aee60']
        require([p.get('sha256') for p in patches[:3]]==originals,'Original ordered patches changed')
        for patch in patches: require(correspondence.get(patch['path'],{}).get('sha256')==patch['sha256'],'Patch correspondence differs')
        for path,h in source.get('locks',{}).items(): require(correspondence.get('source/'+path,{}).get('sha256')==h,'Lock correspondence differs')
        expected=ident['runtimeFiles']; prefix=lock['runtimePrefix']
        require({n[len(prefix):] for n in names if n.startswith(prefix)}==set(expected),'Runtime archive extra/missing files')
        output={}
        for name,row in expected.items():
            data=z.read(prefix+name);require(len(data)==row['bytes'] and digest(data)==row['sha256'],'Runtime byte mismatch');output[name]=data
    require(parse(output['package.json']).get('version')==lock['version'],'Package base version differs')
    for name,data in output.items():
        if name.endswith('.wasm'):require(data[:4]==b'\0asm','Invalid WASM magic')
    for text in (lock['experimentalVersionName'],KIND,lock['upstreamSourceCommit']):require(text.encode() in output['ruffle.js'],'JS missing sealed identity')
    return output
