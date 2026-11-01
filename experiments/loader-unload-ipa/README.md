# Experimental unload-fix diagnostic IPA

This authorized test-package recipe preserves the existing 1.5.6 build23 diagnostic-v2/import-warning/case-compatible app source and integrates the exact reviewed Loader lifecycle candidate engine. It does not update main, tags or official releases.

The engine is reused byte-for-byte from run 41318527222, artifact 13089357368 (SHA256 dac0c326e29d2cfd354eb418000ac049fa7bdcfaa56b7693132f5799661d52c2). Its twelve-scenario neutral browser regression was independently verified in run 41322027104. The earlier engine/core execution is identified as reused, never relabeled as this run's execution.

Native integration tests are **new executions with the candidate runtime**: the original 76 selected native methods, two test-target-only WKWebView Loader smoke methods, and the original two import UI methods. The case-sensitive APFS resolver checks and neutral cadence controls also execute again. No private game assets are inputs. Neutral fixtures exist only inside the DEBUG XCTest source, not application resources.

The workflow uses standard macOS 15 and verifies an installed supported Xcode/iOS SDK/runtime tuple. It prefers Xcode16.4/iOS18.5; actual toolchain details are recorded. This differs from the older Xcode16.2/iOS18.2 package when selected, and is not disguised as the same SDK.

Product integration changes are restricted to the twelve runtime files, required source-modification/license-manifest notices, and accurate runtime identity/lock/manifest metadata. The offline archive and strict schema consumer are rebound to this exact candidate; the existing fetch and bundled-runtime verification gates remain unchanged. The recipe exercises the unchanged offline install and bundle gates, including negative tamper, stale, missing and symlink cases, before the full fresh native rerun. Diagnostics remain revision2/default-off; import warnings and unique case fallback remain unchanged. Release-package checks reject test fixtures, signatures, provisioning profiles and DEBUG-only harnesses, require unsigned arm64 device code, and compare all packaged Web bytes.

The output is a distinct unsigned 1.5.6 build23 test IPA. Passing simulator and neutral tests is not a claim that the user's game or physical device is fixed; real-device feedback remains necessary.
