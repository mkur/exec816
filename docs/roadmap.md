# Remaining work

[Documentation home](README.md)

This page tracks open directions, not completed implementation history. The
[architecture overview](architecture/overview.md) describes what exists now;
the [earlier roadmap](history/roadmap-chronology.md) preserves the milestone log.

## Before a public release

- Run the [release qualification tier](contributing/testing.md#release-qualification)
  against the selected compiler, ROM, emulator and final distribution. Focused
  development records do not replace it.
- Confirm the supported machine and disk profiles, document remaining limits,
  and verify the packaged OF816 boot XEX, system disk, ROM and notices together.

## Follow-on capabilities

The next graphics milestone is a **fast bitmap console**, before overlapping
windows or AES. The [design note](plans/gem4xe/bitmap-console-design.md) and
[implementation plan](plans/gem4xe/bitmap-console-implementation-plan.md) define
B0–B9. B0–B7 and B8 functional integration have focused development evidence.
B8 measurements miss the scroll/repaint targets; fast-console acceptance remains
open. B9 packages only an explicitly labelled development preview. The full-screen 80×30 console uses the existing
640×240 VBXE mode and built-in 8×8 font. Reuse the
[console device](reference/console.md), retained cells, input routes, DOS cooked
editing and shell. The [instance geometry](reference/console-windows.md) follows the selected
backend: 40×24 text or 80×30 bitmap. Keep the existing console worker
as display owner, using one already reserved 2,560-byte pool and the shared
drawing library through a checked ordinary-call bridge.

First measure and improve the shared VDI text path: batch glyph work, amortize
command preparation and driver checks, and preserve bounded completion and
ownership. Add dirty text spans and a VRAM copy/fill scrolling path, with full
redraw as the correctness fallback. Keep the same rendering improvements usable
by later GUI clients. Start with a text caret; mouse-cursor optimization and
window composition remain separate work.

Proposed responsiveness goals on the pinned PAL 65C816 ×8/VBXE configuration are
visible typing or a short edit within **40 ms**, a synchronized one-row scroll
fenced within **20 ms** and visible within the following frame, and a full
80×30 repaint visible within **500 ms**. These are design targets, not achieved
measurements. The design defines acceptance and timing boundaries separately
for accepted console bytes, hardware completion and visible scanout. Measure
with physical disk I/O and input capture active as well as idle.
Require exact pixels, responsive cancellation, bounded memory and clean display
handoff. Existing request completion semantics and SIO deadlines must survive
the performance work. [Cheap idle input checking](plans/console-idle-input-implementation-plan.md)
is implemented: atomic notifications and retained work eliminate repeated input
validation during output-only turns. Development measurements reduce complete
scrolls from about 165 ms to 122 ms.
[Drawing validation and asynchronous scrolling](plans/drawing-validation-implementation-plan.md)
now validate once per public entry and keep one complete copy/fill list in flight.
Isolated scrolls take about 31 ms, repeated scrolls 33–38 ms, with input service
between polls. The [measurement record](history/drawing-validation-and-async-scroll.md)
also records 177–216 ms sampled visible input under eight-Task SDFS/ST load.
A smaller asynchronous candidate improves that latency but still misses 40 ms and
slows scrolling. The 20 ms scroll and 40 ms input goals remain open; complete-turn
CPU attribution is now implemented in the
[console responsiveness slices](history/console-responsiveness.md). Batched
aligned text reduces the maximum measured text-call CPU charge from 49.8 to
6.2 ms. Loaded visible input improves to 79–110 ms across three sampled phases,
but still misses 40 ms. Whole turns reach 22.5 ms CPU charge; time off CPU and
non-text worker work remain significant. Isolated scrolling is 31–33 ms and a
full repaint reaches its final fence in 251 ms. The next investigation should
separate ready-queue delay from deliberate worker yielding and bound the remaining
work between input checks. The 4 ms turn, 20 ms scroll and 40 ms visible-input
targets remain unchanged; these development measurements do not qualify them.

The [blitter completion IRQ plan](plans/blitter-irq-implementation-plan.md)
is implemented through BI5: native/emulation IRQs use the existing producer
framework, an independent watchdog preserves timeout recovery, and the console
waits while its active list blocks output. Input and READ service continue.
The [measurements](history/blitter-completion-irqs.md) show lower completion CPU
cost, but isolated scrolling remains about 32.5 ms and loaded visible input
98–139 ms. Completion-to-adoption delay can still reach 52.6 ms under load.
The next responsiveness work should examine that scheduling delay and remaining
worker work between input checks. Circular character rows remain a separate
preparation optimization.

The other possible milestones have no delivery order:

- Filesystem writing, beginning with a separate SpartaDOS milestone. Current
  [disk support](reference/dos.md) is read-only.
- A RAM filesystem and broader volume assignments beyond the implemented
  [SYS: alias](reference/sys-volume.md).
- Longer shell pipelines, scripts and background execution beyond the current
  [two-command foreground pipeline](guides/shell.md).
- Broader C bindings and more Amiga examples beyond the
  [standalone Calypsi binding](guides/calypsi-c.md).
- Additional pointer protocols, AES and desktop integration beyond the implemented
  [minimal hosted VDI subset](reference/gem-vdi.md) and [input sources](reference/input.md).
  The [optional interactive demo](guides/gem-vdi.md) provides keyboard and ST mouse
  controls, console handoff and bounded redraws during physical I/O. The completed
  [I0–I7 plan](plans/gem4xe/input-and-events-implementation-plan.md) records the
  cursor/injected-event boundary. The implemented
  [physical mouse design](plans/gem4xe/physical-mouse-design.md) adds ST mouse
  motion and the left button on port 1, with shared SIO timing and reusable
  capture. M0–M6 development checks cover GUI controls, bounded timing/failures
  and the packaged production scene. Its
  [M0–M6 implementation plan](plans/gem4xe/physical-mouse-implementation-plan.md)
  and [execution record](history/gem-mouse.md) preserve the measured envelope;
  physical hardware and other configurations remain unqualified.
- Priority scheduling and larger Task capacities. Current priorities are stored
  but selection is FIFO; capacities beyond the supported four/eight layouts need
  separate memory budgeting and qualification.
- Additional platforms and physical-device qualification. Emulator evidence
  applies only to its recorded configuration.

## Deferred API and compiler work

- **Narrow DOS scalar types.** Review `Open` modes and Boolean return widths
  together across DOS, COMMAND and providers. Retain 32-bit positions and counts
  where needed. This is an ABI migration requiring rebuilt callers; expected
  savings are small and do not imply faster disk transfers.
- **CSTRING API migration.** Move selected text signatures together with their
  checked provider declarations. Keep counted binary I/O. The literal type and
  allocation-free library are already implemented.
- **Near/far data pointers.** Define bank context, conversions and signature
  identity in actionc before migrating internal objects. Public pointers remain
  far for now. Near callable pointers need their own calling-convention design.
- **Dynamic libraries and general resource tracking.** Resident command
  providers, explicit memory release and current Process cleanup remain the
  supported scope; general discovery/unloading and automatic raw-Task memory
  reclamation need separate designs.

Implementation plans, including completed ones, are indexed under
[plans](plans/README.md). Completed console scrolling, `Main` return values,
CSTRING, command arguments and SYS work belong in their current documentation
and [history](history/README.md), rather than the open backlog.
