// One explicitly identified pinned-runtime warning, not a general overlay bypass.
import assert from 'node:assert/strict';
export const warningText='It looks like hardware acceleration is disabled. While Ruffle may work, it could be very slow. You can find out how to enable hardware acceleration by following the link below:';
export const warningLinkText='FAQ - Chrome Hardware Acceleration';
export const warningLink='https://github.com/ruffle-rs/ruffle/wiki/Frequently-Asked-Questions-For-Users#chrome-hardware-acceleration';
export function validateWarning(state){
 assert(state?.visible===true&&state.id==='hardware-acceleration-modal','Unexpected warning identity');
 assert.equal(state.text,warningText,'Unknown warning text must not be dismissed');
 assert.equal(state.linkText,warningLinkText);assert.equal(state.link,warningLink);
 assert.equal(state.closeCount,1);assert.equal(state.closeHit,true,'Warning close control is not topmost');
 assert(Array.isArray(state.point)&&state.point.length===2&&state.point.every(x=>Number.isFinite(x)&&x>=0));
 return state.point;
}
export async function dismissHardwareWarning({inspect,capture,click,waitGone,record}){
 const state=await inspect();if(!state?.visible)return false;
 const point=validateWarning(state);
 const evidence=await capture(state); // Do not dismiss if evidence could not be retained.
 await record({state,evidence,warningReportsHardwareAccelerationUnavailable:true,scope:'browser diagnostic only'});
 const latest=await inspect();validateWarning(latest);assert.deepEqual(latest.point,point,'Warning moved before trusted click');
 await click(...point); // Exactly one trusted WebDriver click. Never DOM .click/CSS mutation.
 await waitGone();
 return true;
}
