# Background commands console panes and primes

Status: implemented in F0–F4 and P1–P2. The reusable foundations landed first,
followed by the prime demonstration as a loadable `C:PRIMES` command. The default bitmap
shell still starts with the full screen available and no primes Process.

Follow the current [Process](../reference/process.md),
[program loading](../reference/program-loading.md),
[console](../reference/console.md),
[console instance](../reference/console-windows.md),
[cancellation](../reference/foreground-break.md),
[platform](../reference/platform.md) and
[testing](../contributing/testing.md) contracts. The linked references describe the current public interfaces; the slices below
preserve the implementation sequence.

Slice progress and development evidence are recorded in the
[implementation record](../history/background-pane-primes.md).

## Intended behaviour

- `PRIMES` runs as a foreground command in a lower console pane. BREAK stops
  it and returns to the shell.
- `RUN PRIMES` starts a background Process and returns the prompt. Keyboard
  focus stays with the shell.
- On the bitmap display, the shell occupies 80 by 24 cells and primes the
  lower 80 by 6. The text display uses 40 by 18 plus 40 by 6.
- `JOBS` shows the one background job, its Process identity and state.
  `BREAK job` requests cooperative cancellation using that identity.
- Closing the pane restores the shell's full height. This works while the
  shell is waiting for input, including a partially edited line.
- `PRIMES PASSES 1` finishes after one sieve pass. With no PASSES option,
  calculation continues until cancelled. `RUN PRIMES PASSES 1` exercises
  natural background completion.

Start with one background job and one lower pane. RUN accepts one loadable
command, using existing aliases, PATH lookup, quoting and argument bounds.
Background pipelines, running built-ins, foreground/background promotion,
forced termination and jobs surviving shell EXIT are outside this slice.
The pane is a full-width tile, without framing, dragging or overlapping.
The existing desktop profile remains separate; reject pane creation there.

## Ownership and public operations

The shell owns the background Process record and collects its result. The
command owns its pane and output handle. The console service owns tiling,
retained cells, drawing and restoration of the parent console. The shared
console worker remains the sole drawing owner.

A command closes its pane before returning. The Process DOS finalizer also
closes an owned pane if Main returns without closing it. Pane closure restores
the parent before the child's kernel retirement acknowledgement. Consequently,
screen restoration does not depend on the shell waking from a cooked Read.
Loaded code remains retained until ordinary Process collection.

Use the permanent default console as the initial pane host. It must be visible
at the full display size with no existing docked pane. Default-console control
is already allowed to application Tasks; created instances retain their
creating-Task ownership. General docking into arbitrary application consoles
is deferred. A rejected open leaves the current layout intact.

Add these reusable interfaces through machine-readable ABI inputs and their
generators, with final signatures frozen in F0:

| Interface | Proposed contract |
| --- | --- |
| `COMMAND.WriteAt(handle,column,row,bytes,length)` | Synchronously write one printable horizontal span into a console. Return the committed byte count, or failure with IoErr. Preserve the stream cursor. |
| `COMMAND.OpenPane(rows)` | Return an owned console FileHandle for a lower pane, or NULL with IoErr. Shrink the default console and preserve its input route and focus. Ordinary Close retires the pane and restores the parent. |
| `COMMAND.Delay(ticks)` | Wait for the requested VBI ticks using timer.device. Return success, or failure with IoErr after exact reply collection. Cancellation is cooperative and interruptible. |
| `PROCESS.StartBackgroundLoaded(image,args,length)` | Start a retained loaded Image with an independent cancellation scope, without borrowing or suspending the parent's foreground scope. Return the existing Process identity. |
| `PROCESS.RequestBreak(identity)` | Request cancellation of an owned child. Latch an early request through child setup; repeated requests coalesce. Completion already committed retains its result. |

Reuse `PROCESS.Collect` and `Wait`; do not introduce a job registry or reaper
inside the kernel. New command providers do not expose Task creation, private
driver records or callbacks into loaded code. Use public Exec primitives for
coordination and keep console/timer policy in their existing libraries and
drivers. No pane-specific COP service is needed.

## Foundation implementation

### F0 Baseline and interface definitions

Record the current Exec revision and outstanding timer-listing changes, the
compiler revision from [actionc.json](../../toolchain/actionc.json), and the
actual ROM, emulator and configuration used by the bitmap demo. Preserve one
matching baseline build for memory and drawing comparisons.

