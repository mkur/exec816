# Single large-read throughput

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

Baseline measurement date: 2026-09-20. This isolates sequential read throughput from the
[earlier concurrent workload](block-io-dos-implementation.md#observed-bank-1-results),
which included opens, directory operations, seeks, rereads and background work.

The baseline below used a three-tick sleep after every SIO request. The
[clean-completion verification](#verification-without-the-successful-transfer-sleep)
records the current driver and its before/after results.

## Workload

The [probe](../../tests/programs/dos_large_read.act) opens `D1:LARGE.BIN` from the
existing MyDOS 4.50, 2,000-sector, 256-byte fixture and makes exactly one
`DOS.Read(file, buffer, 70003)`. It allocates a linear upper-RAM destination and
verifies every byte after the call. There are three live public tasks: the
application, filesystem worker and SIO worker, plus the kernel's idle context.
The build retains the existing eight-task stack layout and kernel bank 1.

The timer spans the emitted JSL to `DOS.Read` through its return. Open/mount,
allocation, verification, Close and shutdown are outside that interval. Passive
PC observations add no guest instructions. Time is emulated machine time, not
host execution time. The same workload runs once with raw NIR and once with
optimized NIR; this is not a concurrency or peripheral matrix.

The [existing SIO pin](../../toolchain/altirra-sio-queued.json) supplies AltirraOS
3.44, PAL, an 8x 65816 clock, shadow ROM and 1 MiB of memory. The peripheral is
the built-in FASTEST125 model, with **accurate disk timing enabled**, SIO
patching and burst I/O disabled. "Fastest" selects the serial profile; it does
not remove emulated disk mechanics. The pinned `diskprofile.cpp` still selects
288 rpm, and `disk.cpp` retains seek/rotational delays when accurate timing is
enabled. The local source hashes match those in the pin.

## Results

Both executions pass. See the [measurement record](../qualification/dos-large-read.json).

| Build | Read time | Useful file throughput | Sectors read |
| --- | ---: | ---: | ---: |
| Raw NIR | 48.712 s | 1,437.07 bytes/s | 277 |
| Optimized NIR | 48.714 s | 1,437.01 bytes/s | 277 |

Every sector is fetched once: sectors 18–25 followed by 1152–1420. The read
crosses both a fragmented sector link and a destination memory-bank boundary.
There are no seeks, cached rereads, extra EOF calls or competing applications.
The earlier 500–600 bytes/s figure describes the mixed workload, not this
single sequential call.

The optimized run divides into these non-overlapping intervals:

| Interval | Total | Share of Read |
| --- | ---: | ---: |
| Sector submitted to SIO start, including recovery wait and preparation | 15.834 s | 32.50% |
| SIO start to terminal IRQ post, including peripheral waiting | 26.802 s | 55.02% |
| Terminal post to filesystem's sector-call return | 1.882 s | 3.86% |
| Filesystem work between sector calls | 4.153 s | 8.53% |
| Read entry/exit overhead outside those intervals | 0.043 s | 0.09% |

Within those totals:

- **20.324 s (41.7%)** is the drive's ACK-to-Complete response gap, averaging
  73.37 ms per sector.
- **14.039 s (28.8%)** is recovery sleep overlapping an already submitted
  sector request. The full overlapping recovery sleeps average 58.71 ms;
  their samples include the sleep crossing the Open/Read boundary and the one
  ending after Read returns.
- **5.773 s (11.9%)** is actual serial byte-clock occupancy: 1,385 command bytes
  and 71,743 response bytes, including protocol and sector-link overhead.
- **3.249 s (6.7%)** is inside the file-copy routine. Raw NIR takes 3.850 s there.

The IRQ terminal post reaches the SIO worker's retire entry in an average
**1.515 ms**, with a **1.931 ms** observed maximum. Task wakeup is a small part
of the overall elapsed time in this workload.

## Interpretation

The baseline `lib/io/siodriver.act` published each completed request and then called
`EXECTASKS.Sleep(3)` before allowing the next transaction. This is the existing
[recovery policy](device-io-sio-implementation.md#slice-7-recovery-and-ordinary-registration):
at least two complete PAL frame periods of OS service and quiet-bus observation.
Some filesystem processing overlaps that interval. The report measures the
intersection of recovery sleep with the next submitted request's wait instead
of counting all sleep time as an additional serial cost.

The ACK-to-Complete gap measures peripheral response time before the sector
data arrives. It includes the drive model's seek/rotation and processing delays;
it is not time spent copying the file in Exec. Copy timing is elapsed time
around `MYDOSFILE.Copy`, including any preemption, rather than exclusive CPU
time. These diagnostics overlap the main breakdown and must not be added to it.

Recovery and rotational waiting are coupled. A follow-up check against
Altirra's default DD **15:1 interleave** finds that all **275 consecutive-sector
transitions**, in both compiler modes, match the forward angular spacing
exactly, with zero residual base-clock cycles between successive Complete
bytes. Those intervals are 155.027–188.162 ms. There is no additional revolution
on those transitions. The fragmented jump from sector 25 to 1152 takes one
extra revolution; this check does not isolate whether removing recovery would
avoid it.

The model's rotation period is 372,869 base cycles, or 210.251 ms on the pinned
PAL clock. Sector angular positions use the table
`[0,15,12,9,6,3,1,16,13,10,7,4,2,17,14,11,8,5]`, indexed by
`(sector-1) % 18`, with spacing `10.944 / (60000 / 288)` turns per table unit.
The forward position difference modulo one revolution predicts every
consecutive-sector Complete interval in the captured traces. The
[measurement record](../qualification/dos-large-read.json) includes this check
and the inspected emulator source hashes.

This corrects the initial recommendation to shorten recovery first: on this
particular interleave, submitting the next request earlier can simply move
time from recovery wait into drive wait. The measured 14.039 s is **not a
predicted removable cost**. On a tighter interleave, a pause could instead miss
a sector and add an entire revolution, as suggested during review. A controlled
shorter-pause run establishes its actual effect in the verification below;
these baseline measurements alone do not. The updated platform contract
requires Exec scheduling, unowned IRQ handling and shutdown restoration, but
does not require an OS stage-two service interval between every two requests.

Broad compiler work is not the first throughput fix indicated here. Optimized
copying saves about 0.60 s, but both end-to-end reads take essentially the same
time as recovery overlap and rotational phase change. Stack-use improvements
remain useful independently of this throughput finding.

This baseline investigation changed no production policy or compiler pin. Reserved
bank-zero memory changes by **0 bytes**, including **0 bytes per task**.
The measurements describe the pinned emulator/peripheral setup, not physical
hardware or a peripheral with no rotational delay. No new uninstrumented replay
or broader latency qualification is claimed by this focused probe.

## Reproduce

Use the existing pinned compiler, ROM and observer build, then run:

```sh
python3 tools/probe_dos_large_read.py --case raw --output build/dos-large-read/raw
python3 tools/probe_dos_large_read.py --case opt --output build/dos-large-read/opt
```

Each run produces `results.json` with build identities, runtime checks and
timings. The runner checks all 70,003 bytes, the exact 277-sector chain and
serial byte counts, native stack/domain guards, the protected interrupt stack
reserve, restored OS state, heap/bank ownership, released bus state and unchanged
media. The host watchdog is 1,800 seconds and the guest limit is 30,000 frames.

## Comparison without mechanical timing

The same optimized program and disk images were run once more with only
`accuratedisk=false`. Both images are byte-for-byte identical to the baseline.
The compiler, CPU, ROM, drive profile and baud are unchanged; SIO patching and
burst I/O remain disabled. This comparison still transfers every serial byte
through the IRQ driver. It is a deliberate timing override of the baseline pin,
not a change to the production configuration or a particular SD-drive model.

| Optimized single Read | Elapsed | Useful file throughput |
| --- | ---: | ---: |
| Accurate mechanical timing enabled | 48.714 s | 1,437.01 bytes/s |
| Mechanical timing disabled | 27.768 s | 2,521.02 bytes/s |

All 70,003 bytes, all 277 sectors, stack/domain guards and cleanup checks pass.
The drive's ACK-to-Complete gap falls from 20.324 s total to **0.156 s**
(0.564 ms per sector). Serial byte-clock occupancy remains **5.773 s**.
The remaining intervals are:

- **14.873 s** from sector submission to SIO start, including **13.246 s** of
  recovery sleep with the next request waiting, or **47.7% of the entire Read**.
- **6.634 s** from SIO start to terminal post, including the serial bytes.
- **1.849 s** from terminal post to the filesystem's sector-call return.
- **4.373 s** between sector calls, including **3.193 s** in the copy routine.
- **0.038 s** at the Read entry/exit edges.

The earlier 500–600 bytes/s mixed-workload figure is not a drive-speed ceiling.
With mechanics removed, recovery is the largest measured remaining cost. This
supported testing a shorter successful-transfer recovery policy for fast
peripherals; it did not establish its achievable speedup or late-byte safety.
The wire alone accounts for only about 21% of this baseline run. The 125-kbaud
profile therefore has substantial bandwidth that the per-sector path did not
use. No driver code was changed in this comparison.

Reproduce this single optimized comparison with:

```sh
python3 tools/probe_dos_large_read.py --case opt --no-disk-timing --output build/dos-large-read/opt-no-disk-timing
```

The [measurement record](../qualification/dos-large-read.json) retains the explicit
configuration override, identical-image checks, result hash and timings.

## Verification without the successful-transfer sleep

Verification completed: 2026-09-21.

The current driver omits `Sleep(3)` after a successful hardware transaction.
Completed transactions with errors retain that interval; uncertain outcomes
still leave the bus offline until platform reset. CRITIC is restored at
retirement, but the dedicated Exec workload does not guarantee stage-two OS
service between queued requests. Exec scheduling, unowned IRQ handling and
shutdown restoration remain required. See the
[implementation update](device-io-sio-implementation.md#clean-completion-without-an-os-service-sleep).

The same single Read and media were rerun with the same compiler, ROM, CPU and
FASTEST125 profile. All 70,003 bytes and 277 sector requests pass, with **zero
successful-transfer recovery sleeps** observed in each run.

| Build and disk timing | Read time | Useful file throughput |
| --- | ---: | ---: |
| Optimized baseline, mechanics disabled | 27.768 s | 2,521.02 bytes/s |
| Raw, mechanics disabled, success sleep removed | 17.584 s | 3,980.98 bytes/s |
| Optimized, mechanics disabled, success sleep removed | 16.696 s | 4,192.80 bytes/s |
| Optimized baseline, accurate mechanics | 48.714 s | 1,437.01 bytes/s |
| Optimized, accurate mechanics, success sleep removed | 48.715 s | 1,437.00 bytes/s |

Without mechanics, optimized throughput increases **66.3%** and Read time falls
by **11.072 s**. Submission-to-start time falls from 14.873 s to 3.639 s; serial
byte-clock occupancy remains 5.773 s. The remaining time includes driver setup,
filesystem copying, request/reply processing and scheduling. This change does
not attempt further optimization of those paths.

With accurate disk timing, throughput is essentially unchanged:
earlier submission moves waiting into the peripheral response interval. This
supports the interleave explanation above. Removing the software pause helps
the fast nonmechanical case; it does not bypass the emulated floppy's rotation.

Both compiler modes pass all 22 recovery cases, including late traffic during
preparation of the next request and immediate request deletion/reuse. Separate
eight-task READ/PUT/read-back runs and four/eight-task 256-byte READ runs pass
the existing wire deadlines and replay identically without observation. They
include background heap, ports, signals and timed waits, plus a real keyboard
IRQ during traffic. The 256-byte boundary/recovery suite and FASTEST125,
STOCK810 and Happy NONE functional regressions also pass in both modes.
This reruns the existing transport gates without loosening their limits.

Native guards, clean shutdown state, buffer checks and resource ownership pass.
The large-read SIO worker touches 656 raw / 504 optimized bytes of its existing
1,024-byte stack; the 256-byte interrupt reserve remains untouched. Kernel
interrupt reserves also remain intact. Reserved bank-zero growth is **0 bytes**,
including **0 per task**. The
[verification record](../qualification/sio-fast-completion.json) contains exact
inputs, artifact hashes, results and reproduction commands. Earlier measurements
retain their original record. This is pinned-emulator evidence; physical
peripherals and arbitrary late streams after another command is armed are not
qualified by this check.
