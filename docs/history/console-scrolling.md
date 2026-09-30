# Idle console scrolling

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/console.md) and [history index](README.md).

This is the historical single-instance scrolling qualification. Current
four-window behavior and the native-copy/span refactor are recorded in the
[console refactor development record](console-refactor-implementation.md).
The measurements below remain tied to their original compiler and source.

## Measurement

The unchanged [native benchmark](../../tests/programs/console_scroll.act) measures
16 operations per phase with the guest RTC: retained-cell scrolling alone,
physical redraw alone, a hidden worker, and a visible worker. The worker starts
at the bottom row and receives 16 line feeds in one request. Visible timing
includes draining the final redraw. There are no mounted disks, filesystem
worker or SIO worker. Stack checks stay enabled.

The compiler is pinned to `2d73c03`, with the
[paced shell emulator and PAL 8× machine](../../toolchain/altirra-shell-paced.json).
Both before and after measurements use that same emulator and ROM. Host pacing
does not enter the reported guest times. The baseline is the console code at
`c3500c8`; the benchmark source bytes are identical across the comparison.

| Operation | Raw before → after | Optimized before → after |
| --- | ---: | ---: |
| Retained-cell scroll | 52.5 → 27.5 ms | 47.5 → 22.5 ms |
| Full-screen redraw | 156.3 → 60.0 ms | 148.8 → 53.8 ms |
| Worker, hidden screen | 188.8 → 55.0 ms | 176.3 → 48.8 ms |
| Worker, visible screen | **337.5 → 110.0 ms** | **318.8 → 97.5 ms** |

These are average times per operation using nominal 50 Hz PAL ticks, with
20 ms resolution over each 16-operation phase. The visible worker improves
from about 3.1 to 10.3 lines/second in optimized code. These measurements do not
establish a maximum keyboard latency or filesystem throughput. Shared FIFO
writes and whole filesystem operations can still delay a shell command.

## Implementation and asynchronous entry

`CONSOLECORE.EditQuantum` caches the buffer and bounds and separates forward
copying from clearing the last row. It still changes at most 40 cells per call,
including a quantum that crosses from copied cells into the cleared tail.

`CONSOLEDISPLAY.Cells` clips a row span once, computes its screen position once
and translates glyphs through the existing table inside a contiguous loop.
It still visits at most 38 retained cells and reserves two screen writes for
the cursor overlay. Partially dirty rows, narrow views, hidden rows, unsupported
glyphs and the borrowed-screen restoration keep their existing behavior.

The worker skips empty work without changing its ownership protocol:

- `CONSOLEINPUT.Pending` observes the fixed capture ring's byte counters/loss
  latch. A positive result still enters Forbid/Pump/Permit; native Take still
  protects ring consumption. An IRQ after an empty observation retains its
  notification signal, so the later Wait cannot lose that event.
- The arrival hint only compares the queue head against its embedded sentinel;
  it never dereferences the sampled head. Even a stale or torn pointer comparison
  can only choose whether to attempt the protected dequeue. Control(2) owns
  removal, and Control(8) rechecks durable queues before Wait. An arrival after
  that recheck retains its ordinary port signal.
- An active write is owned and retired only by this worker. While it exists,
  the worker can yield directly without asking the kernel whether work remains.
  Cancellation still marks the active request and completes its current logical
  scroll before replying. Once the write retires, the protected idle check runs.

Input is checked and the worker yields between the original bounded output
quanta. Copying and rendering remain preemptible with IRQs enabled. No new
masked region, service selector, ABI layout or task is introduced.

## Validation and memory

Raw and optimized emitted-code checks cover the retained-cell oracle, public
device requests, cancellation during scrolling, a 65,560-byte source crossing
banks, physical keyboard input, hidden redraw, cursor/screen restoration and
close/reopen input isolation. The display fixture also checks a dirty interval
starting and ending inside rows across three quanta, with clipped columns/rows,
a high-byte glyph and untouched surrounding guards. Core/display runs include
kernel banks 1 and 3. The shipped optimized shell runs its normal command suite.

Eight-task shell regressions use FASTEST125 and 128-byte MyDOS media in raw and
optimized builds, including physical key input, scrolling, allocator/message/
signal interference, passive timing and identical-image/key replay. Byte,
alarm, Forbid and queue timing limits are unchanged. This follow-up does not
repeat the historical 256-byte large-file or stock-drive matrices.

The host suite passes 157 of 158 checks. Its sole failure is the pre-existing
historical SIO sector record comparison against the current `lib/io/siodriver.act`;
that file and historical record are unchanged by this work.

Reserved bank-zero delta is **0 bytes fixed and 0 bytes per Task**, in both
loading and steady runtime. The eight-slot layout remains 57,232 bytes loading
and 61,536 bytes at runtime including the OS. Stack/DP pools, guards, alignment,
interrupt reserves and unused reserved capacity are unchanged. No persistent
upper-RAM state or heap allocation is added. Stack/domain guards and protected
interrupt reserves pass the recorded native workloads.

To reproduce the idle measurement:

```sh
python3 tools/test_console_scroll.py --case raw --output build/scroll-check/raw
python3 tools/test_console_scroll.py --case opt --output build/scroll-check/opt
```

The runner fails if 16 visible scrolls take more than 112 guest ticks (about
140 ms per line); the baseline takes 270 raw and 255 optimized ticks. Existing
core/display/device/lifetime runners accept `--paced` to use the same pinned
emulator. For concurrent SIO:

```sh
python3 tools/test_shell_concurrent_suite.py --only target128-raw,target128-opt \
  --output build/scroll-check/concurrent
```
