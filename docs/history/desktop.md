# Desktop development

[Plan](../plans/gem4xe/desktop-implementation-plan.md) · [Roadmap](../roadmap.md)

## DT0 Inputs and budgets

The [baseline record](../development/desktop-dt0.json) freezes the existing
bitmap shell, companion disk, OF816 image, compiler, ROM and actual mouse-capable
emulator. A fresh unchanged-package smoke passed five-second autoboot, TASKS,
system volume navigation, disk HELLO, shared-cache reads, CAT/WC pipeline and
EXIT with ownership/OS restoration checks.

The current shell runs in the root Task. Console, filesystem and SIO bring
prompt occupancy to four; a two-command pipeline peaks at six. The proposed
second application raises these to five/seven of eight public slots. The
presenter will reuse the existing 2,560-byte worker pool, admitted before other
clients. Root owns the shell window/controller; the second Task registers itself.

The Layers scene occupies 4,782 upper-RAM bytes. Client queues, window records
and retained command storage will be heap allocations, not additions to the
2 KiB resident globals arena. The existing aperture and command arena remain.
Combined stack use and final UI storage are later slice measurements, not
established by the separate Layers fixture.

Existing CAT and ST capture evidence is retained rather than rerun. The saved
short-echo trace ends at drawing return, not visible scanout. DT3 must run its
new visibility observer against the frozen unchanged image as well as the
desktop; no visible-latency baseline is inferred from that older trace.

Reserved bank-zero change is **0 bytes fixed, root/kernel, per public Task and
idle**, including guards, alignment and unused capacity. DT0 adds no runtime
state. This is development evidence and does not qualify the desktop.

## DT1 Client and event service

[Native service](../reference/desktop.md) now implements four registered
clients/windows, retained fill/text batches, bounded event queues, durable
loss/focus/close bookkeeping and separate control/content/event/cancel lanes.
The service retains each owner through final reply publication. It uses ordinary
Exec messages and a recording Layers backend; hardware integration is DT2.

[Raw and optimized evidence](../development/desktop-dt1.json) each passed 143
assertions with two independent client Tasks and a presenter. The fixture covers
a waiting peer, cancellation while a paint defers controls, completion winning
a late cancellation, queue overflow/motion coalescing, invalid batches, stale
IDs, capacity exhaustion and final cleanup. A separate held-removal case reaches
the expected Exec launch fault. Stack/domain guards, native context restoration
and successful-run allocation ownership checks passed. The host suite passed
337 tests with four historical skips. These are development checks.

Service payload is 10,372 upper-RAM bytes. The fixture adds a 32-byte guard and
a separate 710-byte source batch. Three public Task slots are occupied during
the test; the production desktop has not yet been attached to the console.
Reserved bank-zero growth is **0 fixed, 0 root/kernel, 0 per public Task and
0 idle bytes**, including guards/alignment and unused pool capacity.
