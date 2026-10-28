# Ruffle modification and source correspondence

## Experimental composite identity

FlashNest composite experimental 0434fe9a2a3d uses upstream Ruffle 0.7.1 commit `89a7049965f3090e706265670df309a5128233ac`. It is modified software, not an official upstream release or a universal stability fix.

The exact modified-source set SHA-256 is `0434fe9a2a3d2e4637938f6b0f67fe7eff17dd777ea940f02b29febc8b6d70aa`. The engine's provenance.json records the actual build source commit/run, full before/after source inventory, original locks, tool versions, version seal and complete runtime inventory. The accompanying source-correspondence includes exact modified sources, original three ordered patches followed by the final composite patch, build scripts, source lock, reviewed production-GC policy and full license texts. This is reconstructible correspondence, not a claim of independently reproduced binary identity.

## Included changes

The original queued-goto guard, WebAudio context lifecycle cleanup and source-owned audio resume/rejection handling remain. The composite additionally includes reconstructible rendering-cache release, cancelled-load generation checks, stale-parent reentrancy guard, owning audio payload handles, traced semantic MovieLibrary ownership with weak registry and frame-admitted incremental GC scheduling, and reduced render backing densities with unchanged logical geometry. Unsupported renderer/MSAA paths fall back to Original.

Default quality is not forcibly changed: existing mobile detection may select Low; otherwise the upstream default applies. Sampling preference, requested mode and actual applied/fallback status are distinct. Renderer/density changes do not migrate saved-game data.

No new runtime dependency or changed Cargo/npm lock is introduced. Original copyright notices are preserved. Source/probe/test fixtures are not bundled as game assets in the final App.

## Evidence boundary

Engine construction alone does not establish native visual/input, audio/save, physical-device memory or crash acceptance. The final package must consume the exact tested runtime inventory, with separate results naming what ran. Synthetic simulator/browser checks do not certify every private game, unknown file provider, audible speaker output, all graphics hardware or unexplained WebContent termination. No user game, save or reproduction video is included in the public source correspondence.

[Fixed upstream source](https://github.com/ruffle-rs/ruffle/tree/89a7049965f3090e706265670df309a5128233ac). The actual derivative source link and run ID are supplied by the artifact's sealed provenance.
