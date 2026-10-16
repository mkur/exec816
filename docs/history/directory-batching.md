# Directory batching

[Design](../plans/directory-batching-design.md) ·
[Plan](../plans/directory-batching-implementation-plan.md) ·
[Machine-readable evidence](../development/directory-batching.json)

## EB1 Public operation

ExNextBatch returns up to sixteen compact entries through one filesystem packet.
Native DOS, loaded COMMAND and C share action 28. DOS/COMMAND/C-program versions
are 11/19/20; applications must be rebuilt. DirEntry uses `kind` rather than the
design's original `type` spelling because TYPE is an Action! keyword.

The worker reuses ordinary directory metadata and ancestry, checks the cookie
once, and publishes each record with its cursor and count. Errors and active
cancellation retain that prefix; only final publication enters completion-wins
retirement. Ordinary ExNext remains available and can share a cursor with batches.

Development checks used the pinned compiler, Calypsi 5.18 and the pinned
shell-paced Altirra bridge/AltirraOS ROM. Emitted optimized SDFS, MyDOS and RAM
cases cover capacities 1/8/16, empty and exact-multiple termination, invalid
capacities, independent/interleaved cursors, directory ancestry, compact metadata,
unchanged non-cookie FIB fields, RAM epoch rejection and loaded COMMAND calls.
The C layout probe and 1,890-byte result buffer cross a bank boundary. A small
raw C/native/COMMAND run covers the same ABI in unoptimized emission.

Seven optimized retirement cases inject real foreground delivery before send,
while queued, before publication, after three records, during SIO activity,
after final publication, and after a causal prefix error. Each checks reply
collection, resumable cursor position and cleanup. Hooks exist only in copied
test modules. Guards and ownership checks pass; maximum observed Task stack
touch was 391 bytes. These are development checks, not platform qualification.

ABI generators and six DOS packaging host checks pass. The older metadata
regression compiled but its removed historical emulator binary prevented that
runner from executing; the new focused suite uses the available pinned bridge.

Reserved bank-zero change: **0 fixed, 0 per Task, 0 idle bytes**, including
guards and unused capacity. Upper-memory Service size grows **516→520 bytes**
(five field bytes consume one existing padding byte). The C DOS table grows
**72→75 bytes**. The seven changed DOS/FS native modules grow by 2,844 emitted
code bytes against the retained optimized demo; this excludes wrapper/provider
code. Provider usage and capacity are recorded in the JSON. No worker buffer,
Task, port or per-entry heap allocation is added.

## EB2 Shared scanner

Files, desktop folder windows and the standard file selector now share
eight-entry refills. FileScan allocates its upper-memory buffer before taking
the directory lock, retains each batch's terminal status, and consumes records
locally. Cleanup releases both resources once, including failed begin and early
stop. The selector retains its existing event checks between entries.

The 256-entry display limit uses one final record to distinguish an exact fit
from truncation. A real error takes precedence over truncation and clears the
incomplete displayed list. Browser totals now use compact record sizes and
flags: SDFS/RAM totals remain exact; MyDOS bounds say “bytes or less”; unknown
sizes stay unknown. The rendering and selection paths are unchanged.

An optimized emitted C scanner probe passes 0/8/9/255/256/257 entries, final
prefix errors, allocation failure, early/repeated cleanup and path helpers.
RAM's 256-node limit includes its root, so large-count scanner boundaries use
controlled DOS replies. Maximum observed Task stack touch is 165 bytes; guards
and ownership checks pass. Emitted Browser/FileScan and selector layout probes
also pass. All application artifacts were rebuilt. Real desktop root/C/RAM
navigation and Refresh work in the packaged demo; the standalone Files and
selector walkthrough is shared with EB3's delivery/measurement run.

