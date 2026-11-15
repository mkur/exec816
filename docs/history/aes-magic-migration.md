# MagiC-led AES migration

[History](README.md) · [Plan](../plans/gem4xe/aes-semaphore-migration-plan.md) ·
[Current AES contract](../reference/aes.md) ·
[Development evidence](../development/aes-magic-migration.json)

## AM1: direct cursor completion

The native caller handler now publishes logical mouse state, releases the scene
normally, invokes the resident C device helper in that same Task, notifies
satisfied revision waiters and returns. Physical work uses the existing backend
grant and fences. The normal path has no cursor-only presenter wake ahead of
the caller's attempt. Required scene/policy wakes and normal preemption remain.

The existing native/C invocation bridge preserves the enclosing native frame
and lower C workspace across hardware or fallback waits. No extra per-call
phase protocol, request/context fields, public GEM operation or COP was added.
BUSY retains presenter continuation; a device fault reports a display error.
The completion helper follows the current coherent target and can satisfy an
older waiter with a completed newer revision. Remaining physical work still
gets a presenter hint; notifications use the existing guarded waiter scan.

Development checks pass: the existing optimized cursor integration has 431
assertions with exact physical pixels, nesting, forms, peers, UPDATE-held work,
retirement and a background counter. Seven controlled backend cases pass 37
assertions for inline/no-op/no-workstation/BUSY/error/newer/status completion and
unrelated-signal preservation. An initial fixture entry pilot was replaced by
the standard native/C invocation bridge. Host checks pass 718 tests, five skips.
No raw desktop, QED, demo refresh or release matrix ran.

The callback address uses three upper global bytes. Request/context layouts,
Task pools and native gateway remain unchanged. Reserved bank-zero deltas are
**0 fixed, 0 root, 0 kernel, 0 idle, 0 per public Task**, counting guards,
alignment and spare capacity. The integration root peaks at 794 bytes in its
existing 1536-byte stack, leaving 486 bytes above its floor. Per-Task/kernel
peaks and pinned image/compiler inputs are retained in the evidence.

The superseded accounting prototype was archived under the local development
directory and removed before AM1. It was not accepted as native UPDATE migration.
AM2–AM5 remain pending. End-to-end scrolling is measured in AM5; cursor checks
alone establish no viewer latency claim.
