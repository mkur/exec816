# MagiC-led AES ownership and execution-flow migration

[GEM plans](README.md) · [MagiC model](../../architecture/magic.md) ·
[Exec mapping](../../architecture/magic-exec-mapping.md) ·
[Native semaphore contract](../../reference/semaphores.md) ·
[AES contract](../../reference/aes.md)

Status: AM0–AM1 complete, AM2–AM5 pending, 2026-11-15. Implementation resumed
at the user's request. This revision supersedes the AM1–AM4 plan committed as
`79feb9de`. Runtime basis: `4c006f30`; donor: MagiC
`28cfdd29aa16fef692cc287bad3046b44ddcce3d`.
[Execution record](../../history/aes-magic-migration.md).

The superseded uncommitted prototype was archived locally and removed before
AM1. Its native accounting under the old admission queue and UPDATE release
before protected window cleanup were not adopted.

## Reassessment

The previous plan preserved Exec's current coordination structure and attached
native semaphore calls to it. The requested direction is to extract MagiC's
ownership hierarchy and handler flow, then supply Exec-safe synchronization.
That changes the migration, rather than just its implementation details.
The shared UPDATE/MCTRL dependency and acquisition ordering are intentional
semantic changes from current Exec, alongside the execution-flow simplification.

| Previous decision | Source finding | Revised decision |
| --- | --- | --- |
| Keep the mixed AESWAIT UPDATE/MCTRL/window admission queue; native Attempt must always succeed after that queue admits a caller. | `wind_update` waits on the UPDATE blockage; `free_semaphore` commits the oldest waiter's owner/count before making it ready. | The native semaphore performs actual UPDATE arbitration, sleeping and FIFO handoff. Retire the duplicate resource-admission queue at cutover. |
| Keep UPDATE and MCTRL as independent ownership mechanisms. | `beg_mctrl` first acquires UPDATE, then establishes additional menu/input routing state; `end_mctrl` restores routing and releases one UPDATE level. | MCTRL is a routing scope built on the same recursive UPDATE resource. Its overlay count has a distinct purpose, not a second lock authority. |
| Special-case already-owned setters while retaining the surrounding policy machinery. | `_wind_set` enters UPDATE through a shared helper, performs the field operation and releases through the matching helper. | Use that common operation shape for both fresh and recursive setters. Make recursion cheap in the shared helper. |
| Release all UPDATE/MCTRL levels before submitting the existing window/menu retirement operation. | `wind_new` restores MCTRL routing and withdraws menus/backgrounds/windows while UPDATE is owned, then releases UPDATE and repairs mouse state. | Complete protected UI cleanup before final UPDATE release. Detach registration/storage only after native ownership has ended. |
| Preselect extra caller/presenter/completion modes for every mouse call. | `gm_hide`/`gm_show` call the mouse/device helpers synchronously; physical sprite work precedes ordinary AES-return scheduling. | Make synchronous caller completion the normal flow. Use continuation machinery only for actual deferred backend work. |

A short metadata guard and a physical backend grant remain separate from
UPDATE. MCTRL depending on UPDATE does not combine all three resources.

## Source-backed target flow

### One UPDATE resource

`BEG_UPDATE` follows one path: decode the supported operation, obtain the native
semaphore, perform outermost painting-scope setup only when needed, and return.
A contended Obtain sleeps before taking scene metadata ownership. The resumed
call already owns the resource; it does not re-enter an eligibility lottery.
TRY uses native Attempt and returns a miss without enqueueing or mutation.
An existing owner recurses through the same helper.

On END, finish the relevant paint journal, cache and metadata publication while
ownership is still held. A nested END only balances its level and necessary
caller-visible depth facts. Final native Release publishes FIFO ownership.
Exec may schedule the recipient inside Release, so all ownership-dependent
writes and hardware completion must precede it. Preserve the existing native
IRQ/NMI protocol and normal Task preemption throughout the ownership lifetime.
MagiC's supervisor-mode scheduling rules are not an Exec substitute.

