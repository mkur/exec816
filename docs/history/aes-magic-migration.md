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
End-to-end scrolling is measured in AM5; cursor checks
alone establish no viewer latency claim.

## AM2: common handler boundaries

UPDATE is now the common recursive resource. MCTRL adds a routing level to
UPDATE; ordinary UPDATE leaves mouse routing alone. Explicit painting depth is
the sum of public UPDATE and MCTRL levels. Temporary window-handler levels
serialize mutations without starting a journal or changing public context depth.
Safe recursion uses the same transitions without scene admission. The existing
wait engine remains until AM4; this slice adds no native semaphore overlay.

BEGIN resets the journal without touching Layers, cache generations or geometry.
Conservative cache invalidation moves to END, or before an intervening owner
mutation could reuse pixels. Geometry changes and paint handoffs publish views.
Only painting-depth publication remains at the public painting boundary.
Temporary handler ownership still permits cached moves when no painting scope
is active. MCTRL-only application outlines retain their existing permission;
AM3 must make their controller ownership loan explicit before native cutover.

Development checks pass: the tiny owner/contender/Counter fixture has 51
assertions, including named/PB recursion with scene admission deliberately closed,
mixed and MCTRL-only depth, equal/changed sliders, unrelated signals and actual
preemption. Existing optimized locks pass 231 assertions; cache/journal/move
checks pass 224; routing passes 838. The small private-layout/waiter probes pass
19 assertions each in raw and optimized modes. Host checks pass 718 tests, five
skips. C fixture reuse now verifies recorded source and header hashes.

Excluded pilots identified an Action! branch declaration, insufficient fixture
upper image-data capacity, the old cached-move unheld test and a missing fixture
shutdown drain. The final tiny fixture returns normally after frame retirement;
its root peak is 605/1536 bytes. The maximum-window lock fixture peaks at
1089/1536, leaving 191 bytes above its interrupt floor; kernel peak is 287.

The private Service grows 2324→2328 bytes, consuming its old four-byte allocator
rounding space; its rounded allocation stays 2328. Client and public wire/C
layouts are unchanged. Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel,
0 idle, 0 per public Task**, including guards, alignment and unused capacity.
No QED, demo/package refresh or release matrix ran.

## AM3: owner cleanup and continuation boundaries

Cooperative exit now obtains or retains UPDATE in the calling Task, restores
MCTRL, closes admission and waits for retained publishers, withdraws menus and
windows, finishes painting and releases its levels. Cursor repair follows final
release using the AM1 device-completion path. Only then does the existing RPC
detach registration and release storage/Task leases. Raw unprepared exit returns
BUSY. No presenter force-release path remains. Overflow preparation fails before
withdrawal and preserves the live registration for retry.

Menu mutations and application-outline admission use caller handlers; menus use
the common UPDATE scope. Presenter release hints schedule work without granting
ownership. Controller notifications mark a return boundary that erases an outline
without withdrawing capture/gesture identity before availability publication.
AM4 supplies the native Try/Release pair at these prepared boundaries. Current
frame controls notify on release; real-time slider callbacks remain unsupported.
Retained physical effects still complete through their existing lifetimes.

Development checks pass: the tiny owner/contender/Counter case has 60 assertions,
including a real arrow callback followed by application reacquisition/setter,
nested held departure in both Tasks, failed preparation/retry, a live menu,
unrelated signals, preemption and last-client shutdown. The selected scene case
passes 33 application assertions and its native scene/physical guards: captured
input, retained copy/fence completion and a peer advance while scene ownership
is unavailable. The optimized private-layout probe passes 19 assertions.

Excluded fixture pilots omitted pointer-profile metadata, left a debugger
breakpoint installed or stopped before unrelated frame/cache work drained.
The refreshed fixtures drain before shutdown and use the actual pointer profile.
The scene observer was updated for the current routine boundaries. No product
shutdown retry/polling path was added to accommodate them.

The private hint occupies the old final padding byte: Client remains 376 bytes,
Service 2328, with no rounded allocation growth. The existing continuation-mode
byte also marks prepared departure. Public layouts, APP ABI and Task ABI are
unchanged; the generated RPC-operation set reflects the current caller entries.
Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 idle, 0 per public
Task**, including guards, alignment and spare capacity. Stack evidence is in the
development record. No QED, demo refresh or release matrix ran. AM4–AM5 remain.
