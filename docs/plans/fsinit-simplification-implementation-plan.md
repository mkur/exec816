# Simplify filesystem initialization

Status: I1–I3 complete. Each executable slice has a separate commit. See the
[results](../history/fsinit-simplification.md) and
[development record](../development/fsinit-simplification.json).

Reduce resident code and make startup, mounting and rollback easier to follow.
Keep the public DOS API, admitted configurations and ownership rules intact.
This is startup/mount code; ordinary read performance is not the target.

## Baseline and acceptance

Use `c8d6c99`, after the [filesystem object split](../history/filesystem-objects.md), as the
source baseline. The matching optimized mixed-volume artifact under
`build/development/fs-objects/o2/mixed-opt/` has unchanged FSINIT source and gives:

| FSINIT responsibility | Routine bytes |
| --- | ---: |
| Configuration validation | 2,633 |
| Shared worker setup and its callbacks | 1,930 |
| Mount allocation and its callbacks | 2,165 |
| Recognition, publication and rollback dispatch | 2,186 |
| Mount/service teardown | 2,145 |
| **Total** | **11,059** |

The same fixture has 313,310 resident/library Action! routine bytes, excluding
`SDFSDOSTEST`. Freeze compiler `27119ab2804e795b0bbb067c269826b934271754`, guards,
mounts, ROM/emulator and build settings for comparisons. Verify baseline hashes
before reusing the artifact; its build banner predates the final baseline commit.

Aim to remove about **1 KiB of resident code**, bringing FSINIT below 10 KiB.
These are working targets, not predicted measurements. Acceptance requires a
net reduction across all affected modules, including any added helpers. Moving
code into FSSYSTEM, FSBACKEND or BLOCKIO does not by itself count as a saving.
Investigate a missed target and report the measured result before expanding scope.

Keep existing record layouts and allocation boundaries in this pass. Combining
Mount, filesystem Volume and block Volume allocations is a separate follow-up:
it changes teardown ownership and mainly targets allocation/RAM costs. Add no
persistent normalized-descriptor table, callback framework or generic rollback
engine. Compiler defects belong in actionc with their own regression.

## I1 — Remove allocation-only worker callbacks

- Make `First` validate configuration and acquire the adapter, workspace,
  operation, signals and control port through ordinary sequential calls.
  Retain small helpers where they express an ownership unit. Remove
  `AdapterStep` and `WorkspaceStep`.
- Make `MountStep` allocate both mount and block resources, then return
  `OPEN_VOLUME` with `OpenedStep` selected. Remove `BlockStep`.
- Keep the real device-open and metadata-read boundaries in the worker.
  `OpenedStep` begins recognition; `MountedStep` consumes the read result and
  publishes a validated mount. Retain a worker checkpoint between mounts.
- Handle a failed dynamic mount directly through the common failure helper:
  preserve its error, destroy the unpublished mount, clear its slot and reply.
  Remove `RollbackStep`. Initial startup failure still returns `STOP`; worker
  retirement owns whole-service cleanup.
- Preserve bounded processing, stop handling, cancellation pumping and the
  existing publication exclusion. Do not drain all startup/mount states in a
  new loop or hold `Forbid` across allocation, opening or I/O.

The intended callback flow is:

```text
First: configuration + shared resources
  -> MountStep: mount resources -> OPEN_VOLUME
  -> OpenedStep: begin recognition -> backend I/O status
  -> MountedStep: validate + publish, or select the next MountStep
```

Acceptance: FSINIT has four worker callbacks instead of eight. Allocation-only
transitions disappear; startup failure, dynamic failure and successful mount
publication preserve their distinct results. Raw/optimized execution must check
the deeper direct-call paths with existing stack/domain guards and stack
observations. No larger Task stack reservation is allowed to make this pass.

## I2 — Simplify descriptor validation and setup

- Bind the current descriptor and its effective SIO unit once per outer
  configuration iteration. Reuse those values for geometry and conflict checks
  instead of repeatedly constructing indexed field addresses and resolving the
  current system drive inside the inner loop.
