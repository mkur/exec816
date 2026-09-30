# Exec816 versus original SpartaDOS X at Generic57600

The matched HELLO experiment finds Exec816 slower than original SpartaDOS X
4.50 under the same emulated machine, disk image and physical SIO profile.
Reading the same nineteen data sectors takes **3.005 seconds versus 2.202
seconds**, or **36.5% longer**. This is a small-file comparison, not a bulk
throughput or general DOS qualification result.

## Conditions

- Identical pinned shell-paced emulator and AltirraOS 65816 ROM, PAL 800XL,
  65C816 at 8x, shadow ROM, 64K plus fifteen upper banks.
- `diskemu=generic56k`, `siopatch=off`, `burstio=false`,
  `accuratedisk=true`, `randdelay=false`. Rotational and seek delays are active.
- Identical 720-sector, 128-byte SDFS ATR and 2,359-byte HELLO payload from S6.
- Original SDX uses `USE OSRAM`, `DEVICE SPARTA`, `DEVICE SIO`; a small 6502
  program calls documented CIO open/read/close. Its four 512-byte reads and
  final 311-byte read match Exec816's loader request sizes. Returned bytes
  are checked against the complete host payload.
- Exec816 replays the existing optimized S6 diagnostic demo, with its prime
  worker active. No compiler or kernel rebuild is involved. The two systems
  have different scheduling workloads; this compares the current demo with
  ordinary foreground DOS operation, not isolated filesystem code.
- A separate SDX startup disk supplies CONFIG.SYS and the reader. At reader
  entry it is replaced with the unchanged demo ATR. The startup disk has a
  distinct volume identity. HELLO has not been read in either system.
- Traced and untraced runs agree on the VBI phase durations. Trace output is
  observational; guest clocks exclude host debugger pauses.

Both traces show **30 PAL master cycles per transmitted bit and 31 per
received bit** for HELLO's data-sector transactions: the same nominal 57.6
kbaud profile, with no slow-speed fallback or retried payload reads.

## Results

| Measurement | Original SDX 4.50 | Exec816 SDFS |
| --- | ---: | ---: |
| Open | 0.84 s | 0.50 s |
| Size query, rewind and staging allocation | Not performed | 0.12 s |
| Payload phase | 2.20 s | 3.44 s |
| Close | Below 20-ms resolution | 0.04 s |
| Open through close | 3.04 s | 4.10 s |
| Same 19 data sectors: first command assertion through final checksum byte | 2.202 s | 3.005 s |
| Mean gap between those sector transactions | 0.375 ms | 38.848 ms |
| Sum of the 18 gaps | 0.0068 s | 0.6993 s |

VBI phase times use 20-ms ticks. The data-sector span and gaps use peripheral
trace timestamps and include the final byte's ten serial bits. They exclude
file-map reads and any work before the first or after the last data transfer.

The payload phase is **56.4% longer** in Exec816, but its boundaries differ:
Exec reads the file map during this phase, whereas SDX reads it during open.
The nineteen-sector span is the cleaner comparison of actual file-data
transfers. Open also has different cache conditions: SDX checks the changed
volume, while Exec has already read its volume header during startup. The
open-through-close totals describe these runs and do not isolate lookup cost.

Exec's approximately **0.69 seconds of additional inter-request time** accounts
for most of the **0.80-second difference** across the nineteen data sectors.
These gaps include copying, filesystem/request processing, scheduling and
competing tasks. They do not identify one routine as the cause. Rotation still
affects the remaining transaction time and can amplify scheduling delays.
The useful next investigation is the per-sector request/worker path. The
following control removes the demo prime worker's workload.

Exec816's full HELLO command remains 5.20 seconds, including 0.76 seconds of
in-memory loading/relocation and execution/return work. The SDX probe reads
the o65 file as data; it does not execute it. Comparing 5.20 seconds directly
with the SDX read time would conflate those operations.

The earlier [MyDOS/SDFS comparison](../history/spartados-implementation.md) measured
two Exec816 backends, not original MyDOS against Exec816.

