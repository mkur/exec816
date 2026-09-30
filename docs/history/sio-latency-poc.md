# POKEY IRQ-to-worker latency proof

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/device-io.md) and [history index](README.md).

Status: executed on the pinned AltirraOS ROM with an explicit 8× PAL CPU
configuration. **The minimal path meets the 125 kbaud target with platform
constraints. The existing ROM interrupt path does not.** This experiment comes
before the full signal ABI, message ports, allocator integration or task-capacity
work; none of those services was implemented for it.

The [measurement record](../qualification/sio-latency.json) contains the case
results, image/source hashes, actual machine settings, timing statistics and
worst-refill event sequences. The executable experiment is
[one assembly file](../../probes/sio-latency/probe.s) and its
[runner](../../tools/sio_latency.py).

## Question and result

Can a POKEY serial interrupt wake a blocked native worker soon enough for that
worker to supply the next byte at 125 kbaud?

Yes, for the tested minimal implementation, using all three of:

1. A direct native serial IRQ path, avoiding the ROM's per-byte IRQ dispatcher.
2. Fast ROM access (`CPU: Shadow ROMs = 1`) as well as an 8× CPU clock.
3. `CRITIC = 1` during the stream, preserving ROM stage-one VBI work while
   suppressing stage two. This is the same OS critical flag used by ROM SIO.

The longest candidate stream transmitted **65,535 bytes**, crossed **258 VBIs**,
and had zero missed deadlines, gaps, overwritten transmit bytes or changed
worker contexts. Its worst hardware-ready-to-refill time was **65.973 µs**.
Additional idle and initial-phase cases raised the candidate maximum to
**66.537 µs**, leaving **12.405 µs** before the actual hardware deadline.
Across the five candidate streams, 94,207 bytes were transmitted with no gaps.

The proof is deliberately a demanding worker-per-byte experiment. It does not
establish that a general scheduler, public Signal API or future DOS workload
will fit into the remaining time. It does establish a viable minimal delivery
path, and identifies constraints to carry into the next driver experiment.

## Machine and deadline

The ROM is the unchanged AltirraOS 3.44 65816 image from
[the platform pin](../../toolchain/altirra.json). Its normal profiles run at 1×;
they were never 14 MHz qualification. This experiment explicitly selects:

| Setting | Value |
| --- | --- |
| Machine | 800XL, PAL, 65C816, 64 KiB RAM, BASIC off, no high banks/add-ons |
| Base clock | 1,773,447.5 Hz |
| CPU multiplier | 8: nominal 14,187,580 Hz; active multiplier checked by the observer |
| ROM access | Both original slow access and explicitly verified shadowed/fast access tested |
| Display | Normal boot text display and its DMA retained; DLI disabled |
| VBI | Real ROM VBI, either complete or stage one via CRITIC; disabled only in a control case |
| Serial acceleration | SIO patching and burst transfers disabled |
| Launch timing | Random launch delay disabled; three explicit initial-phase offsets also tested |
| Task execution | Native mode, M=X=0, separate guarded stacks and direct pages |