Freeze the provider signatures, console request encoding, pane lifetime and
background cancellation fields. Check the existing 1,664-byte provider manifest
reservation, export count, existing eight-Task capacity and signal requirements.
Keep one current ABI and rebuild consumers whenever it changes.

Measure the baseline's reserved bank-zero bytes, upper reservations, shell
storage, loaded-image backing and actual Task occupancy. Foundation changes
target zero additional bank-zero reservation; active jobs use existing stack
and direct-page slots. Record requested and rounded upper storage separately.

Deliverable: generated-interface changes and a bounded development fixture
design, with the memory baseline recorded. This step does not run a release
qualification matrix.

### F1 Positioned console writes

Extend console device I/O with a positioned-write command using the existing
IOStdReq and FIFO write queue. Define its command and coordinate encoding in
the ABI input; do not add an escape-sequence parser. Provide a DOS adapter and
the checked `COMMAND.WriteAt` provider through
[abi/program.json](../../abi/program.json) and
[generate_program.py](../../tools/generate_program.py).

Accept printable ASCII contained within one row. Reject unsupported controls,
negative lengths and spans outside the current geometry before editing cells.
Zero-length writes are harmless. Retain the caller's buffer until the exact
terminal reply, including cancellation and hardware-error paths.

The worker edits retained cells directly at the requested position, mapping the
circular row origin correctly. It does not change the ordinary stream cursor,
wrap, scroll or clear the instance. Mark only the affected row span. Existing
damage aggregation and bounded drawing remain in use. Partial cancellation
reports the accepted prefix without promising atomic field replacement.

Focused validation: positions at row edges, far buffers, unchanged cursor,
independent row damage, queued ordering, cancellation and exact collection.
Use optimized emitted code plus one small raw provider-layout probe. Check
physical bitmap drawing of a changed field with the existing drawing observer.

### F2 Height changes and owned lower panes

Add a console-library height operation for unchanged-width instances. Keep
the existing backing capacity so an instance can shrink and grow back without
a second screen allocation. Record allocation capacity separately from the
active cell count; freeing must use the original allocation size. Growth
outside that capacity is rejected in this slice. Width changes and reflow are
deferred.

Use the existing presentation transaction to drain worker borrows and settle
pending DMA/scroll work before changing geometry. Preserve instance identity,
open endpoints, pending input, cooked sessions and captured input routes.
Do not reinitialize an instance through CONSOLECORE.Init. Scheduling and
interrupts remain enabled during waits and cell moves; use only the established
short publication exclusions.

Normalize circular rows using at most one row of upper-RAM scratch. On shrink,
retain a range containing the cursor and active input line, discarding older
rows above it only when required. Adjust row/line offsets without changing the
column. On growth, retain rows in place and append blank rows. Discarded screen
rows do not become scrollback. Damage the resized view once after publication.

Implement lower-pane acquisition and restoration as one bounded console
operation. Allocate the child instance and DOS wrapper before publishing the
split; unwind allocation or admission failures without leaving a smaller shell.
The lower instance uses existing ownership and opaque-unit rules. Keep a single
layout association until the lower instance has retired and the parent's height
is restored. Other conflicting presentation operations report busy.

`COMMAND.OpenPane` returns a normal owned output handle with pane-retirement
metadata in the DOS ownership ledger. Close waits for its borrowed I/O and
presentation work, closes the binding, erases/retires the lower instance and
restores the parent before releasing the owner's last lease. Main's normal
return also reaches this cleanup. Preserve the first causal error across it;
do not forcibly free DMA or requests after a device failure.

Relevant implementation: [console.act](../../lib/console/console.act),
[consoletiling.act](../../lib/console/consoletiling.act),
[consolecontrol.act](../../lib/console/consolecontrol.act),
[consolecore.act](../../lib/console/consolecore.act), DOS stream cleanup and
[abi/console.json](../../abi/console.json). Edit generated layouts through
their generators.

Focused validation: text and bitmap geometry, wrapped row origins, cursor near
the bottom, open/close during an active cooked Read, typed draft preservation,
second-pane rejection, allocation failure and cleanup after a returned error.
Check that input captured before a geometry change keeps its original route.
Include a pending drawing completion and normal ownership/stack guards.

### F3 Background cancellation and interruptible delay

