#!/usr/bin/env python3
"""Final cross-binding on independently verified lane output, not test-process exit."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];lane=sys.argv[1]
assert lane in ('browser','native')
lock=json.loads((ROOT/'validation-lock.json').read_text());assert lock['dispatchAllowed'] is True
report=json.loads((ROOT/'evidence'/f'{lane}-acceptance.json').read_text());engine=lock['engine']
assert report['passed'] is True and type(report['skipped']) is int and report['skipped']==0
assert report['engineSHA256']==engine['sha256'] and report['selectedWasmSHA256'] in engine['wasmSHA256']
if lane=='browser':
 assert report['rows']==290 and report['shippingSelectionExecuted'] is True
 assert report['realLoaderPaths']==[engine['wasmFlavorBySHA256'][report['selectedWasmSHA256']]]
 assert report['verification']['rows']==290 and report['verification']['phases']==870 and report['verification']['trustedClicks']==4350
 assert report['physicalDeviceCertified'] is False
 assert report['harnessManifestSHA256']==lock['lanes']['browser']['harnessManifestSHA256']
 assert report['appRendererPolicy']==lock['lanes']['browser']['appRendererPolicy']
 policy=report['appRendererPolicy']
 assert lock['appSourceManifest']['files'][policy['appShellPath']]==policy['appShellSHA256']
else:
 assert report['evidenceKind']=='iOS simulator' and report['physicalDeviceCertified'] is False
 assert report['nativeMethods']==198 and report['samplingRows']==48 and report['samplingPhases']==144
 assert sum(r['tests'] for r in report['results'])==198
 assert report['shippingReductionRequirementMet'] is True and report['shippingPoliciesWithAllReductions']
 assert set(report['shippingPoliciesWithAllReductions']) <= {'automatic','webgl'}
 assert report['shippingDefaultAppliesAllTiers']==('automatic' in report['shippingPoliciesWithAllReductions'])
 geometry=json.loads((ROOT/'evidence/native/sampling-geometry.json').read_text())
 assert geometry['matrixPassed'] is True and geometry['shippingReductionRequirementMet'] is True
 assert report['nativeContract']=='flashnest-native-composite-v4' and report['samplingContract']=='flashnest-native-sampling-v4'
 assert geometry['contract']=='flashnest-native-sampling-v4'
 assert report['positiveRegressionMethods']==196 and report['enhancedBoundaryDiagnosticMethods']==2
 assert report['enhancedRenderHealthCertified'] is False
 assert report['rendererPolicyContract']=='candidate-three-mode-v1' and report['legacyRendererPolicyPreserved'] is True
 selection_raw=(ROOT/'validation-harness/native-composite-runner/selection-contract-v4.json').read_bytes()
 assert hashlib.sha256(selection_raw).hexdigest()==report['selectionContractSHA256']
 selection=json.loads(selection_raw)
 assert selection['contract']=='flashnest-native-composite-v4'
 assert selection['regressionMethodExecutions']==196 and selection['enhancedBoundaryDiagnosticExecutions']==2
 assert len(report['results'])==len(selection['runs'])
 assert {r['runName']:(r['lane'],r['tests']) for r in report['results']}=={r['runName']:(r['lane'],r['expectedCount']) for r in selection['runs']}
 assert all(r['semanticResultValid'] is True and r['osVersion']=='18.2' for r in report['results'])
 # Independently authenticate both complete leaf inventories before reading nested proofs.
 from verify_native_job_bindings import verify_jobs, verify_generated
 evidence=ROOT/'evidence/native'
 verify_jobs(ROOT,report,selection,lock)
 method_raw=(ROOT/'validation-harness/native-sampling-validation/method-map-v4.json').read_bytes()
 assert geometry['methodMapSHA256']==hashlib.sha256(method_raw).hexdigest()
 assert geometry['methodPartition']=='single-tier-v1'
 assert geometry['candidateMatrixMethodsPerDPR']==22 and geometry['baselineMatrixMethodsPerDPR']==2
 # Four sampling lane totals are backed by exact independent one-selector results.
 for expected_run in selection['runs']:
  if expected_run['lane'] not in ('sampling-baseline','sampling-candidate'): continue
  result=next(r for r in report['results'] if r['runName']==expected_run['runName'])
  base=evidence/result['evidencePrefix']
  children=result['children'];selectors=sorted(expected_run['selectors'])
  assert len(children)==expected_run['expectedCount'] and [c['selector'] for c in children]==selectors
  proof_raw=(base/(expected_run['lane']+'-build-for-testing-proof.json')).read_bytes()
  assert hashlib.sha256(proof_raw).hexdigest()==result['buildProofSHA256']
  proof=json.loads(proof_raw)
  assert proof['nativeAcceptance'] is False and proof['sourceExcludedPaths']==['build/']
  assert proof['config']['scheme']=='FlashNestSamplingUI' and proof['config']['configuration']=='Debug'
  assert proof['config']['sdk']=='iphonesimulator' and proof['config']['xcode']=='16.2' and proof['config']['os']=='18.2' and proof['config']['signing'] is False
  assert proof['sourceFiles'] and proof['productFiles'] and proof['references']
  staging=json.loads((base/(expected_run['lane']+'-staging-provenance.json')).read_text())
  expected_built_app=staging['gateOffAppFiles'].copy()
  for path,change in staging['changedAppFiles'].items():
   assert expected_built_app[path]==change['before'];expected_built_app[path]=change['after']
  arm=expected_run['lane'].removeprefix('sampling-')
  approved_project=lock['lanes']['native']['samplingProjectSHA256'][arm]
  assert proof['sourceFiles']['project.yml']==approved_project
  generated=verify_generated(base,expected_run['lane'],approved_project)
  assert proof['generatedAppFiles']==generated
  assert proof['generatedAppFilesSHA256']==hashlib.sha256((base/(expected_run['lane']+'-generated-app-files.json')).read_bytes()).hexdigest()
  assert not set(expected_built_app)&set(generated['files'])
  expected_built_app.update(generated['files'])
  assert {path:digest for path,digest in proof['sourceFiles'].items() if path.startswith('App/')}==expected_built_app
  assert set(proof['approvedDestinations'])=={'2','3'} and proof['config']['firstDestination']==proof['approvedDestinations'][result['evidencePrefix'][-1]]
  assert set(proof['preflightReceiptSHA256'])=={'xcode-version.log','available-devices.log','tool-receipt.json','binding.json'}
  for name,digest in proof['preflightReceiptSHA256'].items():
   assert hashlib.sha256((base/name).read_bytes()).hexdigest()==digest
  xctestrun_relative=Path(proof['xctestrun']).relative_to(Path(proof['products'])).as_posix()
  assert proof['productFiles'][xctestrun_relative]==proof['xctestrunSHA256']
  for index,child in enumerate(children,1):
   child_name=expected_run['runName']+'-selector-'+str(index).zfill(2)
   child_raw=(base/(child_name+'-verification.json')).read_bytes()
   assert hashlib.sha256(child_raw).hexdigest()==child['verificationSHA256'] and json.loads(child_raw)==child['report']
   actual=child['report']
   assert actual['runName']==child_name and actual['lane']==expected_run['lane'] and type(actual['tests']) is int and actual['tests']==1
   assert actual['semanticResultValid'] is True and actual['osVersion']=='18.2'
 for boundary in (r for r in report['results'] if r['lane']=='sampling-enhanced-boundary'):
  candidate_build_raw=(evidence/boundary['evidencePrefix']/'sampling-candidate-build-for-testing-proof.json').read_bytes()
  assert boundary['buildProofSHA256']==hashlib.sha256(candidate_build_raw).hexdigest()
 authority_raw=(ROOT/'validation-harness/native-sampling-validation/approved-candidate-app-source-manifest.json').read_bytes()
 assert hashlib.sha256(authority_raw).hexdigest()==report['candidateAppSourceAuthoritySHA256']
 authority=json.loads(authority_raw)
 expected_app={p:h for p,h in lock['appSourceManifest']['files'].items() if p.startswith('App/') and not p.startswith('App/Resources/Web/runtime/')}
 assert {r['path']:r['sha256'] for r in authority['files']}==expected_app
 negative_raw=(ROOT/'evidence/native/legacy-automatic-known-negative.json').read_bytes()
 assert hashlib.sha256(negative_raw).hexdigest()==report['legacyAutomaticKnownNegativeSHA256']
 negative=json.loads(negative_raw)
 packet_raw=(ROOT/'validation-harness/native-composite-runner/legacy-automatic-negative/manifest.json').read_bytes()
 assert negative['packetManifestSHA256']==hashlib.sha256(packet_raw).hexdigest()
 assert negative['sourceRun']==json.loads(packet_raw)['sourceRun']
 assert negative['knownNegativeOnly'] is True and negative['nativeAcceptance'] is False and negative['historicalRunStatus']=='failed'
 assert negative['contextLossAndMissingVectorConfirmed'] is True and negative['legacyPolicyUnmodified'] is True
 assert geometry['shippingRows']==36 and geometry['diagnosticRows']==12 and geometry['phases']==144
 assert geometry['trustedTaps']==720 and geometry['trustedDrags']==144
 enhanced=geometry['enhancedBoundaryDiagnostic'];assert enhanced==report['enhancedBoundaryDiagnostic']
 assert enhanced['configurationAndErrorBoundaryVerified'] is True and enhanced['diagnosticOnly'] is True and enhanced['nativeAcceptance'] is False
 assert enhanced['platformRenderHealthCertified'] is False and enhanced['contextLossUserErrorReportingCertified'] is False
 assert enhanced['explicitNavigationFailureVisibilityVerified'] is True
 observations=enhanced['observations'];assert len(observations)==6
 assert {(r['dpr'],r['label']) for r in observations}=={(d,label) for d in (2,3) for label in ('ready','after-5s','after-15s')}
 assert all(r['nativeAcceptance'] is False and r['platformRenderHealthCertified'] is False and r['observedOutcome'] in ('bounded-visible','bounded-unhealthy','bounded-unverified-backend') for r in observations)
 assert geometry['historicalStaleDownNegativePhases']==12 and geometry['candidateCurrentDownUpPhases']==132 and geometry['fixtureResetsAfterObservedUp']==864
 assert report['candidateAudioGateOn'] is True and report['candidateAudioMatchesPostGeometryApp'] is True and report['historicalAudioGateOff'] is True
 # Independently bind the audio App build inputs/resources to the final App with only
 # the already-reviewed production gate flip, not just the runner's boolean report.
 audio_raw=(ROOT/'evidence/native/audio-candidate-post-geometry-app-map.json').read_bytes()
 assert hashlib.sha256(audio_raw).hexdigest()==report['candidateAudioAppManifestSHA256']
 expected_audio={p[len('App/'):]:h for p,h in lock['appSourceManifest']['files'].items() if p.startswith('App/')}
 gate=(ROOT/'validation-app-template/App/Player/RenderSamplingSettings.swift').read_bytes()
 assert hashlib.sha256(gate).hexdigest()==expected_audio['Player/RenderSamplingSettings.swift']
 old=b'static let runtimeValidated = false';new=b'static let runtimeValidated = true'
 assert gate.count(old)==1
 expected_audio['Player/RenderSamplingSettings.swift']=hashlib.sha256(gate.replace(old,new)).hexdigest()
 assert json.loads(audio_raw)==expected_audio
 verify_generated(evidence,'main-gate-on',lock['appSourceManifest']['files']['project.yml'])
 assert geometry['actualShippingReductionPolicies']==report['shippingPoliciesWithAllReductions']
 assert report['audibleOutputProven'] is False and report['privateProviderReproduced'] is False and report['ipaBuilt'] is False
print('PASS final lane receipt cross-binding',lane)
