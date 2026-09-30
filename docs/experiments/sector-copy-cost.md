# Isolated SDFS sector-copy cost

Measured against Exec816 `3d8ca49`, using pinned actionc `47cd55b`, the pinned
AltirraOS 65816 ROM and PAL 8x emulator. This implements the measurement step
after the [SIO driver migration](../history/sio-driver-boundary-implementation.md).
Production code, compiler pin and play image are unchanged.

The byte loop takes about **3.2 ms per 128-byte sector** and accounts for about
**96% of uninterrupted Consume time**. Setup and bookkeeping together take
about 0.14 ms. The older 4.24/5.13 ms stopped/active measurements include
interrupts and time spent running other Tasks; they are not pure copy costs.

For HELLO's 18 full sectors and 55-byte tail, the uninterrupted loop samples
imply roughly **58 ms of copy work in total**. Faster copying is worthwhile,
especially for larger reads, but this measurement does not explain most of
HELLO's 3.88/4.16-second open-to-prompt latency. Nor is 58 ms a promised loading
speedup: changing CPU work can change scheduling and disk rotational waits.

## Method

The [fixture](../../tests/programs/sector_copy.act) calls the real
`SDFSFILE.ContinueOperation`, entering `Consume` with a resident sector buffer.
Only the root Task runs; there is no mounted disk or SIO worker. Workspace,
operation records and buffers are in upper RAM, as in the filesystem worker.
IRQs and NMIs stay enabled. Each raw/optimized build measures 32 repetitions of:

- A continuing 128-byte sector, matching HELLO's full sectors.
- A final 55-byte fragment, matching HELLO's last sector and its Finish path.
- A continuing 256-byte sector, checking how loop cost scales with length.

The [host tool](../../tools/measure_sector_copy.py) decodes the emitted routine
with the pinned compiler's decoder. It identifies the unique backward loop
branch and checks the matching exit; it fails if that control-flow shape changes.
Passive emulator PC markers delimit setup, loop and bookkeeping. There are no
additional guest timing instructions and no separately rewritten copy loop.
The optimized loop's 235 machine-code bytes are identical in the fixture and
the retained diagnostic HELLO image. Raw emission uses 278 loop bytes.

Setup includes the prologue, length/offset calculation, pointer preparation and
initial index store. Loop time includes all per-byte address calculations,
source loads, destination stores, the sparse-data branch, index updates and the
final loop test. Bookkeeping includes cursor/count/stage updates, optional
Finish, and the epilogue/return. This is the cost of the compiled byte loop,
not just the two memory instructions that read and write a byte.

Any native IRQ or NMI entry during an activation excludes that whole activation
from the isolated statistics. Interrupted samples remain in elapsed statistics.
Uninterrupted elapsed time still includes machine bus/video timing; it is not
an ideal instruction-cycle model. Host debugger pauses do not count.

## Isolated fixture

These are **means of complete uninterrupted activations**, in milliseconds.
Different bus/video phases explain small differences from the HELLO samples.

| Case | Raw loop | Optimized setup | Optimized loop | Optimized bookkeeping | Optimized total |
| --- | ---: | ---: | ---: | ---: | ---: |
| 128 bytes, continuing | 3.903 | 0.097 | 3.179 | 0.045 | 3.321 |
| 55 bytes, final | 1.667 | 0.104 | 1.363 | 0.102 | 1.569 |
| 256 bytes, continuing | 7.812 | 0.097 | 6.370 | 0.046 | 6.512 |

Of 32 samples per case, raw retains 24/29/19 uninterrupted activations and
optimized retains 27/29/22. The full-sector loop scales approximately with byte
count; the per-sector setup/bookkeeping remains small. The final fragment has
more bookkeeping because it commits the completed file position and result.

The emitted loop reconstructs the buffer pointer and effective byte addresses
on each iteration. It also tests the sparse flag inside the loop. These costs
are visible in the retained disassembly; this slice does not change them.

## Same-image HELLO check

The existing S3 diagnostic XEX is replayed with the new passive markers, once
with the prime worker stopped and once active. On-wire sector commands select
the HELLO payload; directory record consumption is excluded explicitly.
No full demo recompilation is needed.

For the 18 full 128-byte sectors, each run has ten uninterrupted and eight
interrupted activations. The table compares **uninterrupted means** with the
mean across all 18 sectors, in milliseconds.

| Prime worker | Isolated setup | Isolated loop | Isolated bookkeeping | Isolated total | All-sample loop | All-sample total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Stopped | 0.094 | 3.136 | 0.044 | 3.274 | 3.982 | 4.245 |
| Active | 0.095 | 3.154 | 0.045 | 3.294 | 4.986 | 5.126 |

The uninterrupted loop medians are 3.174/3.176 ms stopped/active. The single
55-byte tail is uninterrupted in both runs and takes 1.317/1.318 ms in the loop.
Thus the active prime worker changes elapsed delays much more than the isolated
copy cost. Subtracting averages of different sample groups is not an exact
measurement of time spent preempted.

Both new traces retain exactly the S4 relative load-phase ticks, transfer counts
and all 18 hardware gap lengths. They also match the retained replays without
CPU tracing. Consume boundaries agree with the earlier trace within one 8x CPU
cycle (0.071 microseconds). Loading remains 3.88/4.16 seconds open-to-prompt.

## Validation and reproducibility

The [evidence](../development/sector-copy-cost.json) pins inputs, images, loop
hashes, listings, platform configuration and all measured summaries. Raw and
optimized fixtures each pass 14,371 byte/state/guard checks and replay with
identical runtime results without CPU markers. Stack/domain guards, bounded
completion and OS ownership restoration pass. The host suite passes 206 tests,
including interruption classification, trace completeness and payload selection.
Only the two small fixture images were compiled; HELLO reuses its prior image.

```sh
python3 tools/measure_sector_copy.py --mode raw --output build/development/sector-copy/raw
python3 tools/measure_sector_copy.py --mode opt --output build/development/sector-copy/opt
python3 tools/measure_sector_copy.py \
  --hello-bundle build/development/sio-driver/s3-integration/bundle \
  --output build/development/sector-copy/hello-stopped
python3 tools/measure_sector_copy.py \
  --hello-bundle build/development/sio-driver/s3-integration/bundle \
  --prime-worker active --output build/development/sector-copy/hello-active
```

Use `--from-build <fixture-output>/program` to replay an existing fixture image,
or `--analyze-only` with a HELLO bundle to reanalyze its saved trace.

Production reserved bank-zero change is **0 fixed bytes and 0 per Task**,
including guards, alignment and unused capacity. Stack/DP reservations and the
production memory map are unchanged. Fixture globals fit the existing near-data
arena; 3,072 bytes of test records/buffers occupy a separately claimed 65,536-byte
upper image bank, including its unused capacity. That fixture bank is absent
from production. This is development measurement, not release or hardware
qualification. MyDOS, sparse fill and new copy/fill primitives remain separate
work.