- Retain the bounded scan of at most eight descriptors. Avoid copying all
  aliases or descriptors into temporary records. Evaluate any small temporary
  unit array against emitted size and stack cost before retaining it.
- Review `FSSYSTEM.SameName` alongside Config. Resolve the selected-system-slot
  distinction outside character comparison where it reduces total code; keep
  bounded, case-insensitive comparison and effective physical aliases. Keep SYS
  selection logic with FSSYSTEM rather than duplicating it in FSINIT.
- Replace the handwritten 44-byte descriptor copy with
  `A816MEMORY.Move(...,SIZEOF(FSTYPES.Spec))`. Copy the packaged descriptor before
  applying the boot-selected identity; never mutate the configured table.
- Preserve every native admission check and its error: count/slot bounds,
  legal and reserved aliases, packaged system-drive consistency, supported
  filesystem, geometry, effective-unit conflicts and effective-name conflicts.
  Host configuration validation does not replace the native gate. Preserve
  validation order when it determines the error reported.

Acceptance: the Config/descriptor path emits less code, including changes to
FSSYSTEM. Default, overridden and absent SYS selection behave identically.
Malformed descriptors and collisions remain rejected before opening devices.
No new persistent state or allocation is introduced.

## I3 — Simplify partial teardown and record the result

- Give `BLOCKIO.Detach` one clear contract for a valid allocated block volume:
  release it whether device opening succeeded or its request is still NULL.
  Only an attached request is closed/deleted and decrements `adapter.owners`.
  Preserve adapter identity, busy/reference checks and cache invalidation.
  Update all callers and focused tests together.
- Let `DestroyMount` use that operation directly, removing its separate
  request-present versus raw-FreeMem branch. Keep mount references and queued
  packets as ownership assertions. Backend metadata, filesystem Volume, port
  and mount storage still have their existing owners and release order.
- Keep one partial-startup cleanup path based on acquired pointers and existing
  signal markers. Preserve the distinction between an allocated arrival signal
  and an acquired cancellation signal; clear registry publication consistently.
  Remove unused imports and genuinely redundant locals in touched routines.
- Compare total affected routine bytes, callback count, local frame peaks and
  observed stack use against the baseline. If generalized block teardown only
  moves or increases code, retain the existing ownership split and document the
  result; do not add another wrapper just to shrink FSINIT's reported size.
- Record results and hashes in `docs/history/fsinit-simplification.md` and
  `docs/development/fsinit-simplification.json`; mark this plan and the roadmap
  complete after the selected checks pass.

Acceptance: opened and unopened resources each have a single release path;
failed startup and remount leave heap, signals, requests, ports, cache references
and registry ownership balanced. Other mounted volumes remain usable after a
dynamic failure. A failed initial multi-volume startup publishes no partial set.

## Focused validation

Follow the [two-tier policy](../contributing/testing.md). Batch edits into the slices above and
run checks once per coherent slice, rerunning failures or changed inputs only.
Use bank 1 and 128-byte media; reserve full placement/speed/sector matrices for
release qualification. No demo rebuild is part of this plan.

| Slice | Development checks |
| --- | --- |
| I1 | Host suite; raw/optimized mixed MyDOS/SpartaDOS startup and public DOS operations; affected startup-acquisition failures and failed-mount retry. |
| I2 | Host suite; `test_dos_system.py --drives` in raw/optimized mode and an optimized `--no-selection` case; duplicate alias/unit and malformed native descriptor cases. |
| I3 | Host suite; focused opened/unopened teardown failures, explicit stop/restart and last-application cleanup; final matching optimized mixed-volume size run if its inputs changed. |

Start with `tools/test_dos_startup.py`, `tools/test_dos_lifetime.py`,
`tools/test_dos_system.py` and `tools/test_sdfs_dos.py`. Repair stale acquisition
hooks when their source moves. The startup metadata-read and lifetime retry
overrides still use the older `BLOCKWIRE.Transfer` signature: update them to the
current boundary and preserve request/error behavior before counting their runs.

