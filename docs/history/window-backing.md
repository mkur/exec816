# Aligned window moves and persistent Shell backing

[Plan](../plans/gem4xe/window-backing-plan.md) ·
[Design](../plans/gem4xe/aes-layers-vram-design.md#aligned-aes-moves) ·
[Machine-readable evidence](../development/window-backing.json)

Eligible completed AES windows move through the existing overlap-safe display
transaction. Accepted outer X and width are even; Y remains pixel precise.
Geometry and paint epochs publish before the AES reply. A successful pure move
does not send a redraw to the moved client. Covered, incomplete or resized
windows retain ordinary exposure/reconstruction. Applications still need to
publish accepted work coordinates for hit testing after a move.

Shell now has a fixed 512×160 packed bitmap in VRAM. Dirty model spans update
that bitmap even under another window. Exposed client rectangles copy from it;
scroll batches copy within it, clear new rows and draw final text before the
completed generation becomes current. Existing Layers damage tracks visible
repair separately. No new display engine, worker, signal or kernel operation
was added. The pointer and caret stay out of backing; caret removal still uses
its existing single-cell renderer.

The source baseline is `93f462f5956728c826cf4c0bd822c02bd0c2897c`, the Shell-focus
fix. Both builds use actionc `05c01f39ff3beef97af0e65b0a16666f5a1bd805`, the pinned
AltirraOS 3.44 65816 ROM, PAL, 8× CPU and VBXE FX 1.26. The local build wrapper
selects the release host compiler at this same revision (SHA-256 recorded in
the evidence); it does not alter target optimization, compiler semantics or
ABI. The compiler test suite was not run.

## Memory

Reserved bank zero changes by **0 fixed / 0 per public Task / 0 idle bytes**,
including guards, alignment and unused capacity. There is no stack/DP growth.
The private text upload record uses two additional temporary stack bytes and
existing call-clobbered DP space. Move completion adds six occupied upper-RAM
bytes including alignment, within the existing reserved arena. There is no
per-client metadata growth.

VRAM grows by **40,960 bytes**, at `$41000–$4AFFF`. Production reservations total
416,256 bytes; 108,032 remain unassigned, or 108,000 after the diagnostic
exclusion. Both AES snapshots and all menu saves remain intact.

## Development coverage

- Host checks: 459 tests, four existing skips; affected generators are current.
- Optimized AES geometry: 268 checks. Optimized Layers: 60,184 checks.
- Optimized AES cache: 99 checks, including exact moved pixels, preservation
  of client snapshots and genuine external exposure notification.
- Drawing boundary: 172 checks in each raw and optimized probe. Independent
  screen/offscreen pixel oracles cover both X parities, pitch, first/last rows,
  fills, text upload, copy-back and subsequent ordinary screen drawing.
- Desktop presentation: 117 checks across 19 complete pixel scenes, including
  clipped edges, moves, clear, scrolling and cancellation with overwritten
  caller storage. Five untraced replays per build record zero output overtakes.
- Fully covered-output variant: 117 checks on each build, followed by exact
  exposed pixels; focus/cache fixture: 71 checks and 18 scenes.
- Quiesced drawing-failure replay: 111 checks, clean retirement and OS return.
- Standalone batch interleavings cover abort during DMA, final close during
  DMA, cancellation during repaint and a stale view before submission. These
  complement the desktop path; standalone timings do not measure backing.

These are development checks, not hardware or release qualification.

## Window completion

Twenty physical release samples per move/close cohort, median/p95 milliseconds.
The client endpoint compares the moved work area; the scene endpoint also
requires repaired exposed background. Polling resolution is one PAL frame.

| Endpoint | Baseline | Backing | Gate |
| --- | ---: | ---: | --- |
| Files moved client | 1,123.1 / 1,143.3 | 80.3 / 80.3 | Pass |
| Panel moved client | 702.0 / 702.0 | 100.0 / 100.3 | Pass |
| Files move, affected scene | 1,163.3 / 1,163.3 | 561.6 / 561.6 | Pass |
| Panel move, affected scene | 1,123.1 / 1,123.1 | 681.8 / 702.0 | Open |
| Files close over Shell | 962.7 / 1,002.6 | 882.6 / 902.6 | Open |
| Panel close over Shell | 601.5 / 601.7 | 361.0 / 380.9 | Open |

Both moved applications perform **zero client repaints in 20/20 moves**, versus
one repaint per baseline move. Copied placement meets the half-time target.
Full Shell exposure misses both the half-time and 100 ms p95 targets. The
combined scene therefore has mixed results, despite the large placement gain.

## Throughput and input

Five matched untraced runs per build use resident text, not disk speed. Each
endpoint includes completed output, final screen repair, caret and two settling
frames. Median completion time in milliseconds:

| Workload | Baseline | Backing | Throughput ratio |
| --- | ---: | ---: | ---: |
| Visible 1,600-byte output | 2,166.0 | 2,266.3 | 0.956× |
| Partly covered 1,600-byte output | 9,426.3 | 6,317.6 | 1.492× |
| Partly covered 512-byte short lines | 69,373.2 | 28,258.7 | 2.455× |

The visible and partly covered 95% throughput gates pass. The 1,600-byte
covered stage includes opening its cover window; the short-line stage starts
with that window already settled. A separate single
fully covered run completes the same output workloads in 2,266.3 / 4,211.7 ms,
versus 4,532.6 / 23,946.7 ms. Uncovering checks every final screen pixel against
the retained-model oracle. This measures hidden rendering and subsequent
correctness separately, rather than crediting accepted bytes as finished work.
Initial fixture setup plus the first three characters grows from 2,536.1 to
2,630.1 ms; this includes desktop initialization, not just bitmap construction.

Passive traces show the WB5 scroll path cuts backing text calls in the short-line
stage from 1,040 (WB4 full-row reconstruction) to 74. Aligned idle move/exposure
stages do no backing reconstruction. The separate focus fixture proves aligned
Shell exposure uses ten client copies and zero regenerated text cells; repeated
front-Shell clicks use neither copies nor text. Generic C text entry counts also
include caret removal and native content, so they cannot establish this alone.
Odd clipped edges still use the existing glyph fallback.

Thirty Panel presses run with Counter and a 66,560-byte CAT workload active.
The exact button raster, output progress and final retained Shell pixels are
checked. Median/p95 rises from **120.2 / 180.4 ms** to **140.2 / 280.9 ms**.
The loaded-button gate is **open**. Pointer median/p95 is 100.3 / 139.9 ms,
versus 100.3 / 100.3 ms. Faster completed output has not translated into better
tail input latency.

## Limits and follow-up

Backing removes repeated glyph work, but it does not remove presenter turns,
scene ownership or frame painting. A repair wholly within the Shell client
can copy a complete visible fragment. Damage that also includes frame pixels
still traverses 16-row strips. The ten-copy exposure above demonstrates this
remaining fragmentation. This, and waiting for a paint transaction before an
application UPDATE, are the next candidates to measure and shorten.

The physical move diagnostic records client pixels and the combined affected
scene separately, plus repaint counts. It does not timestamp final application
paint completion separately on the old build. Copy-call counts are recorded;
individual transferred-byte totals and all fallback reasons are not yet traced.
Those finer attribution items remain open. Native move/repair fixture stages
13/14 take about 40 ms longer (601.7 / 501.4 ms versus 561.6 / 461.3 ms), so
fallback non-regression is not established either. Ordinary menu timings include final
Files repaint as a distinct endpoint. Numeric misses remain misses; none of the
limits in the plan have been relaxed.

## Menus and packaged applications

Ordinary menu cohorts retain their background on all measured switches. Warm
File opening remains 200.6 / 200.6 ms and Windows dismissal 140.5 / 140.5 ms
(median/p95, 20 samples). File-to-View is 220.5 / 240.7 ms versus 220.5 / 220.8;
this fits the one-PAL-frame allowance. Final Files repaint stays approximately
602 ms after View dismissal and 381 ms after Windows dismissal.

The first repeated-pointer diagnostic overlapped scheduled physical mouse
phases between samples: it observed 32 heading restores for 20 requested
movements. All pixels matched and no background recapture or Files repaint
occurred. The corrected runner drains each movement after its timed endpoint
before reversing. Matched reruns retain all 20 backgrounds, with zero recaptures
and zero Files paints; pointer median/p95 is 280.9 / 280.9 ms versus
280.7 / 280.9. Keyboard median/p95 remains 341.0 / 401.2 ms.

The exact final ZIP walkthrough checks moved Panel hit testing and keyboard
activation, Counter progress, Text movement and scrolling, the packaged document
hash, Open-selector cancellation, close/focus restoration, HELLO and clean EXIT.
The remaining Text/Dialog/Input move handlers now refresh accepted work geometry;
Text does not force a full repaint after a clean pure move.

The demo retains OF816, the pinned ROM, matching SYS/WORK media, licenses and
five-second autoboot. Expanded executable segments grow by 9,173 bytes; the
compressed boot XEX grows by 2,880 bytes to 485,287. The metadata arena remains
6,912 reserved bytes, with 6,586 occupied. The normal distribution ZIP is
622,479 bytes. Intermediates and diagnostic traces remain outside that ZIP.

```sh
/Users/michalkurcewicz/action/exec816-public/build/window-backing/demo/launch-altirra.command
```
