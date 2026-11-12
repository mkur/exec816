# GEM-first GUI execution

[Design](../plans/gem4xe/gem-first-gui-design.md) ·
[Implementation plan](../plans/gem4xe/gem-first-gui-implementation-plan.md) ·
[Current AES contract](../reference/aes.md)

## GF0 — Native GUI and disk baseline

Status: GF0 passes at the development tier. The
[execution record](../development/gem-first-gf0.json) retains five complete
functional cohorts and separately scoped CPU observations. Production GUI
policy is unchanged.

The fixture loads two private copies of one APP through Program/Process. Its
startup wrapper selects positions; `examples/gem-counter/counter.c` is unchanged.
The disk cohort performs four complete 16 KiB read/write/Close passes against
a fresh SDFS disk through native DOS, the filesystem worker and SIO at the
pinned nominal 57.6k profile with accurate disk timing. A host filesystem audit
checks saved bytes and allocation independently of the guest.

Separate cases replace the second Counter with a small GEM I/O client. They
distinguish an application's own blocked event loop, deliberate UPDATE-held
I/O, and cooperative cancellation during an active wire transaction. They do
not replace the Counter body with a test implementation.

All four 16 KiB read/write passes finish with exact persisted bytes and valid
allocation. Both Counters continue painting during disk work. A synchronous
read leaves its own event-loop count fixed at two while its peer advances;
UPDATE-held I/O also blocks the peer's paint until ownership is released.
Explicit public Process BREAK cancels the active read with error 304, followed
by normal request/application retirement and restored ownership. The initial
fixture incorrectly used GEM Stop, which queues a close and lets the read finish;
that failed attempt remains in `cancel-close-only-failure/`.

The idle census has seven public Tasks: root/controller, filesystem, SIO, two
applications, heartbeat and console/presenter. Both Counter Tasks occupy
ordinary 1,312-byte pools. Two AES registrations and two GEM windows coexist.
The fixture's root and heartbeat use Yield loops; `idle` means no explicit
post-startup disk load, not a quiescent production desktop.

Captured digit pixels during disk work decode to A `2,4,6,8` and B `1,3,5,7`.
Counter A remains inactive. Pixel changes and model/paint counts establish
progress; Counter increments are not a wall clock. The idle capture separates
charged Task CPU, off-Task time and native interrupt time using the existing
passive context observer.

Instruction-history tracing of the complete disk job exceeded a 600-second
host timeout after about 64 seconds of guest execution. Preserve that failed
attempt under `build/gem-first-gui/gf0/disk-trace-timeout/`. The replacement
protocol separates a bounded CPU-observation prefix from the full functional
job. The prefix intentionally terminates its private emulator and claims no
filesystem completion, persistence or cleanup. The full run keeps four passes
and the 18,000-frame guest completion bound. Host observation cost is not a
guest latency failure or permission to relax existing latency limits.

The pointer control records completion of a paced eight-pixel diagonal gesture.
Its elapsed interval includes the scheduled physical movement, so it is not
per-transition input latency or a pass of the original IL3 protocol. Full
latency gates remain open. This is focused development evidence, separate from
hosted release and physical-hardware qualification.

Reproduce the functional cohorts with:

```sh
python3 tools/test_gem_first.py --output build/gem-first-gui/gf0
python3 tools/test_gem_first.py --output build/gem-first-gui/gf0 --reuse
```

The first command builds; `--reuse` checks the frozen executable, seed media
and fixture source inputs. Current production-source edits do not turn a
reused frozen image into a current build. Keep candidate builds in another
directory. For the separate timing prefix:

```sh
python3 tools/test_gem_first.py --output build/gem-first-gui/gf0 \
  --reuse --case disk --trace-prefix
```

The fixed twelve-Task pool, root/kernel/idle stacks, guards, alignment and unused
capacity match the current platform map: **0 added fixed/root/kernel,
0 per-public-Task and 0 idle reserved bank-zero bytes**. The test adds upper-RAM
fixture/application storage and occupies existing Task pools. Preserve the
frozen emitted-input files recorded in the evidence before implementing policy
changes. The narrowest observed public-pool margin is 163 bytes above its
protected floor; no pool enlargement was needed. Host checks run 687 tests:
683 pass and four historical checks skip.

## GF1 — Shared window policy

`AESWINDOW.Request` decodes hidden create/delete and hit lookup before calling
typed helpers. Explicit deletion and client retirement share the same record
destruction. The presenter still executes the operations through the existing
AES request and reply path. [Window policy](../../lib/aes/aeswindow.act)

### Operation and effect inventory

Window mutations currently pass `AESWINDOW.Ready`, which checks mouse
ownership and presenter readiness. `AESLOCKS.NativeReady` consults the
display grant, Layers transaction, bitmap completion, menu replacement, console
batch, outline and tab gesture. The presenter retries pending requests from
`AESCORE.Settle`. `FIND` reads the committed stack before this readiness check.
[AES request dispatch](../../lib/aes/aescore.act) ·
[Readiness and lock admission](../../lib/aes/aeslocks.act)

| Operation | Scene and publication | Resource, input and physical effects |
| --- | --- | --- |
| `CREATE` | Claims a common AES/desktop slot and hidden external-paint layer, normalizes packed-pixel bounds and publishes the new handle, work geometry and initial slider/view. | The C binding allocates the upper-memory view and frees it if admission fails. The scene consumes fixed slots and distinct monotonic layer, desktop and GEM IDs. |
| `DELETE` | Requires a hidden layer. Clears the special desktop role, cache candidate, layer and both records, withdraws the view handle and synchronizes the top/focus directory. Layers retires saved-area identity. | The shared destroy path releases an attached console, which can restore its cursor through the display path. It cancels the window's GUI/gesture lifetime. The C binding frees the view after success. |
| `FIND` | Reads the topmost shown layer at a point and maps it to a GEM handle. A native window, icon tile, desktop or chrome yields zero. | Read-only, with no physical admission. |
| `OPEN` | Validates normalized geometry, publishes a fresh window epoch, sets bounds and chrome order, shows and focuses the layer, refreshes slider/view and can post a pending close. | Allocates a keyboard route from the existing lease for an ordinary GEM window and retires it on GUI epoch exhaustion. Focus may restore a console caret, cancel a widget gesture and publish a new route. |
| `CLOSE` | Withdraws the open epoch and pending GUI facts, closes the shared inbox/menu state after the last open sibling, restores focus, hides the layer, clears paint damage and restores normal bounds for an icon. | Cancels mouse capture, pumps captured keys and retries if the old route still has references. Focus can draw the outgoing caret. GUI epoch and focus can change before route retirement succeeds. |
| `WF_EXEC_CONSOLE` | Converts a hidden external-paint layer to retained content and attaches the console unit and its presentation metadata. | Resolves the unit by owner and checks geometry, presentation, scene and display availability. Claims the view and dirties retained cells. The reciprocal release can draw. |
| `WF_NAME`, `WF_INFO` | Copies bounded caller text and invalidates the corresponding strip. Title changes invalidate the Windows-menu revision. Info changes invalidate the cached body and advance the visual revision. | The presenter paints later. Unchanged strings return before any of these changes. |
| `WF_EXEC_FOCUS`, `WF_EXEC_PRESERVE` | Sets focus-notice or exposure policy. Enabling focus notices posts the current focus fact. | Event publication uses the existing registration and its retained delivery record. |
| `WF_EXEC_DESKTOP` | Marks a borderless window as the unique desktop layer and orders it to the back. | Later focus and hit lookup use this identity. |
| `WF_TOP` | Requires a shown layer, restores normal bounds for a tile, raises within chrome ordering, focuses and updates the published window state. | Focus can touch caret pixels, widget capture, keyboard routes and mouse snapshots. |
| `WF_CXYWH` | Validates bounds and console constraints. Iconified windows change normal bounds. Ordinary resize or move updates geometry, visibility, damage and the published view. | An equal-size move with no UPDATE owner can try `DESKMOVE.Application`. This path hides caret/outline, may hold a Layers token and retained request across a screen copy, and commits new geometry on successful completion. Refusal takes the damage/redraw path. Console moves also rebase presentation. |
| `WF_VSLIDE`, `WF_VSLSIZE` | Validates frame support and range, changes the view and derived slider, invalidates the scrollbar strip and invalidates the cached body. | The presenter paints later. An unchanged value returns immediately. |
| Client exit | Retires registration/menu state, then closes and destroys each owned window and synchronizes the directory. | Waits for endpoint holds, readiness and route retirement. `DESKMOVE.Forget` releases the retained reply identity only after the scene settles. Menu storage, endpoint and Task lease have their own retirement. |

