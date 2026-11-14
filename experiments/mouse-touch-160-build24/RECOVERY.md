# Explicit recovered source baseline, build26

The old audio verification artifact12783974867 from run40614335019 is unavailable. Its exact22076102-byte ZIP, SHA2563befcb048669c074a017e2bfb6d3ccc283028ef90d7960695bbf0964a2634e9a, was not recovered.

This recipe does not execute or claim success for the old materialization chain. It independently derives the existing230-file candidate hash map from fixed baseline, case and delivered manifests plus the current mouse overlay. The only removal is vendor/ruffle-audio-recovery-40614335019.zip. All other229 files retain their exact prior SHA256, including all App, Tests, UITests, current runtime and current offline engine archive. The missing historical ZIP was not packaged into the IPA.

recovery-manifest.json records every retained byte source or deterministic transformation. recovery_stage.py verifies the fixed checkout identities, source hashes, all output hashes, the original current-engine reuse verifier and native-probe generator. It emits a new explicit recovery receipt. No missing archive or old staging success is fabricated.

The original selected92 native tests,3 UI tests, path and cadence matrices, and actual mouse SWF event/frame gates remain required in the current run. A build cannot be uploaded as successful without those gates and independent unsigned IPA verification. User games are not test inputs. Formal main, tags and releases are untouched.

## Archived current-engine recovery (2026-11-14)

The original engine artifact from run 41318527222 is no longer downloadable.
This run uses a retained ZIP, byte-for-byte equal to the original 15,260,480-byte
archive (SHA256 `dac0c326e29d2cfd354eb418000ac049fa7bdcfaa56b7693132f5799661d52c2`).
`engine-backup.json` is an explicit backup descriptor, NOT a fabricated GitHub API
response. `restore_engine.py` executes the original pinned full-archive validator
and source comparisons, then writes a separate archival restoration receipt.
Old engine/core test evidence remains historical; current native/UI/browser tests
must execute and pass before packaging. The prior 70 Node tests are simulated DOM
logic tests, not proof of physical-device or real system-background behavior.

The new workflow targets one exact experimental branch on standard macos-15.
It stops subsequent test/build stages on the first failed stage, keeps diagnostic
logs, and performs no release, tag, main-branch update, or automatic retry.

The backup is stored as two ordered transport parts to fit the upload API limit.
Concatenating `.part01` then `.part02` restores the original ZIP exactly; neither
part is a standalone ZIP. The full original SHA256 is checked before consumption.
