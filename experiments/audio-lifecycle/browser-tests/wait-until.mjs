// WebdriverIO retries predicate exceptions; diagnostic assertions must fail once.
export async function waitUntilFailFast(waitUntil, predicate, options) {
  let predicateFailed=false, predicateError;
  let result;
  try {
    result=await waitUntil(async function (...args) {
      if (predicateFailed) return true;
      try {
        return await Reflect.apply(predicate,this,args);
      } catch (error) {
        // Do not use truthiness: JavaScript permits throwing null/undefined/etc.
        // Keep the first failure if an unusual caller has predicates in flight.
        if (!predicateFailed) { predicateFailed=true; predicateError=error; }
        return true;
      }
    },options);
  } catch (error) {
    if (predicateFailed) throw predicateError;
    throw error;
  }
  if (predicateFailed) throw predicateError;
  return result;
}
