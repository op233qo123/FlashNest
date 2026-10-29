# One sized-bitmap scene diagnostic — local preparation only

This is an isolated successor to d26450da. Do not mutate or reinterpret the prior successful body/Loader case. No external publication/CI is authorized by this package. It is one sized-bitmap case, one device/current Automatic+Original policy, same WK/same Loader, one original Space down/up transition, ≤120s active/32 native observations and ≤10s final evidence. No renderer/GPU/runtime/product changes, repeated loop, audio, VM sweep, readPixels/getError or forced GC.

## Exact workload / reproducibility

Old/new original DefineBinaryData tag lengths and entire payload hashes are unchanged; composition-proof.json binds the prior frozen manifest and both exact tag identities. No padding was retuned to manufacture the old total file length. Each child adds ONE valid DefineBitsLossless2 id2, format5,1024×1024 opaque ARGB (4194304 logical decoded bytes). SymbolClass maps id2 to SceneBitmap extends BitmapData; SceneChild explicitly instantiates it into a Bitmap. This uses actual embedded bitmap decode, unlike the prior unused binary id1. No claim that logical pixels equal process/GPU allocation or that resources are reclaimed.

Original binary id1 remains uninstantiated. Old palette quadrants red/green/blue/white; new cyan/magenta/yellow/black. Display bitmap at stage(32,32), width/height256. Parent explicitly noScale/TOP_LEFT; old first-frame + INIT/COMPLETE emits old.awaiting-space and holds. Only keyCode32, only once, then before-unload→unload→new; new independent first-frame/INIT/COMPLETE→parent.done. Source-defined four quadrant centers are(96,96),(224,96),(96,224),(224,224) CSS units. Runtime first-frame may precede INIT; neither proves physical display.

Native runner must first capture/verify old bitmap pixels and nonzero passive draw count, then one existing session.key Space pair. It must capture distinct new pixels and a greater draw count. Source/protocol holds are explicit diagnostic changes, not claimed existing-game behavior. Production allowScriptAccess=false remains; no ExternalInterface.

`compile_abc.py --asc PATH --imports PATH` verifies small ABC regeneration with existing pinned ASC/playerglobal hashes in compiler-provenance.json. Parent2507B/child986B compiled twice exactly. SceneBitmap source is compiled into child via -in; no separate large compiler upload.

`generate_fixtures.py --out DIR` creates only sized-bitmap/main.swf,old.swf,new.swf plus manifest. It validates AS/ABC pins, preserves original binary payload identities, independently decodes CWS/bitmap zlib and tag structure, and demands exact frozen fixture-manifest.json equality. RFC1950/1951 explicit stored/fixed-Huffman encoding avoids system compressor-version drift. The image uses fixed-Huffman length/distance4 repetitions; independent zlib decode verifies actual pixels. No private assets are inputs.

Exact compressed/decoded SWF sizes: parent2593/2566, old12630171/13668527, new45165019/50368687 bytes. Combined compressed package remains<64MiB. Big generated CWS files must NOT be published; only this small source/ABC/manifest closure is a prospective payload.

## Independent evidence contract

`verify_phases.verify_native(out,expected_identity,fixture_manifest_path)` consumes bitmap-scene-controls.log and attachments/bitmap-scene-controls. Existing scene observation/case markers plus exactly2 FLASHNEST_BITMAP_VISUAL_JSON records, labels old/new. Partial failure retains raw observations/visuals and last AS/body phase; original timeout/errors cannot be erased by later pixels.

`pixel_oracle.py` reopens actual hash-bound raw-CG PNG, UIKit-normalized PNG and canvas crop. It independently verifies orientation dimensions, image points×scale, screen/DPR, integral crop from native viewport+canvas CSS, no clipping/stretching, and exact crop pixels equal the normalized source. It does NOT infer geometry from actual colored pixels. Four5×5physical-pixel interior patches must match source palette RGB±2 and alpha255, with exact independently recomputed min/max matching Swift records. Center pixels use roundHalfUp(stageCenter*dpr+canvasScreenOrigin−integralCropOrigin), including fractional origin correction. Same PNG bytes in distinct captures are legal; hashes are locators, not unique capture IDs.

Old visual must precede the sole native transition timestamp, have transitionCount0, old.awaiting-space and no new request; new visual must follow it with transitionCount1, completed17-phase sequence and draw sum greater than old>0. Both snapshots must be members of the bounded externally identified same-WK observation history. Final configuration remains exact iOS18.2/DPR2/Automatic requested preferredwebgl/Original1/defaultquality and observed WASM in external inventory. Existing draw counters are passive; renderbuffer allocation tuples are NOT texture upload counts. Reports explicitly textureUploadCountMeasured=false/gpuMemoryReclamationProven=false/nativeAcceptance=false/renderHealthCertified=false.

## Local verification, not native acceptance

`python tests/test_native.py` runs7 unique Python methods (5 fixture/pixel/core-phase controls imported plus2 native join/negative controls). `node tests/test_observer.js` checks unchanged body observer identity/bounds. Pinned ASC recompilation and second generated SWF set byte comparison pass. Actual local null-core fixture emitted17 semantic phases with one synthetic Space pair; its empty Flash golden run remains FAILED and is not reclassified. Independently verifying phase semantics is not a Flash golden, native screenshot, texture presentation or memory improvement claim. Actual Xcode/native execution is pending separate user/root approval.
