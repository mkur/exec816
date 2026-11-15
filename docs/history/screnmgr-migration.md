# SCRENMGR migration

[History](README.md) · [Migration plan](../plans/gem4xe/screnmgr-migration-plan.md) ·
[Current AES contract](../reference/aes.md) ·
[Development evidence](../development/screnmgr-sm1-cursor.json)

## SM1a: cursor policy without scene admission

The caller cursor handler no longer acquires or releases AESGATE. It uses
published input routing and bounded Task guards for recipient selection,
application hide/form state and the shared device target. Device depth is read
inside that guard. Registration now publishes client identity, binding and
endpoint within its existing guard so cursor readers cannot observe a partially
published client after losing the scene gate's exclusion.

The existing physical-completion bridge runs in the caller after the transition
guard is released. Display arbitration, fallback continuation, revision wakeups
and fault handling retain their existing responsibilities. A physical operation
can still wait; this slice removes scene admission from cursor policy, not
device arbitration. No viewer/application source or public ABI changes.

This follows MagiC's mouse path, which does not enter the window setter's UPDATE
path. See the pinned [source audit](../architecture/magic-update-scene-audit.md#magic-source-baseline)
and [mouse cross-check](gem-mouse-magic-review.md). The combined presenter and
other scene users still exist. Frame setters and independent manager/input
execution remain later migration work.

### Development scope

The small emitted scene-owner probe runs the production local cursor dispatcher
while a competing native Task owns the scene and computes without yielding.
Normal preemption returns control to the caller. It checks nested hide/show,
form/save state, raw device hide/show, unsupported selectors, preserved outer
Forbid nesting, unchanged scene ownership and an empty scene-waiter list.
Only physical completion is substituted; the probe also requires that callback
to execute in the calling Task. A separate existing mouse/Counter integration
checks actual device pixels, recipient/history behavior and retirement.

Development checks pass: 65 scene-owner assertions and 431 mouse/Counter
assertions, including 147 exact pixel comparisons. Both use the clean pinned
compiler in its optimized mode and the pinned PAL 8x/4 MiB ROM/emulator profile.
The real-device fixture returns status zero with normal ownership restoration
and intact guards. Its root, presenter and kernel stack peaks are 845, 730 and
287 bytes respectively, inside their existing reservations. Host checks pass
718 tests, with five historical skips. Documentation links are checked separately.
The evidence retains image/compiler hashes, runtime context and per-Task stack
measurements. No raw matrix,
QED, application catalog, demo refresh or release qualification is included.
These checks make no scrolling-latency or hosted-system qualification claim.

Fixture preparation initially omitted generated console declarations, then a
test routine's name collided with its local mouse pointer. Those attempts
stopped at compilation and are excluded from executable evidence. The final
scene probe explicitly yields to its computing peer before checking progress.

### Resource impact

Production gains no Task, signal, record field or global storage. Public wire,
request, client and service layouts are unchanged. Reserved bank-zero deltas are
**0 fixed, 0 root, 0 kernel, 0 idle and 0 per public Task**, including guards,
alignment and unused reserved capacity. No stack/DP reservation, upper-memory
record or VRAM reservation changes. Measured stack use belongs to the selected
fixtures and is retained in the evidence.
