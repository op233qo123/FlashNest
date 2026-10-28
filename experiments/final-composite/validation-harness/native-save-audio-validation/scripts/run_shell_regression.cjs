// Execute the existing exact production shell regression against staged shell,
// adding only the UUID and Play DOM interfaces needed by the passive bridge.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const root=path.resolve(__dirname,'../..');
const filename=path.join(root,'next-ipa-156-prep/app-integration/source/scripts/test_shell.js');
let source=fs.readFileSync(filename,'utf8');
const staged=path.join(__dirname,'../overlay/App/Resources/Web/shell.js');
source=source.replace("const source = fs.readFileSync(path.join(__dirname, '../App/Resources/Web/shell.js'), 'utf8');",`const source = fs.readFileSync(${JSON.stringify(staged)}, 'utf8');`);
source=source.replace('    URL, URLSearchParams, Object, Set, Error, String, TextEncoder, atob, btoa,','    crypto: {randomUUID:()=>"test-page"}, URL, URLSearchParams, Object, Set, Error, String, TextEncoder, atob, btoa,');
const m=new Module(filename,module);m.filename=filename;m.paths=module.paths;m._compile(source,filename);
