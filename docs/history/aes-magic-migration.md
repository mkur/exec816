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
development record. No QED, demo refresh or release matrix ran.

## AM4: native UPDATE cutover

One native semaphore now arbitrates UPDATE, MCTRL and temporary handlers.
Uncontended/recursive calls use native Attempt; normal misses use blocking Obtain
before scene access. The native FIFO owns handoff before Ready. The mixed AES
lock queue, prefix barriers, eligibility lottery and retry scan are removed.
Published client/depth facts support GUI permissions and cleanup, without granting
ownership. All journal, routing and cache publication precedes native release.

The presenter tries the resource, retains it through an actual hardware/scene
continuation, and releases through the public primitive at a settled boundary.
Control notifications use the prepared release/reacquire boundary. A failed Try
publishes a guarded wake hint and leaves independent input/fence work active.
An application contender hints that idle gathering should settle, then waits in
the kernel. A separate journal-completion wake remains necessary even if the
presenter slept through the entire painting scope: a cache test caught and fixed
that missed-work case.

MCTRL obtains UPDATE before waiting for any older foreign physical capture;
this is operation readiness, not another ownership queue. A TRY readiness miss
balances the attempted native level without changing routing. Application outline
erasure similarly retains the already established owner while physical work
finishes. Neither continuation can hand ownership to a Task. Forced foreign
release/owner-death recovery remains unsupported.

Development checks pass: 64 tiny owner/contender/Counter assertions, including
native per-Task ownership counts and held cleanup; 237 lock assertions with three
FIFO contenders in both orders, non-barging and ownership before the recipient
runs; 224 cache/journal/move checks with exact pixels; 168 pointer assertions and
25 normalized-input boundaries; one retained-copy/input scene case with 31
application assertions and native physical/scene guards. The small native-object
and private-layout probes pass 19 assertions in both raw and optimized modes.
Host checks pass 718 tests, five skips. Observer boundaries for the other changed
private-layout fixtures were checked without running a qualification matrix.

Excluded pilots exposed the missed journal wake and fixture assumptions about
old ownership fields, scene checks on the now scene-free BEGIN, and background
drain before shutdown. The frame-cache observer now permits a valid intermediate
capture between two independent slider setters: each call releases UPDATE.
This capture has two snapshots there; equal setters still cause none. It does
not claim that separate unheld setters coalesce into one presentation.

Client shrinks 376→374 bytes (eight bytes across four slots). Removing the old
queue and alignment leaves room for the 12-byte native object: Service and its
rounded allocation remain **2328 bytes**. One upper global byte records the
presenter's retained native scope. Reserved bank-zero deltas are **0 fixed,
0 root, 0 kernel, 0 idle, 0 per public Task**, including guards, alignment and
unused capacity. Stack peaks and image/compiler hashes are in the evidence.
No Task/kernel/APP layout or ABI changed. No QED, demo refresh or release matrix
ran.

## AM5: matched original MGVIEW scrolling

The provider/native fixture was rebuilt once; MGVIEW and Counter APPs were
reused byte-for-byte from the pre-AM1 baseline. Both captures use ABI 46,
the same document, viewport, parked pointer, PAL 8x/4 MiB machine, pinned ROM,
emulator and compiler. Each action completes one hardware copy and one exposed
text-row draw, with no redraw fallback or scrolling RPC. Exact pixels match;
Counter advances, all guards remain intact and all applications/service resources
retire. No APP source or binary changed; no QED, catalog, demo or release build ran.

| Measurement, ms | Down before → after | Up before → after |
| --- | --- | --- |
| Offered key to complete-pixel observation | 140.21 → 141.07 | 160.52 → 140.27 |
| Viewer `set_shift` CPU | 80.82 → 78.28 | 81.67 → 71.48 |
| Presenter CPU while UPDATE is held | 30.30 → 7.63 | 31.65 → 2.82 |
| BEGIN call wall time | 7.81 → 18.68 | 7.82 → 1.98 |
| Two slider setter calls, wall time | 18.99 → 22.81 | 21.08 → 23.54 |
| Hide call wall time | 12.72 → 13.68 | 12.33 → 8.16 |
| Copy call wall time | 38.54 → 23.75 | 38.63 → 14.83 |
| Exposed-row draw wall time | 23.03 → 22.66 | 23.20 → 23.28 |
| Show call wall time | 18.89 → 7.01 | 20.60 → 6.96 |
| END call wall time | 17.78 → 26.98 | 40.57 → 23.27 |