Keep resource acquisition separate from painting/cache epochs. MagiC's
`_beg_update` does not walk an application's windows, rebuild visibility, publish
input snapshots or refresh the cursor. Eliminate unconditional equivalents from
Exec's resource-entry helper. Establish current geometry when geometry changes;
attach painting/damage work to its actual semantic boundary. Where Exec's cached
moves require conservative invalidation for an unreported model change, use an
explicit or lazily reconciled scope/generation rather than silently dropping the
protection. Prove empty/unreported UPDATE, partial paint and cached-move behavior
before replacing the existing BeginUpdate/EndUpdate sweeps. A faster nested path
alone does not satisfy this entry-flow goal.

The native owner/count/waiter state is authoritative. AES may publish client
identity, painting depth or window scope for GUI consumers and cleanup; those
facts must not become a second arbitration engine. Distinguish explicit UPDATE
levels, MCTRL routing levels and temporary internal handler nesting. Specify
how existing `view.updates` consumers obtain paint permission and depth facts,
including MCTRL-only ownership, before changing that publication.

### MCTRL and ordinary window operations

MCTRL obtains UPDATE before altering routing. Its first overlay saves/replaces
menu/input state, recursion preserves that saved state, and the last overlay
restores it before releasing the corresponding UPDATE level. Ordinary UPDATE
alone does not create an explicit MCTRL routing scope. The current implicit
mouse-owner and mouse-owner-upgrade rules require explicit migration; the old
upgrade exception becomes ordinary recursion because MCTRL already owns UPDATE.

Window mutators use the common UPDATE entry/exit helpers. Under an existing
UPDATE, a slider setter therefore nests, compares/mutates the field, performs
only the required geometry/damage/publication and balances its level. Equal
values retain the existing no-op behavior. Preserve supported field/value errors
and cache correctness; donor value-clamping details are not adopted implicitly.
Handle admission stays at its proper API boundary rather than being repeated
through every internal layer.

Replace the old cross-resource window-prefix barrier with the common UPDATE
acquisition order. FIFO order means arrival at UPDATE acquisition, not global
message arrival order. Existing redraw/message ordering remains a separate
contract. This is an intentional change from the current Exec policy and must
be documented and tested, rather than hidden behind old compatibility rules.

### Cursor calls

The normal call sequence is:

1. Admit the caller and update its logical contribution/form using short guards.
2. Apply the resulting current target through the existing backend grant/fences.
3. Publish completion and notify any satisfied peer waiters.
4. Return through normal Exec scheduling.

Inner hide/show levels and unchanged targets avoid unnecessary physical work.
No cursor-only presenter wake should run ahead of an eligible caller's own
physical completion. Preserve required scene/policy wakes and independent work.
Copied forms and revision checks protect newer peer targets. A missing workstation,
BUSY backend or real unfinished operation may need the existing continuation;
its durable completion condition and wake-before-Wait rules remain necessary.
Specify failures and retirement without making an extra completion round trip
a universal normal-path requirement.

### UI cleanup and departure

Keep the donor entry points distinct: MagiC's AES `appl_exit` flushes messages
and yields, ending with an UPDATE acquire/release; its broader UI teardown is
the `wind_new` path. Exec currently combines more cleanup in `appl_exit`/detach.
Use the broader donor path to order that combined work, rather than claiming
the two `appl_exit` routines perform identical cleanup.

Model cooperative UI cleanup on `wind_new`: establish or retain UPDATE,
restore/remove owned modal routing and menus, close/delete owned windows and
finish painting/cache effects, release owned UPDATE levels, repair cursor
contributions, then detach registration and storage. A last-client service
cannot be freed while its semaphore or an owner continuation remains live.

Cleanup executes in the owning Task wherever native release is required.
A presenter may complete a separately retained effect, but cannot release a
peer's kernel semaphore. Split preparation, owner completion and final detach
when required by existing asynchronous effects; retain the registration through
the owner phase. Failed preparation preserves the necessary live context and
ownership for retry. Normal `appl_exit` continues to clean up outstanding holds;
held ownership alone must not make the public call a new BUSY failure.

