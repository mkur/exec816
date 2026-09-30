# Exec816 versus SpartaDOS X: one 8 KiB file read

Measured 2026-09-26, Exec816 revision `d4eff6a`. Reading 8,192 bytes takes
**7.624 seconds in Exec816 and 7.554 seconds in original SpartaDOS X 4.50**.
Exec takes 70 ms, or **0.93%**, longer in this workload.

| Measurement | SpartaDOS X 4.50 | Exec816 SDFS |
| --- | ---: | ---: |
| One 8,192-byte read call | 7.553584 s | 7.623775 s |
| Useful throughput | 1,084.5 bytes/s | 1,074.5 bytes/s |
| File-data sectors fetched during Read | 64 | 64 |
| File-map sectors fetched during Read | 1 | 2 |
| First data command through last data checksum | 7.514095 s | 7.486464 s |

The timer covers only the read call and its return. Program loading, allocation,
Open, Close, byte verification and shutdown are outside it. Exec makes one
`DOS.Read(file, buffer, 8192)` into upper RAM; the SDX reader makes one CIO
Get Bytes request into `$8000–$9FFF`. Neither reader prints during the call.
There is no Exec prime worker or shell workload: only the reader, filesystem
and SIO Tasks, plus the kernel's idle context.

Both use the **same ATR and payload**, with 720 sectors of 128 bytes. The
machine is the pinned PAL 800XL, 8x 65816, shadow ROM, 64K plus fifteen upper
banks, and AltirraOS 3.44 for 65816. The drive uses **GENERIC57600**, accurate
disk timing enabled, SIO patching off, burst I/O off and random delay off.
Every timed transaction has the same observed baud: 30 master cycles per TX
bit and 31 per RX bit. These timings include the emulator's mechanical disk
delays; they are not a measurement of maximum serial bandwidth.

SDX boots with `USE OSRAM`, `DEVICE SPARTA` and `DEVICE SIO`. The host swaps
its separate startup volume for the common data disk before Open. The
benchmark file has not been read in either system. Payload bytes vary with
both their low and high offset bytes, so the byte check detects reordered
sectors as well as corrupted bytes.

There is one filesystem boundary difference: SDX fetches the first file map
during Open, while Exec fetches it during Read. Both read the second map
during Read. The final row in the table uses identical boundaries around the
64 data sectors, **including that intervening second map**; Exec is 28 ms
quicker over this span. The practical result is that the systems are very
close for this read, rather than the large difference previously observed
when loading HELLO. This does not measure loader performance.

The [CPU-worker follow-up](read-8k-background.md) repeats the read with a
second application Task continuously computing and a control using the same
compiled image with that worker stopped.

## Validation and reproduction

Two independent cold boots per system produce exactly the same read-call
timings. Each verifies all 8,192 bytes. An additional replay per system with
CPU observation and profiling disabled produces exactly the same data-sector
span. Hardware traces verify sector order, payloads, checksums, baud, and the
absence of repeated payload reads. All runs preserve the disk image.

Exec also passes the existing native stack/domain guards, interrupt headroom,
OS restoration, heap/bank ownership and released-bus checks. This was a focused
optimized-build measurement, not a compiler or full release qualification.
Production code and the play image are unchanged. Reserved bank-zero growth
is **0 fixed bytes and 0 bytes per Task**, including guards and unused capacity.
The readers' temporary application buffers add no system reservations.

The [measurement record](../development/read-8k-comparison.json) retains the
pins, hashes, timing breakdowns, runtime checks and repeated-run evidence.

```sh
python3 tools/measure_read_8k.py --prepare
python3 tools/measure_read_8k.py --hardware-only --repetitions 1
```

Omit `--prepare` to reuse the retained, hash-checked Exec image. Artifacts are
under `build/development/read-8k`. The original SDX cartridge and pinned
emulator/ROM are the same inputs used by the
[earlier comparison](spartados-dos-comparison.md).
