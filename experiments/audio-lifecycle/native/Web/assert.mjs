// Browser-only strict assertions for plain JSON evidence. Not a Node polyfill.
function fail(message){throw new Error(message||'Native audio contract assertion failed')}
function assert(value,message){if(!value)fail(message)}
assert.equal=(actual,expected,message)=>{if(!Object.is(actual,expected))fail(message||`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`)};
function same(a,b){if(Object.is(a,b))return true;if(a===null||b===null||typeof a!=='object'||typeof b!=='object')return false;if(Array.isArray(a)!==Array.isArray(b))return false;const ak=Object.keys(a).sort(),bk=Object.keys(b).sort();return ak.length===bk.length&&ak.every((k,i)=>k===bk[i]&&same(a[k],b[k]))}
assert.deepEqual=(actual,expected,message)=>{if(!same(actual,expected))fail(message||'Plain evidence structures differ')};
export default assert;
