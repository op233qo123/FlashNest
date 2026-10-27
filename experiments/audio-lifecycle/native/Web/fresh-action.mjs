import assert from './assert.mjs';
// Exact body of the locked browser runner's freshAction; tested for equality.
export function freshAction(before,after,kind){const calls=kind==='resume'?'resumes':'suspends';assert(after[calls]>before[calls],'No fresh audio action call');assert(after[kind+'Fulfilled']>before[kind+'Fulfilled'],'No fresh fulfilled action');assert(after[kind+'FulfilledLast']>before[calls],'Only an older initialization Promise settled');}