FileScan grows **20→38 bytes**, Browser **4,039→4,059**, and selector
**3,242→3,260**. Eight-byte heap rounding makes the owner reservation increases
24 and 16 bytes respectively. The temporary eight-record buffer has **946
payload bytes / 952 allocated bytes**; sixteen would use **1,890 / 1,896**.
AllocMem adds no per-allocation prefix. FileEntry remains 112 bytes. The Service
size change in EB1 stays within its previous 520-byte rounded heap allocation.
Reserved bank-zero change remains **0 fixed, 0 per Task, 0 idle bytes**.

## EB3 Measurements

Keep **eight entries** as the production refill size. Sixteen gives a further
18 ms improvement on warm `SYS:C`, but adds about 31 ms to the queued peer's
wait and doubles the temporary result storage. No scheduler, priority, queue
selection or renderer changes are included.

The retained parent (`cbc0a16b`) and both candidates use the eight-entry demo's
same SYS disk from boot. Compiler `05c01f39`, Calypsi 5.18, pinned AltirraOS ROM,
800XL/PAL, 65816 ×8, VBXE, 64K plus 63 upper banks, and accurate Generic57600
transport remain fixed. Version-matched loaded apps use a separate WORK disk.
RAM has the same two names, with each build's embedded Desktop payloads.
Hashes, CPU breakdowns and individual samples are in the JSON record.

Warm results below are medians of three repetitions, in milliseconds. Scan
boundaries include the final UnLock; Refresh continues through sorting, layout
and the fenced redraw return. Each warm refresh adds exactly one full paint.

| Directory | Parent scan | Eight scan | Sixteen scan | DOS packets: parent / eight / sixteen |
| --- | ---: | ---: | ---: | ---: |
| SYS: — 9 entries | 189.958 | 117.156 | 94.318 | 13 / 5 / 4 |
| SYS:C — 29 entries | 532.029 | 297.618 | 279.637 | 33 / 7 / 5 |
| RAM: — 2 entries | 75.154 | 62.653 | 67.213 | 6 / 4 / 4 |

| Complete Refresh | Parent | Eight | Sixteen |
| --- | ---: | ---: | ---: |
| SYS: | 412.501 | 334.569 | 316.526 |
| SYS:C | 835.743 | 594.181 | 575.964 |
| RAM: | 201.884 | 193.006 | 196.454 |

The primary C-directory case has no physical transfers or presenter CPU during
any warm scan. Caller CPU falls **113.916→38.719 ms**, filesystem CPU
**324.457→206.474 ms**, and interrupt time **93.656→52.424 ms**. The reduction
comes from fewer exchanges and compact publication; about 297 ms of work still
follows enumeration in the complete eight-entry Refresh.

Root and RAM samples retain small differences in presenter activity: the
eight-entry root scan includes a 3.70 ms presenter turn; some RAM samples also
include one. These charges are recorded, not subtracted. Three repetitions do
not establish p95 or worst-case input latency.

The partially cold first C visit takes **1,634.320 / 1,488.125 / 1,461.538 ms**
for parent/eight/sixteen, with two physical directory reads in each case. Boot
and the root listing have already warmed other sectors, so this is not a fully
cold-cache benchmark. EB1 separately exercises cancellation while real SIO is
active and verifies borrowed-buffer retirement.

### Competing caller

The GUI-launched background LIST finished before the measured Refresh and
therefore supplies no contention evidence. A separate emitted fixture queues
an already initialized peer's ordinary Lock behind an active warm batch. One
test-only Signal/Yield at batch admission creates repeatable overlap before
enumeration; production worker code is unchanged. Queue timing starts at the
peer's ordinary PutMsg, after the injected handoff. There are no per-entry test
hooks in this measurement.

| Capacity | Peer queue wait, median (range) | Complete peer Lock, median |
| --- | ---: | ---: |
| 8 | 34.375 ms (34.042–34.476) | 71.690 ms |
| 16 | 64.963 ms (64.905–64.966) | 103.309 ms |

These are three controlled samples per size over twenty ordinary SDFS entries,
not a scheduler guarantee or a matched measurement against the parent's ExNext.
Normal preemption continues, but the filesystem services its active packet
before taking the peer's packet. The test exits with intact guards, restored
ownership and a maximum observed Task stack touch of 276 bytes.