Add StartBackgroundLoaded using the existing Process trampoline, image
retention, stream cloning and kernel-acknowledged retirement. Give each
background child a private DOS cancellation scope and signal without binding
it to the shell's keyboard route. BreakPending and interruptible DOS operations
must observe it. The parent remains free to read and run foreground commands.

Use the four reserved bytes at the tail of the 128-byte Process row for a
pending-cancellation byte and the published scope pointer, subject to generated
layout checks. Keep the row stride and existing Task pools. RequestBreak is an
ordinary reusable Process operation restricted to an owned child identity.
Publish, signal and retire the scope under the documented Task-side protocol;
IRQ/NMI handlers do not inspect these pointers.

Cover cancellation before adoption, during scope publication, while waiting,
and concurrent with normal completion. Clear the published pointer before
freeing its scope. A stale or foreign Process identity cannot cancel a reused
slot. A retired child is collected normally; cancellation cannot change its
saved result or release its retained Image early.

Implement Delay in the DOS/COMMAND library over timer.device clock and absolute
wait requests. Keep one lazily acquired timer binding per participating DOS
context, with owned request/port storage in upper RAM. Abort and collect the
exact alarm on BREAK before returning. Context cleanup closes the idle binding
and frees its resources. There is no busy-wait, extra timer Task or callback
into the loaded image.

Update [abi/process.json](../../abi/process.json), its generator, Process/DOS
adoption and cleanup, and the program-provider definitions. Keep existing
foreground loans and two-member pipeline groups intact.

Focused validation: parent input stays usable, inherited file positions and
directory ownership, cancellation at setup/wait/retirement boundaries, natural
completion, reuse and allocation rollback. Cover an actual timer wait and its
abort/collection path; small raw probes cover new ABI shapes, not full duplicate
system scenarios.

### F4 Shell launch and bounded job collection

Add RUN, JOBS and BREAK built-ins in a small shell include. Reserve one job row
in upper RAM, targeting at most 64 rounded bytes. Use the Process identity as
the job identity; do not keep raw Task pointers or invent another ID allocator.

RUN resolves the target as an ordinary loadable command and copies its argument
tail through existing helpers. Default Input and Output are NIL so background
I/O cannot consume or overwrite prompt editing. Explicit file/NIL redirections
use ordinary stream inheritance; reject interactive background Input/Output
and pipelines before publishing the child. A graphical command opens its own
pane rather than receiving special handling by command name.

Restore the shell's selected streams and close temporary wrappers immediately
after launch. Release its Image reference only after StartBackgroundLoaded has
retained execution ownership. Admission failure publishes no job and unwinds
all temporary resources. A second active job reports a normal capacity error.

JOBS lists running/stopping or the latest collected result. BREAK requests stop
and returns the prompt; the child settles its I/O and closes its pane. Poll with
existing Collect at command boundaries and before admitting another job, treating
the documented not-yet-retired result as normal. Print completion diagnostics
at a safe prompt boundary, without interrupting a typed draft or replacing the
foreground command's result.

While the shell is idle, a completed child's Process/Image may remain retained
until the next command boundary. This is bounded to one job. Its pane is already
closed by child cleanup, so screen restoration is immediate without a reaper.
EXIT requests stop, waits for and collects the job, then performs normal shell
shutdown. Uncooperative commands can delay EXIT; forced removal is unsupported.

Focused validation: PATH/alias and quoted argument reuse, RUN/stop/restart,
natural completion while a line is being edited, file redirection, a foreground
command alongside the job, and EXIT with running/retired children. Exercise
task-capacity rejection and two-stage foreground-pipeline admission within the
actual available slots. Confirm foreground BREAK does not cancel the background
job and stale completion signals cannot affect its successor.

## Primes implementation

### P1 Loadable calculation and numeric field updates

Implement `examples/commands/primes.act` against the completed providers. Use
the existing sieve algorithm in
[demo-session.inc](../../examples/demo-session.inc), bounded to 10,000, with
one bit per candidate: 1,251 payload bytes. Keep its state in private loaded
image data/BSS. Use ReadArgsOrHelp with `PASSES/K/N`; zero or omitted means
continuous operation. Positive values count completed passes.

Open a six-row pane before calculating. Draw the separator, title and labels
once. Use this layout for both supported widths, with numeric fields beginning
at column 10:

| Pane row | Static content | Numeric field |
| --- | --- | --- |
| 0 | Full-width separator | None |
| 1 | PRIME SEARCH | None |
| 2 | Primes | 5 characters |
| 3 | Latest | 5 characters |
| 4 | Pass | 10 characters |
| 5 | Blank | None |

