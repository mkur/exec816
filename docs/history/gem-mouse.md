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


## M3 Native ST capture

[M3 evidence](../development/gem-mouse-m3.json) records the reusable ST/port 1
backend, admitted independently of the keyboard through INPUT and the C bridge.
A fixed timer decoder reads both axes and TRIG0, maintains checked signed
counters, and publishes 32 bounded samples plus sixteen durable route notices.
Motion coalesces without crossing reversal/button/loss boundaries and retains
its earliest tick. Task normalization clips coordinates and expands simultaneous
movement/button changes in the required old-buttons/new-buttons order.

Route-qualified notice epochs invalidate older samples and retained BUTTON
output. Discarding an old route preserves another route's coordinate reference;
exhaustion disables addressed capture until reacquisition. The native interface
copies one record under saved I, with no masked ring scan. No PIA, POTGO,
trigger-latch or SKCTL writes were added. Shared field ownership and NMI guards
are documented in the [input contract](../reference/input.md#st-mouse-capture).

Raw and optimized standalone consumers receive the independent controller's
32 axis transitions and two button edges, plus the initial baseline. They cover
combined movement/button expansion, loss, copied leases, contention, route
retirement and reacquisition, with keyboard capture retained concurrently.
C checks include pointer baseline delivery and timer IRQs throughout the C
checksum/context workload. Producer tests reject premature signal freeing and
Task/controller removal, and cover either source's independent release.
Addressed capture, queue publication and wake posts also run during exact-byte
FASTEST125 SIO transfers, including ROM emulation entry. The largest measured
sampling gap is **260.51 µs**, below 1 ms in those workloads. The rebuilt keyboard
GEM scene continues to pass. The complete rate/visible-response envelope is M5
work; these development checks do not qualify the hosted system.

A signed-assignment defect exposed by the negative-counter fixture was fixed in
actionc commit `f1ff4ce0`, and the Exec pin was updated. NIR now explicitly widens
signed store operands, including record and volatile destinations. Focused raw
and optimized 65816, 6502 and 68k execution regressions pass. Compiler snapshots
and the 51-fixture sweep pass. A stale broad-corpus assertion (362 expected,
363 actual) also fails on the clean old pin; all remaining compiler tests pass.
The Exec host checks pass: 288 tests, four historical audits skipped.

The upper native-code reservation grows **2,048 bytes** to 12,288, ending exactly
before the provider table at arena offset `$4000`. Pointer capture's M2 storage,
guards and slack are unchanged. The existing 64 KiB Task-arena reservation does
not grow. Fixed bank-zero, each of eight public Tasks and private idle all change
by **0 bytes**, including guards, alignment and unused reserved capacity. No
extra Task, large stack or VRAM reservation is introduced.

## M4 Interactive integration

[M4 evidence](../development/gem-mouse-m4.json) records physical ST/port 1 motion,
field selection and typing, Count and Exit clicks, release outside a control,
and Escape while held in raw and optimized builds. Independent controller traces
agree with final coordinates; exact scanout pixels match the scene oracle.
Both input leases, signals and graphics requests retire, with hardware and stack
checks intact. Optimized checks also cover five mouse-admission failure boundaries,
keyboard input, wrong disk, early Escape/root stop and 24 injected gesture cases.

The application validates full mouse identity before translating to the current
private queue session, drains eight events per source per turn and includes both
sources in Pending/Wait. Failed mouse admission displays `KeysOnly` and leaves
keyboard controls available. Closing the association purges queued mouse events
and disarms gestures before releasing the source.

Optimized diagnostic C code grows 2,107 bytes, initialized data eight bytes and
zero-fill 88 bytes, within the existing two upper banks. No Task or VRAM is added.
Reserved bank-zero delta is zero for fixed/root storage, each of eight Tasks and
private idle, including guards, alignment and slack. The host suite passes 288
tests with four historical skips. This is development coverage; the declared
sampling/visible-response envelope remains an M5 gate.

## M5 Coexistence and failure closure

[M5 evidence](../development/gem-mouse-m5.json) records raw/optimized decoder,
GUI, keyboard/context and FASTEST125 native/emulation checks, targeted SIO
cancellation/error/recovery (128-byte functional and timeout cases, plus a
256-byte active-cancellation timing case), 62 cursor cases in each compiler mode, full source
identity rejection and production-link checks. Observed and unobserved optimized
GUI/production replays have identical XEX hashes, final coordinates and pixels.

The final maximum sample gap is 270.660 µs in the GUI and 275.946 µs in the
selected FASTEST125 fixture, below the unchanged 1 ms ceiling. Maximum observed
controller-to-capture delay is 125.321 µs. Sampling work takes at most 80.634 µs;
native IRQ entry through fixed source routing takes at most 120.881 µs in the
measured GUI cases, excluding scheduler/RTI. Keyboard small-redraw maxima are
10 PAL ticks, including wrap; first-outstanding-motion to visible cursor is seven
PAL ticks in raw, optimized and production cases. Both retain the 12-tick ceiling.

The existing controller's fastest interval respecting the minimum 1 ms spacing
is 16 scanlines, 1,028.506 µs (about 972 transitions/s). Sustained diagonal input
at that quantization has no unreported count errors. No synthetic exactly-1-kHz
controller replaces it; the separate sampling-gap assertion stays strictly below
1 ms. Button levels are held for at least 10 ms. Faster host bursts reach one
scanline (64.282 µs), produce loss and alias counts; quadrature cannot reveal
all hidden three/four-transition sequences. They are negative controls, not a
wider supported rate.

The decoder fixture found and fixed a missing M=16 annotation that selected the
wrong durable notice slot for a second route. Early typing before SIO admission
also exposed a fresh owned timer edge being delegated to the ROM IRQ path; the
adapter now leaves that edge for its next native entry. Both regressions pass
in the final emitted builds. Diagnostic NMI, ring saturation, signed-counter
endpoints, epoch exhaustion, held recovery and reacquisition checks remain bounded.

The initial keyboard runs exceeded 12 ticks. The final renderer prepackages and
caches arrow masks, skips cursor restoration for conservatively disjoint text
and bars (including saved edge nibbles), and repaints only the edited field tile
and necessary glyphs. A pixel observer was also corrected to wait for disk
progress and scanout to stabilize. Failed iterations are retained in the record;
acceptance limits were not raised.

Compared with M4, optimized diagnostic C code grows 498 bytes, initialized data
960 bytes and zero-fill four bytes (two are diagnostic-only). Native production
code grows 30 bytes, within the existing 12,288-byte allowance. No upper bank,
Task, VRAM or stack reservation is added. Reserved bank-zero delta remains zero
for fixed/root storage, every public Task and private idle, including guards,
alignment and unused capacity. These are development checks on the pinned
emulator; general hosted-system and physical-hardware qualification remain open.
