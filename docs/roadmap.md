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

The **first desktop on Exec816** has development evidence. The
[design note](plans/gem4xe/desktop-design.md) proposes a desktop background,
ST mouse pointer and one framed, movable shell window, followed by a second
overlapping window from an independent application Task to prove focus, clipping
and exposure repair. The [DT0–DT7 implementation plan](plans/gem4xe/desktop-implementation-plan.md)
is implemented at the development tier: client/event lifetime, Layers integration, an ST capture and visible
pointer checkpoint before dragging, independent clients, loaded shutdown and
the optional preview. DT0–DT7 implement the native client/event service, framed
shell, ST input, nonblocking dragging and an independent application. Capture/routing and exact repair
checks pass; pointer, outline and move-repair timing limits remain open.
Loaded shutdown/fault checks and the local OF816 preview pass;
see the [execution record](history/desktop.md). File browsing, menus and
broader AES compatibility follow this milestone.

The [mouse sampling and pointer batching plan](plans/gem4xe/mouse-performance-implementation-plan.md)
is implemented through MP4 at the development tier. Normal capture runs at
about 4 kHz with fine SIO timing preserved; each pointer move uses one blitter
list. [Matched measurements](history/mouse-performance.md) show lower IRQ
overhead and pointer setup cost. The OF816 preview is refreshed, with 2× travel
and memory reservations unchanged. Pointer, outline and move-repair timing
targets remain open; presentation scheduling and exposure repair remain focused
performance follow-ups.

The [desktop rendering design](plans/gem4xe/desktop-rendering-design.md)
is implemented through the
[DR0–DR7 plan](plans/gem4xe/desktop-rendering-implementation-plan.md), with smaller
damage sets, IRQ-completed top-window copies, reduced background overdraw and
two optional VRAM snapshot slots. It keeps one presenter, adds zero
bank-zero reservations and leaves partially obscured scrolling on retained
redraw. [Development measurements and the refreshed preview](history/desktop-rendering.md#dr7-combined-measurements-and-local-preview)
pass correctness checks; pointer, outline and move-repair latency acceptance
remains open. AW5–AW6 stay paused.

The next functional milestone is the
[AES widget library](plans/gem4xe/aes-widgets-implementation-plan.md), planned
through AW0–AW6. AW0–AW4 now host selected GEM4XE object, drawing and form
routines in the existing presenter, with retained widget trees, updates limited
to changed controls and event-driven interaction. The control-panel client,
interaction measurements and preview refresh remain AW5–AW6 work. Existing
Task/stack pools and window layers are reused. The library can later support a task bar; desktop work-area,
window-switching and launcher policy are separate work. Editable fields,
resource-file loading, menus and full AES compatibility remain deferred.

The [Layers library](reference/layers.md) now provides bounded regions, cached
visibility, stacking, damage and drawing transactions. Its
[implementation plan](plans/layers-implementation-plan.md) is complete through
L4 development checks. The desktop now connects retained console
content and the existing drawing backend to these interfaces; Layers itself
does not draw windows or change the working console.

Keep one presentation worker above Exec, evolving the existing bitmap console
worker and reusing its retained cells, input routes and shared GEM drawing code.
Each window is an upper-RAM object; it does not allocate a Task, stack or DP.
The implementation adds zero bank-zero reservations against its DT0 baseline.
The single presenter coordinates drawing tokens, window retirement, pointer
routing and nonblocking gestures. The exclusive
GEM demo remains a separate display client.

Further console optimization is paused. The shell-only bitmap demo's interactive
response is satisfactory for current use, and it is the desktop baseline.
[Bulk output batching](history/console-output-batching.md) is implemented through
OB5: cached `CAT LONG.TXT` improves from 26.670 to 16.082 s, with 332 hardware
scroll lists instead of 769. The 2× throughput target remains open. Initial
limits remain four rows/256 bytes/four turns, flushing on a changed VBI tick,
with unchanged bank-zero reservations. Loaded input results are mixed and
phase-sensitive; the broader worker/scroll/visible-input goals remain unqualified.
These limits stay recorded without blocking the next desktop milestone.

The completed console foundations and their development evidence are indexed in
[console plans](plans/README.md#console-and-interaction). Relevant records are
[the bitmap console design](plans/gem4xe/bitmap-console-design.md) and
[B0–B9 plan](plans/gem4xe/bitmap-console-implementation-plan.md),
[cheap idle input](plans/console-idle-input-implementation-plan.md),
[validated drawing and asynchronous scrolling](history/drawing-validation-and-async-scroll.md),
[bounded text presentation](history/console-responsiveness.md),
[blitter completion IRQs](history/blitter-completion-irqs.md),
[circular retained rows](history/console-circular-buffer.md) and
[input registration and lifetime](history/input-registration-lifetime.md).
The current [console](reference/console.md),
[instance](reference/console-windows.md), [display](reference/display.md) and
[input](reference/input.md) contracts remain authoritative until implementation
changes them. Development evidence does not qualify the hosted system or
physical hardware.

The other possible milestones have no delivery order:

- Broader [filesystem write support](reference/filesystem-writes.md), including
  cross-directory moves, sparse writing and a separately loaded checker if
  needed. MyDOS/SpartaDOS file and namespace writes are implemented; their
  [development record](history/filesystem-write-implementation.md) retains
  the selected coverage and remaining qualification limits.
- A RAM filesystem and broader volume assignments beyond the implemented
  [SYS: alias](reference/sys-volume.md).
- Longer shell pipelines, scripts and background execution beyond the current
  [two-command foreground pipeline](guides/shell.md).
- ASSIGN, multiple-file arguments, TAIL, FIND and regular expressions beyond
  the implemented [command toolbox](guides/toolbox.md) and
  [command usability](history/command-usability.md) services (PATH, fault text
  and template help).
- Broader C bindings and more Amiga examples beyond the
  [standalone Calypsi binding](guides/calypsi-c.md).
- Additional pointer protocols and broader AES/application compatibility beyond the implemented
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