These are two observations, not a latency distribution. PAL-frame polling gives
upper bounds: the down brackets overlap (124.05–140.21 before,
120.38–141.07 after); up brackets also slightly overlap (140.08–160.52 before,
121.00–140.27 after). Down is effectively unchanged; the observed up result is
about one frame earlier. This does **not** establish a consistent latency gain.
The renderer's existing drawing limits remain unchanged.

BEGIN's viewer CPU falls from about 6.45 ms to 3.85/1.63 ms, but the down call
spends another 13.84 ms off-Task. END CPU falls from 10.01/10.69 to 6.37/6.55 ms;
its final handoff/scheduling still costs wall time, much of it after visible
painting. Two setter calls regress from 13.29/13.97 to 15.23/15.19 ms CPU.
The remaining measured work includes 11.58–14.84 ms CPU in the copy binding and
about 18 ms drawing one text row. Native ownership simplifies coordination;
it does not remove that library/renderer cost.

Within the already-owned UPDATE interval, decoded presenter posts fall from five
per action to three/one: scene release/entry hints remain; the old display-release
post disappears. Presenter device mouse returns fall from one to zero there;
hide/show physical work now completes in the caller. Native acquisition/final
release hints outside that core interval are retained by source site in the
comparison. Their arguments were not instruction-traced and are explicitly
reported as undecoded, rather than counted as decoded presenter wakes.

The passive comparison tool checks matching inputs, final pixels and copy units,
then pairs emitted APP API call/return sites and separates viewer CPU, off-Task
time and IRQ/NMI cost. Reanalysis needs no guest execution:

```sh
python3 tools/compare_mgview_scroll.py \
  --before build/aes-migration/baseline-scroll/results.json \
  --after build/aes-migration/am5-scroll/results.json \
  --output build/aes-migration/am5-comparison.json
```

The measurement CLI now treats an absent presenter `Present` span as zero;
the successful capture initially reached a formatting KeyError after writing
its passing results. Read-only reanalysis confirms the corrected CLI without
rerunning the guest. This is development evidence, not hosted-system release
qualification. AM0–AM5 are complete; all reserved bank-zero deltas remain zero.

## AP1: presenter UPDATE scopes follow actual work

MagiC's ordinary key path (`handle_key` → `write_key` → `event_happened` in
the pinned AESEVT source) needs no UPDATE. Its screen manager acquires UPDATE
after `_evnt_multi` returns, for its own UI operation. Exec's loop-wide Try
before input delivery has been removed. Pending menu/gesture actions, paint,
cache transfer and console display controls enter a common presenter scope;
ordinary key delivery, cursor refresh and no-work probes acquire no UPDATE.
Nested scopes share one native hold, with one upper-memory CARD of nesting
state. Actual scene/hardware continuations retain their existing authority and
ownership until retirement. Client-owned effects can still finish without the
presenter obtaining the client's semaphore. Normal Task preemption remains on.

The cache regression exposed a late-work wake race: frame damage could arrive
after the paint attempt while its private handler still owned UPDATE. The
presenter observed blocked work at scheduling and slept without arming a release
wake. A diagnostic extra wake made the unchanged image pass, identifying the
missing notification rather than a rendering defect. Pending-work readiness now
registers the existing hint under the final-release guard; a released owner is
rechecked before sleeping. Empty probes acquire no resource. The cache check
explicitly requires the title repaint to finish before the next copied move.

