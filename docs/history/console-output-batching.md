# Bulk console output batching

[History index](README.md) · [Implementation plan](../plans/console-output-batching-implementation-plan.md) · [Current console contract](../reference/console.md)

OB1–OB5 implement bounded batching in the existing console worker. Several
retained line edits now share one multi-row copy/fill, followed by painting the
surviving text spans. CAT still forwards its existing 512-byte reads directly;
there is no second source buffer, Task, semaphore or kernel operation.

## Behavior and limits

Only long writes to a synchronized, fully visible bitmap view at its bottom row
enter batching. The shared context occupies 44 bytes. Each turn consumes at most
64 source bytes and recycles one character row. A batch ends at four scroll rows,
256 bytes, four turns, a changed VBI tick, request end, a control barrier,
cancellation or waiting short output. There is no delay to collect another
request. The text backend and height-one/clipped fallback remain ordinary paths.

Changed spans move to their final logical rows before submission. Completion
acknowledges the copy/fill without clearing this undrawn text. Painting retains
its four-row/160-cell budget. Input and READ service continue between quanta;
model edits and dependent drawing stay gated while DMA owns the framebuffer.
The batch retains only scalar identities and retained model state after reply.
Cancellation never consumes or replays another source byte. Presentation changes
can discard the optimization and redraw accepted state after DMA is quiescent.

## CAT measurements

The preserved [baseline](../development/console-output-batching-baseline.json)
and [final evidence](../development/console-output-batching-ob5.json) use the
same 23,872-byte/768-LF file, 47 writes, 48 reads including EOF, compiler, ROM,
actual development emulator and 4 MiB PAL ×8/VBXE machine. SDFS uses 128-byte
sectors and the generic 57,600-baud profile. Both bitmap runners select the
actual `mouse_input.tooling` emulator (`a7defb…`), as recorded in their frozen
manifests; the baseline summary's generic emulator field is not that binary.
Command timing is ShellDispatch
entry through return, including loading/unload and excluding typing and the
following prompt. Guest cycles exclude debugger pauses.

| Workload | Before | After | Change |
| --- | ---: | ---: | ---: |
| Cold CAT | 54.154 s | 43.713 s | 19.3% less elapsed time |
| Cached CAT | 26.670 s | 16.082 s | 39.7% less; 1.66× throughput |
| Cached CAT to NIL | 2.116 s | 2.122 s | Essentially unchanged |
| Cached CAT Write intervals | 24.374 s | 13.506 s | 44.6% less |
| Console CPU inside those Write intervals | 12.922 s | 8.461 s | 34.5% less |
| Scroll launches in cached command window | 769 | 332 | 56.8% fewer |
| VRAM copy traffic in cached command window | 57,090,560 B | 23,531,520 B | 58.8% less |

The new cached window contains 768 logical scroll rows. The historical 769
launches include command-boundary overlap with echo; do not equate that count
with the file's 768 LF bytes. The new clear traffic is 1,966,080 bytes. Cold
output initially fills the screen, so its logical scroll count is lower.

The cached run has 98 one-row, 92 two-row, 82 three-row and 60 four-row lists.
Of 355 batches, 248 flush at a tick boundary, 60 at the row/turn limit and 47 at
request end; 23 batches need no copy. The largest accepted batch is 158 bytes.
Thus the tick bound usually stops gathering before the four-row cap. Average
launch-to-IRQ observation is 15.14 ms; it is an upper bound, not an exact BUSY
measurement. Reducing list count supplies most of the gain.

Nested preparation/drawing totals are separate from the disjoint CPU accounting:
retained feeding charges about 0.562 s, retained edits 0.091 s, and batch painting
2.831 s in the cached command window. These totals overlap callers and must not
be added to the CPU partition. Remaining per-turn, submission, completion,
painting and scheduler costs prevent a proportional whole-command speedup.
The **2× cached throughput target is not met**. The initial limits remain;
this result does not justify extending gathering across more VBI ticks.

The evidence also records the next prompt's short-write return as a separate
presentation boundary, and compares exact final retained pixels in an execution
with passive trace logging disabled. This is not a scanout timestamp.

## Input and remaining latency limits

