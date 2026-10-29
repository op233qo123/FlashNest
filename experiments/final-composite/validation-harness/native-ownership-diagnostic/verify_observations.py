"""Observation integrity, not a render-health or production restart acceptance gate."""
import math
CONTROLS = {'owners','same-turn','rendered-nil'}
def verify_records(records):
    assert len(records) == 3 and {r['control'] for r in records} == CONTROLS
    by = {r['control']: r for r in records}
    for r in records:
        assert r['schema'] == 'flashnest-restart-ownership-diagnostic-v1'
        assert r['diagnosticOnly'] is True and r['nativeAcceptance'] is False
        assert r['renderHealthCertified'] is False and r['observationComplete'] is True
    owner = by['owners']
    assert owner['bothOwnersAlive'] is True and owner['containerOnlyAlive'] is True and owner['explicitOwnerAfterDetachAlive'] is True
    assert type(owner['weakNilAfterAllOwnersDropped']) is bool
    assert owner['observationWindowSeconds'] == 3 and owner['gpuMemoryReclamationProven'] is False
    for name in ('same-turn','rendered-nil'):
        r = by[name]
        assert r['initialAttached'] is True and r['sourceCopyNotProductionView'] is True
        assert r['oldStronglyHeldForIdentityComparison'] is True
        assert type(r['identityMatches']) is bool
        assert r['nilRenderedBeforeReplacement'] is (True if name == 'rendered-nil' else None)
        samples = r['samples']; assert len(samples) == 40
        previous = -math.inf
        for s in samples:
            t = s['uptimeSeconds']; assert type(t) in (float,int) and math.isfinite(t) and t > previous
            previous = t
            for key in ('displayedOld','displayedReplacement','displayedForeign','modelIsReplacement','oldHasSuperview','newHasSuperview'):
                assert type(s[key]) is bool
            assert s['modelIsReplacement'] is True and s['displayedForeign'] is False
            assert type(s['displayedCount']) is int and s['displayedCount'] in (0,1,2)
            assert s['displayedCount'] == int(s['displayedOld']) + int(s['displayedReplacement'])
        final = samples[-1]
        assert final['displayedCount'] == 1
        assert r['identityMatches'] is final['displayedReplacement']
    return {'schema':'flashnest-ownership-observation-report-v1','observationComplete':True,
            'diagnosticOnly':True,'nativeAcceptance':False,'renderHealthCertified':False,
            'weakReleaseOutcome':'observed-wrapper-release' if owner['weakNilAfterAllOwnersDropped'] else 'inconclusive-within-3-seconds',
            'sameTurnIdentityMatches':by['same-turn']['identityMatches'],
            'renderedNilIdentityMatches':by['rendered-nil']['identityMatches'],
            'sourceCopyNotProductionView':True,'records':records}
