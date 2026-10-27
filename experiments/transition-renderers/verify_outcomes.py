#!/usr/bin/env python3
"""Explicit single-arm follow-up is never reported as a passing A/B."""
import sys

def verify(scope, default, webgl):
    if scope == 'both':
        if (default,webgl) != ('success','success'): raise ValueError('Both requested arms must pass')
    elif scope == 'webgl':
        if (default,webgl) != ('skipped','success'): raise ValueError('Only requested WebGL arm must pass; default must be explicitly skipped')
    else: raise ValueError('Unknown renderer scope')
    return {'scope':scope,'default':default,'webgl':webgl}

if __name__=='__main__':
    import json
    if len(sys.argv)!=4: raise SystemExit('Expected scope/default/webgl outcomes')
    print(json.dumps(verify(*sys.argv[1:])))
