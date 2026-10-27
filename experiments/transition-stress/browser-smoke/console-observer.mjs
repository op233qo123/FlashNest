// Diagnostic-only observer for the pinned tracing-wasm 0.2.1 console signature.
// Never stringify/inspect logged objects, wrap callbacks, or change native calls.
export function installConsoleObserver(target, {reportError=()=>{}, reportWarning=()=>{}, onText=()=>{}}={}) {
  if (!target || ![reportError,reportWarning,onText].every(x=>typeof x==='function')) throw Error('Invalid console observer callbacks');
  const installed=[];
  let forwarding=false,restored=false;
  function undo() {
    for (const {method,descriptor} of [...installed].reverse()) {
      if (descriptor) Object.defineProperty(target,method,descriptor);
      else delete target[method];
    }
  }
  try {
    for (const method of ['log','warn','error']) {
      const descriptor=Object.getOwnPropertyDescriptor(target,method),original=target[method];
      if (typeof original!=='function') throw Error('Required console method unavailable: '+method);
      const wrapper=function(...args) {
        // Original receiver, argument identities, result, and native exceptions win.
        const result=Reflect.apply(original,this,args);
        if (forwarding || typeof args[0]!=='string') return result;
        forwarding=true;
        try {
          let level=method==='warn'?'WARN':method==='error'?'ERROR':null;
          let message=args[0];
          if (method==='log' && args.length===4 && /^%c(?:WARN|ERROR)%c /.test(args[0]) &&
              args[2]==='color: gray; font-style: italic' && args[3]==='color: inherit') {
            const styledLevel=args[0].startsWith('%cWARN%c ')?'WARN':'ERROR';
            if (args[1]===`color: ${styledLevel==='WARN'?'orange':'red'}; background: #444`) {
              level=styledLevel;
              message=args[0].slice(level.length+5).replace('%c',' ');
            }
          }
          // Diagnostic callback failures must not change the runtime call.
          try {
            if (level==='ERROR') reportError(message,method);
            else if (level==='WARN') reportWarning(message,method);
          } catch (_) { /* Observation only. */ }
          // Renderer banner is in the first string. Do not inspect later values.
          try { onText(args[0],method); } catch (_) { /* Observation only. */ }
        } finally { forwarding=false; }
        return result;
      };
      // Actual browser console methods are configurable writable data properties.
      // Preserve existing data-property flags, and restore exact descriptors later.
      const replacement=descriptor&&'value' in descriptor?{...descriptor,value:wrapper}:{value:wrapper,writable:true,enumerable:descriptor?.enumerable??true,configurable:true};
      Object.defineProperty(target,method,replacement);
      installed.push({method,descriptor,wrapper});
    }
  } catch (error) { undo(); throw error; }
  return {
    restore() {
      if (restored) return;
      for (const {method,wrapper} of installed) {
        if (Object.getOwnPropertyDescriptor(target,method)?.value!==wrapper) throw Error('Console observer hook replaced: '+method);
      }
      undo();restored=true;
    },
  };
}
