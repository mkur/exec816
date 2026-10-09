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
- Investigate the verified-write deadline exposed by 16 KiB COPY on accurately
  timed 256-byte MyDOS media before qualifying that case. The
  [write-performance record](history/write-performance.md) preserves the
  reproducible timeout and the passing bundled 128-byte WORK scope.

## Commands and CLI

Proposed sequence for the next command and shell slices. Keep new utilities
loadable where practical, and record resident code, upper-RAM and reserved
bank-zero costs for each slice before moving to the next.

The [COPY and filesystem write-performance slice](history/write-performance.md)
implements a 16 KiB loadable COPY buffer, fewer physical writes during file
extension, retained sequential cursors and bounded four-sector metadata groups.
Matched buffer/filesystem measurements, confirmed-prefix errors, ownership,
BREAK checkpoints and the bitmap/cartridge preview have development evidence.
The accurate 256-byte MyDOS transport limit is recorded above.

The [SpartaDOS write buffering slice](history/spartados-write-buffering.md)
now coalesces bitmap, free-count, map and length updates within each Write,
with ordered publication before replying and four-sector BREAK checkpoints.
Matched COPY, failure and cancellation checks pass at the development tier;
see the [SB0–SB5 plan](plans/spartados-write-buffering-implementation-plan.md).
Retaining dirty metadata between Write calls until Flush/Close remains a
separate design decision.

The [background command and primes slice](history/background-pane-primes.md)
implements positioned writes, height changes, an owned lower pane, independent
background cancellation and bounded RUN/JOBS/BREAK support. The loadable
`C:PRIMES` uses six lower rows and updates only changed numeric fields. The
bitmap shell starts full-screen; pane closure restores its height and edited
input. One background job and one pane keep this version bounded.

1. Shell `>>` append redirection is implemented through writable Open and
   seek-to-EOF. Development checks cover saved contents, partial writes,
   final Close errors, BREAK and restoration of the shell's selected streams;
   see the [implementation record](history/shell-append-redirection.md).
2. `EXECUTE file` is implemented through the existing dispatcher, with bounded
   lines, blank/comment handling, WARN continuation and ERROR/FAIL/BREAK stops.
   Its source remains separate from command Input; one active script keeps
   arguments, nesting and conditionals out of this slice. See the
   [implementation record](history/shell-execute.md).
3. TAIL and FIND are implemented: a sixteen-line suffix ring for files/pipes
   and filename traversal with eight directory frames and LIST-style patterns.
   See the [implementation record](history/tail-find.md).

The [multiple-file and LIST pattern slice](history/multiple-file-patterns.md)
is implemented with exact CAT/DELETE names and read-only LIST filtering. The
[ASSIGN slice](history/assign.md) adds four bounded logical directory names.
The [shell alias slice](history/shell-aliases.md) adds eight session-local
command shortcuts without changing DOS lookup.
The [system command directory slice](history/system-command-directory.md)
stores external commands in SYS:C, assigns C: there at startup and defaults
PATH to CurrentDir followed by C:.
Before allowing patterns in mutating commands, account for the
[mount-wide enumeration epoch](reference/filesystem-writes.md) that invalidates
ExNext after a mutation. The three bounded command/shell utility steps above
are implemented. The [startup script slice](history/shell-startup.md) now assigns
S: to SYS:S and runs optional STARTUP/USER files sequentially before the prompt.

The [OF816-first boot slice](history/of816-first-boot.md) is implemented through
B4 at the development tier. The monitor runs before the main kernel payload.
`EXEC816` restores the
paused XEX/cartridge reader and returns with RTS; loading then resumes with
progress dots. Defaults are initialized before Forth, its settings survive
kernel startup, and the existing screen text is preserved. The bitmap/no-primes
preview includes both Atarimax forms. Remote image loading remains a later
extension.

## Desktop usability milestones

The three milestones following
[application menus and window switching](history/application-menu-bars.md)
are implemented, with a design note, implementation plan and development
record for each:

The [classic GEM appearance](history/classic-gem-appearance.md) is implemented
through GA1–GA4: flat outlined frames, left closers, centered patterned titles,
consistent menus/controls and a patterned desktop. The exact OF816 package
passes development walkthroughs. Current work-area insets and font metrics are
retained for fixed windows; painting and input share frame geometry. Resizable
windows extend that geometry with working gadgets and kind-dependent insets.

