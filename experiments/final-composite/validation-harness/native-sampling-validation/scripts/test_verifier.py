#!/usr/bin/env python3
"""Mock verifier/patch contract tests only. No native or rendering pass implied."""
import copy, hashlib, json, unittest, tempfile
from pathlib import Path
import os
import prepare_overlay as staging
import verify_results as verify

ROOT = Path(__file__).resolve().parents[1]
APP=Path(os.environ.get('FLASHNEST_REVIEWED_TEMPLATE', str(ROOT.parent / 'next-ipa-156-prep/app-integration/source')))
def measurement(lane='shipping-default-quality', scale=.25, applied=.25):
    row = {'row':'mock', 'arm':'candidate', 'lane':lane, 'tier':'quarter', 'rendererPolicy':'webgl', 'phase':'portrait'}
    m = {'dpr':3, 'canvas':[round(1200*applied),round(1800*applied)], 'gl':[round(1200*applied),round(1800*applied)],
        'client':[400,600], 'css':[0,0,400,600], 'wasm':['actual.wasm'], 'renderer':'webgl', 'context':'webgl2',
        'storage':[[4,1200,1800]] if applied==1 else [], 'attributes':{'data-flashnest-render-scale':str(applied),
        'data-flashnest-render-request':str(scale), 'data-flashnest-viewport-width':'1200',
        'data-flashnest-viewport-height':'1800', 'data-flashnest-renderer':'webgl'},
        'overflow':False, 'hidden':False, 'mobileQualityBranch':True,
        'diagnosticLaunchQuality': None if lane=='shipping-default-quality' else lane.removeprefix('diagnostic-launch-')}
    snapshot = {'identity':{'runtimeInventorySHA256':'candidate', 'runtimeFiles':{'actual.wasm':'sha'}, 'arm':'candidate',
        'simulatorOnly':True, 'shippingDefaultQualityOmitted':True}, 'os':'18.2', 'screenScale':3, 'measurement':m,
        'failure':'', 'traceOverflow':False, 'loaded':True, 'gate':True, 'requested':scale, 'applied':applied,
        'status':'applied' if scale==applied else 'fallback', 'viewport':[0,0,400,600]}
    return row,snapshot

class Contracts(unittest.TestCase):
    def identities(self):
        return {arm: {'arm': arm, 'simulatorOnly': True, 'observerSHA256': 'a'*64,
                     'stagingProvenanceSHA256': 'b'*64, 'approvedAppManifestSHA256': 'c'*64}
                for arm in ('baseline', 'candidate')}
    def test_external_metadata_repin_never_authorizes_executable_changes(self):
        original={'App/Resources/Web/runtime-identity.json':'old', 'App/Player/PlayerSession.swift':'code'}
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'map.json'
            def write(mapping):
                p.write_text(json.dumps({'files':[{'path':k,'sha256':v} for k,v in mapping.items()]}))
                return staging.sha(p)
            safe={**original,'App/Resources/Web/runtime-identity.json':'new'}
            self.assertEqual(staging.resolve_app_manifest(original,p,write(safe))[0],safe)
            for bad in ({**safe,'App/Player/PlayerSession.swift':'changed'}, {'App/Resources/Web/runtime-identity.json':'new'}):
                with self.assertRaises(AssertionError):staging.resolve_app_manifest(original,p,write(bad))
            with self.assertRaises(AssertionError):staging.resolve_app_manifest(original,p,'0'*64)
    def test_external_identity_required(self):
        for bad in ({}, {'baseline': self.identities()['baseline']},
                    {'baseline': {'arm':'baseline','simulatorOnly':True}, 'candidate': self.identities()['candidate']}):
            with self.assertRaises(AssertionError): verify.verify(ROOT/'fixtures','candidate','baseline',bad)
    def check(self, row, snap, unsupported=None): return verify.check_measurement(row,snap,'candidate','baseline',unsupported)
    def test_shipping_mobile_omitted_quality_reduction(self):
        r,s=measurement();self.assertEqual(self.check(r,s),.25)
    def test_actual_custom_msaa_fallback(self):
        r,s=measurement('diagnostic-launch-high',applied=1);self.assertEqual(self.check(r,s),1)
    def test_unavailable_high_msaa_is_explicitly_unsupported(self):
        r,s=measurement('diagnostic-launch-high'); unsupported=[];self.check(r,s,unsupported)
        self.assertEqual(len(unsupported),1);self.assertIn('no High/MSAA pass',unsupported[0]['reason'])
    def test_explicit_low_reduces(self):
        r,s=measurement('diagnostic-launch-low');self.assertEqual(self.check(r,s),.25)
    def test_backing_status_identity_quality_mutants_rejected(self):
        changes=[('gl',[1200,1800]),('canvas',[300,449]),('dpr',2),('client',[401,600]),
                 ('context','webgpu'),('renderer',None),('overflow',True),('hidden',True),
                 ('diagnosticLaunchQuality','low'),('wasm',[]),('wasm',['other.wasm']),
                 ('storage',[[4,1200,1800]])]
        for key,value in changes:
            with self.subTest(key=key):
                r,s=measurement();s['measurement'][key]=value
                with self.assertRaises(AssertionError):self.check(r,s)
        for key,value in [('requested',1),('applied',1),('status','unknown'),('gate',False),('os','18.1'),('loaded',False)]:
            with self.subTest(key=key):
                r,s=measurement();s[key]=value
                with self.assertRaises(AssertionError):self.check(r,s)
    def test_trace_geometry_mismatch_rejected(self):
        verify.trace_equal([['1.05','2','true']],[['1','2','true']])
        for bad in [[['2','2','true']],[['1','2','false']],[]]:
            with self.assertRaises(AssertionError):verify.trace_equal(bad,[['1','2','true']])
    def test_incomplete_matrix_never_passes(self):
        with self.assertRaisesRegex(AssertionError,'Incomplete/unexpected matrix'):verify.verify(ROOT/'fixtures','candidate','baseline', self.identities())
    def test_fixture_exact_original_bytes(self):
        manifest=json.loads((ROOT/'fixtures/manifest.json').read_text())
        self.assertEqual(set(manifest['files']),{'showAll-center.swf','noScale-center.swf'})
        for name, info in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/'fixtures'/name).read_bytes()).hexdigest(),info['sha256'])
            self.assertIsNone(info['fixtureQuality'])
    def test_approved_app_manifest_pinned(self):
        self.assertEqual(staging.sha(ROOT/'approved-app-source-manifest.json'),staging.APPROVED_APP_MANIFEST_SHA256)
    @unittest.skipUnless(APP.exists(),'Local reviewed App source not present')
    def test_exact_overlay_preserves_navigation_policy(self):
        before=(APP/'App/Player/PlayerSession.swift').read_text();after=staging.session_overlay(before)
        start='    func webView(_ webView: WKWebView, decidePolicyFor';end='    func webView(_ webView: WKWebView, didFailProvisionalNavigation'
        self.assertEqual(before.split(start)[1].split(end)[0],after.split(start)[1].split(end)[0])
        self.assertNotIn('-999',after)
        self.assertEqual(after.count('NativeSamplingProbe.record('),5)
        with self.assertRaises(AssertionError):staging.session_overlay(after)
        shell=(APP/'App/Resources/Web/shell.js').read_text();modified=staging.shell_overlay(shell)
        added=modified.replace(shell.split('      ...(requestedRenderer')[0], '',1)
        self.assertIn('window.__samplingNativeDiagnosticQuality',modified)
        self.assertEqual(len(modified.splitlines())-len(shell.splitlines()),1)

if __name__=='__main__': unittest.main(verbosity=2)
