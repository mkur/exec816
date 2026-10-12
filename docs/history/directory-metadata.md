# Cheap directory metadata

[Plan](../plans/directory-metadata-refactor-plan.md) ·
[Baseline](../development/directory-metadata-baseline.json) ·
[Final development evidence](../development/directory-metadata-final.json)

## DM0 — frozen baseline and callers

Production baseline: `0f95a35`, after MP0–MP6. Library/ABI input snapshots
live under `build/directory-metadata/dm0`. The baseline record captures the
pinned compiler and the existing 128/256-byte listing observers and media.
Reuse MP6 measurements as historical comparisons; input differences are
recorded rather than presenting them as freshly matched timings.

| Caller | Metadata needed | Migration |
| --- | --- | --- |
| Resident DIR, loaded LIST | Display size | Honor exact/bound/unavailable flags |
| Shared patterns, FIND | Names/types | Keep ordinary queries |
| COPY destination, shell CurrentDir | Directory type | Keep ordinary queries |
| C FileScan, GEM browser/files/selectors | Names/types | Keep ordinary queries |
| GEM text loader | Capacity decision | Early reject only exact oversize; retain counted reads/EOF probe |
| DOS directory/write fixtures | Sizes/allocated counts | Ordinary flags plus separate explicit exact queries |
| MyDOS/SDFS corruption fixtures | Selected-chain integrity | Keep failures on Exact/Read/mutation; cheap listing need not walk chains |
| Native, COMMAND and C bindings | Layout/call shape | Regenerate together; append C entry |

No additional bank-zero reservation: fixed 0, per-Task 0, idle 0 bytes.
This work uses development checks, not release or hardware qualification.

## DM1 — ABI foundation

Added DOS revision 9, COMMAND contract version 16 and C application ABI version
12. `fib_InfoFlags` is at 258, the FIB remains 260 bytes and the enumeration
cookie is 22 bytes within its 30-byte reservation. `ExamineExact` uses public
packet action 25 and the ordinary owned-lock/cancellation path. Existing queries
still measure during this slice and publish exact size/block flags.

Development checks: the native ABI/layout probe and the C-to-native/loaded
COMMAND exact-query probe passed in raw and optimized modes, with cross-bank
FIB canaries, failed-query preservation, runtime/domain guards and ownership
cleanup. All 448 host checks and relevant generator checks passed. COMMAND's
provider manifest is 1,624 bytes within the unchanged 1,664-byte reservation.
The appended C entry holds three bytes; it introduces no bank-zero reservation.
The first C fixture run used an incompatible emulator drive profile; corrected
to the pinned GENERIC57600 configuration before recording passing results.

Artifacts: `build/directory-metadata/dm1/{abi,c-raw,c-opt}`. No release or
hardware qualification is claimed.

## DM2 — callers ready for cheap metadata

DIR and LIST distinguish exact bytes, `<=` bounds and `?` unavailable sizes.
DIR retains one Write per row and its existing 128-byte draw buffer; LIST NAMES
stays name-only. The GEM text loader rejects early only on exact oversize and
still reads to its bounded capacity plus a one-byte EOF probe. Name/type-only
callers require no change or explicit measurement.

Optimized development checks: LIST 15 controlled cases; the text-loader mock
144 assertions (exact/bound/unknown, 65,536 fitting bytes, 65,537 rejected bytes,
previous-document preservation and resource cleanup); real resident DIR/TYPE
session including exact/bound/unknown row formatting and one Write per DIR row.
The old shell fixture needed an 8 KiB upper-RAM data arena, relocated command
strings and the matching GENERIC57600 drive profile. Production buffers and
fixed/per-Task/idle bank-zero reservations remain unchanged (0-byte delta).
Artifacts: `build/directory-metadata/dm2/{list,text-mock,dir}`.

## DM3 — ordinary queries use directory metadata

Selection/admission and measurement now have separate paths. Ordinary MyDOS
queries admit the initial reference without payload I/O and publish a wide
sector-derived bound; the accepted legacy empty form and admitted live writer
lengths remain exact. Ordinary SDFS publishes stored sizes and unavailable block
counts. RAM refreshes node metadata and reports zero allocated disk sectors.
Only ExamineExact enters the existing resumable extent-measurement path.
Internal Entry length/known fields remain exact-only. No records, caches,
transfer buffers, Task pools or bank-zero reservations grow.

Optimized development checks passed for 128-byte MyDOS directories, 256-byte
MyDOS with a corrupt later chain, legacy empty entries, SDFS over SIO, SDFS over
512-byte IDE, RAM, and MyDOS writes/mutations/remount. Cookie identity, copied
and stale FIBs, interleaved enumeration, ownership and 65,535-sector bound
arithmetic remain checked. The corrupt chain permits cheap metadata but fails
Exact and Read without corrupting the prior FIB.

The real MyDOS GEM text-loader run passed 119 assertions, including a fitting
65,536-byte file whose bound exceeds capacity and a rejected 65,537-byte file.
The C/COMMAND IDE probe recorded zero selected-map fetches for ordinary Examine
and one for ExamineExact. RAM passed 158 assertions. Four selected cancellation
cases exercise scan, final publication, metadata checkpoint and exact accounting;
pre-publication BREAK preserves all 260 FIB bytes and completion-wins behavior
still collects one reply. A real directory-sector checksum fault passed 264
assertions, preserves the FIB and causal SIO error 4, then retries successfully.
Runtime/domain/transfer guards, resource cleanup and bounded completion passed.

