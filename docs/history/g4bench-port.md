# GEM4XE benchmark port execution record

[Plan](../plans/gem4xe/g4bench-port-implementation-plan.md) · [History](README.md)

## G4B1 — Loadable application and clock

The pinned donor is GEM4XE `fbfea9b0b1233a5d659d5ec583c63f863cceadfa`.
The first slice provides the window/event shell and an application-private
adapter over `timer.device`'s monotonic VBI clock. Import ABI 12 exposes seven
existing public Exec message-port/device-I/O calls. The matching provider and
applications rebuild together; no kernel call or timer unit was added.

[Development evidence](../development/g4bench-g4b1.json) records an optimized
emitted clock probe followed by two independently loaded benchmark lifetimes.
The probe covers low-word rollover, changed-rate/reversal rejection, eight
timer bindings, exhaustion cleanup and reuse. Physical Return reads the live
clock; Escape closes each window. Process/heap ownership returns to baseline,
and native stack/domain checks pass. This is development coverage, not release
or real-hardware qualification.

The APP is 3,867 bytes with a 65,901-byte image span and relocation verified at
62 legal bank bases. Its clock port/request use 72 upper-heap bytes. The
ordinary application slot's observed stack peak is 584 bytes, leaving 472 bytes
above its interrupt floor. Existing stack reservations remain unchanged.
Slice bank-zero delta: **0 fixed, 0 per public Task, 0 private-idle**; no new
VRAM reservation. The generic runner's historical compaction deltas include
earlier stack growth and must not be interpreted as this slice's cost.

The first build exposed an existing stack-analysis bug: the IDE scanner read
a `$22` inside a JSL address as another call. The prerequisite fix skips an
accepted call's operand bytes, retains call-map agreement and adds two host
regressions. Re-admission of the emitted image gives a 722-byte IDE worker
bound within its 1,024-byte reservation. Compiler output was unchanged.

## G4B2 — Workloads and reporting

The five rows now use the selected donor geometry and tree through public
VDI/AES calls. The text is exactly 39 bytes. UPDATE groups contain at most four
bars/strings or one tree, with event polling between groups. Calibration,
three timed samples, cancellation, geometry/focus/visibility admission and
the screen/disk reports are implemented. Unsupported donor families remain
explicitly skipped. See the [application guide](../../ports/gem4xe/apps/g4bench/README.md).

[Development evidence](../development/g4bench-g4b2.json) records independent
full-canvas pixels for all five rows, all fifteen saved samples agreeing with
the observed clock endpoints/counts, a physical title drag invalidating a run,
Escape cancellation, missing-WORK save failure, two clean loaded lifetimes,
heap ownership restoration and intact stack/domain guards. The clock probe
also repeats G4B1's rollover, zero-interval and binding-exhaustion checks.
The fixture uses the pinned emulator's 57.6 kbit/s profile for both disks.

Pixel checks exposed Calypsi 5.18 `-O2` miscompiling the new local-array
expressions `p[2]=p[0]+99` and `p[3]=p[1]+49`: emitted additions read stack
slots 11/13 instead of the initialized coordinates at 7/9. Rectangle setup now
uses named X/Y coordinates, and canvas clearing reads its model directly.
The corrected optimized emission passes the independent pixels. Neither
Action! compiler code nor the shared renderer was changed for this adaptation.

The APP is 14,777 bytes, spanning 67,931 bytes, with relocation checked at all
62 legal bank bases. Its observed ordinary-stack peak is 697 bytes, leaving
359 bytes above the interrupt floor. Slice bank-zero delta remains **0 fixed,
0 per public Task, 0 private-idle**, including guards and unused reservation;
no VRAM reservation changes. The clock still owns only 72 upper-heap bytes,
and results/workload state live in the private loaded image.

These checks establish correctness of the selected workloads. G4B3 supplies
the normal packaged-desktop baseline; fixture measurements are not a direct
GEM4XE comparison or an input-latency result.
