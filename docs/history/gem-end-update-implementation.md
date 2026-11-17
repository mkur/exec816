# MagiC-led END_UPDATE implementation

[Plan](../plans/gem4xe/end-update-implementation-plan.md) ·
[Baseline audit](gem-end-update-audit.md)

The user selected the complete plan, including removal of optional external
application backing caches and MagiC's explicit final-release yield, on
2026-11-17. Each executable slice is committed separately. MGVIEW is the sole
application acceptance target; these are development checks.

## EU1 — completed caller drawing retires its old cursor hint

`CONSOLEBITMAP.Submit` consumes the old drawing hint before invoking its private
caller packet. That path already fences and restores overlays/cursor before
releasing the physical grant. Successful completion no longer sets the hint
again. A late publication survives; failed completion goes through the existing
fault/hint path. Native owner operations still mark drawing that needs a later
presentation. No C renderer or application code changes.

The [EU1 record](../development/gem-end-update-eu1.json) retains frozen inputs and
results. The optimized emitted hint fixture passes 72 assertions, including
six caller completion/late-arrival/failure cases and the previous mouse/pointer
cases. The host suite runs 729 tests, four skipped. The MGVIEW pair retains
identical full scanout pixels and three clean Process lifetimes with intact
stack/domain guards. C provider and APP are reused; only native policy is rebuilt.

The unconditional final-release wake is still present. Its manager cycle drops
from 6.81 to **4.90 ms CPU** and calls the mouse adapter **zero times**, versus
one previously. END elapsed drops from 17.34/17.45 to **15.149/15.148 ms**;
viewer END CPU remains **6.237 ms**. Observed viewport completion remains around
120.8/140.3 ms; no end-to-end latency gain is established.

The generated memory map is identical to the audit build. Added reserved
bank-zero bytes: **0 fixed, root, kernel, idle and per-public-Task**, including
guards, alignment and unused capacity. No new state, Task, signal, buffer,
platform operation or physical admission is introduced. No QED, Counter,
catalog, demo or release matrix ran.

## EU2 — final release wakes only an armed continuation

Final painting release no longer manufactures `UPDATE_WAITING`. `SystemBlocked`
still arms under the existing guard, and `Notify` consumes that hint with the
native release. Native FIFO waiting is unchanged; no AES ownership queue or
signal-based semaphore wait is added.

The [EU2 record](../development/gem-end-update-eu2.json) records the production
release/arm routines in a small optimized fixture: 25 checks include nesting,
MCTRL, release before/after arming and a deterministic release between the first
check and guarded recheck. Two actual Tasks verify FIFO ownership handoff.
Journal and mouse edges alone are substituted. Host checks run 732 tests,
four skipped, including sleeping-manager attribution and identity indirection.

The observer reads the live desktop owner and resolves Task DP through native
context identity at the ready checkpoint. A manager with no observed turn is
valid and is charged zero CPU. It never wakes that Task for measurement. The
full-window pixels match; a new settled screenshot also matches the entire
baseline scanout. Four clipped cursor pixels differed in the earlier PAL
observation frame, which is not an atomic framebuffer snapshot.

The two scrolls produce **zero release Signals and zero SCRENMGR CPU during
END**. END is **6.821/6.767 ms elapsed**, **4.928/4.933 ms viewer CPU**. Observed
complete viewport latency is **120.32/120.24 ms**; these remain two quantized
samples. Three Process lifetimes, heap/ownership restoration and stack/domain
guards pass. C provider and APP are reused again.

The generated reservation map remains identical. Added reserved bank-zero
bytes: **0 fixed, root, kernel, idle and per-public-Task**, including guards,
alignment and unused capacity. No new runtime storage or platform service is
introduced. Only the focused release fixture and MGVIEW execute; no QED,
Counter, catalog, demo or release qualification runs.

## EU3 — input and cursor consumers acknowledge independent changes

The existing mouse-dirty byte now has input-refresh and cursor-selection bits.
Real routing/eligibility changes set both. Snapshot refresh consumes its bit
before copying, and cursor selection consumes its own bit under the existing
guard. A later producer remains pending. Physical input retains its independent
capture/publication path. `AESHOST.Service` refreshes copied input only when
pending, and real caller-side routing changes preserve the manager wake needed
to select the new cursor form.