1. **Resizable windows and vertical scrolling.** Size, thumb, arrow and page
   gestures deliver `WM_SIZED`, `WM_VSLID` and `WM_ARROWED`. Applications
   acknowledge geometry and own their scroll position. See the
   [design](plans/gem4xe/window-gadgets-design.md),
   [plan](plans/gem4xe/window-gadgets-implementation-plan.md) and
   [record](history/window-gadgets.md).
2. **Adaptive Files.** A bounded 256-entry snapshot replaces eight-entry pages;
   up to sixteen rows follow the work area, with continuous scrolling and
   preserved selection. See the [design](plans/gem4xe/files-scrolling-design.md),
   [plan](plans/gem4xe/files-scrolling-implementation-plan.md) and
   [record](history/files-scrolling.md).
3. **Editable TEDINFO and dialogs.** Caller-local `objc_edit` supports bounded
   single-line fields. Files uses it for Path, New Folder and Rename while
   continuing window events and child collection. See the
   [design](plans/gem4xe/editable-dialogs-design.md),
   [plan](plans/gem4xe/editable-dialogs-implementation-plan.md) and
   [record](history/editable-dialogs.md).

Application state remains caller-owned. All slices add zero reserved bank-zero
bytes. Development checks do not close HY4/PI4 or qualify the hosted system.
Horizontal scrolling, richer editing and desktop icons remain outside this
bounded subset. Cartridge compression remains separate work.

Next, the [application stack headroom plan](plans/gem4xe/application-stack-headroom-implementation-plan.md)
addresses the narrow worker-stack margins observed in the final dialog checks.
SH1–SH3 attribute deep call paths, enlarge ordinary stack pools and verify
at least 128 bytes above the existing checked floor in selected application
scenarios. The selected 256-byte increase per ordinary pool adds 1,280 reserved
bank-zero bytes; interrupt reserves and guards remain intact.

## Follow-on capabilities

