# Original MagiC MGVIEW port

[GEM plans](README.md) · [Planning index](../README.md) ·
[GEMDOS contract](../../reference/gemdos-compatibility.md) ·
[AES contract](../../reference/aes.md) · [VDI contract](../../reference/gem-vdi.md) ·
[Window foundations](mgview-foundation-plan.md) ·
[Mouse delivery](../../history/gem-mouse-calls.md)

Status: proposed, 2026-11-14. Implement MP1–MP6 in order and commit each passing
executable slice separately. This plan ports the original MGVIEW application;
the existing Exec Text application and Mouse probe remain separate programs.
Planning records no new executable qualification.

## Outcome and scope

Deliver a disk-loaded `MGVIEW.APP`, rebuilt from MagiC's original viewer sources,
which opens native command-line paths, displays text, scrolls both axes, handles
ordinary GEM window operations and retires cleanly beside a Counter. Preserve
the original line index, tab expansion, event dispatch and copy/exposed-strip
structure. Keep the source patch set small and reviewable.

The first delivery accepts ASCII fixtures with LF, CRLF, CR and an unterminated
last line. Keep original tab-width selection with digit keys, line/page motion,
Home/End, full/restore, move/resize, Ctrl-W window cycling, Ctrl-U close and
Ctrl-Q quit. Multiple command-line documents use the available shared window
capacity; the viewer does not reserve twenty windows just because its original
local table has twenty entries. No-argument startup exits cleanly, as the
original helper does. No file-selector dialog or RSC conversion is required.

Use native `SYS:`, `WORK:`, `RAM:` and inherited relative paths. Initial filename
length remains the original 127-byte bound; reject longer input visibly before
publication. The common runtime supplies `main(argc,argv)` and double-quoted
arguments. This is a native source port, without executing the original 68000
binary or importing TOS startup, traps, basepages or ARGV environments.

Keep grow/shrink animation calls out of the initial port: full/restore changes
geometry directly. MagiC `VA_START`/`AV_STARTED`, its drag/drop pipe refusal,
desktop process reuse, extra fonts and automatic TXT association changes are
follow-ups. Omit unsupported protocol branches explicitly; do not provide
success-returning pipe or animation stubs. General ATASCII/other 8-bit encoding
conversion is also separate; do not reinterpret ST high bytes as newlines or
change the GEMDOS byte-preserving I/O contract silently.

## Existing services and source selection

**Use GEM4XE for rendering; use MagiC for multitasking ownership.**
The source port uses current Exec services, not donor polling, scheduling or
hardware routines. The GEMDOS wrappers, raster copy, VDI alignment/inquiry/fill,
full/previous geometry, horizontal gadgets and mouse calls are implemented.
The planning baseline is APP ABI 45 / AES 24; machine-readable ABI inputs remain
authoritative. Use the compiler revision in `toolchain/actionc.json`.

Select MagiC revision `28cfdd29aa16fef692cc287bad3046b44ddcce3d`, already pinned in
[the Atari reference configuration](../../../toolchain/atari-st-reference.json).
MP1 must verify upstream source bytes and notices at that revision; local
`build/magic-scroll-research/` files were sufficient for this planning audit,
but are not the reproducible source package for the port.

| Input | Retained role / adaptation |
| --- | --- |
| `MagiC/APPS/MGVIEW/SRC/MGVIEW.C` | Original argument loop and key/message dispatch; adapt Pure C declarations and event-call shape. |
| `MGWIND.C`, `MGWIND.H` | Original document load, line counting/indexing, tab expansion, text draw and window callbacks. |
| `WINDOWS.C`, `WINDOWS.H`, `GLOBALS.H`, `MGVIEW.H` | Original window table, geometry, scrollbars, redraw and `set_shift` structure. |
| `MEMCHAR2.S` | Behavioral reference for finding the first CR or LF; replace only this 68000 routine with bounded C. |
| Viewer README, project/library metadata and applicable upstream licence | Provenance, linked helper inventory and distribution notices. |

