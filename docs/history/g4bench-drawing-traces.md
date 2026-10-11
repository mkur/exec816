# G4BENCH drawing traces

[History](README.md) · [Benchmark port and baseline](g4bench-port.md)

Passive traces of the unchanged OF816 demo separate application preparation,
UPDATE and physical drawing ownership, rendering, command construction, uploads
and completion polling. Both the idle-shell and visible-counter scenes use the
original 480×160 canvas at (152,56), pointer at (630,230), PAL and pinned 8×
65C816/VBXE FX 1.26 configuration.

[Development evidence](../development/g4bench-drawing-traces.json) records the
image, ROM, emulator, compiler and donor identities, raw benchmark samples,
per-sample breakdowns, call counts, stack observations and trace hashes.
The demo ZIP and all guest executables are unchanged. The application's five
reported medians match the preceding baseline in both loads.

## Elapsed time and Task accounting

These are cycle-observed **means per operation over the three measured
batches**, rather than medians of VBI-quantized batch averages. CPU charge
includes kernel calls, return overhead and bus stalls. Interrupt bodies on the
benchmark Task are separate; execution assigned to another Task, including its
interrupts, is off-Task time. The components sum to elapsed time.

| Workload | Idle elapsed | Task CPU | Off-Task | Interrupt | Counter elapsed |
| --- | ---: | ---: | ---: | ---: | ---: |
| 100×50 rectangle | 28.102 ms | 16.662 ms | 7.872 ms | 3.568 ms | 31.365 ms |
| 39-character text, even X | 24.011 ms | 13.277 ms | 7.896 ms | 2.838 ms | 26.896 ms |
| Same text, odd X | 39.349 ms | 25.850 ms | 7.977 ms | 5.522 ms | 42.387 ms |
| Clipped text | 41.618 ms | 27.682 ms | 8.024 ms | 5.912 ms | 45.304 ms |
| Five-object dialog | 144.786 ms | 93.196 ms | 31.646 ms | 19.944 ms | 157.010 ms |

With the counter, off-Task time rises to 10.828, 10.586, 10.508, 11.462 and
42.716 ms respectively. Most of the additional elapsed time is there; the
benchmark Task's CPU cost changes comparatively little.

## Exclusive CPU costs

Nested uploads and waits are removed from their parent renderer/builder costs.
Every column sums to its Task CPU total above, subject to rounding. These rows
are not independent inclusive function timings.

| CPU work, ms/operation | Rectangle | Even text | Odd text | Clipped text | Dialog |
| --- | ---: | ---: | ---: | ---: | ---: |
| Application arithmetic | 0.135 | 0.139 | 0.137 | 0.138 | 0.108 |
| Other application/state setup | 1.974 | 2.021 | 1.989 | 1.989 | 0.794 |
| VDI/AES preparation | 1.685 | 2.400 | 2.409 | 2.429 | 4.074 |
| Visibility checks | 1.216 | 1.228 | 1.205 | 1.257 | 4.947 |
| UPDATE calls | 1.632 | 1.641 | 1.631 | 1.718 | 6.479 |
| Event polling | 0.801 | 0.799 | 0.797 | 0.829 | 3.191 |
| Display ownership | 3.784 | 1.938 | 1.961 | 1.978 | 9.597 |
| Borrow setup/pointer handling | 0.387 | 0.194 | 0.193 | 0.193 | 1.032 |
| Renderer/callback setup | 1.837 | 0.893 | 8.166 | 9.369 | 25.231 |
| Command construction | 1.622 | 0.306 | 4.835 | 5.181 | 26.263 |
| Upload/encoding | 0.515 | 1.119 | 1.742 | 1.827 | 8.175 |
| Submission/fence bookkeeping | 0.733 | 0.191 | 0.367 | 0.367 | 1.825 |
| Completion polling | 0.342 | 0.408 | 0.416 | 0.409 | 1.478 |

The native text uploader encodes records directly into VRAM, so its encoding
and writes remain one measured bucket. Completion polling measures software
inside `idle()`, including immediately successful checks. It is not an exact
measurement of the hardware BUSY interval; DMA can overlap other CPU work.

## What the traces establish

- Even, odd and clipped text each use **two display borrows and two blitter
  launches** per string. The odd-X penalty is not additional submissions or
  extended completion polling. It adds about 12.573 ms of Task CPU and
  2.684 ms of interrupt time relative to even X.