Development checks pass on the pinned optimized compiler, PAL 8x/4 MiB machine,
ROM and emulator: 68 tiny owner/contender/Counter assertions; 168 pointer checks,
25 input-boundary checks and five native checks; 224 cache checks over 32 phases
and five native checks, including exact pixels, copied moves and mixed-owner
menu restoration. The tiny observer stops after key publication and before
consumption: presenter native hold and scope depth are both zero; the recipient's
immediate UPDATE TRY succeeds. Runtime status is zero, guards remain intact and
cleanup passes. Root/kernel peaks are at most 758/287 bytes across these scenes;
the presenter's peak is at most 734 bytes in its existing 2560-byte reservation.

Observer pilots and the artificial-wake diagnosis are excluded from acceptance.
Final captures use the direct fixture-owned inbox pointer and native IRQ
rendezvous, covering native fast paths without an upper-bank breakpoint. No
public ABI, Service size or stack/DP reservation changes. Reserved bank-zero
deltas are **0 fixed, 0 root, 0 kernel, 0 idle and 0 per public Task**, including
guards, alignment and spare capacity. No QED, catalog, demo or release build ran.
AP2 will measure the unchanged MGVIEW/Counter APPs separately.

## AP2: unchanged APPs with operation-scoped presenter ownership

Only native policy was rebuilt after AP1. The C provider's 50 source and 87
header hashes were verified before reuse; MGVIEW and Counter APPs, disk,
document, viewport, parked pointer, ABI, ROM, emulator and PAL 8x/4 MiB
configuration match AM5. Exact final pixels match, each action still performs
one physical copy and one exposed-row draw, Counter advances and all four
application executions retire. Runtime status is zero and guards remain intact.
No C/provider application, QED, catalog, demo or release build was added.

| Measurement, ms | AM5 down → AP2 down | AM5 up → AP2 up |
| --- | --- | --- |
| Offered key to complete-pixel observation | 141.07 → 120.93 | 140.27 → 140.62 |
| BEGIN wall time | 18.68 → 1.99 | 1.98 → 12.55 |
| BEGIN viewer CPU | 3.85 → 1.63 | 1.63 → 2.33 |
| BEGIN off-Task time | 13.84 → 0 | 0 → 9.54 |
| Two slider setters, viewer CPU | 15.23 → 15.20 | 15.19 → 15.19 |
| Whole `set_shift`, viewer CPU | 78.28 → 71.18 | 71.48 → 72.17 |
| Presenter CPU within already-owned UPDATE | 7.63 → 3.55 | 2.82 → 3.55 |

The viewer reaches the acquisition-miss signal site once/zero times in AM5
down/up and zero times in both AP2 actions. This is source-site evidence from
`AESLOCKS.Call`'s failed native Attempt branch, without guessing signal arguments.
The AP2 up BEGIN's 9.54 ms off-Task therefore is not a native semaphore contender
wait. Ownership and total off-Task time must not be conflated.

These remain two actions, not a distribution or a worst-case bound. Down's
pixel brackets are 120.38–141.07 before and 104.29–120.93 after; up's are
121.00–140.27 and 120.12–140.62. Both pairs overlap. The observed down result
arrives about one PAL frame earlier, while up is effectively unchanged; this
does not establish a typical latency gain. The operation-scoped ownership and
ordinary key publication behavior are established separately by AP1's emitted
regressions. Setters and renderer cost remain outside this follow-up's scope.

Reproduce the frozen capture/comparison without any rebuild:

```sh
python3 tools/measure_mgview.py --cache build/aes-migration/ap2-provider \
  --output build/aes-migration/ap2-scroll --presenter --expect-copy-units 1
python3 tools/compare_mgview_scroll.py \
  --before build/aes-migration/am5-scroll/results.json \
  --after build/aes-migration/ap2-scroll/results.json \
  --output build/aes-migration/ap2-comparison.json
```

The standalone MagiC model now records the ordinary-key/screen-manager UPDATE
split explicitly; its source and documentation checker passes 32 pinned sources,
67 ranges and 39 structural checks. AP1–AP2 are complete at the development tier.
All fixed/root/kernel/idle/per-public-Task bank-zero reservation deltas remain
zero, including guards, alignment and spare capacity. There is no public ABI
change or hosted-system release qualification claim.
