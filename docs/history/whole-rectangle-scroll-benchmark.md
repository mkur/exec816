# Whole rectangle scroll benchmark

[Historical records](README.md) · [Drawing validation plan](../plans/drawing-validation-implementation-plan.md)
· [Machine-readable evidence](../development/whole-rectangle-scroll.json)

3 October 2026. A test-only whole-rectangle copy and bottom-strip fill reduces
isolated optimized full-screen console scrolling from **121.8–122.2 ms to 29.5–29.6 ms**
on the pinned PAL ×8 65C816, 4 MiB, VBXE FX 1.26 profile. This is about **4.1×
faster**, with identical final pixels. Repeated scrolls during continuous output
fall from **126.4–126.6 ms to 43.3–45.2 ms**, about **2.8–2.9× faster**.
The 20 ms complete-scroll target remains
unmet. Production drawing code, public interfaces and chunk limits are unchanged.

## What was measured

The existing thirteen-scene bitmap fixture exercises two isolated full-screen
scrolls, repeated scrolling, clear, a narrow offset tile, a height-one tile,
hidden updates, redisplay, text editing and full repaint. Each scene uses the
independent pixel oracle, including the caret and surrounding pixels.

The control is the current console: fifteen copy calls and one fill, with thirty
copy/fill hardware launches. The experimental build replaces only generated
inputs. Its console continuation passes the entire retained rectangle to one
drawing call. A fixture-only driver helper validates the owner and complete
geometry, constructs a 640×232-pixel upward copy and 640×8-pixel zero fill, and
submits the two records together through the existing synchronous uploader.
Narrow tiles use the same screen pitch and their own width and height.

The experiment preserves the existing GEM fence and ownership checks, hardware
status reads, mapping protocol, completion waits and recovery implementation.
It bypasses the small software work budget only for the checked fixture helper;
public `VbxeSubmit` and all production limits retain their existing behavior.
This is not the proposed validate-once refactor. The helper supports only the
console's aligned upward eight-pixel scroll and zero background.

## Full screen results

| Measurement for the two isolated scroll scenes | Current console | Whole rectangle and fill |
| --- | ---: | ---: |
| Logical edit through final copy/fill acknowledgement | 121.82 / 122.22 ms | 29.55 / 29.56 ms |
| Drawing calls within that interval | 16 / 16 | 1 / 1 |
| Hardware launches within that interval | 30 / 30 | 1 / 1 |
| Summed drawing-call elapsed time | 81.76 / 80.14 ms | 16.96 / 16.88 ms |
| Summed launch-to-idle intervals | 18.65 / 18.90 ms | 13.94 / 13.90 ms |
| Input checking within that interval | 9.74 / 10.02 ms | 0.60 / 0.60 ms |

The repeated-output scene contributes three more full-screen samples:
126.42 / 126.43 / 126.60 ms for the control, and 45.15 / 43.32 / 44.23 ms
for the experiment. The experimental drawing calls take 19.54 / 27.89 / 18.65 ms
in that scene; launch-to-idle intervals reach 24.91 ms. Scheduling and preemption
remain part of the result. The isolated 29.6 ms result is not a worst-case bound.

These boundaries exclude the surrounding fixture pauses and additional text/caret
drawing. One launch executes two blitter commands, not one combined hardware
opcode. Elapsed routine time includes interrupts and preemption. Launch-to-idle
includes software observation and any delay before the owner resumes; it is an
upper bound, not an exact hardware BUSY-edge measurement or isolated Task CPU time.

The control XEX hash exactly matches the prior Q3 image:
`c6796ebbf0400abb6120381eff86d3a5cdd8ad175c683908f9022c53fa4ec57c`.
The experimental optimized image is
`12fb8233508a5396e2bc72a19f097fafcde1b5d5a9e5cd1059b830336cad72fb`.
The narrow 17×3-cell scroll falls from 17.77 ms to 11.57 ms. Raw-build
full-screen measurements are 30.56 and 26.21 ms; differing interrupt phases mean
these two samples do not establish that raw code is faster than optimized code.

## Input and disk activity under load

The eight-Task workload uses an 80×24 output region and two 40×3 input regions,
physical SDFS reads, keyboard/BREAK events and ST mouse sampling. The original
fairness fixture was widened to exercise a large rectangle. Keys arrive during
ongoing output and disk activity; this is a sampled comparison, not an exhaustive
phase sweep. One of four control captures overlapped a copy call; none of the
four experimental captures did. The two executions reach different scheduling
phases, so these samples do not isolate the copy call as the cause of a delay.