On the preserved and new shell-only images, unloaded physical `ECHO A`/`EXIT`
keys reach echo drawing completion about 0.14–0.16 ms later. For `A`, capture IRQ
to the echo presentation return changes from 15.972 to 16.113 ms; Return changes
from about 17.071 to 17.234 ms. These exclude hardware scan latency and subsequent
scanout. The short-write present-before-reply contract remains intact.

A separately rebuilt baseline at `d211234` and the current image run the same
eight-Task workload: 80-byte full-width output, other console instances, physical
keys, pointer sampling and SIO. Complete worker-turn CPU peaks are 21.225 and
21.255 ms. SIO deadlines pass in both. Sampled first correct frames change from
89.9/89.9 ms to 78.8/103.0 ms for unfocused/focused letter echo. The frame-sampling
intervals overlap; this is a mixed result, not a visible-input improvement claim.

The sampled READ collection improves from 39.4 to 21.9 ms, while BREAK delivery
changes from 2.4 to 45.5 ms. In the latter current sample, capture occurs just
after input service and the worker spends 37.4 ms off CPU before its next turn;
the baseline capture falls just before service. This records a real phase-sensitive
latency cost, without attributing it to accumulation limits. The input-service
CPU itself remains about 1.78 ms for BREAK. Gathering still yields between its
bounded quanta. No priority, Task quantum or input policy was changed.

The loaded harness requires actual BUSY for Z/A/Return. BREAK samples the active
output phase: after focus damage, continuous output can remain on full-redraw
fallback and offer no eligible asynchronous scroll at that rendezvous. The
4 ms worker, 20 ms scroll and 40 ms visible-input goals remain unqualified.

## Validation, memory and reproduction

All checks use the development tier. The linked evidence covers:

- [OB1](../development/console-output-batching-ob1.json): checked multi-row
  rectangles, fill-only lists, exact pixels/neighbors, busy rejection, completion
  IRQs, timeout/wrap/lost IRQ and reset-required retention.
- [OB2](../development/console-output-batching-ob2.json): independent linear
  terminal and damage reconstruction across 188 accepted prefixes per NIR mode.
- [OB3](../development/console-output-batching-ob3.json): raw/optimized bulk
  pixels, multi-row hardware launches, ordinary scroll/reply paths, cancellation,
  poisoned sources after reply, text output and eight-Task fairness.
- [OB4](../development/console-output-batching-ob4.json): 24 batch phase/control
  cases per mode, ordinary continuation interleavings and eight fault cases per
  mode. These cover hide/show, focus, stale generation, Stop, destroy/reuse,
  PRESENTING deferral, accepted-prefix retention and reset-required park.
- [OB5](../development/console-output-batching-ob5.json): throughput, loaded and
  unloaded input, trace-free replays, archive contents/checksums and OF816 boot.

All 331 host tests pass, with four expected historical skips. Generated ABI
checks pass. These results do not constitute full hosted-system qualification.

Every slice adds **0 reserved bank-zero bytes**, fixed, root/kernel, per public
Task and idle, including guards, alignment and unused capacity. The batch adds
44 used bytes inside the existing 2,048-byte globals arena; the demo uses
1,450 bytes, leaving 598. Upper resident reservations and Task pools are unchanged.
The demo's emitted routine total grows by 9,199 bytes; linked segment payload
including C data grows by 9,246. The worker still reserves 2,560 stack bytes;
observed stack peaks and remaining guard/headroom margins are in the evidence.

Use fresh output directories; preserve `build/demo-bitmap-shell/` and
`build/cat-long-trace/`. Build with `tools/build_demo.py --bitmap-shell-only`,
then run `tools/measure_bitmap_cat.py --bundle DIR --output DIR`. Its
`--input-only` mode measures unloaded keys, and `--analyze-only` reuses a saved
trace. `tools/measure_console_batch_load.py --output DIR` runs the loaded
comparison; `--reuse` and `--replay` reuse its image. The baseline loaded build
uses the preserved pre-batching revision with the same measurement harness.

The refreshed `build/output-batching/demo/exec816-demo.zip` boots OF816 into the
full-screen bitmap shell after five seconds, includes the matching disk, pinned
ROM, notices and checksums, and starts no primes. Build files and traces remain
outside the ZIP. GitHub publication is separate.
