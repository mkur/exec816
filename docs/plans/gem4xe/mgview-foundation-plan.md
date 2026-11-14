# MGVIEW drawing and window foundations

[GEM plans](README.md) · [VDI contract](../../reference/gem-vdi.md) ·
[AES contract](../../reference/aes.md)

Status: proposed, 2026-11-14. Implement MV1–MV3 in order and commit each
passing executable slice separately. This delivers shared drawing/window
services needed by MGVIEW; the application port, mouse calls and window
animations remain separate work.

## Source and architecture

Use GEM4XE as the behavioral reference and preserve provenance for extracted
code. The existing 0.9.4 source at
`e413c39d2f8e1bec8fe16596f610b923de4a0ae9` already supplies these algorithms;
the audit also checked 0.17 at
`ac476b8bdeda63b8b53ad22ec25b9d88bd7886af`. Pin selected files and hashes,
distinguishing extracted implementation from independently written bindings.
Keep donor GPL implementation under `ports/gem4xe/`; public C bindings retain
their existing licence.

Keep Exec's caller-owned workstation state, shared native window policy,
Layers visibility, UPDATE ownership and ordinary Task preemption. Geometry
changes keep the existing commit/effect protocol; physical input sends
application-acknowledged messages. Add no worker, kernel operation, polling
loop, global VDI parameter block or bank-zero reservation.

## MV1: text alignment, text inquiry and rectangle fill

- Add named and parameter-block `vst_alignment` (39), `vqt_attributes` (38)
  and `vr_recfl` (114) through common helpers. Record counts in the binding
  manifest and publish the new named calls to loaded C applications.
- Store horizontal/vertical alignment per workstation. Keep left/baseline
  defaults; accept the conventional three horizontal and six vertical modes,
  with donor fallback for out-of-range input. Convert the entire text origin
  once before streaming chunks; return actual fixed-face metrics and state.
- Reuse the current ordered, widened, clipped solid rectangle path. Retain
  UPDATE admission, damage, hardware batching and error reporting. No new
  patterned-fill or perimeter capability is advertised.
- Check small emitted raw/optimized layout and public/PB behavior probes,
  including two workstations, rejected handles, long/empty strings, clipping,
  top/baseline alignment and rectangle ordering. Use the focused optimized
  graphical VDI fixture for physical pixels and preemption.

## MV2: full and previous window rectangles

- Add `WF_FULLXYWH`/`WF_FXYWH` and `WF_PREVXYWH`/`WF_PXYWH` queries.
  Full geometry is the rectangle supplied at creation; previous geometry is
  initialized on open and updated only by a committed normal geometry change.
- Preserve both through hide/show, top changes and iconification; failed or
  unchanged mutations do not replace previous geometry. Keep state in the
  shared window view so named/PB and caller/system paths agree.
- Generate layouts and rebuild current ABI callers together. Check emitted
  raw/optimized record access and optimized geometry/lifetime behavior,
  including two windows, rejected moves, resize and close/reopen.

## MV3: horizontal scrollbar support

- Publish `LFARROW`, `RTARROW`, `HSLIDE`, `WF_HSLIDE`, `WF_HSLSIZE`,
  `WM_HSLID` and the four horizontal `WM_ARROWED` actions. Extend the native
  frame-kind encoding without colliding with borderless/iconified flags.
- Adapt donor bar/track/thumb geometry to Exec's existing frame metrics and
  slider range 0–1000. Store horizontal position/size and cached thumb geometry
  per window; update work-area calculation, minimum bounds, painting, hit
  testing and drag capture together. Preserve existing vertical behavior and
  slider-size admission semantics.
- Add horizontal arrow/page clicks, drag endpoints, cancellation and deferred
  acknowledgement through the existing input/message path. Frame setters
  retain existing ownership, no-op, hidden-window and repaint behavior.
- Check focused emitted layout access in both modes; optimized geometry,
  physical frame pixels, arrows/pages, slider dragging and cancellation;
  current vertical regressions and independent Counter lifetimes. Do not use
  QED as the routine integration workload.

## Completion and delivery

Use development-tier checks, not the release qualification matrix. Run the
host suite and affected generators after each code slice. Update current
reference contracts and retain exact executed scope in a development record.
Refresh the final demo once, with all current ABI applications rebuilt, through
`tools/build_demo.py`; retain OF816 and the five-second standard autoboot.

For each implementation commit, report fixed/root/kernel/idle and per-Task
reserved bank-zero deltas, including guards, alignment and unused capacity.
Expected deltas are zero; additional window/workstation fields live in upper
RAM. Measure actual structure growth and verify the generated memory maps.
