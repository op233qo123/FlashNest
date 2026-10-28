#!/usr/bin/env python3
"""Fail-closed *record* verifier, not native execution/authenticity attestation.

Input schema is documented in EVIDENCE-SCHEMA.md. Model unit records do not
constitute WebKit, trusted-input or iOS recovery evidence.
"""
import argparse
import base64
import binascii
import json
import struct
from pathlib import Path

MODES = ('candidate-known', 'candidate-unknown', 'baseline-known')

class EvidenceError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise EvidenceError(message)

def obj(value, name):
    require(isinstance(value, dict), name + ': object required')
    return value

def integer(value):
    return type(value) is int and 0 <= value <= 9007199254740991

def tap(value, target):
    value = obj(value, target + ' tap')
    require(value.get('method') == 'XCTest.tap' and value.get('target') == target,
            target + ': actual native tap record required')
    require(value.get('enabled') is True and value.get('hittable') is True,
            target + ': enabled/hittable evidence required')

def continuity(value):
    value = obj(value, 'continuity')
    require(isinstance(value.get('pageId'), str) and value['pageId'], 'page identity required')
    require(integer(value.get('childInputSerial')), 'child serial required')
    text = value.get('solSnapshot')
    require(isinstance(text, str) and 0 < len(text) <= 16777216, 'real SOL snapshot required')
    try:
        sol = json.loads(text)
    except (ValueError, TypeError) as e:
        raise EvidenceError('SOL snapshot must be canonical JSON') from e
    require(isinstance(sol, dict), 'SOL inventory object required')
    entries = sol.get('entries')
    require(sol.get('version') == 1 and isinstance(entries, list) and len(entries) > 0,
            'nonempty real SOL inventory required')
    require(len(entries) == 1, 'exact one fixture SOL required')
    entry = entries[0]
    require(isinstance(entry, dict) and entry.get('scope') == 'origin' and
            entry.get('key') == 'LifecycleFixture' and isinstance(entry.get('value'), str),
            'exact origin LifecycleFixture identity required')
    try:
        raw = base64.b64decode(entry['value'], validate=True)
    except (ValueError, binascii.Error) as e:
        raise EvidenceError('SOL base64 invalid') from e
    require(base64.b64encode(raw).decode('ascii') == entry['value'], 'SOL base64 must be canonical')
    # Deliberately not a general AMF decoder. This exact fixture writes one AMF0
    # Number property. Alternate encodings/extra properties fail closed.
    name = b'LifecycleFixture'
    key = b'progress'
    tail = (b'TCSO\x00\x04\x00\x00\x00\x00' + struct.pack('>H', len(name)) + name +
            b'\x00\x00\x00\x00' + struct.pack('>H', len(key)) + key + b'\x00' +
            struct.pack('>d', 420) + b'\x00')
    expected = b'\x00\xbf' + struct.pack('>I', len(tail)) + tail
    require(raw == expected, 'exact minimal AMF0 LifecycleFixture progress420 SOL required')
    canonical = json.dumps({'version': 1, 'entries': [{'scope': 'origin',
        'key': 'LifecycleFixture', 'value': entry['value']}]}, separators=(',', ':'), ensure_ascii=False)
    require(text == canonical, 'exact canonical production bridge snapshot required')
    return value

def probe(value, arm):
    value = obj(value, 'probe')
    require(value.get('schema') == 1 and value.get('mode') == arm, 'wrong probe schema/arm')
    require(integer(value.get('sample')) and value['sample'] > 0 and integer(value.get('eventCount')) and value['eventCount'] <= 64, 'bounded fresh probe sample required')
    require('totalContextCount' in value and value['totalContextCount'] is None,
            'total context count must remain explicitly unknown')
    require('contexts' not in value, 'old invented context census forbidden')
    require(all(integer(value.get(k)) for k in ('captureCalls', 'capturedReceivers', 'injections', 'trustedRetries')), 'invalid probe counters')
    require(value.get('captureCalls') == 1 and value.get('capturedReceivers') == 1 and
            value.get('captureComplete') is True, 'one synchronous completed capture required')
    require(value.get('prototypeRestored') is True and value.get('instanceRestored') is True,
            'both descriptors must be restored')
    require(value.get('failure') is None and value.get('failures') == [], 'probe failure')
    require(value.get('disposed') is False, 'pre-cleanup evidence cannot be disposed')
    ownership = 'source-status-correlated-public-call' if arm == 'candidate' else 'weaker-public-call-inference-no-context-id'
    require(value.get('ownershipEvidence') == ownership, 'incorrect ownership claim')
    if arm == 'baseline':
        require(value.get('contextId') is None, 'baseline cannot attest source context ID')
    else:
        require(integer(value.get('contextId')) and value['contextId'] > 0, 'candidate context ID required')
    return value

def operation(value, context_id, status, phase='core-play', operation='resume'):
    value = obj(value, status + ' operation')
    require(value.get('schema') == 1 and value.get('contextId') == context_id and
            value.get('current') is True and value.get('status') == status and
            value.get('phase') == phase and value.get('operation') == operation,
            'wrong current source operation')
    require(all(integer(value.get(k)) and value[k] > 0 for k in ('operationId', 'intentId')),
            'invalid source operation identifiers')
    return value

def same_tuple(a, b):
    return all(a.get(k) == b.get(k) for k in ('contextId', 'operationId', 'intentId'))

