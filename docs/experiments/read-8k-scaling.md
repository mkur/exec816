# An 8 KiB read with 2, 4 and 6 application Tasks

Measured 2026-09-26. Read time rises sharply when three computing Tasks run
alongside the reader. The six-application case uses all eight public Task slots.

| Application Tasks, including reader | Computing workers | Public slots used | Read time | Useful bytes/s |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 1 | 4 | 7.821973 s | 1,047.3 |
| 4 | 3 | 6 | 20.918342 s | 391.6 |
| 6 | 5 | 8 | 21.820753 s | 375.4 |

The filesystem and SIO workers occupy two additional public slots. The private
idle context is separate. These counts were checked in the live kernel state
before Read. There is no shell or console workload.

All three cases use **one compiled image**, with a host-supplied application
count selected before startup. Each computing worker has the reader's priority
(0), private computation state and progress counters. It repeatedly performs
256 shift/XOR iterations without I/O, Sleep, Yield or other kernel calls in
the work loop. Native preemption schedules the reader and workers.

The exact disk from the [original comparison](read-8k-comparison.md) is reused:
8,192 payload bytes, 720 sectors of 128 bytes, GENERIC57600, accurate disk timing
enabled, SIO patching and burst I/O disabled, random delay disabled. ROM,
emulator, PAL 800XL, 8x 65816 and compiler pins are unchanged. Only the one
`DOS.Read` call is timed; loading, Open, worker setup, byte verification,
worker shutdown and Close are excluded.

The generalized fixture uses per-worker arrays and differs from the
[previous one-worker fixture](read-8k-background.md). Its two-application
result is the baseline for this table. Code and startup timing, including the
initial rotational phase, differ from that earlier build. The earlier original
SpartaDOS X foreground baseline remains 7.553584 s; it was not rerun here.

## Sector timing explains the large jump

| Component of Read | 2 applications | 4 applications | 6 applications |
| --- | ---: | ---: | ---: |
| Outside SIO transactions | 1.781 s | 7.408 s | 12.942 s |
| ACK-end to Complete-start device waiting | 4.303 s | 11.772 s | 7.141 s |
| Mean gap between sector transactions | 26.348 ms | 109.823 ms | 191.850 ms |

The first two rows are disjoint elapsed-time components. The final row is a
diagnostic within the first and must not be added to it. All cases issue the
same 66 reads: 64 data sectors and two maps. Baud, wire-byte counts and payload
checksums are unchanged, with no repeated data reads.

The device Complete timestamps give a precise rotational check. Comparing
the same 65 successive-sector intervals:

- From 2 to 4 applications, **62 intervals gain exactly one disk rotation**;
  the other three are unchanged. This accounts for 13.036 seconds of additional
  interval time, versus 13.096 seconds of additional whole-call time.
- From 4 to 6 applications, three intervals gain a rotation and 62 are
  unchanged, adding 0.631 seconds within those intervals.

One rotation in the pinned model is 372,869 base ticks, approximately 210.251 ms
on the PAL clock. Local disk-model source hashes match the pin. Increased
request gaps under CPU contention cause missed rotational opportunities in
this accurate disk profile. The slowdown is in the read path; no executable
loader runs inside the measured interval. This does not establish throughput
for a peripheral without mechanical delays.

## Validation and reproduction

Two independent cold boots per count produce identical timings, runtime
checks and worker counters. All 8,192 bytes and each worker's final computation
match independent host checks. Every worker progresses in each quarter of
Read. Work entries during Read are `[629]`, `[642, 621, 628]`, and
`[402, 396, 399, 393, 395]` respectively. Background work is observed during
all 66 transactions in every case.

The six-application case also passes a hardware-only replay with instruction
observation/profiling disabled: its sector span, counters and runtime checks
match exactly. Native stack/domain guards, interrupt headroom, worker removal,
OS restoration, heap/bank ownership, unchanged media and released-bus checks
pass. This was a focused optimized benchmark, not full qualification.

Production code, compiler pin and play image are unchanged. Reserved bank-zero
growth is **0 fixed bytes and 0 bytes per Task**. Each computing worker uses
an existing 1,568-byte slot: 1,024 stack bytes, 32 stack-guard bytes and a
512-byte DP reservation including guards, alignment and unused capacity.
The eight-slot layout and total memory reservation are unchanged.

The [record](../development/read-8k-scaling.json) retains the pins, hashes,
all timings, per-worker progress, runtime checks and rotational comparison.

```sh
python3 tools/measure_read_8k_scaling.py --prepare
python3 tools/measure_read_8k_scaling.py --tasks 6 --hardware-only --repetitions 1
```

Omit `--prepare` to reuse the retained image. Artifacts are under
`build/development/read-8k-scaling`; the existing original comparison supplies
the common disk image.
