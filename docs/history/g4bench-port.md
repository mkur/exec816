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

G4B2 workloads and G4B3 package/measurement are pending.