MagiC also has privileged process/application cleanup (`SEM_FPD`/`SEM_FALL`).
Exec's native service deliberately has no cross-Task release or owner-death
recovery. This plan covers cooperative departure and explicitly leaves forced
foreign-Task cleanup unsupported. Do not describe that difference as MagiC
requiring owner-side cleanup in every termination path.

## Exec dependencies to resolve before native cutover

Use this lock order: obtain UPDATE before short scene/metadata access; drop the
scene guard before physical work or waits; retain the backend grant through its
hardware/scratch completion. No contended UPDATE Obtain is permitted under a
scene or display resource that the owner needs in order to release UPDATE.

The presenter also dispatches independent input and device completion. It must
not park the whole Task on UPDATE when an owner needs that independent work.
Resource-dependent presenter work may try UPDATE and defer while independent
work continues. Define a non-authoritative release hint for that case, using
existing signals and a bounded publication/release/wake protocol. Prove no lost
hint at final Release, including a recipient running before the wrapper returns.
A hint cannot grant ownership or recreate the AES client-admission queue.
Normal application contenders use native blocking Obtain directly.

Audit every presenter mutation, caller-local handler, route/resource continuation,
menu/form entry and gesture callback against this rule before switching engines.
In particular, MagiC's real-time slider callback explicitly releases UPDATE,
notifies the application, then reacquires and restores its scope. Express any
needed Exec ownership loan as balanced public acquire/release operations with
retained routing/lifetimes. Never edit private native semaphore depth to imitate
MagiC's direct counter save/restore. Test close, input loss and cancellation at
that boundary.

## Executable slice order

Each slice must be concrete, bounded and separately committed. Do not start the
next one before recording the previous slice's actual scope and results.

| Slice | Delivery | Focused acceptance |
| --- | --- | --- |
| AM0 — Source/flow reassessment | This plan, verified donor anchors, explicit semantic changes and lock/dependency map. | Source hashes, operation-flow and documentation checks only; no runtime acceptance claim. |
| AM1 — Direct cursor completion | Implement the existing inline cursor design around the synchronous caller flow above. | Small cursor/Counter cases for nesting, peer completion, required wakes, fallback and failure; one existing cursor pixel/retirement case. Commit before broader UPDATE work. |
| AM2 — Common handler boundaries | Restructure the current handler flow around shared UPDATE entry/exit, MCTRL's dependency and short scene access; route window mutators through the same helpers. Separate resource entry from unconditional window/snapshot/cache sweeps. | Tiny owner/contender/Counter fixture plus named/PB recursion, MCTRL-only and mixed nesting, unchanged/changed slider fields, painting-depth publication, empty/unreported scopes and cached-move correctness. Existing representation may remain during preparation; add no second semaphore/accounting layer or replacement custom queue. |
| AM3 — Cleanup and continuation flow | Move protected UI cleanup into the owner context before final release; establish lifetime retention, presenter release hints and controller ownership loans. | Held/nested `appl_exit`, failed preparation/retry, last-client shutdown, independent input/timer/fence progress and a controlled callback/reacquire case. Retain current mechanism until these paths are ready for native ownership. |
| AM4 — Native UPDATE cutover | Replace the existing resource owner/wait engine with one native semaphore for UPDATE, MCTRL dependencies and temporary handler scopes. Remove obsolete eligibility/retry arbitration in the same slice. | Native FIFO/non-barging and TRY, recursion across MCTRL/window calls, owner-before-ready publication, no blocked scene owner, retirement and the relevant prepared continuation cases. Recheck earlier tiny fixtures against this one current implementation. |
| AM5 — Matched scroll acceptance | Run the same loaded MGVIEW/Counter line-down/up comparison, then update current contracts and evidence. | Exact pixels, Counter progress, guards, cleanup; timings of BEGIN/setters/hide/show/END, presenter wakes, IRQ/off-Task attribution and input-to-pixels latency. Report the actual result, including regressions or inconclusive variation. |

