# Cheap directory metadata

[Plan](../plans/directory-metadata-refactor-plan.md) ·
[Baseline](../development/directory-metadata-baseline.json)

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