Artifacts: `build/directory-metadata/dm3/{mydos128,mydos256-chain,legacy,sdfs,ram,
write-mydos,text-mydos,ide-measured,break,directory-error}`. Some old directory
fixtures needed relocated kernel code and larger upper-RAM test data arenas;
production reservations remain unchanged. Fixed/per-Task/idle bank-zero delta:
0/0/0 bytes, including guards, alignment and unused capacity.

## DM4 — matched measurements and final contract

Both runs use the pinned release compiler, the same MyDOS media, optimized
fixture, cache setting, observer boundaries and emulator configuration. The
comparison control replaces only FSDIRECTORY with its DM1 exact-default source
from `89e7df9`, adapted to the current private four-argument FSINFO.Fill. The
rest of the current production tree and the new ABI are identical. This is a
private build comparison, not an installed compatibility mode or a rebuild of
the historical MP6 kernel. Historical MP6 records remain unchanged.

| Sector bytes | Listing | Frames, control → cheap | Directory fetches | Selected-file fetches, control → cheap | Physical reads, control → cheap |
| ---: | --- | --- | ---: | --- | --- |
| 128 | First | 31 → 5 | 9 | 76 → 0 | 12 → 0 |
| 128 | Repeat/warm | 10 → 5 | 9 | 76 → 0 | 0 → 0 |
| 256 | First | 34 → 4 | 9 | 41 → 0 | 9 → 0 |
| 256 | Repeat/warm | 8 → 4 | 9 | 41 → 0 | 0 → 0 |

First means the first listing after the same preceding create/read/seek
workload, not a completely empty cache. All four listings issue zero writes.
Selected-file chain visits fall from 76/41 to zero. First metadata appears in
1/0 frames rather than 6/7 (PAL, 50 Hz integer sampling). This measures the first
returned FIB; it does not time the first rendered screen row. Warm first results
remain 1/0 frames. The observer records no output calls, so these numbers do
not include DIR/LIST formatting or console presentation. DM2 checks their
formatting and DIR's one Write per row separately.

The 8,000-byte explicit exact query still visits/fetches 64/32 MyDOS sectors.
Read/Seek(END), writable Open, writes, truncate, delete and directory mutations
pass in both matched workloads; final media audits preserve unrelated files.
Ordinary SDFS selected-file Examine performs zero map fetches in the 512-byte
IDE probe; Exact performs one. SIO SDFS and RAM retain their focused functional
checks. Complete counters, pins, image/input hashes and runtime observations are
in the [compact evidence](../development/directory-metadata-final.json).

The final real DIR/TYPE session passes with sector-derived MyDOS bounds and
one Write per DIR row. A focused concurrent-reader run passes 335 assertions
with four live Tasks, file reads/seeks and cheap metadata while heap, message
and signal work continues. That fixture needed helper procedures excluded
from the bounded Task-entry table, relocated code and a matching Generic57600
functional profile. Its timing observer is still limited to the older
FASTEST125/STOCK810 profiles; no new transport qualification is claimed.

The control/current instrumented emitted bodies are 850,631/850,955 bytes:
the dispatch split costs 324 bytes in FSDIRECTORY. These include the test
observers and ABI/caller foundation; this is not a release-kernel size delta.
Against the DM1 emitted module bodies, FSBACKEND/FSDIRECTORY/FSINFO together
grow 1,262 bytes (501/371/390) for admission, dispatch and availability handling.
Workspace/Cursor/Entry remain 174/110/42 bytes; write state remains 2,214
and SDFS backend state 730 bytes, with existing 8-byte allocator rounding.
Service remains 466 bytes. Cache payload stays 512 × 128 bytes (64 KiB),
shared sector scratch 512 bytes and transfer staging 2,048 bytes. Peak observed
root/filesystem/serial stacks are 271/522/139 bytes; kernel stack 260 bytes.
Guards remain intact and reserved Task/DP/stack capacity does not change.

The appended C binding grows its table from 60 to 63 bytes. Calypsi 5.18 places
it at `$0D0009` without new linker alignment padding; the controlled probe's
initialized-plus-BSS extent grows 69 → 72 bytes, both rounding to 72 at eight-byte
alignment. Other C images may cross a rounding boundary. COMMAND remains within
its existing 1,664-byte manifest reservation; FIB/cookie capacity is unchanged.
Additional fixed/per-Task/idle reserved bank-zero bytes remain 0/0/0, counting
guards, alignment and unused capacity.

Reproduce the matched runs with `tools/measure_mydos_operations.py --size 128`
or `256 --output DIR`. For the control, put the DM1 FSDIRECTORY source under
`CONTROL/lib/fs/fsdirectory.act`, change its Fill call from `(info, entry)` to
`(info, entry, service.work.volume, 1)`, and pass `--frozen-sources CONTROL`.
Use the current fixture/observers in both runs. Full artifacts are under
`build/directory-metadata/dm4/{before128,after128,before256,after256}`.
The focused concurrency command is `tools/test_dos_concurrent.py --case opt
--size 128 --capacity 4 --profile 4 --output DIR` (run with Python 3).

Development scope: affected optimized emitted-code checks, DM1 raw/optimized
ABI probes, host/generator and documentation/link checks. The emulator uses
Generic 57,600 serial timing with rotational delays disabled. Timings include
observer overhead and frame quantization; they neither predict physical floppy
throughput nor qualify a release or real hardware. No demo/release was rebuilt.

The subsequent [SpartaDOS listing measurements](spartados-listing-measurements.md)
time complete resident DIR and loaded LIST invocations, including output and
first-row drawing, on cold/warm IDE and SIO configurations.
