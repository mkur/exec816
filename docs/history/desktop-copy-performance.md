# Desktop copy throughput

[Implementation plan](../plans/gem4xe/desktop-copy-performance-plan.md) ·
[Historical records](README.md)

The desktop now uses the same **16 KiB copy buffer** as shell COPY. The change
is confined to the single heap-allocated copy job and its private layout
observer. It adds no worker, API, runtime setting or validation layer.

## Matched desktop comparison

All variants reuse the resident image from `build/merge-origin-20261012/demo`.
Only the desktop application's buffer size changes. The source is 32,805 bytes
(32 KiB plus a 37-byte tail), copied within a fresh WORK volume with 2,880
256-byte SDFS sectors. The machine is PAL, 65C816 at 8x, with the pinned
AltirraOS 3.44 ROM, VBXE and accurate Generic 57600 SIO timing. These are
emulator development measurements, not hardware qualification or IDE timings.

| Desktop buffer | Transfer and finalization | Bytes/s | Speed relative to 512 B |
| --- | ---: | ---: | ---: |
| 512 B | 155.39 s | 211 | 1.00x |
| 1 KiB | 106.61 s | 308 | 1.46x |
| 2 KiB | 78.64 s | 417 | 1.98x |
| 16 KiB | 54.88 s | 598 | 2.83x |

Shell COPY, already using 16 KiB, took **47.64 s** (689 bytes/s). Its timing
starts with the READ into the loaded command's transfer buffer, excluding
executable loading and file opening, and ends at shell readiness after closing
both handles. It ran later in the same session on the same WORK geometry;
cache history, destination placement and completion/publication work differ.
Treat it as a reference, not proof that all of the 7.24-second difference is
GUI overhead.

Times start at the first observed active payload READ packet and end after
Close/Rename, when the copy job is retired. They exclude destination admission,
the initial dialog repaint and the final folder refresh. The pinned bridge
cannot put PC breakpoints in upper banks, so the harness samples packet and
application state at bank-zero IRQ checkpoints. One completed transfer per
variant establishes this comparison; these are not throughput percentiles.

SDFS publishes staged allocation and file metadata at the end of a Write
request, and at internal boundaries. A 512-byte Write closes the batch after
only two payload sectors. Larger requests reduce those forced publications,
read/write alternations and application/API round trips. The filesystem keeps
its existing internal transfer and commit bounds. Progress redraws occur at
completed chunk boundaries: 16 KiB chunks naturally publish progress every
16 KiB rather than every 4 KiB.

## Cancellation tradeoff

Escape remains handled between synchronous Read/Write pairs. On the measured
SIO configuration, increasing throughput makes cancellation much slower:

| Buffer | Escape during first Read: close begins / cleanup complete | Escape during first Write: close begins / cleanup complete |
| --- | ---: | ---: |
| 512 B | 2.35 / 3.37 s | 1.89 / 2.91 s |
| 1 KiB | 3.19 / 4.63 s | 2.30 / 3.75 s |
| 2 KiB | 4.43 / 6.72 s | 2.92 / 5.20 s |
| 16 KiB | 24.49 / 38.69 s | 12.91 / 27.12 s |

These are two phase-controlled samples per variant, not worst-case bounds.
Cleanup includes closing the handles and deleting the partially written
temporary file; more copied data also makes deletion more work. Ordinary
desktop events on this Task wait for the same Read/Write pair. Other
applications have their own Tasks.

Forty physical Panel presses per case measure submission to matching button
scanout. Idle median/p95 is 80.3/100.3 ms for all variants. With a 128 KiB copy
active throughout the sample batch:

| Copy buffer | Panel median | Panel p95 | Largest sample |
| --- | ---: | ---: | ---: |
| 512 B | 80.3 ms | 120.2 ms | 120.2 ms |
| 1 KiB | 80.3 ms | 120.5 ms | 140.3 ms |
| 2 KiB | 100.1 ms | 120.4 ms | 140.5 ms |
| 16 KiB | 100.2 ms | 120.5 ms | 140.4 ms |

Feedback is sampled once per frame after application state changes. The larger
buffers cost about one frame at the median in this batch; p95 stays near
120 ms. This is a limited appearance comparison, not a universal latency bound.

Throughput is the chosen priority: most copies finish normally. Retain 16 KiB
and consider a separate copy Process only if desktop-local interaction during
long transfers becomes the next usability problem. A worker alone would not
remove the filesystem cost of deleting a partial file.

## Memory and validation

The copy job grows from 1,302 to 17,174 bytes, **15,872 additional upper-heap
bytes while a copy is active**, released with the job. Reserved bank-zero delta
is **0 fixed, 0 per public Task, 0 idle**, including guards, alignment and unused
capacity. Stack reservations, VRAM, filesystem commit rules and file-replacement
semantics remain unchanged.

The [measurement record](../development/desktop-copy-performance.json) retains
the four complete comparisons and their input hashes. All pass independent
readback of the source and destination, partial final-chunk handling, temporary
file removal, preserved source bytes, orderly EXIT and stack/domain guards.
The selected variant's smallest public-Task stack margin is 154 bytes above
its reserved floor; idle retains 127 bytes. The host suite passes 451 tests
with 4 skips. The production desktop binary is byte-identical to the measured
16 KiB variant.

The packaged file-operation fixture now leaves room for one full 16 KiB chunk
before running out of space. Its cancellation check requires the actual
`Copy cancelled` result with no DOS error. The old 21-free-sector fixture could
hit disk full on the first large Write before Escape was processed; checking
only that temporary files vanished would conflate cancellation with failure.
The following replacement still reaches a partial disk-full failure and must
preserve the existing destination.

The rebuilt OF816 package is `build/desktop-copy-dc2/demo/exec816-demo.zip`
(SHA-256 `33dacd5582fd5fb33383a942209ab8ddd59af17d9a10d9bc3b6a444a79d8a9a2`).
Its extracted-distribution `--files-only` walkthrough passes copy, default and
confirmed replacement, actual cancellation, read-only and partial disk-full
errors, preserved old destination, temporary-file removal, TXT launching and
collection, saved-settings restart and orderly EXIT. Guards remain intact;
the smallest public-Task margin in this walkthrough is 161 bytes, idle 127.
All 22 packaged checksum entries match. The ZIP retains OF816's five-second
autoboot, the matching disks, pinned ROM and license notices.

Launch from the repository root:

```sh
./build/desktop-copy-dc2/demo/launch-altirra.command
```

Reproduce an experimental size without changing production sources:

```sh
python3 tools/measure_desktop_copy.py \
  --bundle build/merge-origin-20261012/demo \
  --output build/copy-comparison-16384 --buffer 16384
```

Use `--shell` to include the existing shell COPY reference and `--reuse` to
repeat a previously built comparison on a fresh WORK disk. The harness records
application/source hashes, machine inputs, 40 idle and loaded physical button
presses, cancellation samples, stack usage and independent binary readback.
Experimental system disks are explicit measurement overrides; the original
OF816 ZIP is not altered to pretend they are distribution checks.