Cover the changed ownership boundaries: workspace/operation/backend work,
arrival/cancel signals, control port, mount/parser/backend/block volumes, mount
port, device request/open, metadata read/format and generation exhaustion. Include
a later-mount failure after an earlier mount acquired resources, dynamic failure
with another volume live, and successful retry after the injected fault clears.
Assert the original error as well as balanced cleanup.

Keep this inexpensive: use small test-only fault selectors and reuse one emitted
image for related failure cases where practical, rather than rebuilding the
whole system for each acquisition. Extend the existing runners only as needed;
do not build a general fault-injection framework. Record the overrides and
actual cases executed. Passing results are reusable only with matching inputs.

For every slice, reserved bank-zero delta is **0 fixed bytes / 0 bytes per Task**,
including guards, alignment and spare capacity. Fixed upper-memory reservations,
Task DP/stack capacity, worker count and signals remain unchanged. Local stack
use may change and must be measured; touched-byte observations are not worst-case
proofs. Keep native guards, bounded completion, ownership checks and OS
restoration enabled throughout.

## I1 result

FSINIT now has four worker callbacks. Shared setup, mount allocations and
remount rollback use ordinary calls; device-open/read boundaries and the
between-mount checkpoint remain. Optimized FSINIT shrinks from 11,059 to 10,676
bytes; total resident/library routines fall from 313,310 to 312,927 (383 saved).
The complete memory map is unchanged: bank-zero delta 0 fixed / 0 per Task.

Development checks passed: 236 host tests; raw/optimized mixed-volume operations
(124 assertions each); 22 optimized and five raw acquisition-failure scenarios,
using one image per mode. They cover first/later-mount failure, unpublished
startup resources, repeatable rollback, peer-volume use and successful remount.
The largest observed Task stack use is 318 bytes raw and 291 optimized; guards
and ownership checks pass. Artifacts: `build/development/fsinit/i1/`.

## I2 result

Config binds each descriptor and effective unit once; mount setup uses the
shared record-copy primitive. FSINIT falls from 10,676 to 9,706 bytes, and total
resident/library routines from 312,927 to 311,957 (970 saved in this slice).
Resolving alias pointers before comparison added 353 bytes to FSSYSTEM, so that
experiment was discarded; the existing bounded comparator remains.

The Config local frame rises from 42 to 46 bytes; AllocateMount falls from 38
to 34. Complete memory reservations remain unchanged: bank-zero delta 0 fixed /
0 per Task. Validation covers the host suite, raw/optimized SYS selection and
drive overrides, absent SYS selection, 19 native configuration cases and the
matching optimized mixed-volume fixture. Artifacts: `build/development/fsinit/i2/`
(`final-*` paths contain the retained comparator).

## I3 result

`BLOCKIO.Detach` releases both unopened and opened volumes; `DestroyMount` no
longer branches between raw storage release and device teardown. Cleanup uses
the existing NULL-tolerant adapter destroy operation and drops redundant locals
and unused imports. Ownership assertions, cache invalidation and distinct
signal acquisition markers remain.

FSINIT is 9,494 bytes; BLOCKIO grows by 34 bytes. This slice saves 178 bytes
across resident modules, bringing the total saving to 1,531 bytes against the
baseline. Memory reservations remain identical: bank-zero delta 0 fixed / 0 per
Task. The final mixed-volume run observes at most 291 Task-stack bytes and 260
kernel-stack bytes, matching the baseline maxima.

All 236 host tests and 26 final-slice native scenarios pass: raw/optimized block
ownership and cache checks; opened/unopened failures on both filesystems;
first/later-mount rollback and live-peer recovery; malformed media; explicit
stop/restart, last-application shutdown and retry; matching mixed-volume DOS
operations. The lifetime fixture's obsolete 524-byte Service assertion was
corrected to the current 454 bytes. Artifacts: `build/development/fsinit/i3/`.
