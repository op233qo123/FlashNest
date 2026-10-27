// Diagnostic-only passthrough hooks. No callback wrapping or strong nodes in normal arms.
const category=value=>value===null?'null':typeof value;

// Uses the real native descriptor before observer installation, without a live
// AudioContext, playback, startRendering, callback dispatch or retained references.
export function nativeOnendedPreflight(g){
  if(typeof g.OfflineAudioContext!=='function')throw Error('OfflineAudioContext required for native onended preflight');
  const context=new g.OfflineAudioContext(1,1,44100),node=context.createBufferSource();
  function descriptor(object){for(let p=object;p;p=Object.getPrototypeOf(p)){const d=Object.getOwnPropertyDescriptor(p,'onended');if(d)return d}throw Error('Native onended descriptor unavailable')}
  const actual=descriptor(node),scheduled=descriptor(g.AudioScheduledSourceNode.prototype);
  const report={kind:'offline-native-onended',descriptorMatched:actual.get===scheduled.get&&actual.set===scheduled.set,cases:[],cleanupGetterCategory:null,passed:false};
  function handler(){}
  try{
    for(const value of [handler,null,handler,undefined]){
      node.onended=value;const getter=node.onended;
      report.cases.push({setterCategory:category(value),getterCategory:category(getter),identityPreserved:typeof value==='function'?getter===value:null,cleared:value==null?getter===null:null});
    }
  }finally{node.onended=null;report.cleanupGetterCategory=category(node.onended)}
  report.passed=report.descriptorMatched&&report.cleanupGetterCategory==='null'&&report.cases.every(c=>c.setterCategory==='function'?c.getterCategory==='function'&&c.identityPreserved===true:c.getterCategory==='null'&&c.cleared===true);
  return report;
}
export function installAudioObserver(g, {mode='normal', maxEvents=4096, maxNodes=4096}={}) {
  if (!['normal','start-first','start-second','synthetic-ended'].includes(mode)) throw new Error('Unknown fault arm');
  const contexts=new WeakMap(), nodes=new WeakMap(), contextRows=[], nodeRows=[], events=[], patches=[];
  let cycle=-1, overflow=false, active=true, retainedNode=null, injected=false;
  const record=(kind,data={})=>{if(events.length>=maxEvents){overflow=true;return}events.push({seq:events.length,kind,...data})};
  const context=(ctx)=>{
    let row=contexts.get(ctx); if(row)return row;
    row={id:contextRows.length+1,cycle,nodes:0,sourceAttempts:0,sourceThrows:0,starts:0,resumes:0,suspends:0,resumeFulfilled:0,suspendFulfilled:0,resumeFulfilledLast:0,suspendFulfilledLast:0,resumeRejected:0,suspendRejected:0,closeCalls:0,closeFulfilled:0,closeRejected:0,closeSnapshots:[]};
    contexts.set(ctx,row);contextRows.push(row);record('context',{context:row.id,cycle});return row;
  };
  function find(proto,key){for(let p=proto;p;p=Object.getPrototypeOf(p)){const d=Object.getOwnPropertyDescriptor(p,key);if(d)return [p,d]}throw new Error('Missing Audio API '+key)}
  function replace(proto,key,build){const [owner,old]=find(proto,key);if(!old.configurable)throw new Error('Nonconfigurable Audio API '+key);const next=build(old);Object.defineProperty(owner,key,next);patches.push({owner,key,old,next})}
  if(!g.AudioContext||!g.AudioBufferSourceNode||!g.AudioScheduledSourceNode)throw new Error('WebAudio unavailable');
  try {
    replace(g.AudioContext.prototype,'createBufferSource',old=>({...old,value:function(...args){
      const ctx=context(this);ctx.sourceAttempts++;record('source-attempt',{context:ctx.id,cycle:ctx.cycle,attempt:ctx.sourceAttempts});
      let node;try{node=Reflect.apply(old.value,this,args)}catch(error){ctx.sourceThrows++;record('source-throw',{context:ctx.id,error:String(error)});throw error}
      if(nodeRows.length>=maxNodes){overflow=true;return node}
      const row={id:nodeRows.length+1,context:ctx.id,cycle:ctx.cycle,attached:false,attaches:0,detaches:0,starts:0};
      nodes.set(node,row);nodeRows.push(row);ctx.nodes++;record('source',{context:ctx.id,node:row.id,cycle:ctx.cycle});
      if(mode==='synthetic-ended')retainedNode=node;
      return node;
    }}));
    replace(g.AudioScheduledSourceNode.prototype,'onended',old=>{
      if(typeof old.set!=='function'||typeof old.get!=='function')throw new Error('Missing onended descriptor');
      return {...old,set:function(value){
        Reflect.apply(old.set,this,[value]);
        const row=nodes.get(this);if(!row)return;
        const getter=Reflect.apply(old.get,this,[]),attach=typeof value==='function',detach=value===null||value===undefined;
        // Be conservative: only an observed exact native null counts as empty.
        row.attached=getter!==null;
        if(attach)row.attaches++;else if(detach&&getter===null)row.detaches++;
        record(attach?'attach':detach?'detach':'unsupported-onended',{context:row.context,node:row.id,
          setterCategory:category(value),getterCategory:category(getter),
          identityPreserved:attach?getter===value:null,cleared:detach?getter===null:null});
      }};
    });
    replace(g.AudioBufferSourceNode.prototype,'start',old=>({...old,value:function(...args){
      const row=nodes.get(this);if(row){
        const ctx=contextRows[row.context-1];ctx.starts++;row.starts++;
        const failAt=mode==='start-first'?1:mode==='start-second'?2:0;
        if(!injected&&failAt&&ctx.starts===failAt){injected=true;record('injected-start-error',{context:ctx.id,node:row.id,start:ctx.starts});throw new g.DOMException('Original audio lifecycle diagnostic start fault','InvalidStateError')}
        record('start',{context:ctx.id,node:row.id,start:ctx.starts});
      }
      return Reflect.apply(old.value,this,args);
    }}));
    for(const method of ['resume','suspend'])replace(g.AudioContext.prototype,method,old=>({...old,value:function(...args){
      const ctx=context(this),key=method==='resume'?'resumes':'suspends';const call=++ctx[key];record(method,{context:ctx.id,call,state:this.state});
      const promise=Reflect.apply(old.value,this,args);
      Promise.resolve(promise).then(()=>{ctx[method+'Fulfilled']++;ctx[method+'FulfilledLast']=Math.max(ctx[method+'FulfilledLast'],call);record(method+'-fulfilled',{context:ctx.id,call})},error=>{ctx[method+'Rejected']++;record(method+'-rejected',{context:ctx.id,call,error:String(error)})});
      return promise;
    }}));
    replace(g.AudioContext.prototype,'close',old=>({...old,value:function(...args){
      const ctx=context(this);ctx.closeCalls++;
      const attachedIds=nodeRows.filter(x=>x.context===ctx.id&&x.attached).map(x=>x.id);
      const snapshot={attachedIds,explicitlyDetached:nodeRows.filter(x=>x.context===ctx.id&&x.detaches>0).length,state:this.state};
      ctx.closeSnapshots.push(snapshot);record('close-entry',{context:ctx.id,...snapshot});
      let promise;
      try {promise=Reflect.apply(old.value,this,args)}catch(error){ctx.closeRejected++;record('close-throw',{context:ctx.id,error:String(error)});throw error}
      // Observe but return the original Promise unchanged. Closures capture only plain metadata.
      Promise.resolve(promise).then(()=>{ctx.closeFulfilled++;record('close-fulfilled',{context:ctx.id})},error=>{ctx.closeRejected++;record('close-rejected',{context:ctx.id,error:String(error)})});
      return promise;
    }}));
  }catch(error){for(const p of patches.reverse())Object.defineProperty(p.owner,p.key,p.old);throw error}
  return {
    setCycle(value){if(!Number.isInteger(value)||value<0)throw new Error('Invalid cycle');cycle=value},
    snapshot(){return structuredClone({mode,overflow,injected,contexts:contextRows,nodes:nodeRows,events})},
    dispatchSyntheticEnded(){
      if(mode!=='synthetic-ended'||!retainedNode)throw new Error('Synthetic arm requires its explicitly retained node');
      const row=nodes.get(retainedNode),before=nodeRows.length,beforeAttempts=contextRows[row.context-1].sourceAttempts,beforeThrows=contextRows[row.context-1].sourceThrows,hadHandler=typeof retainedNode.onended==='function';
      record('synthetic-ended',{node:row.id,context:row.context,hadHandler});
      const result=retainedNode.dispatchEvent(new g.Event('ended'));
      return {node:row.id,context:row.context,hadHandler,beforeNodes:before,afterNodes:nodeRows.length,beforeAttempts,afterAttempts:contextRows[row.context-1].sourceAttempts,beforeThrows,afterThrows:contextRows[row.context-1].sourceThrows,result};
    },
    releaseRetained(){retainedNode=null},
    restore(){
      if(!active)return;retainedNode=null;
      for(const p of [...patches].reverse()){
        const current=Object.getOwnPropertyDescriptor(p.owner,p.key);
        if(current?.value!==p.next.value||current?.set!==p.next.set)throw new Error('Audio hook overwritten: '+p.key);
        Object.defineProperty(p.owner,p.key,p.old);
      }
      active=false;
    }
  };
}
