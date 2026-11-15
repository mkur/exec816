# One synchronous unit for aligned screen copies

[Cursor fix baseline](cursor-drawing-hint.md) · [History](README.md) ·
[Measurements](../development/gem-screen-copy.json) ·
[Current raster contract](../reference/gem-vdi.md#conventional-raster-copy)

On 2026-11-15, even-X/even-width S_ONLY screen copies changed from repeated
sixteen-row admissions to one typed synchronous operation. The GEM adapter
erases intersecting source/destination overlays once, retains its existing
grant through the complete copy and fence, restores overlays and releases.
Normal Task preemption remains enabled throughout.

The driver already has a full-rectangle, overlap-safe BCB encoder for typed
asynchronous copies. Its synchronous `VbxeOwnerCopyRect` now uses that same
encoder once when both surfaces are the standard screen: offset zero,
pitch 320, width 640 and height 240. Existing full-geometry validation bounds
the record to 320 bytes × 240 rows, or 153,600 source/destination accesses.
Submission, polling, timeout and recovery use the existing synchronous path.
No asynchronous operation identity, completion IRQ, new API or kernel service
is introduced.

This is an operation-specific bound, rather than a change to general drawing
limits. Masked-edge copies retain source-edge staging and bounded strips.
Other raster modes, memory surfaces, generic callbacks, objects, text,
fills, native batches and raw lists retain their existing limits. Larger
hardware work per aligned copy means competing drawing waits for that complete
unit; other Tasks still run. It follows the existing separation between
logical UPDATE ownership, physical renderer ownership and Task scheduling.

## Focused development results

The unchanged original MGVIEW and Counter APPs use the same reference document,
488×200 viewport, parked pointer, pinned PAL/8× machine, physical down/up keys
and independent pixel oracle as the saved mouse-fix baseline. Only the changed
C provider and native fixture were rebuilt; no APP, QED, demo or boot transport
was built.

| Measured per scroll | Down before → after | Up before → after |
| --- | ---: | ---: |
| Input → complete viewport observed, ms | **180.65 → 120.12** | **180.14 → 140.49** |
| Copy elapsed, ms | **74.10 → 28.56** | **66.90 → 14.56** |
| Copy viewer CPU, ms | **36.82 → 9.68** | **37.22 → 12.05** |
| Whole-scroll viewer CPU, ms | 91.91 → 63.22 | 90.71 → 66.22 |
| Owned-copy completions | **12 → 1** | **12 → 1** |
| Display enter/leave pairs inside copy | **12 → 1** | **12 → 1** |
| Fence calls inside copy | **48 → 4** | **48 → 4** |

Copy CPU falls by 74% down and 68% up in these samples. The copy interval
includes setup, fences, polling, interrupts and preemption; it is not a
blitter BUSY-edge measurement. The typed encoder constructs one BCB, and the
trace confirms one successful owned-copy call, one grant and four fences.
There are zero asynchronous completion-IRQ markers inside either copy.

The retained grant is observed from successful `DisplayEnter` return to
`DisplayLeave` entry. Down retains it for 14.24 ms, including **6.54 ms off
the viewer CPU** and 1.47 ms of viewer-context native interrupts. Up retains
it for 12.03 ms, with 2.11 ms of native interrupts. Thus peer execution and
interrupt delivery occur while physical ownership remains held; full viewport
pixels still match afterward. This is an observed preemption/coexistence case,
not forced coverage of every interrupt or scheduling boundary.

Both directions still perform one `vro_cpyfm`, one exposed text-row draw and
zero AES RPC. Exact complete viewport hashes match the baseline. Counter
advances twice over the wider run including post-settle frames. Four Process
lifetimes, heap checks, stack/domain guards and ownership restoration pass.

Visible timings are PAL-frame/COP sampled upper bounds. The new complete-view
brackets are 100.56–120.12 ms down and 120.35–140.49 ms up. One action per
direction, the busy-yielding fixture supervisor and the reused saved baseline
do not establish latency percentiles or a physical-hardware speed guarantee.

## Descriptor, overlap and failure checks

```sh
python3 tools/test_screen_copy.py --output build/mgview-screen-copy/encoding
```

The optimized emitted probe extracts the actual driver geometry/BCB encoder
and `GemDrawingCopyBorrow` routines unchanged. It substitutes only admission,
overlay and hardware submission boundaries. The host interprets captured BCBs
against an independent whole-source snapshot, comparing all 512 KiB of modeled
VRAM, including unchanged regions. Eighteen cases pass: viewer up/down,
horizontal and diagonal overlap, full-width and full-height limits, last row,
identical/empty areas, BUSY admission, submit failure, invalid height and the
non-screen chunked fallback. Request preservation and enter/leave counts pass.

The probe checks emitted descriptors and error transitions, rather than real
hardware timeouts. The loaded viewer supplies actual VBXE pixel, grant,
preemption and cleanup evidence. The full masked-edge/raster-mode matrices,
full-screen hardware maximum and forced timeout cases were not rerun.

```sh
python3 tools/measure_mgview.py --presenter --expect-copy-units 1 \
  --cache build/mgview-screen-copy/cache \
  --output build/mgview-screen-copy/scroll
python3 tools/measure_mgview.py --cache build/mgview-screen-copy/cache \
  --output build/mgview-screen-copy/scroll --analyze-only
```

The measurement tool checks the linked copy-call target and pixel/model result;
`--expect-copy-units` asserts the selected image's expected operation count.
Offline analysis also records the already-owned grant intervals without
rerunning the guest. Raw captures stay in the development directory; the
compact record retains input identities, exact statistics and validation scope.

## Memory and remaining work

No new state, staging, VRAM reservation, command arena or Task is allocated.
The same 21-byte BCB and descriptor locals are used. Fixed runtime and phase
reservation maps and all Task pools are identical to the mouse-fix baseline.
Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 private idle and
0 per public Task**, including guards, alignment and unused capacity.

This completes the aligned-copy slice. Text-row rendering and remaining
UPDATE/scene coordination costs remain separate follow-ups. Development
checks do not qualify a release or establish the larger input-latency targets.
