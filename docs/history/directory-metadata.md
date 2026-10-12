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