- Even-X text uses two native text uploads. Odd and clipped text enter donor
  `vdi_v_gtext` twice and `vbxe_glyph` **39 times** per string. Odd text emits
  32 ink glyph records; seven characters are blank. The clipped workload also
  exercises partial glyph edges/rows. Renderer and command-construction CPU
  account for most of their extra cost.
- The rectangle uses **four physical borrows and four launches**. Its display
  ownership CPU alone costs 3.784 ms. The varying X parity averages 12
  `blit_mask` calls across those four strips.
- The dialog uses **ten borrows and ten launches**, **75 rectangle-fill calls**
  and **179 `blit_mask` calls**, plus 18 ink glyph records. Rendering and
  construction together cost 51.494 ms of Task CPU; ownership adds 9.597 ms.
  Reducing repeated object/strip work is a more promising target than its
  1.478 ms of completion polling. This row redraws a whole dialog, not one
  pressed button.
- UPDATE and the benchmark's visibility checks also account for much of the
  off-Task time. Idle UPDATE spans contain 6.244/6.032/5.880/5.727 ms off-Task
  per rectangle/even/odd/clipped operation and 22.596 ms per dialog. Primitive
  groups have four operations; dialogs have one. These are throughput costs
  of this application protocol, not click-feedback measurements or pure
  uncontended lock costs.
- There are **no `VbxeOwnerRead` or `VbxeOwnerWrite` calls** in any measured
  workload, in either load. The 4 KiB staging-page transfer path is not involved
  in these results. Arithmetic in the application is also a small contributor.

The next focused optimization candidate is VDI odd-X/clipped text: retain
whole-glyph runs and use a partial-glyph path only where the clip cuts cells.
The dialog offers a separate opportunity to reduce object/strip construction
work. These traces do not justify enlarging uninterruptible work units or
removing drawing ownership. No rendering optimization is part of this change.

## Capture and reproduction

`tools/trace_g4bench.py` copies the existing package to a development directory
and drives its ordinary shell launch and Return/Escape interaction. Passive PC
observations add no guest instructions, buffers or scheduler changes. Full
compiler sections are matched against linked bytes to locate JSL successors;
native S and D identify returns, including tail calls and shared epilogues.
The loaded Process supplies the actual relocation base. Repeated entries
without a matching return fail analysis. Arithmetic is measured through its
wrappers, which include the compiler runtime's private helper work.

The `borrow_callback` interval runs from `pointer_erase`'s return to the first
`fence_owner` entry. It includes callback argument setup and the call into the
fence, but no fence body. This covers the application's renamed object renderer
without misattributing it to pointer handling. The outside pointer makes those
boundaries unambiguous in these scenes.

Capture ends at the first IRQ checkpoint after the benchmark enters its report
phase. An unexecuted trailing IRQ entry is removed before interrupt accounting.
All timed calls must be complete. Clearing, warmup, calibration, clock calls,
report saving and shutdown are outside the measured intervals. Each sample's
operation count matches the application's saved result, and its elapsed time
agrees with the VBI result within one tick plus clock-call allowance.

```sh
python3 tools/trace_g4bench.py --bundle build/g4bench/demo \
  --output build/g4bench/trace-new-idle --load idle
python3 tools/trace_g4bench.py --bundle build/g4bench/demo \
  --output build/g4bench/trace-new-counter --load counter
python3 tools/trace_g4bench.py --output build/g4bench/trace-new-idle --analyze
```

Each output contains `trace-summary.md`, complete per-sample
`trace-results.json`, the marker definition, loaded-app identity and compressed
selected CPU observations in `cpu-trace.log.gz`. `drawing-trace.json` uses
Chrome Trace Event format: the first UPDATE group (four primitives or one
dialog), including visibility checks and event polling, from sample one
occupies a separate workload lane, each rebased to zero. Those lanes
are comparisons, not simultaneous execution. Inclusive function bars include
preemption; their metadata separates CPU, off-Task and interrupt time.

The initial broad capture timed out during reporting. The accepted captures
stop profiling before report saving; both subsequently save results, close,
execute shell `HELLO`, shut down and pass stack/domain and ownership checks.
Host tests cover return matching, missing/truncated returns, clock wrap,
exclusive accounting, CRLF parsing and instruction operands. This is development
coverage only. It adds **0 reserved bank-zero bytes**, fixed or per public Task
or private idle Task, including guards/alignment/unused capacity. Guest upper
RAM and VRAM reservations also change by zero.
