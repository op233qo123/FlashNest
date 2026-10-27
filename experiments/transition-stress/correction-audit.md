# Diagnostic fixture correction: reserved pushstring index

The first Chrome smoke run [40537957524](https://github.com/op233qo123/FlashNest/actions/runs/40537957524) reported `VerifyError #1032: Cpool index 0 is out of range 114` while executing `LoaderTransitionRoot/frame1()`, before any LT trace. This was an error in our original diagnostic assembler/structural validator, not evidence of a Ruffle engine defect. The original raw failure artifact remains historical evidence and is not rewritten.

## Exact source and bytecode chain

At pinned Ruffle commit `89a7049965f3090e706265670df309a5128233ac`:

- [`verify.rs` lines 723–726](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/avm2/verify.rs#L723-L726) translates PushString through `pool_string_or_err`.
- [`script.rs` lines 264–279](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/avm2/script.rs#L264-L279) explicitly rejects string index zero. Its separate `pool_string` API permits zero in contexts where the implicit empty string is valid; these APIs are not interchangeable.
- [`error.rs` lines 492–505](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/core/src/avm2/error.rs#L492-L505) adds the implicit entry to the reported pool length. The old root stores 113 explicit strings, yielding the observed upper bound 114.

Independent decode of the old root finds illegal `pushstring 0` at these method-relative byte offsets:

| Method | Offset |
|---|---:|
| mark | 126 |
| onResize | 9 |
| onKey | 23 |
| onClick | 20 |
| onComplete | 90 |

`frame1` itself has no such instruction; its byte offset 126 calls `mark` for BOOT. Verification failure in that called method before emitting a trace is consistent with the observed caller stack and zero LT traces. The artifact does not contain a measured failing instruction offset, so the byte offsets above are static decode evidence, not an invented runtime PC.

The assembler deduplicated `push("")` to reserved string entry zero; the previous structural validator incorrectly accepted zero for that instruction. The correction changes only literal-string handling: an empty literal gets an explicit nonzero pool entry (22 in the corrected root). Package namespace names may still use their valid reserved zero. The strict validator now rejects zero pushstring operands, with method and byte offset in its error.

## Byte identity and scope

- Old root: 2743 bytes, SHA256 `7671411b8be327cb9cc105a782d14c9e999e828dbd2125268f2c913d5ddae151`.
- Corrected root: 2744 bytes, SHA256 `9e6f0768d08018c2ae324dbc61d33eb1d62378f8c7de7b30bc054e1a74a63878`.
- Child remains byte-identical: 965 bytes, SHA256 `7f5015789f368ac2221d47930d255b204828f9d33384c14f36e6ed947edf58c8`.
- Former helper SHA256 `d8d7f30cc2edc06fda039f0d57fc8b8e38126b5f98d0b6b7b82e0de464de6701`; corrected helper `41a549bf200bac3bb97d55273d36da8bd6311ca3ed6922979d0faa6865843fef`.

All 19 root methods retain their decoded opcodes, instruction offsets, branch targets, resolved names, string values and non-pool operands. Only constant-pool encoding changes. Reference AS source, load/unload choices, input/milestone predicates and runtime bytes are unchanged. No fixture output assertion is weakened. Eight local structural/unit tests pass, including explicit-empty-string interning and rejection of reserved pushstring zero. Corrected runtime execution is still required; structural checks are not a substitute.

The separately running 799-byte audio fixture (`e25f5dba4162a25b9a07832be4e6f8f62242734f6f39e92983c53467a28e7fd2`) was independently reparsed with the stricter rule: five methods, four pushstring instructions, no zero operand. Its frozen bytes/helper/manifest were not edited. That excludes this specific bytecode defect, not every possible fixture or audio issue.

Prior native GPU/WebContent terminations remain independent observations. Correcting a diagnostic verifier error does not establish or dismiss the cause of those terminations, and does not repair any user-game or production engine behavior.
