"""Execute the actual native JS checkpoint/receipt functions with synthetic time/host.

No Swift, FileManager, WKWebView, AudioContext or runtime execution is claimed.
"""
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent


class MidcaseRunnerTests(unittest.TestCase):
    def test_actual_polling_pipeline_drains_only_durable_mock_receipts(self):
        source = (HERE / 'Web/native-runner.mjs').read_text()
        functions = source[source.index('async function waitFor('):source.index('\nasync function trustedAudio(')]
        functions += '\n' + source[source.index('window.__nativeAudioReceipt='):source.index('function allObservedAudioPromisesSettled(')]
        program = r"""
import assert from 'node:assert/strict';
import {webcrypto as crypto} from 'node:crypto';
import {createNativeEventWindow} from 'WINDOW';
let now=0,delay=65000,row,events,window,host={deadlineMS:600000},arm='baseline',mode='normal',requestSequence=0,
 pendingAction=null,pendingEvidenceReceipt=null,acceptedEvidenceReceipt=null,activeCycle=0,
 checkpointInFlight=false,chunkCount=0,finished=false,sent=[],due=null,ackMode='ok',produce=true;
const Date={now:()=>now};
const setTimeout=fn=>{
 now+=50;
 if(produce)for(let i=0;i<5;i++)window.nativeAudioEvidenceWindow.record('synthetic-observation',{context:1});
 if(due&&now>=due.at){const r=due.receipt;due=null;window.__nativeAudioReceipt(r)}
 fn();
};
function checkHealthy(e){assert(!e.audio.overflow);assert(e.audio.events.length<=4096)}
function snapshot(){
 if(now>=delay&&row.actions.length===0)row.actions.push({name:'remove',trusted:true});
 const eventWindow=window.nativeAudioEvidenceWindow.status();
 return structuredClone({runtime:arm,mode,rows:[row],audio:{overflow:eventWindow.overflow,eventWindow,events,nodes:[],contexts:[],lastReceipt:acceptedEvidenceReceipt}});
}
function send(type,body){
 if(type!=='event-chunk'&&type!=='case')return;
 const record=JSON.parse(body.caseJSON),bytes=Buffer.from(body.caseJSON);
 sent.push({record,bytes,sha256:body.sha256});
 // Test-double durability boundary: a real file-write negative is NOT claimed.
 if(ackMode==='write-failure')throw Error('mock write rejected');
 if(ackMode==='missing')return;
 due={at:now+200,receipt:{...record.eventWindow,bytes:bytes.length,sha256:body.sha256}};
}
FUNCTIONS
function reset(){
 now=0;delay=65000;row={cycle:0,actions:[]};events=[];
 const accept=window?.__nativeAudioReceipt;window={nativeAudioEvidenceWindow:createNativeEventWindow(events),__nativeAudioReceipt:accept};
 pendingAction=null;pendingEvidenceReceipt=null;acceptedEvidenceReceipt=null;activeCycle=0;checkpointInFlight=false;chunkCount=0;sent=[];due=null;ackMode='ok';produce=true;
}
// Install functions before replacing only the per-test observer state.
"""
        # The callback assignment needs a window before evaluating the real functions.
        program = program.replace('FUNCTIONS', 'window={};\n' + functions)
        program += r"""
reset();await trustedClick('remove',0);
assert(now>=65000&&now<90000);assert.equal(pendingAction,null);assert(chunkCount>=5);
let next=0;
for(const {record,bytes,sha256} of sent){
 assert.equal(record.type,'event-chunk');assert.equal(record.eventWindow.start,next);
 assert(record.evidence.audio.events.length>=1024);assert(record.evidence.audio.events.length<=4096);
 for(const e of record.evidence.audio.events)assert.equal(e.seq,next++);
 const digest=await crypto.subtle.digest('SHA-256',bytes);
 assert.equal(Buffer.from(digest).toString('hex'),sha256);
}
for(const e of events)assert.equal(e.seq,next++);
assert(next>=6500);assert.equal(next,window.nativeAudioEvidenceWindow.status().endExclusive);
assert.equal(window.nativeAudioEvidenceWindow.status().overflow,false);
assert.equal(activeCycle,0);assert.equal(acceptedEvidenceReceipt.kind,'chunk');
for(const failure of ['missing','write-failure']){
 reset();produce=false;ackMode=failure;for(let i=0;i<1024;i++)window.nativeAudioEvidenceWindow.record('test');
 await assert.rejects(checkpointEvents(),failure==='missing'?/readback acknowledgment/:/mock write/);
 assert.equal(events.length,1024);assert.equal(window.nativeAudioEvidenceWindow.status().start,0);
 assert.equal(window.nativeAudioEvidenceWindow.status().receiptPending,true);assert.equal(acceptedEvidenceReceipt,null);
 if(failure==='missing'){assert.throws(()=>window.__nativeAudioReceipt(pendingEvidenceReceipt.expected),/Late evidence/);assert.equal(events.length,1024)}
}
console.log('PASS actual native JS polling/receipt pipeline:6500+ records in one slow-action case, exact prefix+late-tail continuity, no mock failed/missing readback drain');
"""
        program = program.replace('WINDOW', (HERE / 'Web/observer-window.mjs').as_uri())
        subprocess.run(['node', '--input-type=module', '-'], input=program, text=True, check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
