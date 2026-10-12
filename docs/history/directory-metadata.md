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
