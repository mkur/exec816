# MyDOS simplification implementation record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

Status: M1–M4 complete. This is development evidence, not release
qualification. The [plan](../plans/mydos-simplification-plan.md) records the scope and acceptance criteria.

All measurements use pinned compiler `bcabe0a4cbb8bb57b389a8596aa8fd72cb9ee0c7`,
with stack checks enabled and no compiler override. The earlier review used a
newer local compiler; its sizes are not the baseline for these source changes.
[Machine-readable evidence](../development/mydos-simplification.json) records the
compiler/image hashes, native checks and pinned platform for the read benchmark.

## Baseline

The standard console system emits 492,884 compiler-code bytes, of which 32,197
belong to MyDOS and its adapter. Original images remain under
`build/development/mydos-simplification/baseline` for final comparison.

The matching 8 KiB read uses 128-byte MyDOS sectors, the pinned paced emulator,
57.6-kbaud profile 4 and one busy CPU task. With a 512-block cache it takes
7.842 seconds cold (66 logical and 66 physical reads) and 0.943 seconds warm
(66 logical reads, no physical reads). Boundaries are DOS.Read call/return;
Open/Close, allocation and byte verification are outside the timing interval.
Every returned byte, task progress, final ownership and stack guards are checked.

## M1 — Test-only blocking drivers

The standalone fixtures now drive bounded production parser steps through a
test-only include and file-operation loop. Six convenience routines are removed
from production; their baseline code totals 1,979 bytes. This is removed routine
code, not a freshly measured whole-image delta. Fixture bytes and error/operation
accounting remain unchanged. The cache-read harness can now select MyDOS and
counts logical BeginFetch entries independently of physical SIO transactions.

Development checks: 234 host tests and four native 128-byte-sector cases pass:
metadata raw/optimized (1,099 assertions each) and files raw/optimized (740 each).
These retain malformed-media, geometry, read/seek, I/O-failure, ownership,
bounded-completion, guard and OS-restoration checks. Logs and images are under
`build/development/mydos-simplification/m1`.

Reserved bank-zero change: **0 fixed bytes / 0 bytes per task**, including guards,
alignment and unused capacity. No runtime allocation layout changes in M1.

## M2 — Common records, without the adapter

MyDOS now updates the shared workspace, cursor and operation directly. FSMYDOS,
its conversion helpers and duplicate private records are removed. The disk key
still carries the raw flags and ordinal; common flags, dates and unknown lengths
are initialized directly. Sector requests are published at each I/O boundary.
Cancellation commits partial reads while failed operations and canceled seeks
retain their previous position.

The optimized standalone parser emits 23,126 MyDOS bytes (22.6 KiB). Whole-system
and common-dispatcher totals are recorded in M4 below. Removing the second workspace
and operation saves one 160-byte heap allocation per filesystem service. The
private volume falls from 14 to 10 active bytes, but both round to 16 heap bytes.
Shared cursor storage remains unchanged for this slice.

Development checks: 234 host tests; metadata raw/optimized at 128-byte sectors
(1,164 assertions each); files raw/128 (767) and optimized/256 (1,289); optimized
public-DOS startup failure at the private-volume allocation, cleanup and retry.
File checks include independent cursors, cancellation followed by reuse, corrupt
chains, both trailer encodings, and the 70,003-byte file on 256-byte media.
Historical qualification records remain unchanged; collectors understand the
new representation separately. Images and results are under
`build/development/mydos-simplification/m2`.

Reserved bank-zero change: **0 fixed bytes / 0 bytes per task**, including guards,
alignment and unused capacity.

## M3 — Smaller shared storage

The emitted MyDOS chain is 28 bytes and the SDFS map cursor is 16 bytes. Both fit
in the named 28-byte reservation, with layout checks in the native file fixture.
The common cursor shrinks from 180 to 116 bytes. Every enclosing file object,
file backing, filesystem service and SDFS backend state therefore saves 64 active
bytes and 64 rounded heap bytes. An ordinary open file has an object and a backing,
saving 128 bytes in total; a lock or an additional wrapper for shared backing saves
64 bytes. Cursors continue to own their independent chain state.

The emitted layouts and eight-byte allocation rounding are:

| Record | Active bytes before → after | Heap bytes before → after |
| --- | ---: | ---: |
| Common cursor (standalone) | 180 → 116 | 184 → 120 |
| File object / lock | 204 → 140 | 208 → 144 |
| File backing | 182 → 118 | 184 → 120 |
| Filesystem service | 524 → 460 | 528 → 464 |
| SDFS backend state | 540 → 476 | 544 → 480 |
| Common workspace | 174 → 172 | 176 → 176 |
| Private MyDOS volume | 14 → 10 | 16 → 16 |
| Removed MyDOS workspace + operation | 160 → 0 | 160 → 0 |

Removing the unused workspace pointer reduces active workspace bytes from 174 to
172; both sizes round to 176 heap bytes. Together with the allocation removed in
M2 and the two service-owned embedded cursors, a running filesystem service saves
288 heap bytes before counting open files and locks. Mounted MyDOS volume heap
cost is unchanged. No per-handle sector buffers are introduced.

Reserved bank-zero change: **0 fixed bytes / 0 bytes per task**, including guards,
alignment and unused capacity.

