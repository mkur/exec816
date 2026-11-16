# One synchronous unit for aligned screen copies

[Cursor fix baseline](cursor-drawing-hint.md) · [History](README.md) ·
[Measurements](../development/gem-screen-copy.json) ·
[Current raster contract](../reference/gem-vdi.md#conventional-raster-copy)

The later [odd-edge copy slice](gem-odd-edge-copy.md) extends the single-interior
path to same-parity partial-byte edges after the MagiC geometry cutover. The
aligned-copy measurements below retain their original workload and scope.

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

## Remaining cost at individual call boundaries

The subsequent [granular analysis](../development/gem-scroll-detail.json)
reuses this exact capture, with no build or guest run. All times below are ms.
Wall time includes other Tasks and native interrupts; CPU is the viewer's
conservative charge, including kernel execution and bus stalls.

| Call inside `set_shift` | Down wall | Down CPU | Up wall | Up CPU |
| --- | ---: | ---: | ---: | ---: |
| BEGIN UPDATE | 7.71 | 6.39 | 27.74 | 7.76 |
| Window-view query | 2.23 | 1.20 | 0.89 | 0.75 |
| Slider arrangement, two `wind_set` calls | 6.73 | 5.55 | 6.73 | 5.55 |
| `graf_mouse(M_OFF)` | **19.20** | 6.58 | **19.57** | 3.96 |
| First visible rectangle | 1.27 | 1.05 | 1.27 | 1.05 |
| Screen rectangle intersection | 0.07 | 0.07 | 0.07 | 0.07 |
| Copy clip setup | 1.65 | 1.34 | 1.65 | 1.34 |
| `vro_cpyfm` | 28.57 | 9.68 | 14.56 | 12.05 |
| Exposed-row callback | 18.62 | 14.66 | 23.30 | 15.59 |
| Painted-region acknowledgement | 1.10 | 0.93 | 1.10 | 0.93 |
| Next visible rectangle | 2.91 | 1.67 | 1.23 | 1.01 |
| `graf_mouse(M_ON)` | **20.32** | 3.94 | **17.96** | 3.95 |
| END UPDATE | 17.11 | 9.80 | 38.81 | 11.16 |
| Caller code, argument setup and compiler helpers | 0.45 | **0.36** | 2.04 | **1.04** |

These are disjoint direct-call intervals plus their residual. Indirect callbacks
are identified by their contained slider/draw routines. Public calls match
the viewer DP, native stack and linked JSL successor; all matched stacks agree.
Compiler switch helpers and helpers with inline operand data do not have a
normal JSL+4 return; their work remains in the caller residual. Thus almost
all viewer CPU is inside GEM/binding callbacks rather than MGVIEW's own scroll
arithmetic.

### Mouse handoff

Hide/show together take 39.52 ms down and 37.53 ms up, including 26.80/27.95 ms
off the viewer CPU. The corresponding native scene entries are uncontended:
each `AESGATE.EnterTask` takes about 0.15 ms of CPU. The substantial off-CPU
intervals occur while the caller is in **`AESGATE.Release`**:

| Mouse call | Release wall | Release CPU | Other-Task time inside release |
| --- | ---: | ---: | ---: |
| Down hide | 9.14 | 1.52 | 7.31 |
| Down show | 17.41 | 1.52 | 15.58 |
| Up hide | 16.61 | 1.52 | 14.77 |
| Up show | 15.01 | 1.52 | 13.18 |

Down hide also spends 3.91 ms off CPU inside display admission. These intervals
account for all off-CPU time inside the four mouse calls.

[`AESLOCAL.Call`](../../lib/aes/aeslocal.act) releases the scene with
`AESGATE.Release(AESCURSOR.Pending())`. Release signals the presenter and calls
`Permit()`. The C caller's attempt to apply that target through its workstation
grant comes afterward in
[`ExecAESMouseControl`](../../c/calypsi/aes-input.c). This creates an opportunity
for the presenter to run before the caller reaches its physical mouse update.
The measured pause is a scheduling handoff at release, rather than scene-gate
acquisition contention. Whether that visibility wake can be deferred for a
caller that will apply its own target is the next focused protocol question;
required scene-waiter wakes and fallback completion still need preservation.

### Exposed-row CPU

The row callback itself breaks down as follows; these nested costs are already
included in the callback row above:

| Work | Down CPU | Up CPU |
| --- | ---: | ---: |
| Set text clip | 2.03 | 2.02 |
| Clear exposed row | 2.30 | 2.29 |
| Fetch source line | 0.36 | 0.27 |
| Expand tabs/text | 2.29 | 1.66 |
| `v_gtext` | 7.02 | 5.69 |
| Trailing blank fill | 0 | 2.13 |
| Remaining callback/call/compiler work | 0.66 | 1.53 |

The presenter separately calls `DESKINPUT.Present` nine times during either
whole scroll, costing 21.99/21.94 ms CPU. Contiguous native caller segments
attribute 5.28/5.29 ms to cursor selection, 5.78/7.08 ms to cursor waiter/wake
handling and 8.28/6.29 ms to bitmap mouse work. Segment costs include caller
setup/cleanup; they are not pure callee timings and are not added to the
viewer call table.

### Visible pixels versus callback completion

The handler starts at 27.83/20.45 ms after input. The exposed-row callback
returns at 114.32/118.25 ms; complete pixels are observed at 120.12/140.49 ms.
END UPDATE starts at about 138.66/138.56 ms, and the scroll handler returns at
155.77/177.37 ms. Its late release cost therefore affects readiness for the
next key even when pixels are already visible.

The input-to-observed-pixels interval has this disjoint CPU accounting:

| Attribution before observed completion | Down | Up |
| --- | ---: | ---: |
| Viewer Task | 54.40 | 58.99 |
| Presenter Task | 30.73 | 41.15 |
| Busy-yielding test supervisor | 13.47 | 7.04 |
| Other Tasks | 0 | 8.08 |
| All native interrupts | 21.52 | 25.23 |
| Total elapsed | **120.12** | **140.49** |

The supervisor is fixture overhead. The frame-sampled completion brackets
remain authoritative; no pure hardware BUSY-edge duration or production
desktop latency is inferred from these diagnostic samples. The analysis adds
zero fixed or per-Task reserved bank-zero bytes and changes no target code.