def validate(record):
    record = obj(record, 'case')
    require(record.get('schema') == 'late-native-case-v1', 'wrong case schema')
    require(all(k in record for k in ('hostError', 'nativeFailure', 'retryTap', 'recovered', 'reopenRootTrace')), 'explicit nullable outcome fields required')
    mode = record.get('mode')
    require(mode in MODES, 'unknown mode')
    arm = mode.split('-')[0]
    require(record.get('hostError') is None, 'native host failure')
    tap(record.get('playTap'), 'Play / enable audio')
    ready = obj(record.get('readiness'), 'readiness')
    require(all(ready.get(k) is True for k in ('trustedPlay', 'rootReady', 'childReady', 'saveReady')),
            'all actual readiness gates required')
    require(record.get('initialTraces') == ['LIFECYCLE_ROOT_READY:undefined',
            'LIFECYCLE_CHILD_READY', 'LIFECYCLE_CHILD_KEY:32:1'], 'exact initial fixture traces required')
    before = continuity(record.get('before'))
    require(before['childInputSerial'] == 1, 'initial child input serial must be one')
    capture = probe(record.get('capture'), arm)
    require(capture.get('phase') == 'captured', 'capture phase required')
    require(capture.get('injections') == 0 and capture.get('trustedRetries') == 0 and
            capture.get('contextState') == 'running', 'capture must precede injection')
    injected = probe(record.get('injected'), arm)
    require(injected.get('phase') == ('rejected' if arm == 'candidate' else 'injected'), 'injection settlement phase required')
    require(injected['sample'] > capture['sample'], 'fresh injected sample required')
    require(injected.get('injections') == 1 and injected.get('trustedRetries') == 0,
            'exact one-shot injection before retry required')
    require(injected.get('contextId') == capture.get('contextId'), 'context changed')
    after = continuity(record.get('after'))
    require(after['pageId'] == before['pageId'] and after['solSnapshot'] == before['solSnapshot'],
            'same page and unchanged actual SOL required')
    if arm == 'candidate':
        c = operation(capture.get('capturedOperation'), capture['contextId'], 'pending')
        i = operation(injected.get('injectedOperation'), capture['contextId'], 'pending')
        r = operation(injected.get('rejectedOperation'), capture['contextId'], 'rejected')
        require(same_tuple(i, r) and i['operationId'] > c['operationId'] and i['intentId'] > c['intentId'],
                'injection must be a newer matching source rejection')
        require(r.get('retryEligible') is (mode == 'candidate-known'), 'incorrect retry classification')
    order = obj(record.get('order'), 'order')
    keys = ['play', 'readiness', 'capture', 'pause', 'injection', 'outcome', 'cleanup']
    require(all(integer(order.get(k)) for k in keys) and all(order[a] < order[b] for a, b in zip(keys, keys[1:])),
            'ordered native journey required')
    if mode == 'candidate-known':
        require(record.get('nativeFailure') is None, 'recovery must not have native failure')
        tap(record.get('retryTap'), 'Retry audio')
        recovered = probe(record.get('recovered'), arm)
        require(recovered.get('phase') == 'recovered' and recovered['sample'] > injected['sample'], 'fresh recovered phase/sample required')
        require(all(recovered.get(k) == injected.get(k) for k in ('injectedOperation', 'rejectedOperation')) and recovered.get('capturedOperation') == capture.get('capturedOperation'), 'operation history changed')
        require(recovered.get('contextId') == capture['contextId'] and recovered.get('contextState') == 'running' and
                recovered.get('injections') == 1 and recovered.get('trustedRetries') == 1,
                'same captured running context and one trusted retry required')
        require(recovered.get('ok') is True and recovered.get('reasons') == [], 'probe recovery verification required')
        pending = operation(recovered.get('retryOperation'), capture['contextId'], 'pending')
        fulfilled = operation(recovered.get('fulfilledRetry'), capture['contextId'], 'fulfilled')
        require(same_tuple(pending, fulfilled) and fulfilled.get('state') == 'running' and
                pending['operationId'] > r['operationId'] and pending['intentId'] > r['intentId'],
                'matching fresh fulfilled retry required')
        require(record.get('warningVisible') is False, 'production warning gate must clear')
        at = record.get('childInputSerialAfterFulfillment')
        require(integer(at) and at >= before['childInputSerial'] and after['childInputSerial'] > at,
                'fresh child trace must follow retry fulfillment')
        require(record.get('afterTrace') == 'LIFECYCLE_CHILD_KEY:32:2' and after['childInputSerial'] == 2,
                'exact fresh child trace required')
        require(record.get('reopenRootTrace') == 'LIFECYCLE_ROOT_READY:420', 'explicit real SOL reopen proof required')
        require(all(integer(order.get(k)) for k in ('retry', 'child', 'verified', 'reopen')) and
                order['injection'] < order['retry'] < order['child'] < order['verified'] < order['reopen'] < order['cleanup'] and
                order['outcome'] == order['verified'], 'reopen must follow in-place recovery verification')
    else:
        expected = 'Original synthetic unknown audio failure' if mode == 'candidate-unknown' else 'Failed to start the audio device'
        failure = record.get('nativeFailure')
        require(isinstance(failure, str) and expected in failure, 'expected actual PlayerSession.failure required')
        require(record.get('warningVisible') is False and record.get('retryTap') is None and record.get('recovered') is None,
                'fatal control must not retry or claim recovery')
        require(record.get('reopenRootTrace') is None, 'fatal control must not mask failure through reopening')
    cleanup = obj(record.get('cleanup'), 'cleanup')
    require(all(cleanup.get(k) is True for k in ('disposed', 'closed', 'drained')), 'complete cleanup required')
    return {'mode': mode, 'recordValid': True, 'nativeExecutionAttested': False,
            'note': 'Record semantics only; independently authenticate native xcresult and source/runtime identity.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(json.loads(args.record.read_text())), sort_keys=True))
    except (EvidenceError, ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')