The confirmed GUI direction is a multitasking GEM-compatible desktop over Exec816,
using VBXE and preserving application source interfaces. The
[XaAES study](plans/gem4xe/xaaes-study.md) recommends client/wait and window-redraw
contracts followed by a two-client compatibility proof. Existing native desktop
and widget milestones below are foundations, not full AES compatibility.
The [AES layer](reference/aes.md) reuses the presenter for client registration,
update/mouse locks and orderly exit. Copied messaging and event/timer waits run
in the callers through public Exec services.
Its [implementation slices](plans/gem4xe/aes-server-implementation-plan.md) use the implemented
[timer.device](reference/timer.md) with ordinary Exec Wait and include
a measured two-client foundation before GEM window redraw. Native
[interrupt-context ReplyMsg](reference/ports.md#native-interrupt-reply), protected
port transactions and controlled NMI continuations are implemented. The
[IR0–IR5 execution record](history/interrupt-reply.md) includes real Action!/C
timer adoption without a worker. Development checks cover the standard 57.6k
loaded envelope. Close the open 125k transport refill timing gate before
claiming that combination is supported; AES TD4 measurements remain separate.
AS0–AS3b have development evidence for generated wire layouts, private C
registration, messages, shared timer alarms and native GUI ownership gates.
The AS4 proof runs two C clients beside the native desktop within the
existing eight-Task budget. Functional checks pass; resolve the recorded relative
latency regressions before accepting AS4/TD4. The
[latency follow-up](development/aes-server-latency.json) records widget copying,
focus damage, clock and presenter changes against the frozen limits. See the [execution record](history/aes-server.md)
and [resident application guide](guides/aes-applications.md). GEM windows,
`WM_REDRAW`, visible rectangles and independent VDI workstations follow.

The proposed [hybrid AES and VDI model](plans/gem4xe/hybrid-aes-vdi-design.md)
moves suitable operations, application messages and event waits into callers,
retaining one GUI authority for window policy and input. Direct rendering needs
explicit scene/display ownership and measured application stack capacity.
Keep priority scheduling deferred until this execution model is measured.
The [HY1–HY4 implementation plan](plans/gem4xe/hybrid-aes-implementation-plan.md)
first refactors the existing AES profile: endpoint lifetime, caller-owned timers,
atomic message/event migration and the integrated native GUI latency proof.
[HY1](development/aes-hybrid-hy1.json) implements shared endpoint lifetime and
passes development checks. [HY2](development/aes-hybrid-hy2.json) moves standalone
timer waits into callers and passes PAL/NTSC development checks.
[HY3](development/aes-hybrid-hy3.json) moves messaging and combined waits into
callers and removes the presenter event engine.
[HY4](development/aes-hybrid-hy4.json) records the integrated proof, reduced clock
query work and refreshed OF816 desktop bundle. Functional checks pass; active
clients still exceed the unchanged native GUI latency limits. HY4 and the
AS4/TD4 successor performance gate remain open. The
[latency diagnostics](guides/aes-latency-diagnostics.md) now separate caller
device-I/O CPU, presenter scheduling delay and equal offered load;
[measurements](development/aes-hybrid-diagnostics.json) retain the failed gate.
The [timer I/O follow-up](history/aes-hybrid.md#hy4-timer-device-call-costs)
reduces handle-validation arithmetic and records bridge, driver and gateway
costs. The [trusted-request slice](history/aes-hybrid.md#hy4-trusted-device-requests)
then removes layered request and binding validation, retaining operational
errors and synchronization. DoIO/SendIO medians fall; scheduling tails remain
variable and GUI acceptance is still open.
The [caller dispatch slice](history/aes-hybrid.md#hy4-caller-device-dispatch)
removes the established-device routing gateway; DoIO/SendIO medians fall to
0.394/1.115 ms with unchanged memory reservations and public API. Development
checks pass, while scheduling tails and the GUI acceptance gate remain open.
The [I/O latency plan](plans/io-latency-implementation-plan.md) follows with
caller-local CheckIO (IL1: 0.111 ms median) and removal of redundant timer
exit polling (IL2: SendIO 0.644 ms median). The
[IL3 rerun](development/io-latency-il3.json) passes functional checks but retains
18 failed rows across frozen and matched GUI comparisons. Loaded scroll/disk
button consumption improves over the previous HY4 record; idle-load panel and
pointer-button tails worsen. HY4 remains open.
Additional local GEM calls and
direct VDI drawing follow their own coverage gates.

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
targets remain open. Following the tested PI3 demo, further presenter latency
work is deferred until the desktop experience is more complete; PI4/HY4 remain
open.

The implemented [mouse acceleration design](plans/gem4xe/mouse-acceleration-design.md)
adds precise slow movement and faster desktop travel, with a fixed 2× off option.
The [MA1–MA4 plan](plans/gem4xe/mouse-acceleration-implementation-plan.md) preserves
timed relative motion in capture, applies the curve once in the desktop Task,
checks loaded behavior and refreshes the OF816 preview. All four slices pass
development checks and the extracted-demo walkthrough, with pre-existing caret
artifacts recorded separately. Mild is now the default. Sampling cadence and
bank-zero reservations are unchanged; net reserved upper growth is 512 bytes.

The completed functionality milestone is an ordinary
[AES window application](plans/gem4xe/aes-window-app-design.md): a resident
counter using GEM window calls, durable `WM_REDRAW` delivery and a private VDI
workstation. The [WA1–WA6 plan](plans/gem4xe/aes-window-app-implementation-plan.md)
first establishes delivery and window ownership, then proves delegated display
access before direct application drawing. It finishes with two independent
applications beside the native shell and an optional OF816 demo. The implemented
profile keeps the existing Task/layer limits and targets zero bank-zero growth;
menus, resources, resizing and broader GEM compatibility follow.
[WA1–WA6](history/aes-windows.md) pass development checks for durable GUI delivery,
window ownership, delegated display access, private application VDI and two
ordinary GEM counters, with unchanged ordinary message capacity and zero
bank-zero growth. Matched native/coexistence diagnostics and the extracted
OF816 counter bundle pass. PI4/HY4 remain open.

The [AES application input milestone](plans/gem4xe/aes-application-input-design.md)
provides keyboard and single-button events for ordinary GEM application content, combined
locally with messages/timers. The design keeps one presenter for focus and
gesture routing, preserves shell cancellation, and adds zero bank-zero
reservations without per-wait RPC. The [AI1–AI7 plan](plans/gem4xe/aes-application-input-implementation-plan.md)
provides seven executable slices through a two-application OF816 demo, committing
after each passing slice. AI1–AI7 pass development checks: public input waits, independent
interactive apps, native coexistence and the extracted OF816 ZIP.
[Cost measurements](history/aes-application-input.md#ai7--coexistence-measurements-and-packaged-demo)
show that redraw/presentation dominates button feedback; PI4/HY4 remain open.
Rectangle events and multiple clicks remain follow-on work; public widgets/forms
and resource loading are covered by the desktop application milestone below.

The [desktop rendering design](plans/gem4xe/desktop-rendering-design.md)
is implemented through the
[DR0–DR7 plan](plans/gem4xe/desktop-rendering-implementation-plan.md), with smaller
damage sets, IRQ-completed top-window copies, reduced background overdraw and
two optional VRAM snapshot slots. It keeps one presenter, adds zero
bank-zero reservations and leaves partially obscured scrolling on retained
redraw. [Development measurements and the refreshed preview](history/desktop-rendering.md#dr7-combined-measurements-and-local-preview)
pass correctness checks; pointer, outline and move-repair latency acceptance
remains open.

[AES widgets](plans/gem4xe/aes-widgets-implementation-plan.md) are implemented
through AW6 at the development tier. Selected GEM4XE object, drawing and form
routines run in the existing presenter, with retained trees, bounded patches
and event-driven interaction. The optional desktop now includes an independent
Control Panel; [interaction measurements and the packaged walkthrough](history/aes-widgets.md)
pass correctness checks while widget-feedback latency remains open. Long
clipped drawing calls and scene-token waits need focused follow-up. Existing
Task/stack pools and window layers are reused. The library can later support a task bar; desktop work-area,
window-switching and launcher policy are separate work. Editable fields and
full AES compatibility remain deferred.

The [desktop application milestone](plans/gem4xe/desktop-facilities-implementation-plan.md)
now provides application-owned widgets/forms, a GEM Control Panel, classic
resources, windowed popup menus and a Files browser beside the counter and shell.
The [loadable GEM applications](plans/gem4xe/loadable-gem-applications-implementation-plan.md)
work moves the shared GUI payload to `GEMSYS.BIN` and the panel, counter and Files
to separate APP files. Program/Process owns each private C image; Files can launch
native commands or a GEM child, while the shell collects closed initial apps
through existing completion signals. Caller-local AES/VDI execution and the
bank-zero reservation remain unchanged. The final cartridge/package checks are
recorded in the [LG6 development results](development/loadable-gem-lg6.json):
both Atarimax variants pass, with 56,444 bytes of cartridge headroom.

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
  [SYS: alias](reference/sys-volume.md) and [directory assigns](reference/assigns.md).
- Longer shell pipelines and background job control beyond the current
  [two-command foreground pipeline](guides/shell.md) and the implemented
  [single background job](guides/shell.md#one-background-job).
- Regular expressions beyond the implemented [command toolbox](guides/toolbox.md),
  [writable commands](history/write-commands.md) (COPY, TEE, DELETE, RENAME, MAKEDIR), and
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

- **Arithmetic in latency-sensitive paths.** Measure software multiply,
  divide and remainder helper calls in the optimized presenter and timer paths
  before attributing GUI delays to them. First candidates are the
  [layer-selection counter](../lib/desktop/deskpaint.act) (`MOD 5`, currently
  a 16-iteration helper), [console cursor coordinates](../lib/console/consoledisplay.act)
  (separate division and remainder on the same operands), and repaint row
  offsets (`row*width`). Consider bounded increment/wrap, shared coordinate
  calculation and incremental row offsets. Also audit caller-side deadline
  conversion and relative timer submission; preserve PAL/NTSC rounding and
  overflow behavior. These conversions are outside native interrupt expiry.
  General compiler improvements, including constant multiplication such as
  timer open-record indexing by 24 and reuse of quotient/remainder work, belong
  in actionc with focused regressions. Avoid Exec-specific compiler workarounds.
  Compare any resulting GUI improvement against the unchanged HY4 limits;
  the arithmetic contribution to the measured presenter delays is still unknown.
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