AM1 is the first implementation slice: it is independently supported by the
existing scroll trace and follows MagiC's synchronous mouse flow. AM2/AM3
prepare operation and lifetime boundaries before AM4 changes ownership. This
avoids treating the unfinished accounting prototype as a delivered foundation.
The AM4 commit must not retain two live UPDATE arbitration paths.

## Validation, ABI and memory budget

Use development-tier checks: clean pinned actionc, release host compiler,
optimized guest builds and the pinned GEM PAL 8x/4 MiB ROM/emulator configuration.
Use small raw/optimized probes only for changed compiler-facing layouts/bridges.
Run host checks after coherent code slices; reuse frozen images only when their
actual source/ABI/machine inputs match. Keep failed/excluded pilots identified.

Use the current ABI-46 baseline and selected MGVIEW/Counter APPs where their
inputs are compatible; verify their provenance before reuse. Rebuild affected
provider/native fixtures. If a public binding/layout changes, advance its ABI
coherently and rebuild only the selected consumers. MGVIEW's standard GEM source
calls stay unchanged. No QED, MagiC image, application catalog, demo refresh or
release matrix is part of this migration.

Target zero added reserved bank-zero bytes for fixed, root, kernel, idle and
each public Task, including guards, alignment and unused capacity. One native
UPDATE object costs 12 upper bytes; report the net private-state change after
old queue/state removal and actual allocator rounding. Do not carry the old
prototype's service-size assumption into the revised implementation. Keep Task
and kernel semaphore ABIs and stack/DP reservations unchanged unless a measured
need is separately justified. Record actual stack high-water marks.

## Donor anchors and reassessment evidence

Local raw sources were checked against `build/magic-architecture/source-manifest.json`
at the pinned donor revision. Hashes are SHA-256:

| File | Verified digest |
| --- | --- |
| `AESMAIN.S` | `180fd7bc8453ecbdddf1bedce4932a299c81c9dfca269e4d3f891e74945927cc` |
| `AESEVT.S` | `ca75b9b85de9631caaa838ae8a3215c05ac72cbc1b0595cdeef275292ba89c81` |
| `AESWIN.S` | `29d9ac92d87f66c08c2b428e118e4478171a1272c37627ece557b1e64821ae0a` |
| `AESOBJ.S` | `abbda7614a2a9339894c87ca65666cc9581624ea631889dae2e070e2f3e66bd3` |
| VDI `INPUT.S` | `cd304139c8372592ec2bb7b6207cdaea85c42c04f3d502105b4399ed022c16c5` |

- [UPDATE acquire, wait, release and FIFO handoff][update].
- [MCTRL acquiring UPDATE and restoring routing][mctrl].
- [Window-setter common UPDATE entry][setter] and [slider/return flow][slider].
- [AES hide/show dispatch][mouse], [device nesting helpers][device] and
  [physical VDI cursor work][vdi], followed by [ordinary AES return scheduling][return].
- [MCTRL cleanup and protected window/menu teardown before UPDATE release][cleanup].
- [The distinct MagiC AES `appl_exit` entry][appl-exit].
- [Privileged process/application semaphore cleanup][forced].
- [Real-time slider callback's explicit release/reacquire][loan].

These are source-derived structural requirements, not an executable equivalence
claim. Exec's preemptive synchronization, independent presenter work, paint/cache
journals, backend grants and cooperative-only native semaphore cleanup are
explicit adaptations to validate at their own boundaries.

[update]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L1414-1558
[mctrl]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L562-632
[setter]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESWIN.S#L2273-2345
[slider]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESWIN.S#L2733-2802
[mouse]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L7199-7208
[device]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESOBJ.S#L362-376
[vdi]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/VDI/SRC/MAGICVDI.2/INPUT.S#L233-274
[return]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L411-427
[cleanup]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L11037-11145
[appl-exit]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L112-139
[forced]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L1367-1409
[loan]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESWIN.S#L3081-3156
