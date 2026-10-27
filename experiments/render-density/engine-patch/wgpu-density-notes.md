# Experimental WGPU dual-size viewport patch

Status: implemented and source-checked; **not compiled or GPU/native-tested**.
This is one component of a proposed render-density API, not a runtime pin or a
release. It does not include or modify the independent queued-goto guard.

## Base and exact scope

Base: Ruffle commit `89a7049965f3090e706265670df309a5128233ac`.
`wgpu-density.patch` changes exactly four files:

| File under `render/wgpu/src/` | Original SHA-256 | Modified SHA-256 |
| --- | --- | --- |
| `backend.rs` | `a1fb1cd3a58776c04faf5bbb7d416148bd6855b271399d1f830e2f13c8afbd05` | `791f3a51e16719770739ae82e4dca7bf4b843252dc80e9b175e2dd2102176ca0` |
| `surface.rs` | `e947f13637eb1820c4601b5d7cd3eb35c0afde6d2ca82b2f7c6b546275a13bfd` | `f0e7655c8ea7422a0c51702dee6cfb01cde1de4b82f49add03bad880219167e1` |
| `surface/commands.rs` | `b048f76494fd780f43dbd8da7020f77ef00829454eeaa754d8c4535b342faeba` | `7652d605d47e4b2568859e79a0dabb3994ec3005c1f1d16bae62fa1b06641c5c` |
| `surface/target.rs` | `14e9e258647c1de98ce84b8ba2f9e4beaef15f57f7f21706dbe28614b5dc6517` | `769e55726b0ca1af6251210c922332d7066553dabbcec4637a97641046e42928` |

Patch SHA-256:
`dee72fec368345d1d91bbad7e2a16b19328ce48f3e97f8f35217672639b91e09`.

Original bytes were fetched from the pinned official repository. The source
checker verifies all four Git blob IDs, not just locally generated hashes.
No core Stage, input, ActionScript, frontend, Canvas, WebGL, shaders, or
queued-goto source is included in this patch.

## Interface dependency

The parent component must add this optional `RenderBackend` trait method, with
a default implementation returning `false` without mutation:

```rust
fn set_viewport_dimensions_with_backing(
    &mut self,
    dimensions: ViewportDimensions,
    backing_width: u32,
    backing_height: u32,
) -> bool;
```

This patch implements it for WGPU. `dimensions` remains the stock virtual
viewport: native-DPR-scaled integer size and unchanged native DPR. Backing
dimensions are independently rounded positive integers, never larger than the
virtual viewport. The frontend owns tier validation, canvas attributes, and
fallback: on `false`, restore original canvas dimensions and call the legacy
setter. A successful return is acceptance of dimensions, **not** proof of a
completed render or successful GPU allocation after asynchronous device loss.

The method rejects zero dimensions, invalid/nonpositive DPR, supersampling, and
virtual dimensions exceeding the existing texture limit before mutation. It
does not use lower density to bypass a limit that would clamp the baseline.
The identity-size case calls the old setter. The old setter clears the optional
override, and otherwise retains its exact old resize/allocation body.

## Coordinate separation

- `WgpuRenderBackend` reports the virtual size/DPR to core while resizing its
  target to the physical backing. Tier changes do not require changing Stage
  matrices, logical size, pointer conversion, filters, or render commands.
- `Surface` defaults its projection size to its physical size. The onscreen
  surface alone receives the virtual projection override.
- `CommandTarget` retains physical textures and replaces only its cached global
  projection uniform when the two sizes differ. `Globals` and shader source are
  unchanged. The existing globals pool already keys by projection width/height.
- Nested onscreen blend and alpha-mask surfaces inherit both dimensions. Their
  physical textures remain small; their compositing quads use the **virtual**
  extent so they still fill the same viewport. Omitting either propagation or
  virtual quad extent would crop/shrink blended content.
- Quality changes retain projection size. Existing next-texture recovery still
  resizes the target using its physical width/height; this code is unchanged.
- Cache/filter/BitmapData surfaces keep ordinary identity construction. Stage3D
  backbuffer creation is unchanged. Therefore no reduction is promised for
  those allocations, texture assets, script CPU work, or total process memory.

This is intended to reduce onscreen render-target pixel count without altering
logical geometry. It does not render at full resolution and then merely shrink
the final canvas. Raster sampling, antialiasing, thin lines, and pixel-based
shader blend effects can still look different at lower density; visual gates
are required, and no blanket pixel-equivalence claim is made.

## Primary-source review

At the pinned source, [backend viewport allocation and reporting](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/render/wgpu/src/backend.rs#L427-L455)
couple target size to the reported viewport. [Surface command rendering](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/render/wgpu/src/surface.rs#L105-L144)
passes that size into blend processing. [Blend composition](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/render/wgpu/src/surface/commands.rs#L709-L787)
and [alpha-mask composition](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/render/wgpu/src/surface/commands.rs#L965-L999)
are the additional dimension-sensitive paths handled here.

All 31 Rust files under pinned `render/wgpu/src` were searched read-only for
`Surface` construction, `CommandTarget::new`, and `chunk_blends` call sites.
The free `chunk_blends` caller is `Surface::draw_commands`; other
`CommandTarget::new` uses are filter paths and retain the original constructor.
The [copy shader](https://github.com/ruffle-rs/ruffle/blob/89a7049965f3090e706265670df309a5128233ac/render/wgpu/shaders/copy.wgsl)
emits normalized device coordinates directly and does not use the bound globals.
Its shader and copy pipeline therefore remain unchanged.

## Checks performed

```sh
python3 check_wgpu_density.py --original ORIGINAL_SOURCE --modified PATCHED_SOURCE
patch --dry-run -p1 < wgpu-density.patch
```

Passed: four pinned Git blob checks; exact patch reconstruction; legacy setter
body except override clearing; unchanged cache rendering, Stage3D creation,
offscreen rendering, and next-texture recovery; dual-size propagation and quad
source assertions; 80 algebra cases covering odd/portrait/landscape/tiny sizes,
DPR 1/1.25/1.5/2/3, and tiers 1/.75/.5/.25. Applying the patch to a temporary
copy reproduced all four modified files exactly. Algebra/source assertions do
not run Rust, ActionScript, shaders, Stage, or hit tests.

## Required before runtime use

1. Compile/type-check both WGPU web targets with the agreed trait/core wrapper;
   run formatting and lint checks. No Rust toolchain is installed in this review
   environment, so compile plausibility is not a compilation result.
2. Prove original/default output and behavior remain unchanged. Test all four
   Stage scale modes and alignments with odd sizes and DPR 1/2/3 (also fractional
   DPR), including no density-only resize events and unchanged Stage getters.
3. Compare actual pointer hits, local/global coordinates, drag continuity,
   letterbox edges, focus outlines, text, nested masks, alpha masks, simple and
   complex blends, shader blends, cached/filtered objects, `BitmapData.draw`, and
   3D/perspective composition across tiers. Retain screenshots and raw values.
4. Exercise quality changes, repeated tier changes, zero/hidden viewports,
   rotation/DPR changes, invalid requests, limit rejection, and renderer/device
   loss/recovery. Confirm requested/applied sizes from actual canvas/target data.
5. Re-run the unchanged queued-goto fixture/control and adjacent engine gates,
   followed by isolated native regression and lifecycle checks. No new binary
   should replace the current pin based only on these source checks.
