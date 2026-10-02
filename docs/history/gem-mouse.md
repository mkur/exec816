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

## M1 Shared timer ownership

[M1 evidence](../development/gem-mouse-m1.json) records independent SIO-alarm
and diagnostic sampling demands on timer 1. Timer configuration, vector
ownership, acknowledgement and enable composition now live in one platform
component. SIO keeps its existing watchdog, alarm units and transfer policy.
The timer-1 divisor remains 7. Joining an owner does not reset clocks; SIO's
transaction STIMER reset is included in the gap measurements.

Raw/optimized emitted checks cover both acquisition orders, both release orders,
capture admission and release during an armed alarm, incompatible ownership,
native IRQ and ROM emulation callbacks. The fixed sampler continues after SIO
shutdown and through cancellation/offline recovery. It is not public pointer
capture. An initial fastest-rate SIO overrun led to bounded RX/TX checks before
and after sampling; the same byte and phase deadlines then passed. Across the
six ownership runs the largest measured sampling gap is **254.52 µs**, below the
unchanged 1 ms gate. Independent POKEY-latch accounting finds no duplicate timer
dispatch or backend service. These limits apply to this diagnostic workload;
M3 must repeat them with the complete decoder.

The SIO-only raw transaction/timing check, real active cancellation and timeout
wrap checks with sampling, and the optimized interactive keyboard case pass.
Observed and unobserved optimized combined runs have identical XEX hashes,
results, checks and runtime records. The interactive image excludes diagnostic
timer entry points. All 287 host tests pass, with four historical audits skipped.
These are development checks, not hosted-system qualification.

Timer state reserves **32 upper bytes**, including 16 currently unused bytes,
at Task-arena offset `$0F30`, after the console tables. The upper native-code
reservation grows **512 bytes**, from 9,728 to 10,240; interactive native payload
grows 474 bytes. Both fit the existing reserved 64 KiB Task arena: whole-bank
reservation delta **0**. Fixed bank-zero, each of eight public Tasks, and private
idle all change by **0 bytes**, counting guards, alignment and unused capacity.
There are no additional Tasks or VRAM reservations.

## M2 Input records and source descriptors

[M2 evidence](../development/gem-mouse-m2.json) records Config version 2 at 32
bytes, retaining the 32-byte lease, 24-byte event and eight library operations.
Generated Action!, C and assembly layouts agree. Keyboard callers now use the
new record; version 1 is rejected. Pointer protocol/port, signed bounds, initial
position and reserved fields are checked before admission, which remains
UNSUPPORTED at this slice boundary.

Fixed source descriptors now identify existing leases by address, then validate
their complete retained identity. A single monotonic 32-bit allocator supplies
acquisition identities; source route epochs and notices remain independent.
Kernel removal, signal retention and release/drain enumerate the added source.
Its public producer name is `POINTER_INPUT=3`: the planned spelling `POINTER`
is an Action! keyword. Gateway packet profile 7 and its shapes are unchanged.

Raw and optimized emitted C/Action! checks cover layouts, malformed fields,
complete 32-byte bank-end extents, owner identity, routes and allocator exhaustion.
Both standalone keyboard-capture modes pass. Selected producer lifetime,
independent-source and unsupported-pointer cleanup cases pass, and the rebuilt
optimized interactive keyboard scene passes. All 288 host tests pass, with four
historical audits skipped. This is development validation; concurrent live
pointer capture is M3 work.

The keyboard descriptor grows 16 upper bytes. A second descriptor reserves 144,
the global allocator 4, and pointer capture 1,536: 128 control, 768 raw-ring,
384 notice, 32 guard and 224 unused bytes. Total additional occupied/reserved
extents inside the existing Task arena are **1,700 bytes**; the arena's whole-bank
reservation does not grow. Each caller's configuration grows 16 bytes, including
the GEM C configuration and console configuration. Fixed bank-zero, each public
Task and private idle all change by **0 bytes**, including guards, alignment and
unused capacity. There are no new Tasks or VRAM reservations.
