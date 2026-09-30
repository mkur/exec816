# Filesystem initialization simplification

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

FSINIT now uses four worker callbacks instead of eight. Configuration and shared
resource acquisition happen in `First`; mount and block allocation happen in
`MountStep`. Device opening and metadata reads still return to the worker, and
the checkpoint between mounts remains. No new callback or rollback framework
was introduced.

Startup failure retires the whole service. A failed dynamic mount destroys only
its unpublished mount, preserves the original error and replies to the caller.
Initial publication still happens only after every configured mount is ready;
dynamic publication retains its existing exclusion. Other mounted volumes stay
available during a failed remount.

Configuration validation binds each descriptor and its effective unit once.
It retains validation order, bounded alias comparison, system-drive selection,
geometry checks and duplicate detection. Mount setup copies the immutable
44-byte descriptor through `A816MEMORY.Move` before applying the selected drive.
An experiment resolving alias pointers before comparison added 353 bytes to
FSSYSTEM, so the existing comparator was retained.

`BLOCKIO.Detach` now releases a valid allocated volume even if opening its device
never succeeded. It requires matching adapter ownership and idle, unreferenced
state, invalidates cached identity and releases storage. Only a non-NULL attached
request is closed/deleted and decrements the adapter's owner count. `OpenVolume`
already clears the request after an unsuccessful open. NULL volume/adapter
cleanup remains supported by `Detach`/`Destroy` respectively.

`DestroyMount` uses this shared operation instead of maintaining a raw-free
branch. Mount references and queued packets remain ownership assertions.
Cancellation and arrival signals retain their separate acquired-state markers;
record layouts, allocation boundaries and release ordering are unchanged apart
from keeping request/owner teardown together inside `Detach`.

## Measurement and validation

The [implementation plan](../plans/fsinit-simplification-implementation-plan.md) uses
source baseline `c8d6c99` and compiler
`27119ab2804e795b0bbb067c269826b934271754`. Size comparisons use the same guarded,
optimized mixed MyDOS/SpartaDOS fixture and include resident/library routines,
excluding only the fixture module. Full release matrices and a demo rebuild
are separate work.

| Optimized routine bytes | Baseline | Final | Change |
| --- | ---: | ---: | ---: |
| FSINIT | 11,059 | 9,494 | −1,565 |
| BLOCKIO | 6,996 | 7,030 | +34 |
| All resident/library modules | 313,310 | 311,779 | **−1,531** |

The slices save 383, 970 and 178 resident bytes respectively. Generalized
teardown therefore saves code across module boundaries; it does not merely
move bytes out of FSINIT. The result exceeds the approximate 1 KiB net target
and puts FSINIT below 10 KiB.

The compiler binary, ABI, guards, mount configuration and platform inputs match
the baseline. The complete memory map is unchanged. Reserved bank-zero delta
is **0 fixed bytes / 0 bytes per Task** in every slice, including guards,
alignment and unused reserved capacity. Task DP/stack capacity, fixed upper-RAM
reservations, worker count and signals are unchanged.

Config's local frame grows from 42 to 46 bytes; AllocateMount falls from 38 to
34. DestroyMount, Cleanup and Detach retain their 20/26/20-byte local peaks.
In the matching final mixed-volume run, the largest observed Task stack use
remains 291 bytes and kernel use remains 260 bytes. No interrupt reserve is
touched. Watermarks are lower bounds, not worst-case stack proofs.

Each slice passed the 236-test host suite. Native development evidence covers:

- I1: raw/optimized mixed-volume operations and 27 acquisition-failure
  scenarios. Tests repeat failure, verify original errors and exact heap/signal
  restoration, retry successfully and exercise a live peer during failed remount.
- I2: raw/optimized SYS selection and drive overrides, absent selection, 19
  native configuration cases and the matching mixed-volume size run. Invalid
  descriptors and exhausted generation are rejected before device opening.
- I3: 26 scenarios covering raw/optimized block ownership and cache behavior,
  unopened/opened rollback, MyDOS/SpartaDOS resource failures, malformed media,
  stop/restart, last-application cleanup, retry and mixed-volume DOS operations.

The small acquisition selector reuses one emitted image per selected suite;
related configuration cases likewise reuse one production image. Overrides are
test-only and recorded. Guards, bounded completion, ownership cleanup and OS
restoration checks pass. Earlier-slice evidence is tied to its own source
revision rather than being presented as final-source coverage.

Three stale fixture assumptions were repaired: empty configuration returns
before a worker changes registry state; Service is 454 bytes rather than 524;
and read-failure hooks must use the current BLOCKWIRE completion boundary.

The [development record](../development/fsinit-simplification.json) records source,
image, platform and result hashes, per-module deltas, local frames and stack
observations. Artifacts are under `build/development/fsinit/`.
