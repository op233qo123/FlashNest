// Native diagnostic adapter primitive. Not imported by the browser observer or
// production application. The original observer/goldens remain unchanged.
const integer=value=>Number.isSafeInteger(value)&&value>=0;
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const check=(ok,message)=>{if(!ok)throw Error(message)};
const keys=['kind','ordinal','token','cycle','start','endExclusive','count','bytes','sha256'];
function receiptShape(value){
 check(value&&typeof value==='object'&&Object.keys(value).sort().join()===keys.slice().sort().join(),'Invalid receipt schema');
 check(typeof value.token==='string'&&value.token.length>0&&value.token.length<=100&&!/[\r\n]/.test(value.token),'Invalid receipt token');
 check(['case','chunk'].includes(value.kind)&&integer(value.ordinal)&&value.ordinal<40,'Invalid receipt kind/ordinal');
 check(value.kind!=='chunk'||value.count>=1024,'Chunk below highwater');
 check(integer(value.cycle)&&value.cycle<8&&integer(value.start)&&integer(value.endExclusive)&&value.endExclusive>=value.start,'Invalid receipt interval');
 check(integer(value.count)&&value.count===value.endExclusive-value.start&&value.count<=4096,'Invalid receipt count');
 check(Number.isSafeInteger(value.bytes)&&value.bytes>0&&value.bytes<=2*1024*1024&&digest(value.sha256),'Invalid persisted case digest');
}

export function createNativeEventWindow(events,maximum=4096){
 check(Array.isArray(events)&&events.length===0,'Event window requires fresh empty storage');
 check(maximum===4096,'Native event cap must remain 4096');
 const seenTokens=new Set();
 let base=0,next=0,overflow=false,pending=null,lastReceipt=null,finalBoundary=null,postFinalActivity=0,nextCycle=0,chunks=0;
 function consistent(){
  check(events.length===next-base,'Event window count drift');
  for(let i=0;i<events.length;i++)check(events[i]?.seq===base+i,'Event window sequence drift');
 }
 function status(){
  consistent();return Object.freeze({start:base,endExclusive:next,count:events.length,overflow,
   finalBoundary,postFinalActivity,receiptPending:pending!==null});
 }
 return Object.freeze({
  record(kind,data={}){
   check(data&&typeof data==='object'&&!Object.hasOwn(data,'seq')&&!Object.hasOwn(data,'kind'),'Reserved event metadata');
   if(finalBoundary!==null){
    if(postFinalActivity<Number.MAX_SAFE_INTEGER)postFinalActivity++;
    else overflow=true;
   }
   if(events.length>=maximum||next===Number.MAX_SAFE_INTEGER){overflow=true;return}
   // Sequence is never reset by acknowledgment. Original metadata payload and
   // event order are unchanged; no AudioNode or callback is retained here.
   events.push({seq:next++,kind,...data});
  },
  status,
  armReceipt(receipt){
   receiptShape(receipt);consistent();check(!overflow,'Overflow is not drainable');
   check(finalBoundary===null&&pending===null,'Receipt already pending or final boundary set');
   check(receipt.start===base&&receipt.endExclusive<=next,'Receipt does not describe current prefix');
   check(receipt.ordinal===(lastReceipt===null?0:lastReceipt.ordinal+1),'Wrong receipt ordinal');
   check(receipt.cycle===nextCycle,'Wrong receipt cycle');
   check(receipt.kind!=='chunk'||chunks<32,'Mid-case chunk cap');
   check(!seenTokens.has(receipt.token)&&seenTokens.size<40,'Reused receipt token or receipt cap');
   seenTokens.add(receipt.token);pending=Object.freeze({...receipt});
  },
  acceptReceipt(receipt){
   receiptShape(receipt);consistent();check(pending!==null,'Unsolicited or duplicate receipt');
   for(const key of keys)check(receipt[key]===pending[key],'Receipt mismatch: '+key);
   check(!overflow,'Overflow remains fatal while receipt is pending');
   check(receipt.start===base&&receipt.endExclusive<=next,'Receipt prefix changed');
   // Only the exact host-readback-acknowledged prefix is removed. A tail appended
   // during serialization, write, readback or acknowledgment stays observable.
   events.splice(0,receipt.count);base=receipt.endExclusive;
   lastReceipt=pending;pending=null;if(lastReceipt.kind==='case')nextCycle++;else chunks++;
   consistent();return {...lastReceipt};
  },
  lastReceipt(){return lastReceipt===null?null:{...lastReceipt}},
  markFinalBoundary(){
   consistent();check(!overflow&&pending===null&&finalBoundary===null,'Cannot mark final evidence boundary');
   finalBoundary=next;return status();
  },
 });
}