SCRENMGR runs its second presentation only after actual interaction. Presentation
selects the cursor only for pointer/routing changes, and wakes mouse-completion
waiters after physical presentation rather than on every idle check. Paint-only
END no longer calls routing publication; END_MCTRL still publishes its routing
transition. Lifecycle settlement and application-outline suspension remain.

The [EU3 record](../development/gem-end-update-eu3.json) records 31 optimized
emitted routing assertions: stationary focus/MCTRL changes, separate consumer
acknowledgment, raw form survival and closing-endpoint retirement. The old
routing fixture is updated for canonical heap-owned window records, work
rectangles and a valid lifecycle wake target. Host checks run 732 tests, four
skipped. MGVIEW retains the entire settled scanout, three clean lifetimes and
intact guards. Provider/APP bytes remain reused.

END is **6.574/6.572 ms elapsed**, **4.726/4.731 ms viewer CPU**, with zero manager
CPU and zero routing-publication calls. Journal/cache work remains until EU4.
Observed viewport latency varies with the PAL sampling boundary; no further
latency gain is claimed from this slice.

No runtime state is added: the two bits reuse one existing byte. Generated
reservations remain identical; added bank-zero bytes are **0 fixed, root,
kernel, idle and per-public-Task**, including guards, alignment and spare
capacity. No Task, service, signal, queue, buffer or physical admission is added.

## EU4 — standard GEM application painting replaces the journal

The selected cutover removes the ordinary BEGIN/END paint transaction, the
per-draw journal writes and application backing-cache preservation together.
External GEM windows cannot enter backing-image capture or restore. System-owned
window/menu/background storage retains its owning operation's validity and
physical completion rules. The old patch producer and scoped journal helpers
are removed; there is no replacement per-primitive RPC or success stub.

MGVIEW now uses ordinary `wind_update(BEG_UPDATE)` across visible enumeration,
copy and exposed-strip redraw. Its completeness query, paint reports and extra
repair fallback are gone. Native geometry/lifetime epochs remain; pixel-proof
fields are removed from the application view. `SetExternal` establishes drawing
responsibility without inventing an initial coverage obligation. Explicit
Layers coverage primitives remain opt-in and have a focused emitted check;
their older fixtures now request that protocol explicitly.

Application import ABI is **48**, AES wire ABI **28**, desktop records **24**.
Removed APIs are `ExecAESBeginUpdate`, `ExecAESInvalidate`, `ExecAESPainted`,
`ExecAESPaintedChanges` and `WF_EXEC_PRESERVE`. The request shrinks from **418 to
190 bytes**, and each window view from **840 to 826 bytes**. The read-only
geometry/identity view helper remains. Other applications using the removed
protocol need migration; they are not built or admitted as compatibility gates.

The [EU4 record](../development/gem-end-update-eu4.json) records 162 independent
C/native layout checks in each of raw and optimized modes, plus actual emitted
array-stride, three-byte pointer, signed-coordinate and wide-field bridging.
The focused external handoff/coverage/move fixture passes 20 assertions. Host
checks run 733 tests, four skipped. MGVIEW's scroll pair and one resize/move
case pass with exact viewport/window pixels and three clean lifetimes each.
The settled scanout matches the audit baseline completely; guards remain intact.

END takes **1.987/1.987 ms elapsed**, **1.636/1.637 ms viewer CPU**, with no
journal, cache operation, routing publication or manager CPU. `set_shift` is
**74.67/76.40 ms CPU**, down from the audit's 82.76/81.33 ms. Observed viewport
completion remains **120.72/140.03 ms** in these two PAL/COP samples; it is not
a latency distribution or evidence of a consistent end-to-end gain.

The APP and shared provider are rebuilt for the changed ABI. After correcting
remaining internal references, the final relink reuses already compiled objects
from that new-ABI build and recompiles the two affected C objects; the object
hashes are retained. No QED, Counter, catalog or demo is built. All reservation
map fields match EU3 except foreign code placement: added bank-zero bytes are
**0 fixed, root, kernel, idle and per-public-Task**, including guards, alignment
and spare capacity. No VRAM range, Task, signal or platform operation is added.