Development checks: 234 host tests; raw/128 and optimized/256 native file cases
(768 and 1,290 assertions); optimized mixed SDFS/MyDOS public DOS case
(118 assertions), including seek, enumeration, inheritance, repeated lifetime
and exact final heap/ownership restoration. Guards are intact. Results are under
`build/development/mydos-simplification/m3`; the mixed case also supplies M4's
cross-backend integration evidence without a repeat run.

## M4 — Integration and final measurements

The final public MyDOS check passes 82 assertions for relative paths, enumeration,
independent tasks, retained handles, invalid bases and cleanup. Active cancellation
passes at partial-read, copy and seek checkpoints (2,143 / 2,268 / 16 assertions),
including reuse, committed positions, OS-console restoration and exact ownership.
The mixed-volume case from M3 remains valid; production inputs did not change.

The standard console system uses the same pinned compiler, optimized mode,
enabled stack checks, eight-slot configuration and `config/shell-sdfs.json` as
the baseline. Totals count all emitted compiler routines, including shared code:

| Code | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| MyDOS, including the removed adapter | 32,197 B | 23,126 B | 9,071 B (28.2%) |
| Common filesystem modules | 75,812 B | 75,691 B | 121 B |
| Whole system | 492,884 B | 483,692 B | 9,192 B (9.0 KiB) |

Other compiler-code totals are unchanged. Code still occupies banks `$01–$08`;
this reduction does not release a complete bank. Fixed upper reservations and
all bank-zero reservations are identical, including task DP, stacks, guards,
alignment and unused capacity. Reserved bank-zero change for M4 is
**0 fixed bytes / 0 bytes per task**. The runtime bank-zero budget remains 24,672
bytes excluding OS reservations: 10,560 fixed, 2,080 for the root slot, 1,568 for
each of seven other public slots, and 1,056 for idle.

The matching MyDOS 8 KiB read uses identical fixture bytes, emulator/ROM hashes,
57.6-kbaud SIO configuration, a 512-block cache and one busy CPU task:

| Read | Before | After | Logical requests | Physical reads |
| --- | ---: | ---: | ---: | ---: |
| Cold | 7.842 s | 7.842 s | 66 → 66 | 66 → 66 |
| Warm | 0.943 s | 0.566 s | 66 → 66 | 0 → 0 |

The warm read is about 40% faster in these matched runs. Every byte is verified;
the CPU task progresses during both reads. These are Read timings, excluding
Open/Close and loader work, and are single matched samples rather than a timing
distribution.

All native guards remain intact. The maximum optimized MyDOS local stack peak
is 40 bytes before and after; this is not a static whole-task bound. During the
read comparison, the filesystem worker's observed stack use falls from 242 to
232 bytes. Kernel watermarks are 266 and 274 bytes out of 1,536; neither touches
the 256-byte interrupt reserve. Task-policy, SIO-worker and benchmark routine
frame maps are unchanged. All selected integration cases preserve interrupt
headroom and restore ownership.

Final images and detailed results are under
`build/development/mydos-simplification/final`. Historical qualification records
were not replaced. Full release qualification, including alternate placement,
baud and concurrency matrices, remains pending.

The final development checks can be reproduced with:

```sh
export PYTHONDONTWRITEBYTECODE=1
python3 tools/test_dos_relative.py --case opt --only bank1-128 --output build/mydos-check/relative
python3 tools/test_filesystem_active_cancel.py --case opt --format mydos --suite middle,copy,seek --output build/mydos-check/cancel
python3 tools/test_sdfs_dos.py --case opt --size 128 --output build/mydos-check/mixed
python3 tools/measure_sector_cache.py --prepare --format mydos --cache-blocks 512 --output build/mydos-check/read
python3 tools/native_program.py --compiler-dir build/actionc --source examples/demo.act --tasks --task-capacity 8 --console --dos-mounts config/shell-sdfs.json --output build/mydos-check/system
```

## Follow-up — Remove unused production helpers

`FSNAMES.Alias` and `SameAlias` had no callers and are removed. `BLOCKIO.Attach`,
`Fetch` and `ReadSector` were used only by standalone tests; their behavior now
lives in [test support](../../tests/fixtures/block/driver.inc). The filesystem worker
continues to use `OpenVolume`, `BeginFetch` and `FinishFetch` directly. Rejecting
a test read destination still clears scratch validity without discarding the
retained sector cache. The volume-allocation failure fixture now injects its
failure in test support.

The matching standard system, with the same compiler and configuration as M4,
emits **481,245 bytes**, down from 483,692: **2,447 bytes saved**. The block wrappers
account for 1,842 bytes and the alias helpers for 605. Every remaining routine's
size is unchanged. Code still occupies eight banks (`$01–$08`).

Reserved bank-zero change: **0 fixed bytes / 0 bytes per task**, including guards,
alignment and unused capacity. Fixed upper reservations and runtime record
layouts are unchanged. [Development evidence](../development/filesystem-helper-removal.json)
records the matching images, removed routines and focused checks.

Development checks pass: 234 host tests; raw/optimized block fixtures; optimized
volume-allocation failure and cleanup; optimized MyDOS file operations on
128-byte sectors. Native guards and ownership checks pass. Results are under
`build/development/fs-helper-removal`. Historical qualification records remain
unchanged; this follow-up does not rerun the release matrix or read timings.

The subsequent [CPU-step consolidation](filesystem-cpu-steps.md) reduces common
request setup and publication overhead for both filesystems.