## Prime worker stopped

The follow-up replays the **same XEX and ATR**, setting the existing
`demoStop` flag after startup and waiting for the worker to exit normally before
typing HELLO. Live Tasks fall from five to four. Prime frame, pass, candidate
and count values remain unchanged through HELLO and DIR. Normal EXIT collects
the completed Process, and the existing stack/ownership checks pass. No
production code, scheduler state or instruction bytes are patched.

| Measurement | Prime active | Prime stopped | Original SDX |
| --- | ---: | ---: | ---: |
| Payload phase | 3.44 s | 2.84 s | 2.20 s |
| Same 19 data-sector span | 3.005 s | 2.587 s | 2.202 s |
| Mean gap between sector requests | 38.848 ms | 34.740 ms | 0.375 ms |
| Sum of the 18 gaps | 0.6993 s | 0.6253 s | 0.0068 s |
| Exec HELLO, open through prompt | 5.20 s | 4.52 s | Not executed |

Stopping the worker reduces the measured payload phase by **17.4%** and the
nineteen-sector span by **13.9%**. However, approximately **89% of the
inter-request gap time remains**. The average gap improves by only **4.11 ms**,
leaving about **34.37 ms more than SDX**. The background worker contributes,
but does not explain most of the time between requests.

The elapsed-time improvement is not a direct measurement of prime computation
cost: stopping the worker changes request timing and therefore rotational
waiting. The nineteen-sector span falls by 0.418 seconds, while summed gaps
fall by only 0.074 seconds. With the worker stopped, that span remains **17.5%
longer than SDX**. This still does not isolate the SIO driver from filesystem,
copying and completion/scheduling costs.

Traced and untraced stopped-worker runs match exactly at all recorded phase
boundaries. The nineteen sectors, transfer counts and serial bit rates are
unchanged. The [control record](spartados-prime-control.json) retains those
checks, the worker-state observations and both result hashes.

The subsequent [SIO path analysis](sio-path-analysis.md) breaks down the
remaining gaps using passive instruction timestamps. It identifies repeated
empty cancellation checks and 512-byte DOS packet boundaries as substantial
costs above the hardware serial engine.

## Reproduction and scope

The [record](spartados-dos-comparison.json) contains input hashes, pins, phase
samples, traced/untraced agreement and serial trace summaries.

```sh
python3 tools/measure_spartados.py \
  --output build/development/spartados-comparison/sdx
EXEC816_LATENCY_TRACE=1 python3 tools/measure_spartados.py \
  --output build/development/spartados-comparison/sdx-traced
python3 tools/measure_command_loading.py \
  --bundle build/development/spartados-s6/sdfs/bundle \
  --output build/development/spartados-comparison/exec816
EXEC816_LATENCY_TRACE=1 python3 tools/measure_command_loading.py \
  --bundle build/development/spartados-s6/sdfs/bundle \
  --output build/development/spartados-comparison/exec816-traced
python3 tools/measure_command_loading.py \
  --bundle build/development/spartados-s6/sdfs/bundle --prime-worker stopped \
  --output build/development/spartados-comparison/exec816-prime-stopped
EXEC816_LATENCY_TRACE=1 python3 tools/measure_command_loading.py \
  --bundle build/development/spartados-s6/sdfs/bundle --prime-worker stopped \
  --output build/development/spartados-comparison/exec816-prime-stopped-traced
```

`measure_spartados.payload_trace(log_path, media_path)` extracts the same data
sector span from either trace. The retained S6 instrumented bundle is required
for exact replay; `measure_command_loading.py --prepare` creates a new bundle
from an explicitly selected demo when rebuilding is intended.

Validation is limited to these focused machine-code measurements, SDX payload
equality, successful Exec HELLO/DIR/EXIT replay, and the existing replay's stack
and ownership checks. No full release suite or compiler qualification ran.
There are no production changes. Exec816 reserved bank-zero change is **0
fixed bytes and 0 per Task**. The standalone SDX reader and its payload buffer
occupy temporary SDX application RAM, not new Exec816 reservations.