Put one counter on each row because the existing damage model combines edits
into one span per row. Keep count/latest as CARD and pass as LONGCARD. Format
with the existing compiler-owned `STR.u32toa` primitive and pad each field to
its fixed width. Compare against the last successfully displayed values and
issue WriteAt only for changed fields. This includes pass resets and shorter
numbers. Update the saved values only after the complete field write succeeds.

Use bounded calculation batches, initially 100 candidates, with cancellation
checkpoints inside longer marking/clearing loops. Delay one VBI tick between
batches. Refresh at most once per ten batches, plus initial/final values: at
most about five updates per second on PAL or six on NTSC before computation
and drawing cost. Calculation and painting remain separate routines.

An ordinary refresh sends at most 20 numeric characters in three positioned
writes. Unchanged fields produce no write. It sends no FF, newline, labels or
full-pane frame, and does not manipulate the stream cursor. Exposure and layout
changes repaint through retained console contents. Initial pane creation and
resizing may repaint complete views.

On completion or cancellation, close the pane and return through the ordinary
Process wrapper. Preserve ERROR_BREAK or the earlier device error through
cleanup. Keep all borrowed buffers alive until their terminal replies. Do not
install a prime-specific shell command, driver callback or kernel service.

Focused validation: one complete pass produces 1,229 primes and latest 9,973;
pass transitions and stop preserve the independent expected results. Check
digit growth/shrink, unchanged values and failures after partial field writes.
Compare retained cells and physical damage: normal updates touch only the three
numeric spans, leaving the separator/title/labels untouched. Check cancellation
while calculating, delaying and writing, plus full-height prompt restoration.

### P2 Shared demo command and screenshot package

Add PRIMES to [build_demo.py](../../tools/build_demo.py)'s command set and `SYS:C`.
Refactor the optional automatic-primes demo to launch the same loaded command
through the foundation. Remove its resident sieve, complete-frame refresh loop
and duplicate prime-lifetime implementation. The shell-only bitmap selection
continues to start without primes; users choose RUN PRIMES themselves.

Update command/shell/console/Process references and guides when their changes
land, along with affected fixtures and indexes. Record the actual upper-RAM
and code costs, drawing requests and byte counts, cancellation observations,
and the source/compiler/ROM/emulator hashes. Existing timer-listing edits are
separate work and must be preserved.

Build a matching bitmap shell preview with the new command, system/work disks,
OF816, five-second autoboot, pinned ROM, guides, licenses and checksums. Use
`tools/build_demo.py`; keep intermediates and evidence outside `exec816-demo.zip`.
Existing cartridge augmentation can package the same XEX for a later release.

Run one focused integration session through RUN PRIMES, normal shell/file
commands, a partially edited prompt, Ctrl-L, BREAK, restart, finite completion
and EXIT. Reuse the current nominal 57.6k disk profile and its recorded bounds.
Report the development scope; this does not qualify release images, hardware
or the unrelated desktop/transport latency gates. Screenshot-only refreshes
after the focused checks need builds, not repeated test matrices.

## Memory and completion criteria

All slices target **0 additional fixed, root/kernel, idle, loading and per-Task
reserved bank-zero bytes**, counting guards, alignment and unused capacity.
Reusing a Task slot consumes existing capacity rather than creating a new
stack/DP reservation. Report the actual delta for every implementation slice.

Account separately for the bounded upper-RAM job record, pane cells and
metadata, height/capacity and layout fields, row scratch, private cancellation
scope, cached timer objects, providers, and the complete loaded Image including
its alignment slack. Preserve existing Process-row and provider reservations
where they fit; record any required upper reservation change rather than
silently enlarging it. Pane creation adds one instance, not another worker.

Implement and commit F0 through F4 before P1/P2. Each slice must demonstrate
its behaviour with focused development checks before adding the next consumer.
Optimized emitted-code checks are the default; raw checks are limited to new
ABI/compiler-facing shapes. Documentation edits need content and link checks;
full qualification remains a release task or an explicit request.

The work is complete when the default shell uses all 30 bitmap rows, RUN PRIMES
opens the six-row lower pane while the prompt remains usable, only changed
numeric fields are repainted, and stop/natural completion/EXIT release all
owned resources and restore the shell. Keep one current implementation and
leave arbitrary-window docking and larger job-control features for later work.