### UI completion and delivery

The narrow packaged observer measures the following single samples, in ms:

| Operation | Parent | Eight | Sixteen |
| --- | ---: | ---: | ---: |
| New SYS: window: service entry through first fenced paint | 772.564 | 692.649 | 672.686 |
| Selector entry through usable list | 952.997 | 913.427 | 912.725 |
| Escape during live scan through form retirement | 137.424 | 138.685 | 139.190 |

New Window paints its initial listing once. Selector completion is its first
blocking AES event call after final directory unlock, filtering, focus setup
and painting. The larger helper settling intervals are retained as upper bounds
in the JSON, not used as these drawing timings. Opening improves less than
Refresh because frame/form creation and drawing still dominate.

Escape is injected after observing a live scan lock. That proves normal UI
cancellation/cleanup, not that Escape lands inside an ExNextBatch packet or at
its worst phase. These cancellation intervals have no physical disk traffic;
they do not replace EB1's wire-cancellation case or the active-batch peer test.

The complete scan intervals were retained from the broad observer, then the
observer processes were intentionally stopped before finishing their slow UI
walkthrough. `--partial` trims only the unfinished trace tail after the saved
samples. UI completion and normal EXIT/guards use a separate observer with 42
PC markers. Host instruction profiling is disabled during disk-app loading,
which is setup outside the measured intervals. No guest code or input policy
is patched by either GUI observer.

An initial UI run exceeded the host timeout during profiled app loading.
The subsequent run passed standalone Files refresh/retirement and selector
opening, then stopped on an unsupported `dd` debugger expression in the host
cancellation check. The corrected observer uses two `dw` reads and the bridge's
`!=` comparison; a stopped retry established that `<>` is not inequality here.
Those completed phases are retained; the selector phase was rerun separately.
The UI analyzer also separates entry-only event markers from paired calls.
All three final runs pass normal EXIT, OS display/input restoration, ownership
restoration and guards. The eight-entry selector touches 990 of its Task's
1,312 stack bytes, leaving 66 above the separate 256-byte interrupt reserve;
the parent touches 994. This is an observed watermark, not a worst-case proof.

The selected demo was built with `tools/build_demo.py --gem-desktop
--release-compiler`. It includes OF816, the five-second autoboot, pinned ROM,
matching rebuilt system disk and license notices. Source-input hashes match the
committed implementation; its banner is `c13a783-dirty` because EB2 was built
before its commit. ZIP CRC/content checks pass. All checks are development tier;
there is no new hosted-platform or real-hardware qualification claim.

- ZIP: `build/directory-batching/demo/exec816-demo.zip`
- SHA-256: `382d649e1ef638f63a79bc10e8b511147943d79fb73b088f466005653e474aec`
- Launch: `build/directory-batching/demo/launch-altirra.command`
- EB3 reserved bank-zero delta: **0 fixed, 0 per Task, 0 idle bytes**.

### Reproduction

Use fresh output directories; large capture/build files stay under `build/`.

```sh
python3 tools/test_directory_batch.py --group enumeration --format sdfs --output build/batch-check
python3 tools/test_file_list.py --output build/batch-scanner-check
python3 tools/trace_directory_batch_contention.py --output build/batch-peer-check
python3 tools/trace_files_enumeration.py --bundle build/directory-batching/demo --output build/batch-scans --app-bank 9
python3 tools/trace_directory_batch_ui.py --bundle build/directory-batching/demo --output build/batch-ui
```

The scan observer verifies the requested desktop bank before recording. Use
`tools/build_directory_batch_demo.py --capacity 16 --output build/batch-demo16`
for the diagnostic size; its compiler provenance records the define. SYS media
can be held fixed with each observer's `--media` option. `--analyze` processes
retained observations without executing target code. Historical stopped scan
captures use `--partial`; complete UI runs do not.
