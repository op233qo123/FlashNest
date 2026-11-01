# Experimental Loader unload lifecycle candidate

This isolated recipe investigates and fixes a neutral Loader event omission. It is not an official release, IPA, Flash reference conformance result, or private-game/iOS compatibility verdict.

The accepted baseline is Ruffle `89a7049965f3090e706265670df309a5128233ac` plus the six patches and source lock published by FlashNest commit `6d3e4322293972a28ab2cdf129ee6398f40f0f37`. The candidate must first reconstruct and verify that exact source, then apply only the separately reviewed lifecycle delta. Existing lazy registration and resource fixes remain part of the candidate.

The baseline browser runtime comes from the exact previously delivered diagnostic artifact, not a fresh baseline rebuild. Candidate runtime bytes come from this workflow's actual build. Each actual browser-selected WASM response and every neutral SWF response is hashed. Both runtime inventories, source identities, runner/GPU identity, event traces and finite observation windows are preserved in evidence.

A successful baseline observation means the previously reproduced omission is observed under valid controls. A successful candidate regression run means the specified neutral controls pass; neither result proves an application-wide fix. No private game assets, names or filesystem paths belong in this recipe or its artifacts.

No workflow here changes main, tags, releases, game files, application packaging, browser sandbox settings or security settings.
