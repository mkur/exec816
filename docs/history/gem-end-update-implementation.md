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
