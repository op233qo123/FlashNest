# Neutral AVM2 texture lifetime fixtures

These five synthetic SWFs contain only mathematical JPEG/alpha patterns and locally authored ActionScript. No game material or private input is used. All bitmap source planes are 512×512 RGBA; displayed fill geometry is 64×64. The primary visible rectangle is (32,32)–(96,96).

## Stable phases

- `root-16.swf` and `root-64.swf`: begin on blank frame1. Trusted S starts one traversal of all16/64 distinct symbols. Each resource remains selected for four ENTER_FRAME ticks, with a `settled resource=N cycle=C` marker. At `cycle=C`, the code stops traversal and retains the final visible symbol. R repeats a traversal in the same player. U returns to blank frame1; **root definitions and Library remain alive**. The runner must render after each stable marker, not infer displayed pixels merely from the trace.
- `loader-release.swf` and `loader-retain.swf`: S performs six real Loader loads of relative `texture-child.swf?cycle=N`, displaying each for eight normal frames then calling `Loader.unload()` and removing the Loader. Eight further normal frames precede the next load. The retain variant holds the first three content objects in an AS array; the release variant holds none. At `complete`, R re-adds retained content and calls its `ping()` method. U removes content, clears the array and waits120 normal frames before `done`. No forced GC or explicit BitmapData disposal occurs. `loaded=N` and `unloaded=N` markers expose every cycle.
- `texture-child.swf` has one bitmap-fill shape and a ping method. It is support content, not a separate top-level measurement case.

The manifest defines exact stable trace strings, trusted keys and expected visibility. Browser texture counters still require API-level classification; texture-size budgets are not physical GPU memory. A finite no-delete interval cannot prove a leak or lack of driver reclamation.

## Reproduction

Compiler: official Ruffle `tools/asc/asc.jar` at upstream commit89a7049965f3090e706265670df309a5128233ac, SHA256 recorded in `provenance.json`. Java is used only locally to compile these fixtures. The jar and compiler cache are not published in this experiment.

Build import ABC from the same upstream618 AVM2 global source files (each checked against Git blob identities), using its `macromedia.asc.embedding.ScriptCompiler` with `-optimize -builtin -apiversioning -outdir <tools> -out playerglobal_avm2`, then `Toplevel.as globals.as`. For each authored class, use `java -jar asc.jar -AS3 -import playerglobal_avm2.abc <class>.as`. Move emitted ABCs to `abc/`.

Run `python generate.py` with Pillow13.0.0, then `python test_fixtures.py`. Generator JPEG output is version-bound; checked-in SWF/ABC hashes are the CI input contract. The raw `reference_generate.py` bit/record encoder comes from the previously committed neutral fixture generator and does not run its standalone main block.

Static tag/source checks have passed locally. Actual AVM2 execution, phase progression and rendering are pending browser CI; source compilation is not runtime acceptance.
