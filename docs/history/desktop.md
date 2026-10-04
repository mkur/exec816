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
