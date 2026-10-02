# Physical mouse development

[History](README.md) · [Plan](../plans/gem4xe/physical-mouse-implementation-plan.md) ·
[Design](../plans/gem4xe/physical-mouse-design.md)

## M0 Controller and baseline

[M0 evidence](../development/gem-mouse-m0.json) records the existing ST/port 1
controller, emitted observation in raw and optimized compiler modes, optimized
replay with observation disabled, and grouped host movement. Each run observes
eight transitions in each axis direction and a left-button press/release. The
independent controller trace contains all 34 electrical changes. The optimized
observed and unobserved runs have identical XEX hashes and target samples.

The input manager scales 16 host units to one electrical transition. The
controller schedules phases on the **scanline scheduler** with a distance-based
delay of 1–256 scanlines. Small opposing host movements can therefore cancel
before the controller emits a phase. The bridge schedules host input in base
cycles and timestamps passive controller output on that same clock; it does not
change controller timing. Separated movements show 35,910–36,024 base cycles
between phases. Eight-transition host bursts reach 4,104 base cycles between
phases. These observations do not establish the later 1 ms capture limit.

The fixture only reads PORTA/TRIG0. PIA direction/control and port 2, GTIA trigger
latch mode, POKEY write-register state and OS masks are unchanged after the run.
Trigger latching is disabled. Task ownership and stack guards pass. The existing
optimized interactive keyboard case, SIO transaction timing with observed/replay
comparison, and deadline rounding checks pass with the ST map enabled. Those
baseline runners retain their original workload pins inside their reports;
`mouse_input.tooling` identifies the actual overriding emulator binary. All 284
host tests pass, with four historical audits skipped.

This is development evidence. No production mouse capture is installed yet.
Runtime memory is unchanged: fixed bank-zero delta **0 bytes**, each of the eight
public Task deltas **0 bytes**, private-idle delta **0 bytes**, including guards,
alignment and unused reservation capacity. No upper-runtime or VRAM reservation
is added by this observation fixture.