The effect boundaries for GF2 include `DESKCORE.Focus`, `RestoreFocus`,
`Iconify` and `RestoreIcon`, which the native desktop also calls. The copied
move keeps old geometry while `DESKMOVE` retains the token, source window and
request. `DESKMOVE.Pump` finishes the transaction after bitmap completion and
publishes copied geometry only on success. Route preparation and retirement
use the existing keyboard lease. The close drain calls the presenter's
`CONSOLEINPUT.Pump`, including its shared capture record and delivery path.
[Native desktop policy](../../lib/desktop/deskcore.act) ·
[Move continuation](../../lib/desktop/deskmove.act) ·
[Console attachment](https://github.com/mkur/exec816/blob/39e93a28/lib/desktop/desk-owned-console.inc) ·
[Keyboard routes](../../lib/input/input.act) ·
[Input drain](../../lib/console/consoleinput.act)

### Scene access and scratch

The console worker reclaims `AESGATE` before each turn. It offers admission for
caller UPDATE after its last readiness check. `AESLOCAL.Call` claims that
handoff and shares `AESLOCKS` and `AESWINDOWSTATE` with RPC. BEGIN touches
Layers and cache identities and publishes views. END consumes the caller's
invalidation and paint journal synchronously, updates pixel readiness and marks
cache candidates. C-side `wind_get` uses the published view and directory.
[Worker](../../lib/console/consoledriver.act) ·
[Current gate](../../lib/aes/aesgate.act) ·
[View publication and UPDATE](../../lib/aes/aeswindowstate.act) ·
[C binding](../../c/calypsi/aes-windows.c)

| Current path | Scene access to account for when changing serialization |
| --- | --- |
| Service lifetime and controls | `DESKBOOT` binds and allocates the scene before worker startup. `DESKHOST`, `DESKCORE`, `DESKSTATE`, `AESHOST`, `AESCORE`, `AESWINDOW`, `AESLOCKS` and `AESWINDOWSTATE` use scene state for admission, control dispatch, settlement, wake decisions, publication and teardown. The native Shell and preview submit controls to the worker. |
| Input and gestures | `DESKINPUT`, `DESKDRAG`, `AESMOUSE`, `DESKAPPMENU`, `DESKMENU`, `DESKTABS` and `DESKWIDGETINPUT` read or change hit geometry, focus, chrome, widget state or gesture continuation. `DESKEVENTS` publishes native events and records loss. Input capture uses route tags and rings across interrupt entry. |
| Frame, menu and cache work | `DESKPAINT`, `DESKWIDGETS`, `DESKHOST`, `DESKCACHE`, `DESKMENUCACHE` and `DESKMOVE` read layer damage, visibility and identities, start and finish Layers transactions, and schedule or retire display work. `DESKMENUPAINT` consumes a prepared layer strip. Runnable and cache-candidate queries read the scene even when no transfer starts. |
| Console rendering and lifetime | `DESKCONSOLE` binds or releases presentations. `CONSOLEDISPLAY`, `CONSOLEBITMAP` and the console desktop drawing hooks use the selected scene layer for damage, text, scroll/copy admission and retirement. Caller-side `CONSOLE.Destroy` scans the window table for an attachment before freeing a unit. That scan and the console registry's selected-unit lookup also need an ownership audit. |

`LAYERS` uses its scene-owned `work` region and active transaction fields.
The active token preserves logical ownership of dependent geometry during a
physical transfer. Module storage also retains cache candidates, menu
save/restore, move and paint continuations, selected console and the shared
bitmap packet. Renderer GSX state, command buffers, mapped VRAM scratch and
their fences belong to physical display ownership. These are separate from the
compiler's Task-local scratch. [Layers layout](../../lib/display/layertypes.act) ·
[Bitmap binding](../../lib/console/consolebitmap.act) ·
[Renderer storage](../../ports/gem4xe/adapter/README.md)

The native helpers use stack locals and the running Task's direct page.
Action! call-clobbered scratch is D-relative `$80–$BF`. `A816MEMORY`'s pinned
runtime `Clear` and `Move` use the native ABI with no shared writable scratch.
The existing C UPDATE bridge stages its argument in Task DP `$80–$83` and
builds its aligned native argument frame on that Task's stack. Its global
entry address is bound at startup. The C context and request belong to the
registered caller. A future caller entry still needs scene admission and a
bridge check for its own call signature and transitive effects.
[Native DP contract](../reference/platform.md#compiler-and-memory-contract) ·
[UPDATE bridge](../../c/calypsi/aes-local.s) ·
[C context and UPDATE](../../c/calypsi/aes.c)

### Development checks

The optimized `windows` runs match the independent 10,952-pixel visibility
oracle, physical window events and outline pixels. The optimized `cache` runs
match all 32 checkpoint records and all 14 captured scanouts byte for byte.
The `windows` assertion count includes the loop that drains redraw messages
while waiting for each control event.

The original `multiwindow` fixture fails on the parent and candidate at check
25. It expects the pre-existing frame insets that produced `(104,80,184,96)`.
The current 11-pixel top and 2-pixel bottom insets produce `(104,75,184,107)`.
The fixture uses the current coordinates for the front window's unobscured work
area. Both corrected runs pass all 67 C checks. All six passing runs return
through the OS boundary with intact guards and zero live worker Tasks. The
original failed runs are retained alongside the corrected runs.

In the matched optimized `windows` image, `AESWINDOW` grows from 14,652 to
14,874 emitted code bytes within the same code banks. The refactor adds zero
upper-RAM data bytes, VRAM bytes, Tasks or signals. The reserved bank-zero
delta is **0 fixed, 0 root/kernel, 0 per public Task and 0 idle bytes**, including
guards, alignment and spare capacity. These focused AES fixtures use eight
public slots. The production twelve-slot map is the one measured in GF0.

Run the three optimized fixtures with `tools/test_aes_server.py --mode opt`,
selecting `--suite windows`, `--suite multiwindow` or `--suite cache` and a
separate `--output` directory for each. The host suite reports 683 passes and
four skips. [GF1 execution record](../development/gem-first-gf1.json)

## GF2 — Window effects and scene commits

GF2 passes at the development tier through the existing presenter transport.
Copied moves now retain their Layers token, window and reply storage before
submission. The physical copy consumes the reservation's frozen source and
target. Completion retires that reservation before publishing geometry and
replying. Both submission failure and quiescent completion failure use the
same retirement path, preserve old bounds and invalidate dependent paint state.
A reset-required failure retains the operation storage. Unsupported copies
continue through ordinary damage/redraw.

Focus changes prepare the outgoing caret before committing focus, frame damage,
capture routing and notices. Native top/restore, hide, close and gesture callers
use the same phases. Open owns a local input-route tag until admission succeeds;
epoch exhaustion retires that unpublished tag. Close hides the window and
retires its epoch before draining captured input, retaining the old route tag
until retirement completes. Console attachment prepares the retained
presentation before publishing its unit; release restores the caret before
withdrawing that presentation. These boundaries prepare GF3's scene-gate work;
GF2 retains the presenter's existing serialization.
[Move continuation](../../lib/desktop/deskmove.act) ·
[Window policy](../../lib/aes/aeswindow.act) ·
[Focus policy](../../lib/desktop/deskcore.act) ·
[Console attachment](https://github.com/mkur/exec816/blob/39e93a28/lib/desktop/desk-owned-console.inc)

### Development checks

The optimized `windows`, `multiwindow`, `cache` and `keyboard` fixtures pass
285, 67, 224 and 111 C checks respectively, including physical move/resize/top,
iconify/restore, copy refusal, visibility, redraw and keyboard routing. Cache
checks cover all 32 checkpoint records. The application-owned console fixture
passes two FastBasic cycles with root mode/cells preserved and all eight pixel
checkpoints matching.

The focused effect fixture forces preemption before copy submission and before
commit. A headless peer progresses during each four-frame pause while the
Layers token, window and request remain retained and both layer and caller
views retain old bounds. It also forces failed open admission and checks exact
route rollback, then observes close hidden with epoch zero and its retirement
tag still retained. Success passes 29 C checks. Quiescent watchdog failure
passes 24 checks, preserves old bounds and cleans up. The nonquiescent case
passes 17 checks before the expected `FF93` reset park, retaining three live
Tasks and the operation storage. Every case submits one move copy and keeps
stack/domain guards intact.

The native desktop fixture passes 376 checks and its expected held-removal
fault case. Both console-bind runs pass 109 checks and nine raster checkpoints;
the combined case also checks iconified pixels and stale completion. The bind
fixture now compares the committed `ShellUnit()`, since `ConsoleUnit()` selects
the transient rendering target. Its earlier checkpoint-4 failures and the
diagnostic snapshot remain under the development output directory. The desktop
runner uses the pinned release compiler after the debug compiler exceeded its
600-second build timeout. GUI/inbox synthetic producers use `AESGUI.Open`'s
commit-only procedure contract; those optimized fixtures pass 102 and 254 C
checks. All returning cases have intact guards and zero live worker Tasks;
the held-removal and reset-park cases retain their expected Tasks. The host
suite passes 683 tests with four historical-source skips.

The matched optimized `windows` image adds 1,468 native code bytes within the
same 17 code banks, with zero added native data, zero-fill or VRAM. It adds no
Tasks or signals. The reserved bank-zero delta is **0 fixed, 0 root, 0 kernel,
0 per public Task and 0 idle bytes**, including guards, alignment and unused
reserved capacity. These fixtures use eight public slots; GF0 retains the
production twelve-slot inventory. Build-specific sizes, hashes, final GUI/inbox
results and host checks are in the [GF2 execution record](../development/gem-first-gf2.json).

Reproduce the selected AES cases with `tools/test_aes_server.py --mode opt` and
`--suite windows`, `multiwindow`, `cache`, `keyboard`, `gui` or `inbox`.
Run `tools/test_aes_window_effects.py --variant 0`, `--variant 3` and
`--variant 4` for isolated success, quiescent failure and reset park; reuse the
same emitted image with `--reuse`. Also run `tools/test_console_window.py`,
`tools/test_desktop.py` and `tools/test_desktop_console_bind.py`, the latter
once with defaults and once with `--iconified --stale-completion`. Each runner
requires a separate `--output` directory. This is development evidence; it
does not qualify the hosted system or establish new latency results.

## GF3 — Scene ownership

GF3 passes at the development tier. Its complete record follows the historical
admission step below.

### Initial admission step

The first step made presenter admission nonblocking.
`AESGATE.TryOwner` closes the handoff on success, or publishes the presenter's
wake obligation and returns failure while the caller retains ownership. Both
decisions use a short `Forbid` section. The console worker retries and waits at
the turn boundary, before any scene access or readiness query. No gate helper
sleeps. The existing caller UPDATE path still uses the same claim/release
protocol; there is no new bridge or record layout.

The focused optimized fixture passes 46 checks. It holds caller ownership
across three natural VBI ticks, proves peer progress while the presenter sleeps,
and preserves an unrelated pending input bit. It also forces release after
failed admission but before the gate wait, two coalesced release hints, and
release before any waiter is published. Successful retries close the gate,
clear the wake obligation and preserve nested `Forbid` state. The initial
fixture failed because it compared an unsigned nesting byte with `-1`; the
correct stored value is `$ff`. That failed build/log is retained.

The optimized lock and cache fixtures pass 181 and 224 checks. All 32 cache
checkpoint records and 14 captured scanouts match GF2 exactly. All three
returning fixtures have intact guards and zero live worker Tasks. Host checks
pass 683 tests with four historical-source skips. Emitted-image hashes,
results and resource comparison are in the
[admission execution record](../development/gem-first-gf3-admission.json).
The matched cache image adds nine native code bytes within the same code banks,
with zero added data, zero-fill, VRAM, Tasks or signals.
The reserved bank-zero delta is **0 fixed, 0 root, 0 kernel, 0 per public Task
and 0 idle bytes**, including guards, alignment and unused capacity. The
fixtures retain their existing eight public slots and private idle pool.

Reproduce with `tools/test_aes_gate.py --output DIR` and
`tools/test_aes_server.py --mode opt --suite locks --output DIR`, then the same
AES runner with `--suite cache` in another directory. This is development
evidence for the admission boundary as it existed at that commit. The worker
still waited for scene admission before servicing input/events in that
preparatory step. The following completion supersedes that implementation.


### Complete scene, input and physical partition

`AESGATE` now serializes library scene metadata independently of rendering
readiness. Caller admission publishes a stack-local waiter under a short
`Forbid`, sleeps on an already owned signal, and rechecks the gate after every
wake. Publication and release use the same guard, so early or coalesced signals
cannot lose the wake obligation. The system side tries admission and runs only
independent work before waiting. Metadata lookups and mutation remain
preemptible; queued logical UPDATE/MCTRL requests retain the existing eligible
FIFO and owner-upgrade rules. Local TRY also wakes newly eligible older work.

Bitmap calls, widget callbacks, display delegation and route creation/retirement
release scene ownership. The continuation stays on the presenter's existing
guarded native stack. A separate effect count excludes conflicting new UPDATE
acquisitions until that continuation resumes. Layers tokens remain logical
reservations through physical completion, quiescent failure and reset-required
parking. Physical polling can retire DMA without reading scene/cache state;
scene retirement and coherent view publication wait for admission. No callback,
external wait or physical drawing admission retains the scene gate.

`AESSNAPSHOT` publishes copied routing geometry, window/route epochs, focus,
menu/MCTRL state and held input endpoints. It retains no scene or C view pointer.
Geometry/focus/lifetime keys avoid rebuilding unchanged snapshots at every paint
boundary. Endpoint holds cover readers and publication withdrawal through exit.
C selected-view stores/withdrawal use short guards before view memory can be
freed. Caller lock changes refresh eligibility synchronously with a bounded
per-inbox guard, preventing an older sample from overwriting newer capture.

The deferred presenter drains captured keyboard/pointer events through those
snapshots and retires physical fences. It retains native keys/gestures for
interpretation under scene ownership; queue loss cancels the old native stream
before callbacks can capture a new one. Captured event scratch lives on each
call's stack because independent input can run while a native callback is
paused. Message and timer delivery use the existing independent protocols.
Only actual fresh capture is rearmed; retained native work cannot cause a busy
retry loop while another Task owns the scene.
Cursor presentation consumes its old dirty hint before the physical call and
rearms an arrival captured during that call's deferred continuation. A failed
admission alone does not generate another wake. This preserves the latest
position without requiring another mouse edge after scene release.

The [complete GF3 execution record](../development/gem-first-gf3.json) contains
pinned inputs, selected development checks, failures and resource measurements.
These checks do not qualify the hosted system, change the open latency gates,
or implement GF4's caller-side window creation/deletion.

The raw and optimized native gate probes each pass 49 checks, including the
complete 32-bit deferred callback argument, early/coalesced wakes, actual
sleeping Tasks and unrelated signal preservation. The final preemption fixture
passes 37, 33 and 30 checks. Keyboard, button, message and timer bits all arrive
while a caller owns the scene; a second caller and the presenter both sleep.
The physical case retires DMA while preserving its Layers token and the old
published geometry. A third case pauses a completed cursor call, captures
new movement during caller ownership, and requires a physical cursor redraw
after release without another input. Instrumented scene/cache/readiness and
physical-call boundaries enforce ownership through emitted code. The minimum measured margin
above the interrupt floor is 232 bytes in these cases.

Selected broader checks pass: locks 181, windows 285, cache 224, pointer 168,
keyboard 111, input events 713, multiwindow 67, menus 321, native desktop 376
and console attachment 109. The final pointer run includes 25 wake/drain and
retained-key checks: the original 21 boundaries plus copied deferred keys,
runnable work without another hardware edge, overflow and loss retirement.
All 32 cache checkpoints and 14 scanouts match GF2 exactly. The owned-console
fixture completes eight pixel/lifetime cases and 20 C/native ABI checks. The
record distinguishes earlier broad regressions from the final focused reruns.
Host checks pass 683 tests with four historical-source skips.

The production twelve-slot disk/GUI cohort passes 31 checks. Both loaded
Counters continue painting through four 16 KiB read/write/Close passes, with
exact saved bytes and an independent filesystem allocation audit. Guards and
ownership retire normally; its minimum measured interrupt-floor margin is
192 bytes. This is a selected functional cohort, with no CPU timing or full
GF0 matrix refresh claim.

The matched optimized cache image adds 14,991 native code bytes, 2,714 data
bytes and 2,713 zero-fill bytes, within the same native code banks. The two
routing publications occupy 610 bytes each; the 64-slot native key queue uses
1,536 bytes. The private AES service grows from 1,976 to 1,982 bytes, an eight-byte
increase after heap chunk rounding. A contended caller retains a 12-byte waiter
inside its existing native stack; no separate waiter allocation is required.
No Task or fixed signal is added. Console destruction temporarily allocates one
caller-owned signal while its existing presentation lock serializes retirement.

The reserved bank-zero delta is **0 fixed, 0 root, 0 kernel, 0 per public Task
and 0 idle bytes**, including guards, alignment and unused capacity. Matched
runtime/phase reservations and Task pools are unchanged. Composed demo upper
static arenas grow by 3 KiB within the already owned upper kernel bank; no
additional bank is reserved for those arenas. The GEM demo uses 11,385 of
12,288 bytes. Its OF816 package retains the ROM, combined writable system disk,
licenses and checksums; development manifests and intermediates stay outside
the ZIP. Package/workflow results and their exact source stage are recorded
separately from the final focused fixtures.

Reproduce the ownership cases with `tools/test_aes_scene.py --output DIR`, and
use `tools/test_aes_gate.py --mode raw --output DIR` then `--mode opt` in separate
directories for the native callback probe. The AES runner selects `locks`,
`cache` and `pointer` for ordering, journals/pixels and input handback/loss.
GF4 remains the next slice.

## GF4 — Caller hidden-window lifecycle

GF4 passes at the development tier. The first creation step is retained below;
the following completion adds ordinary hidden deletion.

### Caller creation

The first executable step routes hidden `wind_create` through the shared
`AESWINDOW.Lifecycle` decoder and GF1 helper under the GF3 scene gate. Its
caller frame avoids the remaining dispatcher's frame/string/effect scratch.
The C binding allocates view storage before admission and frees rejected storage
after scene release. Eligible calls leave both transport sequence counters
unchanged. Deferred calls apply no window mutation before sending the same
packet through RPC. Ordinary and parameter-block entries use this one path.

The former UPDATE-only bridge is now the single private caller bridge,
`ExecAESLocalEntry`/`_AESLocalCall`. UPDATE keeps its policy and MCTRL remains
RPC. There is no new public C entry or wire layout; rebuilt resident images
install the matching private entry. Native/C observation tools use its current
name too.

Window requests respect older lock waiters and unadmitted messages, while an
existing logical owner can finish dependent mutations. Each pending window
records the prefix of the lock queue that preceded it. Grants remove that
predecessor from every affected prefix. Those older locks can pass the window
barrier; newer locks wait behind it. This avoids a cycle where the window waits
for an old UPDATE while its own pending flag prevents that UPDATE from running.
The count uses one existing padding byte per private client record: client and
service sizes remain 136 and 1,982 bytes.

The optimized lifecycle fixture passes 149 checks. It covers two clients filling
all six slots, ordinary/PB creation, bounded allocation/admission failures,
slot reuse with new identities, sibling preservation, queued owner recursion,
an older lock followed by a window request, an older unadmitted message, mixed
transport numbering and identity exhaustion. Caller checks also require view
allocation/free outside scene ownership. It observes 12 caller create attempts,
three RPC creates and 12 RPC deletes; hidden deletion is still unmigrated in
this step. Both clients exit with restored heap and intact guards. The peer uses
its existing 1,312-byte pool with 540 bytes above the interrupt floor.

Raw and optimized bridge probes pass both stack parities across natural VBI.
The lock and window regressions pass 181 and 285 checks. Host results and exact
artifacts are in the [creation record](../development/gem-first-gf4-create.json).
The first fixture needed a completion wake when clearing its private readiness
fault and an aligned synthetic message; those failures remain in development
outputs. Reserved bank-zero growth is **0 fixed, 0 root, 0 kernel, 0 per public
Task and 0 idle bytes**, including guards, alignment and unused capacity. No
Task, signal, heap reservation or upper static arena is added. This is
incremental development evidence; GF4 is not complete at this step.

### Complete caller hidden-window lifetime

Ordinary hidden `wind_delete` now uses the same caller entry and shared
lifecycle decoder as creation. It retires the native association and publishes
siblings under scene ownership, then the binding withdraws its selected view
and frees retired caller storage after release. Both API forms use this path.
A shown-window rejection preserves the live view/epoch; foreign handles cannot
change a sibling client. A readiness miss leaves the existing association and
view untouched until one RPC commit. Console-bound deletion explicitly stays
in the presenter because caret retirement can perform physical work.

The final optimized lifecycle fixture passes 263 checks, including all creation
cases above, direct ordinary/PB deletion, complete catalog retirement, shown and
foreign rejection, ordered/unapplied fallback, and console attachment deletion
through RPC. Every eligible call retains its transport sequence. The three
forced-preemption variants still deliver input/events, retire DMA without scene
commit and redraw a retained cursor position without new input. Their final
continuation assertion now runs after controller shutdown retires the worker;
application exit need not wait for unrelated system cursor work. The earlier
immediate assertion and the fixture's rejected unnormalized fixed-size open
remain in development output.

The selected window, lock, cache and multiwindow regressions pass. All 32 cache
checkpoints and 14 scanouts match GF3 exactly. The copied-move success, quiescent
failure and reset-required cases retain their token/geometry and shutdown rules.
The production twelve-slot idle cohort loads both unchanged Counter bodies;
both keep painting and close normally. Each uses its existing 1,312-byte pool,
peaking at 806 bytes with 250 bytes above the interrupt floor. No new renderer
or I/O qualification is claimed.

The matched cache image adds 1,619 native and 184 C code bytes within the same
code banks. Native/C data and zero-fill sizes, the 23-byte C DP workspace,
private client/service sizes and upper static arena are unchanged. The reserved
bank-zero delta is **0 fixed, 0 root, 0 kernel, 0 per public Task and 0 idle
bytes**, including guards, alignment and unused capacity. No Task, signal or
heap reservation is added. Exact pins, source/artifact hashes, execution stages,
stack results and failures are in the [GF4 record](../development/gem-first-gf4.json).
GF5's bounded frame attributes remain next; hosted-system and latency
qualification remain open.

## GF5 — Caller frame attributes

GF5 passes at the development tier. The title/info step below is followed by
completion of the supported slider setters.

### Title and info

The first GF5 step extracts `AESWINDOW.Frame` for both RPC and the caller entry,
with the same eligibility rule as hidden lifecycle operations. Title/info run
in the caller; the shared helper also retains slider policy behind RPC for the
next step. Geometry, top, open/close and extension setters retain their existing
transport. The helper reports actual metadata changes so unchanged strings do
not request a frame wake. Copy bounds, menu rename, cache invalidation, damage
and publication stay in one implementation; no physical drawing enters the
scene gate.

The focused fixture compares 34 ordinary/PB checkpoints with a GF4 parent,
including hidden/covered windows, two owners, maximum/copied/rejected strings,
slider values and unsupported fields. Functional calls hold UPDATE to establish
that pixels remain unchanged until release. Separate unheld setters measure
complete call brackets and observed deferred pixel feedback. An injected
readiness miss must leave publication untouched until its single RPC retry.
The controller drains final background repair under scene ownership before
stopping its worker; detaching its default native pane at setup otherwise
skips that normal shutdown drain. Earlier unsuccessful fixtures are retained.

The [title/info record](../development/gem-first-gf5-text.json) records exact
scope, pins, artifact/source hashes, results and reserved memory. GF5 remains
open at this step; supported slider setters are next.

This step passes 185 frame checks and all 34 parent state/frame/menu pixel
checkpoints, plus 265 lifecycle, 181 lock and 224 cache checks. The lifecycle
fixture now expects a local title setter and separately checks an unmigrated
preservation setter. All 32 cache records and 14 scanouts still match GF4.
Host checks run 687 tests: 683 pass and four skip. The matched cache image adds
1,302 native and five C code bytes; data and zero-fill sizes are unchanged.
Reserved bank-zero growth is **0 fixed, 0 root, 0 kernel, 0 per public Task and
0 idle bytes**, including guards, alignment and unused capacity.

### Complete bounded frame setters

`WF_VSLIDE` and `WF_VSLSIZE` now share the caller entry with `WF_NAME` and
`WF_INFO`. RPC uses the same `AESWINDOW.Frame` policy. Supported values commit
under the scene gate; changed fields schedule later frame work after release.
Unchanged values preserve publication and cache behavior. Geometry/top,
open/close and extension setters retain their established transport. Public C
signatures and wire version 19 are unchanged.

The complete optimized fixture passes 185 checks. All 34 view/native-state,
frame-pixel and renamed-menu checkpoints match the GF4 parent. Thirty functional
UPDATE-held checkpoints retain their old pixels until release. All 33 eligible
bounded setters, including rejected values, avoid request/reply exchanges;
the unsupported test field remains RPC. Two application owners, hidden/covered
windows, ordinary/PB bindings, copied and rejected strings, slider bounds and
readiness fallback retain their expected state and retirement behavior.

Separate unheld observations include the full C call and deferred physical
feedback, sampled once per PAL frame. These are inclusive measurements with
debugger/sampling overhead, not percentile estimates:

| Setter | GF4 call / feedback upper bound (ms) | GF5 call / feedback upper bound (ms) |
| --- | ---: | ---: |
| Title | 16.658 / 99.899 | 16.225 / 99.734 |
| Info | 16.996 / 59.796 | 16.897 / 59.983 |
| Slider position | 16.436 / 99.804 | 16.746 / 99.936 |
| Slider size | 16.898 / 99.926 | 16.755 / 99.896 |

The selected regressions pass: 284 window checks in the final image, 224 cache
checks, and the earlier 181 lock and 265 lifecycle checks from the shared-helper
step. All 32 cache records and 14 scanouts match GF4. The affected GF0 idle
cohort loads both unchanged Counter bodies on the production twelve-slot map;
both keep painting and close normally. Their existing 1,312-byte pools peak at
806 bytes, leaving 250 bytes above the protected floor. The host suite runs 687
tests: 683 pass and four historical checks skip. The existing focused GF4
raw/optimized bridge probe remains applicable to the unchanged entry ABI.

The matched cache image adds 1,318 native and five C code bytes within the same
code banks. Native/C data and zero-fill, the 23-byte C DP workspace, private
client/service payloads and upper static capacity are unchanged. Reserved
bank-zero growth is **0 fixed, 0 root, 0 kernel, 0 per public Task and 0 idle
bytes**, including guards, alignment and unused capacity. No production Task,
signal or heap reservation is added. The fixture controller borrows one signal
for scene-protected final background retirement and frees it before shutdown.

The [complete GF5 record](../development/gem-first-gf5.json) retains pins,
source/artifact hashes, actual execution stages, resource comparisons, stack
results and unsuccessful fixture attempts. Frame/cache native rebuilds reuse
the unchanged matching C images from the text step; window and loaded Counter
fixtures build their C inputs afresh. This is development evidence; hosted,
hardware and latency qualification remain open. GF6 is next.

## GF6 — Caller geometry and lookup

### Coherent lookup

The first step shares `AESWINDOW.Query` between caller and RPC, using the same
committed layer-stack lookup. Ordinary/PB `wind_find` acquires only the scene
gate; it does not wait for physical readiness, older mutations or another
client's UPDATE. Registration errors, foreign/border hits and hidden/native/
background/menu occlusion remain unchanged. Selection, visible-rectangle
iteration and transport sequence are preserved.

The optimized two-owner fixture passes 84 checks and all 20 parent state
checkpoints. Eleven query calls execute in the caller without RPC, including
queries while a peer holds UPDATE and mutation readiness is deliberately
unavailable. The remaining geometry/top calls still use RPC in this step.
Host checks run 687 tests: 683 pass and four skip. The matched fixture adds
246 native and 93 C code bytes, with unchanged data and zero-fill. Reserved
bank-zero growth is **0 fixed, 0 root, 0 kernel, 0 per public Task and 0 idle
bytes**, including guards, alignment and unused capacity. No Task, signal or
upper static capacity is added.

The [query record](../development/gem-first-gf6-query.json) preserves exact
pins, source/artifact hashes, state comparison and stack observations. GF6's
geometry/top and integration acceptance remain open at this step.

### Geometry/top and integration completion

GF6 passes at the development tier. `AESWINDOW.Geometry` now shares bounds/top
policy between caller and RPC. Owner mutations within UPDATE, resizes,
hidden/iconified bounds, no-ops and effect-free focus/top can commit in the
caller. Older queued work and peer exclusion retain their existing ordering.
Copy-eligible unheld moves decline before mutation; the presenter retains copy
identity, frozen pixels and its completion/failure continuation. Console
geometry, outgoing caret restoration and retained-widget cancellation also
retain system admission. Frame drawing and interactive gestures remain system
work. The public wire ABI and private entry signature are unchanged.

The optimized development checks pass:

- Geometry: 84 C checks, four native checks and all 20 parent state checkpoints.
  All eleven marked queries and nine marked bounds/top calls execute directly.
  Readiness fallback remains unapplied and uses one RPC on the separate tail.
- Windows: 285 checks; locks: 181; lifecycle: 265. Cache: 224 checks, with all
  32 cache checkpoints and fourteen scanouts identical to GF5.
- Copied-move effects: 30/25/18 checks across success, injected stop and reset.
  A registered peer queries old committed geometry during preparation and
  precommit while the physical token remains reserved. Reset deliberately
  retains live resources at `$FF93`; it is not a normal-cleanup claim.
- Scene/preemption: 37/33/30 checks cover caller/presenter contention, input/event
  delivery and fence retirement without acquiring the scene.
- GF0 disk cohort: 31 checks, four complete 16 KiB read/write/Close cycles and
  persisted-byte/allocation audit. Both Counters advance six counts and six
  paints during disk work. The other GF0 cohorts were not rerun.
- Host: 689 tests, 685 pass and four skip, including five fixed-image placement
  checks. The small raw/optimized bridge evidence remains applicable because
  neither entry ABI nor record layout changed.

The frozen geometry fixture records inclusive parent/candidate call observations.
For example, lookup with a peer owning UPDATE changes from 78.81 to 3.77 ms;
move from 36.08 to 49.44 ms, resize from 38.49 to 52.50 ms and top from 61.01 to
64.14 ms. These include scheduling and gate waits; they are individual
observations, not a general geometry speedup or percentile qualification.

The matched cache fixture adds 2,589 native and 93 C code bytes versus GF5,
with unchanged data and zero-fill. It adds no Task, signal, client/service
record, static arena or heap reservation. Reserved bank-zero growth is
**0 fixed, 0 root, 0 kernel, 0 per public Task and 0 idle bytes**, including
guards, alignment and unused capacity. The eight- and twelve-slot reservation
maps match their parents. The geometry fixture leaves 523 bytes above the floor
in its tightest active worker; the loaded disk Counters leave 244/246 bytes.
All ordinary-return checks preserve guards, retire Tasks and restore the OS.

The demo build exposed native code growing into SDX's fixed bank `$28`.
Placement now clears both fixed C and SDX banks, starting native code at
`$290000` in this enabled profile. Lower unclaimed banks remain heap eligible;
no reservation grows. The enabled SDX profile already reserves 544 fixed
bank-zero bytes, separately from GF6's zero delta. A missing EDX input was
recovered from the exact pinned local archive without relaxing any hash.
Failed build/download logs remain in the development record.

The current `build_demo.py` package includes OF816, the combined writable SYS
ATR, matching ROM, MD5/ARC/EDX and notices. Cold ATR boot observes exactly
250 PAL countdown frames, intact reader guards and restored firmware context.
The original drag observer still expected window-scoped BEGIN, retired by
Counter's conventional GEM redraw change in `64d2719a`; the pending request
correctly contains ordinary BEGIN. Its old hard-coded Shell title click also
misses the current window position; cleanup now selects Shell through the
physical Windows menu and verifies focus. With those observer corrections, the
regression replays this boot's native-entry snapshot and independently verifies
all expanded native image bytes. Failed/interrupted runs and the snapshot are
retained.

Physical Files/Counter drags preserve motion and XOR outline pixels while
UPDATE waits. Release commits accepted geometry and exact Counter digits;
Escape preserves geometry and erases the border while the button remains held.
Cross-application pending UPDATE, stationary presenter sleep and normal shutdown
also pass. One-frame sampling gives release-to-digit upper bounds of 481.50 ms
after movement and 80.33 ms after Escape, with 312/304 independently checked
digit pixels. Escape's restored border is observed at 220.53 ms after the
existing eleven-frame key settling sequence. These are sampled upper bounds,
not percentile latency qualification. Shutdown retires all Tasks, preserves
stack/domain guards and restores the OS.

The [complete record](../development/gem-first-gf6.json) retains pins,
source/artifact hashes, comparisons, stack observations, intermediate failures
and package evidence. This is development evidence only; hosted-system,
hardware and latency qualification remain open. GF7 is next.

## GF7 — Window open/close and route lifetime

GF7 passes at the development tier. The three slices below retain route
extraction, caller open, and caller close/exit integration evidence.

### Shared route resources

The first GF7 step extracts `AESROUTES.Prepare` and `AESROUTES.Retire` from
`AESWINDOW`. Preparation owns an unpublished keyboard tag and rolls it back
when no fresh GUI epoch remains. Retirement pumps input with scene ownership
suspended, retains the hidden window's tag on a busy result and clears it only
after successful retirement. `AESWINDOW.CommitOpen` and the existing
`CommitClose` keep geometry, open epochs, focus and GUI publication together.
Ordinary open/close still use RPC. Exit reaches the same close and retirement
helpers before destroying a window; no second cleanup policy is introduced.

Optimized emitted-code development checks pass:

- Windows: 285 C checks and four native checks, including repeated close/reopen,
  full sixteen-record application queues, obsolete GUI notification withdrawal,
  exit with an open window, physical capture/focus and deferred mutations.
  Geometry/visibility, iconification, gadgets and physical-request observations
  match the frozen GF6 fixture.
- Effects: 30/25/18 C checks across success, injected quiescent stop and reset.
  Open-epoch failure leaves input tags unchanged and publishes no window route.
  At close, a peer queries a point inside the old bounds while the withdrawn
  window retains its tag; lookup completes and returns no GEM window before
  input draining resumes. Normal cases retire all Tasks with intact guards and
  restored OS state. Reset deliberately retains live resources at `$FF93`.
- Host: 689 tests run, 685 pass and four skip. Python syntax, source/artifact
  hashes and local documentation links are checked before commit.

The matched window fixture adds 599 native code bytes, with unchanged C code,
data and zero-fill. Client/service payloads remain 136/1,982 bytes. No Task,
signal, static arena or heap reservation is added. Reserved bank-zero growth is
**0 fixed, 0 root, 0 kernel, 0 per public Task and 0 idle bytes**, including
guards, alignment and unused capacity. Reservation maps match GF6. Observed
remaining stack space above the checked floor is 653 bytes for root, 1,374 for
the presenter, 993 for kernel and 139 for idle.

The [route record](../development/gem-first-gf7-routes.json) retains exact pins,
source/artifact hashes, comparisons, stack observations and execution scope.
This is development evidence for the extraction. No demo refresh, disk cohort
or full qualification matrix was run. The wire/private entry ABIs are unchanged;
the existing focused raw/optimized bridge evidence remains applicable. Caller
open and caller close/exit admission remain the next GF7 steps; hosted-system,
hardware and latency qualification remain open.


### Caller open

The caller-open step passes its development checks. `AESGATE.Leave`/`Reenter`
retain the continuation kind on the native stack and reacquire the scene using
the admitted request's Task and reply signal. The presenter keeps its existing
physical-effect protocol. Route preparation and unpublished-route rollback use
ordinary input APIs outside scene ownership. Caller re-admission checks older
work, logical ownership and focus readiness before the shared open commit.
Console-bound windows and physical caret/widget effects fall back before
mutation. Ordinary and parameter-block opens use the same path.

The optimized visibility fixture passes 168 C checks and fourteen checkpoints:
fresh/unchanged epochs, shown-window and bounds errors, actual route-slot
exhaustion, epoch rollback, a peer taking UPDATE during preparation, late
admission fallback, and full application queues with close/reopen/exit.
Normal transport observations run within owner UPDATE scopes; the ownership
and readiness races deliberately run without that scope. The six eligible
marked opens complete without RPC; the three deferred opens use one RPC each.
The frame/fence settlement barrier lets the controller stop after all physical
work retires. Unsuccessful fixture readiness/import and teardown attempts remain
in the evidence record.

Windows pass 285 checks with matching GF7-route geometry, visibility, gadgets
and physical-request observations. Effects pass 30/25/18 checks, including
retained copied moves and withdrawn-window queries before route drain. The
small gate probe passes 61 checks in both raw and optimized builds; host checks
pass 685 tests with four skipped. The wire/private C entry ABI is unchanged.
Reserved bank-zero growth is **0 fixed, 0 root, 0 kernel, 0 per public Task and
0 idle bytes**, including guards, alignment and unused capacity. No Task,
signal, static arena or private client/service capacity grows.

The [caller-open record](../development/gem-first-gf7-open.json) retains exact
pins, code/data deltas, stack observations, source/artifact hashes and failed
fixture attempts. GF7 close/exit integration remains next. These are development
checks; hosted-system, hardware and latency qualification remain open.


### Caller close and integration completion

Eligible ordinary/PB closes now use the shared visibility policy in the caller.
The scene commit cancels capture, withdraws the open epoch and GUI facts, hides
the layer and publishes replacement focus. Route retirement runs after releasing
the scene. The caller does not consume the presenter's input lease; referenced
input keeps the hidden window/tag for the existing RPC drain continuation.
Exit remains a registration RPC and reuses the same close/retirement helpers.
A failed transport submission cannot authorize view reuse: open/delete report
BUSY until close retry or exit finishes retirement. No extra closing record or
per-Task reservation is introduced.

One bounded Task guard serializes pointer-sample routing with window-capture
cancellation. It includes no drawing or wait; IRQ/NMI capture remains separate.
Published input routes retain endpoints and copied values. A publisher can
therefore outlive a deleted view, while exit waits for the registration's last
publication hold before replying and allowing its storage to be freed.

Development checks pass:

- Visibility: 204 C assertions, five native controller checks and 22 checkpoints.
  Ordinary/PB open/close execute directly when eligible. The earlier fourteen
  result/status/view checkpoints match the caller-open image. An older UPDATE
  waiter remains queued while the existing owner closes; release then admits
  it. Real input-route references force a close continuation. Exhausted RPC
  submission preserves its hidden view/tag; open/delete reject reuse and a
  later direct close retires it. A real reserved message producer is paused
  across view deletion and replacement-window exit; cleanup waits for its hold.
- Windows: 285 checks with matching route-step geometry, visibility, gadgets
  and physical-request observations. Effects: 30/25/18 checks, including
  copied-move failure/reset and withdrawn-window lookup before retirement.
  Reset deliberately retains live resources at `$FF93`.
- Scene: 37/33/30 checks for input/event delivery, fence retirement and pointer
  redraw through caller contention. The pointer oracle now freezes its target
  after button stimuli and the input-only dispatcher settle: a final ST
  quadrature step changes the captured X from 139 to 140. The exact redraw
  assertion retains its original 100-frame bound and sends no further input.
- Locks: 181; lifecycle: 265; pointer/capture: 168; sibling windows: 67; menus:
  321. Cache: 224 checks and fourteen byte-identical GF6 scanouts. All 32 cache
  checkpoints match apart from one fewer cumulative restore at phases 26–32
  after the close/reopen sequence; other fields are identical.
- The production twelve-slot loaded Counter idle cohort passes six checks.
  The two applications advance six/five counts and six/six paints, retain
  247 bytes each above their checked stack floor, and retire cleanly. This run
  does not repeat GF0's disk/blocking/UPDATE-held/cancellation cohorts.
- The unchanged open-slice gate probe retains 61 raw and 61 optimized checks;
  host checks run 689 tests, with 685 passing and four skipped. Documentation
  links, source/artifact hashes and Python syntax pass final checks.

The matched window fixture adds 2,582 native and ten C code bytes versus the
route-extraction image, with unchanged data and zero-fill. That is 3,181 native
and ten C code bytes over GF6 including route extraction. Private client/service
payloads stay at 136/1,982 bytes. There are no new Tasks, signals, static arena
or heap reservations. Reserved bank-zero growth is **0 fixed, 0 root, 0 kernel,
0 per public Task and 0 idle bytes**, including guards, alignment and unused
capacity. Both eight- and twelve-slot reservation maps match their parents.
Window-suite stack margins are 580 bytes for root, 1,352 for the presenter,
993 for kernel and 139 for idle; no guards or checked floors are changed.

The [complete GF7 record](../development/gem-first-gf7.json) retains pins,
source/artifact hashes, comparisons, stack observations and unsuccessful
fixture attempts. Native console attachments and physical caret/widget focus
effects retain system admission; contended admission remains for GF8. No new
demo distribution or full qualification matrix was produced for this slice.
Hosted-system, hardware and latency qualification remain open. GF8 is next.


## GF8: shared admission queue

`AESWAIT` now owns lock insertion/removal, the older-lock prefix retained by
window waiters, window admission/removal and queued-work inspection. Lock and
window dispatch still use their existing execution paths in this first slice.
The change establishes one ordering implementation for the caller-wait slices.

Development checks: 689 host tests (four existing skips) and the optimized
emitted lock fixture. No new fields, Tasks, signals or reservations are added.
Reserved bank-zero delta is **0 fixed, 0 root, 0 kernel, 0 per public Task and
0 idle bytes**, including guards, alignment and unused capacity. Private
client/service payloads remain 136/1,982 bytes. This is not hosted-system
qualification.


### Caller UPDATE/MCTRL waits

A pending lock now publishes its queue record before releasing the scene.
The existing system Task signals the oldest currently eligible caller without
acquiring its lock. That caller rechecks eligibility and commits its own BEGIN;
recursive ownership, TRY, owner upgrades, synchronous snapshots and final END
journals retain their existing policy. The private reply-port signal is reused
as a wake hint, with no message/reply on this path. The busy C context and Task
lease retain the request and registration until completion.

Development checks: optimized emitted locks pass 193 C checks, including six
new assertions that contended acquisitions preserve their RPC sequence and
release C occupancy. The scene gate passes 61 checks each in raw and optimized
builds; 689 host tests pass with four existing skips. One private waiter-mode
byte plus one alignment byte per client changes the upper-heap client/service
payloads to 138/1,990 bytes (eight extra bytes in total). No Tasks or signals are added. Reserved bank-zero delta remains **0 fixed,
0 root, 0 kernel, 0 per public Task and 0 idle bytes**, including guards, alignment
and unused capacity. Window admission migration follows in the next slice.


### Window waits and GF8 completion

Window mutations now publish a scene-protected waiter and release all scene and
physical ownership before waiting on the existing private reply-port signal.
Ordinary metadata resumes in the caller using the retained older-lock prefix.
Input-route draining, copied moves, caret/widget focus and console extensions
retain explicit system continuations. Completion writes the pinned descriptor
and signals its caller; it neither sends that descriptor nor replies to it.
All window/UPDATE/MCTRL RPC admission and binding fallbacks are removed, and the
machine-readable RPC operation list now describes the remaining message calls.

A failed caller waiter must wake the system after removing its barrier too.
The broader window fixture caught a missing wake at 59 checks: deferred painting
remained asleep before the first redraw. The final window image passes all
284 checks with this fixed, including its unchanged physical/pixel assertions.

Development checks pass: visibility 204 (22 checkpoints), lifecycle 265, locks
199, geometry 84, frame 185 and cache 224. The locks fixture injects spurious
private hints plus unrelated signals; hints never grant ownership and the other
signal bits survive. The small queue/layout probe passes 19 raw and 19 optimized
checks; the gate retains 61 in each mode. The twelve-slot loaded Counters pass
ordinary (six), UPDATE-held (six) and disk (31) checks, with orderly cleanup and
persisted disk bytes checked. The other successful cohort images precede the
failure-only wake correction; the final window image exercises that correction.
The [GF8 record](../development/gem-first-gf8.json) records the exact artifacts,
source hashes, reservation comparison and execution scope.

Client/service payloads are 138/1,990 bytes, including one alignment byte beside
each new waiter-mode byte: eight extra upper-heap bytes total. No Task, signal,
arena or heap reservation grows. Reserved bank-zero delta is **0 fixed, 0 root,
0 kernel, 0 per public Task and 0 idle bytes**, counting guards, alignment and
unused capacity. Eight- and twelve-slot reservation checks retain their existing
maps. No full qualification matrix or demo refresh was performed. GF9 follows.


## GF9: extracted AES system loop

`AESSYSTEM` now owns graphical input dispatch, menu/gesture continuation,
frame/pointer work, pending physical completion, scene handoff and the turn's
scheduling decision. Its start/stop hooks retain the existing desktop/AES and
display-drain ordering. The existing resident console worker remains the Task
entry and driver owner. Its stream/model work is behind six private callbacks:
input, controls, bounded model/presentation turn, runnable hint, stop request and
stop state. Each turn releases borrowed console instances before returning to
system input/event work. Text/bitmap backend selection remains before startup.
The retained console presentation adapter stays in place for GF10/GF11.

Readiness and menu-wait probes now observe the system loop. Current profiling
markers follow its collection and scheduling boundaries; the existing worker
entry and resource lifetime remain unchanged. Task-entry discovery explicitly
excludes system/waiter helpers, and a host regression checks that extraction
cannot add another worker.

Development checks pass:

- Windows 284, visibility 204, mixed locks/signals 199, cache 224 and menus 321.
  All fourteen cache scanouts are byte-identical to GF8 and all 32 logical cache
  checkpoints match. Menu pointer/keyboard navigation, deferred replacement
  input, completion waits and exact selection/popup pixels run without stream
  output driving the loop.
- Scene contention passes 37/33/30 checks, including independent input, event
  delivery, fence retirement and pointer redraw while caller metadata is held.
  Move/route effect cases pass 30/25/18 checks. The reset case intentionally
  retains live resources rather than claiming normal cleanup.
- Twelve-slot loaded Counters pass ordinary (six), UPDATE-held (six) and disk
  (31) checks, including persisted output and orderly final-client/service/
  display retirement. The standalone text-backend startup/close probe passes
  with desktop and AES unbound. Host checks run 690 tests, with four existing
  skips. These are development checks, not full hosted-system qualification.

The matched window image adds 2,622 code bytes and 18 zero-fill bytes versus
GF8; the loaded fixture adds 2,700 code and 18 zero-fill bytes. Initialized data
and executable bank sets are unchanged. Six callback pointers occupy those
18 upper-image bytes inside existing production reservations. Private
client/service records remain 138/1,990 bytes. No new Tasks or signals are
allocated. Reserved bank-zero delta is **0 fixed, 0 root, 0 kernel, 0 per public
Task and 0 idle bytes**, including guards, alignment and unused capacity. The
eight- and twelve-slot maps match GF8. Window-case margins above checked floors
are 582 root, 1,367 presenter, 983 kernel and 139 idle bytes.

The standalone text fixture's old 2 KiB image-data allowance already overlapped
code before extraction: a compile-only substitution of the preceding driver
measures 296 initialized and 4,044 zero-fill bytes. GF9 changes zero-fill to
4,062 bytes. The fixture now reserves 4,608 upper-image bytes; production
profiles and all bank-zero reservations are unchanged. The baseline override
and diagnostic-only images are recorded separately from executed tests.

The [GF9 record](../development/gem-first-gf9.json) retains source/artifact hashes,
reservation and footprint comparisons, cache equality and actual execution
scope. No demo distribution or full qualification matrix was generated.
Hardware and latency gates remain open. GF10 is next.


## GF10: console backend and copied views

### View contract and subscription lifetime

The first GF10 slice defines machine-readable pointer-free snapshot/input
records and generates their Action!/C declarations. A snapshot copies at most
64 logical cells, plus unit/revision, geometry, cursor and mode. The private
subscription core retains its consumer Task and owned signal mask. It detects
model, cursor, mode and in-progress edit changes; revisions never wrap within
one subscription. A stale acknowledgement rearms the hint without acknowledging
newer pixels. Source retirement closes existing handles before source storage
can be freed; consumers explicitly unsubscribe and can then bind a fresh unit.
No mutable model/cell pointer is returned through the public record contract.

Raw and optimized probes each pass 103 checks. They check target-emitted C
layouts and C/Action! accesses through a bank boundary, a producer changing the
model between snapshot chunks, stale acknowledgement, cursor-only changes,
busy edits, resize, retirement/rebind and complete heap restoration. A local
name initially shadowed the private record type in `SIZEOF` during unsubscribe;
the heap check caught the short free and now passes. Host checks run 691 tests
with four existing skips. The [view record](../development/gem-first-gf10-view.json)
retains source/artifact hashes and actual scope.

This slice does not switch production stream processing or presentation. It
adds no production Task or signal. Reserved bank-zero growth is **0 fixed,
0 root, 0 kernel, 0 per public Task and 0 idle bytes**, including guards,
alignment and unused capacity. The next slice adds the backend worker and
connects the public facade and temporary snapshot frontend.

## GF10 console backend and copied views

The [backend evidence](../development/gem-first-gf10.json) follows the frozen
[view foundation](../development/gem-first-gf10-view.json). `CONSOLEBACKEND.Worker`
handles bounded stream/model and cooked-input turns. The existing system Task
keeps capture and physical drawing, consuming bounded copied snapshots into
private cells. Accepted output completes while its caller owns UPDATE. No
request or mutable cell pointer enters the view ABI.

Version 2 view packets include foreground route authority. A delayed input or
BREAK cannot target a later scope. Eight copied byte/raw packets backpressure
view producers; separate coalesced loss/cancel slots survive saturation. Captured
routes remain retained until backend delivery/drop. Clear/open/close invalidate
copied input already withdrawn from capture. Snapshot revisions detect mixed
chunks; stale acknowledgements rearm hints. Closed external handles retain their
consumer until explicit unsubscribe and prevent service stop.

The optimized AES check passes 226 assertions including held-UPDATE output,
full input, loss, read cancellation and stale acknowledgements. Both raw and
optimized view probes pass 121 assertions. Console lifetime cases pass 149,
12 and 52 assertions, with injected failure at each of six creation allocations,
closed-handle retirement and exact display restoration to the acquisition
snapshot. The input pump passes ordinary and invalid-lease cases; normal
resident startup/automatic shutdown also pass. A dormant backend originally
counted as an application and prevented resident shutdown; it now registers as
a resident and retires under its parent's explicit stop protocol.

The added small Task consumes 1,600 bytes of the already reserved pool: 1,312
stack, 256 direct page and 32 outer guards. It owns one signal. The system Task
reuses its existing signal for view hints. **Reserved bank-zero delta is zero**
for fixed/root/kernel, every public Task and idle, including guards, alignment
and spare capacity. The matched loaded native image adds 16,281 code bytes,
3 initialized bytes and 850 zero-fill bytes. The temporary mirror adds 206
upper model bytes plus its cell capacity per instance; a subscription payload
is 56 bytes. C applications rebuild for APP ABI 33.

These are focused development checks. They do not qualify the hosted system,
pass the original latency gates or replace the final GF15 package checks. The
current [console](../reference/console.md) and [view contract](../reference/console-views.md)
supersede the [coupled presentation record](console-presentation-before-gf10.md).

## GF11 GEM terminal

The [terminal record](../development/gem-first-gf11.json) covers the production
GEM root, loaded terminal APP and matching development disk. One terminal
Process presents all four console slots through ordinary AES windows, VDI,
UPDATE and visible rectangles. The backend retains stream/model authority;
the application owns copied cells and row damage. The
[glyph slice](../development/gem-first-gf11-glyphs.json) checks all 256 ROM
terminal bytes, mixed GEM text, clipping and odd X through private VDI state.

Console-view version 4 adds a copied directory and coalesced activation hint;
the existing shell protocol now has generated C records. APP ABI 34 exports
four ordinary Exec calls for named-port submission and reply waits. The root
waits for the initial shell's READY while continuing controller work before
starting applications. This avoids simultaneous first RAW/CON endpoint opens.
A missing or lost mandatory terminal closes supervised sessions. Root withdraws
its named port before waiting for frontend retirement, avoiding a parent/reply
wait cycle. Forms temporarily unbind console keyboard routing; cancel and
confirm retain their normal AES input and session authority.

The emitted walkthrough checks shell output, backspace editing, the final
column, covered/exposed exact viewport pixels, a second session, switching,
keyboard cancellation of close, confirmed retirement and final EXIT. Front and
exposure hashes agree. Missing-terminal startup returns with controller failure,
withdrawn port, intact guards and restored ownership. Raw/optimized view probes
each pass 122 assertions; console lifetime/directory cases pass 152, 12 and 52.
The existing input-binding/held-UPDATE check passes 231 assertions. BASIC's
output migration and target layout probes compile; its complete program walk
remains part of later integration.

Normal startup observes eight live Tasks, two AES clients and three windows
(desktop, SYS folder and terminal). A second shell raises the observed Task
peak to nine without adding another terminal window. Terminal slot 5 reserves
1,312 stack bytes; the close/form walkthrough touches 870, preserving the
256-byte interrupt reserve plus 186 untouched bytes. Its private state payload
is 5,846 upper bytes. APP emission and exact source/media hashes are retained
in the record. No VRAM extent is added. **Reserved bank-zero growth is zero**
for fixed/root/kernel, every public Task and idle, including guards, alignment
and unused capacity. The frontend consumes an existing 1,600-byte small slot
(stack, DP and outer guards).

The development builder now supplies the RAM mount needed by its RAM-installed
desktop. Its default upper image arena is 12 KiB, matching the existing production
demo setting. Production skips native console attachment and the temporary GUI
mirror. Legacy preview paths and their native protocol remain for the next GF12
slice. These are development checks; combined final-load/QED/package acceptance
and the existing failed latency gates are not claimed by this slice.

## GF12 unified window records

The [first GF12 slice](../development/gem-first-gf12-records.json) places frame,
AES owner/input association, pending GUI facts and caller-view binding in one
window record. AES keeps six stable pointers into those records as a derived
index. Native IDs, GEM handles and open epochs retain their separate purposes.
Deletion detaches the caller view before clearing the complete record; a sibling
and its view remain untouched. Public AES/C wire layouts are unchanged.

Raw and optimized emitted probes each pass thirteen alias, stride, clearing and
heap-restoration checks. The optimized multiwindow fixture passes 66 C and four
native checks. The production terminal walkthrough preserves its exact viewport
and exposure pixels, session/focus behavior, modal close and normal EXIT. Guards
and ownership restore. Host checks pass 692 tests with four existing skips.

The generated window is 1,022 bytes, scene service 19,544 and AES service 1,264.
Moving metadata adds six live upper bytes overall; eight-byte heap rounding
keeps the combined service reservation unchanged. **Reserved bank-zero delta
is zero** for fixed/root/kernel, every public Task and idle, including guards,
alignment and unused capacity. Native previews and packet dispatch remain for
the following GF12 retirement slice; this is not full GF12 acceptance.


## GF12 native graphical policy retirement

The [completed GF12 record](../development/gem-first-gf12.json) removes the
DESKTOP packet API, retained command/widget window kinds, native preview
clients, shell-frame tabs and console attachments. AES owns the sole window
policy. Scene records retain frame/geometry/cache helpers; its six window
records are 294 bytes each, indexed directly by the AES service. Layers and
caller views remain derived publications, with distinct identities, handles
and lifetime epochs.

GEM application menus retain their presenter renderer through a private
50-byte DRAW/INVERT packet. They retain no native widget contexts or client
policy. Standalone text/bitmap consoles still render copied views; production
GUI output uses the ordinary GEM terminal. APP ABI 35 removes
`ExecAESConsole`; all ten standard APPs and the optional BASIC APP were rebuilt.
The BASIC build job also loses its unused attachment fields.

Development checks cover exact terminal pixels, focus/exposure, session
switching, modal cancellation/close, missing-terminal startup and EXIT;
six-window and four-client exhaustion; hidden lifecycle with input-only view
binding; menu input, replacement and retirement; metadata/cache journals;
standalone console operation; and raw/optimized record and waiter layouts.
Menu/snapshot/cache fixtures now follow the pointer index directly. The
registration fixture checks its publication hold separately from input snapshot
holds and uses the existing twelve-Task inventory. The source/provider audit
covers 1,182 production and fixture files. Host checks run 688 tests with four
existing skips; changed documentation has 923 valid local targets.

The final matched drawing control passes 67 measured operations, eleven exact
frames and 486 guest assertions. Its frame hashes match the first GF12 control.
It is the frozen input for GF13; no renderer optimization or latency-gate pass
is claimed here.

The production terminal walk starts with eight Tasks and observes nine at its
peak, two AES registrations and three windows. The terminal remains in slot 5,
using 870 of 1,312 stack bytes, with 186 bytes above its protected 256-byte
interrupt floor. The kernel watermark is 289 of 1,536 and its interrupt reserve
is untouched. Guards and ownership restoration pass.

The rounded scene allocation shrinks by 8,512 upper-RAM bytes. C executable
segments shrink from 230,261 to 211,286 bytes, initialized data from 5,106 to
5,102, and zero fill from 20,911 to 18,625. Native emitted routine/data sizes
are recorded separately. The existing offscreen range remains reserved;
VRAM reservation growth is zero. Reserved bank-zero growth is **0 fixed,
0 root/kernel, 0 for each of twelve public Tasks and 0 idle**, counting guards,
alignment and unused capacity. No hosted/hardware qualification, demo refresh
or final combined disk/input/QED acceptance is claimed; those remain for GF15.