Store the selection, original file hashes, notices and adaptation recipe under
`ports/magic/mgview/`. Keep upstream snapshots immutable; generate build copies
or apply recorded patches. Record source encoding and line-ending conversion.
Normalize host source text before newline-sensitive inspection, while preserving
exact binary and document-fixture bytes. Exec-authored public C helpers retain
the repository's interface licence; imported viewer code retains its own notices.

## Binding and ownership decisions

Use the shared `<gem.h>` and `<compat/gemdos.h>` surfaces. Do not copy QED's whole
supplementary header or introduce a second GEMDOS/runtime implementation.

- Adapt `MT_appl_init(global)` to the current Task-local AES context and adapt
  the Pure C compound `evnt_multi` arguments to the published binding. Keep the
  application event structure local; no process-global VDI parameter arrays.
- Promote the reusable rectangle helpers currently in
  [QED's adapter](../../../ports/gem4xe/apps/qed/native/gem-helpers.c) into a
  common source module, proposed as `c/compat/gem/rect.c` with
  `c/include/compat/gem-rect.h`. Link it into the consumers and remove the QED
  duplicates. Retain conventional scalar AES calls; change original rectangle
  call sites to explicit `wind_*_grect` helpers rather than overloading them.
- Supply viewer-local workstation setup and bounded error alerts using existing
  `graf_handle`/`v_opnvwk`/`form_alert`. Replace `form_xerr` call sites with that
  real error path. Preserve the error before closing/freeing resources.
- Source-linked helpers should need no new APP import or kernel operation.
  If the real link inventory exposes a missing shared service, implement the
  narrow reusable interface with its own focused checks. Update ABI definitions
  and rebuild providers/callers together when necessary; retain one current ABI.
- Keep document reads, allocations, indexing and line-width scans outside
  UPDATE. Keep normal Task preemption, existing scene/display guards, physical
  drawing quanta and the current mouse contribution model.

The existing `redraw_window()` holds UPDATE. The original `set_shift()` does
not: its mouse hide alone cannot authorize drawing or stabilize Exec's visible
rectangles. MP3 must hold UPDATE across the complete copy/strip operation.
M_OFF/M_ON only contribute visibility; do not add MCTRL merely to paint.

Use `ExecAESPainted` after genuinely reconstructed visible regions and before
outer END_UPDATE. Copied destinations are complete only if their source pixels
were known current; otherwise redraw from the document model. Use the existing
`pixelsReady` snapshot / painted-changes contract where applicable. An empty
rectangle enumeration or successful END_UPDATE alone is not paint completion.
Keep window preservation at its default for this port; stronger preservation
requires a separate complete change-publication contract, including hidden
scroll/tab changes. Add no new bitmap cache or per-row RPC.

## Executable slices

### MP1: first original-source viewer

Pin the selection, build recipe and notices. Add `tools/prepare_mgview.py` and
`tools/build_mgview.py`, composing the current C APP builder with
`main_signature='args'` and GEMDOS source compatibility. Implement the small
binding/helper adaptations and C `memchr2`; preserve original function ownership
and callbacks. Remove the optional animation/desktop-protocol branches above.

Produce an actual `MGVIEW.APP` which opens one command-line file, paints its
initial viewport and closes. Start navigation with the existing full-redraw
fallback through `update_window`/`redraw_window`; defer admission of the copied
scroll path to MP3. This is one progressing implementation, without selectable
old/new runtime profiles. Keep upstream copy code in the immutable selection.

Establish safe resource ownership now: initialize the window record, validate
size arithmetic before allocation, terminate the extra text byte, accept empty
input and publish the window/table count only after required storage exists.
Every failure must close a live descriptor at most once and withdraw/free any
unpublished window and buffers. Free the window record on ordinary close.

Use actual VDI cell metrics and screen work bounds. Choose character-grid minimum
dimensions compatible with the existing gadget minima, including height 80 for
vertical gadgets; clamp staggered bounds to the supported screen rectangle.
Empty/one-line documents must not produce a rejected or permanently hidden window.

Exit checks: execute the original parser/scanner and changed C layout/callback
bridges in small raw/optimized probes; execute the optimized loaded application
with a short file, no arguments, a quoted path and close/restart. Compare initial
glyph/blank-region pixels with an independent oracle. Measure stack headroom;
move the 273-byte draw buffer to application-owned upper scratch if needed.
Do not enlarge a Task stack reservation to make the first port fit.

### MP2: original loader/model failure and lifetime coverage

Complete the admitted loader profile through the original application code,
not only the independently written GC4 loader model. The shared allocator admits
65,520 payload bytes per block. With one terminator byte, admit at most 65,519
file bytes; independently bound `line_count*sizeof(char *)` before multiplying
or narrowing. Native huge pointers are four bytes, so at most 16,380 line-index
entries fit one block, subject to actual available memory. These are ceilings,
not memory reservations. No cross-bank allocator is added.

Keep FSTAT tied to the opened object, exact-count read checks and the existing
consumed-close semantics. The original index-allocation failure occurs after
table publication and descriptor close; correct that rollback instead of
retaining a dangling slot, inflated window count or second Close. Audit close,
Ctrl-Q/Pterm and failed later opens so earlier documents remain usable.

Exit checks: emitted optimized loader/app cases cover empty and one-byte files,
LF/CRLF/CR, final CR and missing final newline, tabs 0–9, embedded NUL behavior,
long lines and original 272-column truncation. Cover file/index limits and the
next rejected values, missing paths, short reads and allocation failures at the
window/text/index stages. Verify error preservation, descriptor/heap ownership,
repeated open/close and application exit. Keep fixtures byte-exact on disk.

### MP3: original copy/exposed-strip scrolling

Restore the original `set_shift` algorithm as the ordinary incremental path,
using existing `vro_cpyfm(S_ONLY)`. Keep the original distinction between small
line/column movement and large-jump redraw. Acquire UPDATE before publishing
the new drawable scroll state/slider changes and enumerating visible rectangles;
retain it through hide, copy, exposed-strip draw and completion reporting.
Balance hide and UPDATE on every ordinary exit. Parsing/loading remains outside.

Use each stable visible work fragment for source/destination geometry. Preserve
correlated clipping and overlap direction; initialize screen MFDBs explicitly.
Fall back to model repaint when old pixels are not current or a copy cannot
cover the intended destination. Report only verified copied/repainted regions;
retain ordinary repaint fallback if the completion journal cannot retain all
claims. Do not report an entire viewport after painting only a strip.

Exit checks: exact scanout for up/down/left/right line and page actions, Home/End,
all shift signs, endpoints, jumps exceeding a viewport and partial final lines.
For one-line movement, require old row two to become row one and independently
check the exposed strip. Add horizontal column checks, partial occlusion and a
non-current starting image. Observe pointer hide/show completion and background
Counter progress while UPDATE is retained. Record warm AES RPC counts externally
and physical-copy work; do not add observation calls inside every draw row.

### MP4: complete window interaction and cooperative stop

Qualify move, size, full/previous restore, horizontal/vertical arrows, track
clicks, thumb endpoints, tab-width changes and keyboard navigation through
the original dispatch structure. Honor current even-X/bounded geometry and
font-grid snapping. Verify actual top-window keyboard routing across documents,
including Ctrl-W, simultaneous key/message readiness and self-posted redraws.
Use existing window/input services; fix a demonstrated shared-binding defect
there with a focused regression rather than an MGVIEW-specific kernel exception.

Exercise multiple command-line documents in one registration, rejected excess
windows, later-open failure, single-window close, Ctrl-U/Ctrl-Q and ordinary
Process stop. Stop during file I/O, after hide/during copy, and before main;
retain buffers, context, grants and image until admitted operations retire.
Preserve reset-required backend ownership instead of forcing cleanup after DMA
failure. Reuse existing bounded cursor/copy fault-injection boundaries.

Exit checks: loaded MGVIEW beside a Counter, cover/expose and cached-move
correctness during/after scrolling, repeated execution with restored heap and
unchanged peers. Respect four AES registrations and six shared window slots.
The standard Desktop plus Terminal leaves room for MGVIEW and one Counter;
larger concurrency cases use the minimal GUI fixture, not an enlarged pool.
Check application-owned allocations explicitly as well as runtime exit cleanup.

### MP5: paired MagiC/Exec viewer checks and measurements

Reuse the existing
[MagiC MGVIEW reference](../../history/magic-scroll-comparison.md) and its pinned
Hatari configuration. Run the same byte-identical document and line/page/column
input sequence on MagiC and Exec. Keep the unchanged original binary as a
functional reference; if a rebuilt MagiC reference is needed for matching cell
metrics, use the same selected source and record every reference-only adaptation.

Compare line indexing, tabs, viewport positions and within-machine pixel-copy
relations. For timing comparisons, match visible row/column counts, scroll
distance, font metrics and input schedule; record CPUs, clocks, display depth,
emulator settings, cache state and background workload. The old 8x16 versus 8x8
viewer captures are not a normalized performance baseline. If matching is
incomplete, report that limitation and functional results without a speed ratio.

Exit checks: optimized emitted binaries show correct final pixels on both
platforms. Record input-to-first-correct-pixels and complete-viewport time on
the Exec port, together with CPU, RPC/physical-work and Counter progress.
Separate file load/index time from scrolling and matched repaint from copy.
Do not attribute an improvement to the blitter or close an earlier latency goal
without supporting measurements. Missed performance goals remain explicit
follow-up work; they do not authorize a scheduler or drawing-limit rewrite.

### MP6: shared SDK and final package delivery

Add `MGVIEW.APP` to the common desktop/demo APP build and writable SYS/WORK disk.
Ship a byte-identical ASCII sample using the binary-file staging path, preserving
its CR/LF bytes. Document `RUN C:MGVIEW.APP SYS:MGVIEW.TXT`, no-argument exit,
supported keys, file/index/path/window limits and the scoped desktop extensions.
Keep the existing Text application/default TXT association and Mouse probe.
Include the selected MagiC application licence/provenance notices in `licenses/`.

Refresh once with `tools/build_demo.py`: retain OF816, matching SYS disk, pinned
AltirraOS ROM, notices, checksums and the standard five-second autoboot behavior.
Rebuild every affected ABI consumer; rebuild QED if the shared helper extraction
changes its link inputs, but do not execute QED as routine port acceptance.
The ZIP contains only boot files, guide, licences and checksums; manifests,
objects, screenshots and test logs stay in development output.

Exit checks: audit ZIP/SYS and current APP headers; require the packaged MGVIEW
and Counter to match their tested binaries. Run the small loaded viewer/Counter
workflow from those exact APPs and cold-boot the final ATR through OF816 to
byte-verified native entry. Record these distinct execution scopes rather than
claiming a full interactive desktop or release qualification from transport alone.
Add current application guidance and a history/evidence page, update the indexes,
and record the delivered ZIP and launcher paths.

## Memory, validation and completion rules

Target **zero new reserved bank-zero bytes**: fixed, root, kernel, private idle
and each public Task, including guards, alignment and unused capacity. Reuse the
current Task/DP/stack pools and cursor/raster VRAM reservations. Add no viewer
worker, kernel selector, timer-poll loop or alternative renderer. Charge source
code, window records, document/index allocations and scratch in upper memory;
measure actual compiler layouts, ownership prefixes, allocator rounding and
live/peak footprint instead of quoting payload lengths as total cost.

Use the [development tier](../../contributing/testing.md): host checks and
affected generators per code slice; small raw/optimized probes for changed
compiler-facing layouts, callbacks or helpers; optimized functional, failure,
pixel, ownership and performance cases. Use emitted code and real read-only
document files. Preserve stack/domain/register, heap, IRQ/NMI/display and OS
restoration checks where relevant. Compiler defects belong in their owning
repository with focused regressions. Normal validation uses MGVIEW and Counter.

Do not rerun the release matrix or refresh the entire demo after each slice.
Record per-slice evidence and all reserved bank-zero deltas, then commit before
the next slice. Unsupported calls must be adapted, explicitly removed from the
admitted scope or implemented as shared services; a successful link with dummy
implementations is not completion. Keep current contracts distinct from this
proposed plan and preserve historical qualification records unchanged.