| Sampled interval | Current console | Whole rectangle and fill |
| --- | ---: | ---: |
| Raw key capture to client delivery | 50.26 ms | 92.41 ms |
| Raw key capture to fixture presentation completion | 110.29 ms | 157.59 ms |
| Return capture to cooked-read presentation completion | 297.83 ms | 355.75 ms |
| BREAK capture to durable cancellation notification | 15.44 ms | 8.27 ms |
| Longest observed copy call, including preemption | 55.68 ms | 46.34 ms |

The faster scroll does **not** establish faster typing. The experimental sampled
key and echo completion intervals are worse, while BREAK delivery is better.
Presentation completion is a fixture marker after its cleanup/settling check,
not the first scanout containing the changed cell. No 40 ms input acceptance
claim is made.

Both builds complete their data, pixel, ownership, stack and cleanup checks.
Both loaded images also complete the same workload with tracing disabled.
The control misses the existing 100 µs SIO watchdog-service gate at **101.22 µs**;
the experiment passes at **78.80 µs**. This baseline miss is retained as a failed
timing gate, not waived. Neither run loses pointer records; maximum ST sample
gaps are 274.61 and 272.70 µs, below the existing 1,000 µs limit.

This run also exposed a host-test bug: the fairness key helper watched only the
native-mode capture counter. A valid BREAK arrived during an OS emulation-mode
activation, so the helper waited after capture had already occurred. The helper
now waits on the sum of native and emulation capture counters. Production input
code is unchanged.

## Validation and reproduction

The development checks include thirteen pixel scenes in the current optimized
build and in experimental raw and optimized builds. Both experimental images
also pass all thirteen scenes with passive tracing disabled. Stack/domain guards,
Task cleanup, display/input ownership and OS screen restoration pass.
The host suite passes 303 tests with four historical-source audits skipped.

Reserved bank-zero change is **0 bytes**: fixed storage, root/kernel, each of
eight public Tasks and private idle, including guards, alignment and reserved
slack. The same staging buffers, command arena, aperture and VRAM layout are
used. The test helper's two records live on the existing owner stack.

Run from the repository root with the pinned toolchain and emulator available:

```sh
python3 tools/measure_rectangle_scroll.py --variant current --output build/rectangle-scroll/current-opt
python3 tools/measure_rectangle_scroll.py --variant whole --output build/rectangle-scroll/whole-opt
python3 tools/measure_rectangle_scroll.py --variant whole --replay --output build/rectangle-scroll/whole-opt
python3 tools/measure_rectangle_scroll.py --variant whole --mode raw --output build/rectangle-scroll/whole-raw
python3 tools/measure_rectangle_scroll.py --variant whole --mode raw --replay --output build/rectangle-scroll/whole-raw
python3 tools/measure_rectangle_scroll.py --variant current --workload fairness --output build/rectangle-scroll/current-loaded
python3 tools/measure_rectangle_scroll.py --variant whole --workload fairness --output build/rectangle-scroll/whole-loaded
python3 tools/measure_rectangle_scroll.py --variant current --workload fairness --replay --output build/rectangle-scroll/current-loaded
python3 tools/measure_rectangle_scroll.py --variant whole --workload fairness --replay --output build/rectangle-scroll/whole-loaded
```

The [benchmark tool](../../tools/measure_rectangle_scroll.py) records original
and generated source hashes. The [fixture helper](../../tests/programs/rectangle_scroll.inc.c)
is appended only to the generated driver. Build directories contain XEX files,
compiler provenance, traces, pixel captures, full results and compact
`benchmark.json` measurements. This work does not refresh or publish a demo.

## Design consequence

The result supports treating a complete rectangle plus exposed-strip fill as
one candidate drawing operation. Small chunks currently cost far more in repeated
software work than they save in individual call latency. Optimizing validation
alone while retaining all thirty launches would miss most of this measured gain.

A production change still needs a defined combined-operation contract, admission
and full-list validation, failure/cancellation tests and better input response.
The current 2 ms list-occupancy and 4 ms Task-CPU targets are not qualified by
these elapsed-time measurements. First-visible scanout timing also needs its own
observation; pixel correctness after settling does not establish it.