POKEY uses linked timers 3+4 with divisor zero. At the PAL base clock this gives
**126,674.821 baud**, slightly faster than the requested 125,000. A ten-bit frame
takes 140 base-clock cycles, or **78.942 µs**. The CPU multiplier does not multiply
POKEY's baud rate. The deadline is one complete byte, not one serial bit.
The timer/baud relation and transmit-ready behavior are described in the
[Altirra hardware reference, sections 5.6 and 10.2](https://www.virtualdub.org/downloads/Altirra%20Hardware%20Reference%20Manual.pdf).

This is an emulator measurement of that explicit memory/clock configuration,
not a physical-board measurement or qualification of every nominally 14 MHz
machine. In particular, an accelerated CPU with slow ROM does not reproduce
the passing configuration.

## What executes

Initialization primes SEROUT with one byte, then the worker enters a private
COP `$50` consume-or-block operation. A single pending byte flag stands in for
signals. With no pending post, the worker's complete native frame remains on
its stack and the probe restores a background context. The background either
runs an ordinary busy loop or uses WAI as idle.

When POKEY transfers SEROUT into its output shifter, its real transmit-ready IRQ
asserts. The native handler acknowledges the source and posts the flag. At a
safe interrupt exit, it restores the worker's saved frame. The worker returns
from its wait and writes the next byte to SEROUT. **Only the worker writes the
next byte; the handler never feeds the transmitter.**

The test repeats with incrementing byte values. A late worker introduces a
measurable idle gap in the actual POKEY transmitter; eventually delivering all
bytes is not enough to pass. The final byte must finish shifting before the
experiment restores the OS vectors and critical flag.

The native frame saves A including its hidden byte, X, Y, D, DBR, P, PC, PBR and
the native S position. There is no Task structure, public ABI, compiler-generated
wrapper, dynamic memory, queue or general scheduler. Other COP signatures chain
to the saved OS dispatcher. The private COP operation is not a supported Exec
service selector.

The NMI wrapper follows the current adapter's page-one stack rule and chains
the ROM VBI. A ROM serial-vector callback can post while the OS is in emulation
mode, but it cannot switch tasks. Delivery waits until the OS activation has
retired. The experiment therefore includes the important coexistence delay
instead of escaping it by switching out a live ROM activation.

## Measurements

All rows use the same 126.675 kbaud hardware setting. Each ordinary comparison
transmits 4,096 bytes and has 4,095 measured refills after the priming byte.

| Serial IRQ route / ROM access / VBI | Worst refill, µs | Missed refills | Result |
| --- | ---: | ---: | --- |
| Native / slow ROM / VBI disabled | 69.356 | 0 / 4,095 | Control passes; not OS coexistence |
| Native / slow ROM / full VBI | 555.415 | 16 / 4,095 | Fail |
| ROM / slow ROM / full VBI | 575.715 | 4,095 / 4,095 | Fail |
| Native / slow ROM / CRITIC | 160.140 | 16 / 4,095 | Fail |
| Native / fast ROM / full VBI | 106.572 | 9 / 4,095 | Fail |
| ROM / fast ROM / CRITIC | 80.070 | 48 / 4,095 | Fail |
| Native / fast ROM / CRITIC, long busy-background run | 65.973 | 0 / 65,534 | Pass |
| Same, idle background | 65.973 | 0 / 16,383 | Pass |
| Same, three initial-phase cases | 66.537 | 0 / 12,285 | Pass |
| Deliberate long IRQ masking, VBI disabled | 260.510 | 117 / 255 | Expected failure detected |

Every detected missed deadline in this matrix also produced a transmitter gap.
The negative control masks IRQs over 1,600 NOPs in the background context; its
failure demonstrates that the runner checks real timing and continuity.

The failure mechanisms are distinct. The slow-ROM per-byte dispatcher already
exceeds the deadline before considering VBI. The direct native route removes
that cost, but full ROM VBI can still hold the worker off for hundreds of
microseconds. CRITIC shortens the VBI path, and fast ROM access shortens its
remaining work. Neither change alone passed this matrix.

CRITIC is not IRQ masking or Forbid. In this ROM, VBI stage one updates the
real-time clock and services OS timer one, then checks `$0042` before stage two.
ROM SIO itself sets that flag on entry. The inspected source is in the
[ROM provenance and build](../../tools/build_rom.py), with the generated listing
under `build/firmware/altirraos-816.lst`. No timer-one callback was active in the
recorded runs. Stage-two display-shadow updates, later timers and deferred VBI
callbacks are postponed during CRITIC; it is not transparent full OS service.

## Timing and validation method

The [observer patch](../../probes/sio-latency/observer.patch) adds host-side logging
to the corrected pinned emulator. It records POKEY shifter-load/ready events,
SEROUT writes and transmitter-idle events using the scheduler's base-clock
time. Selected existing CPU-history entries record wait, post, interrupt and
worker checkpoints, including complete register values and subcycles. Extra
read-only register-query fields verify the active CPU multiplier and ROM mode.
The patch adds no guest instructions, IRQ sources or emulated scheduling calls.

The acceptance measurement is **hardware ready to actual SEROUT write**. It
includes delayed IRQ recognition, masked sections, NMI/OS interference, context
restoration and the worker's refill instructions. IRQ-entry-to-wake and
post-entry-to-wake are reported as diagnostic breakdowns; neither substitutes
for that end-to-end measurement. A post checkpoint marks entry to the tiny post
sequence, not a separate hardware event.

Hardware times use base cycles, including DMA stalls. The bridge's ordinary
`REGS.cycles` subtracts halted cycles and is unsuitable for this deadline.
CPU history supplies 32-bit base timestamps plus subcycles; the runner extends
them against the hardware's 64-bit clock across wraparound. For each refill it
also independently checks the next shifter-load interval and the byte sequence.
Samples and raw logs stay under `build/sio-latency/decision`; their hashes and
worst-event windows are in the committed record.

Acceptance covers complete wait/wake counts, actual blocked waits, transmitted
byte order, no SEROUT overwrite, final-byte completion, full worker register
restoration, both private direct pages, stack guards and OS-vector restoration.
The long stream crosses an OS clock-byte rollover. The same long-run XEX is
replayed on the unchanged pinned emulator and must match its counters, clocks,
background progress and saved stack positions. The observer also passes the
existing ten native/emulation interrupt-mask regressions.

The guest is hand-written machine code, so raw/optimized NIR comparison does
not apply. No compiler ABI, production Task or complete hosted regression suite
was changed or qualified by this experiment. The existing two rendezvous tests
and settings checks cover the small launcher-setting extension.

## Consequences for the next slice

Carry a direct native device IRQ entry into the platform adapter; do not send
every serial byte through its generic ROM dispatch path. Make fast ROM access
an explicit requirement of any profile claiming these results. Specify scoped
ownership of CRITIC and restore it between transfers so deferred OS work runs.
Arbitrary OS calls, timer callbacks, longer kernel critical sections and richer
display DMA still need their own latency measurements.

The remaining 12.405 µs is a measured margin for this small workload, not a
budget already available to an allocator or general scheduler. For the eventual
driver, keep urgent byte movement in the IRQ handler and use task notifications
for block/phase completion where possible. The worker-per-byte experiment shows
that waking a task can fit; it does not require the production driver to wake
one for every byte. Receive overrun, a real device's responses, turnaround,
checksums, timeout and cancellation remain untested.

The next executable work is the bounded native IRQ path and its SIO/OS ownership
rules. Repeat this measurement as that code replaces the hand-rolled path.
Keep the full signal/port/capacity stack behind that check.

## Storage and reproduction

Production bank-zero reservation delta: **0 bytes**. The disposable XEX uses
these isolated ranges; they are not added to the production memory map:

| Reservation | Fixed / per context | Bytes |
| --- | --- | ---: |
| Probe code `$3000-$3FFF` | Fixed, includes unused assembly limit | 4,096 |
| State `$2000-$20FF` | Fixed, includes unused bytes | 256 |
| Existing OS stack `$0100-$01EF` | Shared fixed range, includes bottom guard | 240 |
| Direct page plus guards | Per context | 288 |
| Native stack plus guards | Per context | 1,568 |
| Total for two contexts | 4,592 fixed + 2 × 1,856 | 8,304 |

Ordinary phase-zero code emits 885 bytes inside the 4 KiB code reservation.
Using bank-zero code here is an explicit throwaway-probe simplification; it
does not establish production placement or release unused reservation bytes.

Prepare a fresh emulator source checkout and the pinned ROM as described in
the [native IRQ correction](emulator-native-irq-fix.md). Apply the observational
patch once to that corrected source, then build into a separate directory:

```sh
git -C build/altirra-irq-fix apply ../../probes/sio-latency/observer.patch
cmake -S build/altirra-irq-fix -B build/altirra-irq-fix/build/latency \
  -DCMAKE_BUILD_TYPE=Release -DALTIRRA_BRIDGE_SERVER=ON \
  -DALTIRRA_STATIC_SDL3=OFF -DALTIRRA_SKIP_SDL3_IMAGE=ON \
  -DENABLE_LIBRASHADER=OFF -DALTIRRA_CPU_TESTS=ON
cmake --build build/altirra-irq-fix/build/latency --target AltirraBridgeServer -j 8
mkdir -p build/altirra-latency-bridge
ln -sfn ../altirra-irq-fix/build/latency/src/AltirraBridgeServer/AltirraBridgeServer \
  build/altirra-latency-bridge/AltirraBridgeServer
ln -sfn ../altirra-irq-bridge/sdk build/altirra-latency-bridge/sdk
build/altirra-latency-bridge/AltirraBridgeServer --cpu-test-interrupt-mask
python3 tools/sio_latency.py --matrix --trace \
  --bridge-dir build/altirra-latency-bridge \
  --pinned-bridge-dir build/altirra-irq-bridge \
  --output build/sio-latency/decision
```

The local build used the same system SDL3 and explicit ImGui cache override as
the existing emulator build record. The observer binary hash and patch hash
are recorded separately; the production emulator pins remain unchanged.
The matrix intentionally includes failing timing cases and succeeds only when
the candidate passes, the required negative controls fail, and unchanged-binary
replay agrees. To vary one condition, run the tool without `--matrix`; its flags
select VBI, ROM IRQ routing, CRITIC, ROM shadowing, divisor, phase, background
activity and stream length.
