# Console input/output implementation plan

Status: all eight initial-console slices complete, 2026-09-21. See the
[implementation record](../history/console-io-implementation.md) and
[integrated qualification](../qualification/console-concurrency.json). The
[console design](../reference/console.md) defines the interface, platform ownership,
Amiga deviations and required future support for independent text windows.
This plan delivers its first usable full-screen console in eight executable
slices, with a separate commit after each slice. The required multiwindow
follow-up is listed separately below; completing the first eight slices does
not complete that future capability.

The result is a resident `console.device` using ordinary Exec I/O requests,
one worker, native keyboard capture and a retained text buffer in upper RAM.
It works while native SIO and MyDOS run and has the instance/presentation
separation needed by future windows. It does not require an application binary
format, executable loader, complete shell or DOS `CON:` handler.

## Baseline and working rules

Use [actionc.json](../../toolchain/actionc.json), currently compiler revision
`c2268b7c742958bd9078c4e11ef9b10f3b7a0221`, native ABI
`action65816.native.v1` and image format 2. Start with the
[queued SIO pin](../../toolchain/altirra-sio-queued.json) and
[256-byte sector pin](../../toolchain/altirra-sio-sectors.json). Record ROM,
emulator, observer, compiler, machine and media hashes for executable evidence.
Do not silently switch to a newer compiler or interpret source inspection as
hardware qualification.

The [current SIO completion record](../qualification/sio-fast-completion.json)
and [sector qualification](../qualification/sio-sectors.json) are the regression
baseline. Clean transfers have no mandatory OS-service sleep. Preserve that
behavior, error recovery and unsafe-bus fail-stop. Console progress must not
depend on ROM stage-two VBI or a gap between successful sectors.

Follow the [platform contract](../reference/platform.md),
[critical-section protocol](../history/kernel-critical-sections.md) and
[bank-zero rule](../reference/platform.md#bank-zero-memory-budget). IRQs capture
events and directly notify the known worker; task context translates input,
updates console cells, draws and replies. No public port call, allocation,
window/Task search or rendering belongs in IRQ/NMI. Preserve COP `$50`/`$00`,
full context, direct-page ownership and asynchronous NMI safety.

For each slice, run its relevant checks, update this plan's status and add an
entry to `docs/history/console-io-implementation.md`, then commit before the next major
slice. Record commands, results, artifact hashes, maximum stack use and complete
memory reservations. Failed probes can be committed as evidence, but their
gates stay failed. Do not create passing qualification records in advance.

Test compiled behavior through emitted raw and optimized code. Use host tests
for generation, map validation and trace/result parsing; they do not replace
machine execution. Compiler defects belong in actionc with focused regressions
and a recorded pin update. Emulator correctness fixes belong in actionc-vm;
changes needed in the pinned Altirra backend must also be recorded explicitly.
Keep one current implementation; no compatibility profiles or successful stubs.

Keep the console unavailable in ordinary builds until slice 6 completes service
lifetime. Earlier slices use explicit test fixtures and must restore everything
they claim, even on failed admission. Slice 6 makes the completed device
available through an explicit console build option; leave existing headless
builds unchanged. Slice 8 qualifies the integrated workload.

## Sequence and dependencies

| Slice | Executable result | Suggested commit |
| --- | --- | --- |
| 1. Keyboard/SIO gate | Real key events coexist with continuous FASTEST125 transfers and recovery | `Probe native keyboard and SIO coexistence` |
| 2. Instance state and terminal core | Generated layout and independent retained cells execute without hardware drawing | `Implement console instance state and terminal core` |
| 3. Native input delivery | Keyboard/BREAK IRQs feed a bounded ring, direct worker wake and translated FIFO | `Implement native console input delivery` |
| 4. Device requests and worker | READ/WRITE/CLEAR, quick/replied completion and cancellation work through Exec | `Implement queued console device requests` |
| 5. Native screen presentation | Dirty cells and cursor render to the borrowed text screen and restore it | `Implement native console screen presentation` |
| 6. Service lifetime and publication | Configured startup, rollback, close/reopen and coordinated shutdown are safe | `Complete console service lifetime and publication` |
| 7. Resident DOS example | Interactive console I/O works alongside a real MyDOS read | `Add resident console and DOS example` |
| 8. Integrated qualification | Eight live tasks pass console correctness and existing SIO timing gates | `Qualify console I/O under concurrent SIO and DOS` |

Execute in this order. Slice 1 is the first gate: resolve shared POKEY behavior
before committing to the full device path. Slice 2 defines the state used by
slices 3–5; slice 4 joins input and the terminal core; slice 5 adds physical
presentation. Slice 6 enables ordinary configured use only after those pieces
and their teardown are complete. Slices 7–8 establish end-to-end acceptance.
An unresolved coexistence gate must not be hidden by a test input backend or
stock-speed-only results.

## Repository integration

New paths are proposed; create them in their owning slices. Reuse the existing
generic I/O API rather than adding another public gateway or request layout.

| Location | Work |
| --- | --- |
| `abi/console.json`, `tools/generate_console.py` | Console error constants, private instance/service/ring layout and shared Action!/assembly definitions. Reuse `abi/io.json` for IOStdReq and standard commands. |
| `lib/console/consolecore.act` | Instance-oriented character/control processing, retained cells, cursor and bounded scroll state. No screen or POKEY access. |
| `lib/console/consoledriver.act`, `lib/console/task-console.inc` | One worker, protected device dispatch, per-instance read/write state and resident lifetime. |
| `lib/console/consoleadapter.act`, `platform/altirraos/console.s` | Checked native input/display operations, hardware claim/restore and IRQ entry. Keep bulk drawing outside protected policy. |
| `lib/io/task-io.inc`, `lib/io/iocore.act`, `tools/generate_io.py` | Recognize the resident and reuse existing calls, validation, collection and replies. Console Open must not lazily allocate its worker. |
| `platform/altirraos/signal-irq.s`, `lib/exec/task-wakes.inc`, `platform/altirraos/sio.s` | Independent console binding, shared bounded post logic and explicit keyboard/serial ownership. Preserve existing SIO paths. |
| `lib/exec/taskpolicy.act`, `lib/dos/task-dos.inc`, `lib/io/task-sio.inc` | Worker admission/removal protection and service-aware shutdown; remove assumptions that only SIO and DOS can be resident workers. |
| `tools/native_program.py`, `tools/generate_tasks.py`, `config/kernel.json` | Explicit console enablement, generated startup/entry bindings, upper-RAM reservations and build provenance. |
| `platform/altirraos/hosted.s`, platform map generation | Reject conflicting ROM console calls while native console ownership is active; check callback space and screen extents. |
| `tests/programs/native_console_*.act`, `tools/test_console_*.py`, focused host tests | Emitted fixtures, keyboard injection, screen/cell checks, fault cases and bounded trace analysis. Existing `console_inputs.act`/`console_bounds.act` remain ROM-adapter tests. |
| `examples/console.act`, documentation and qualification records | Resident example, usage, implementation evidence and explicit unsupported behavior. |

Private worker handoffs must use the existing protected-policy mechanism or a
small generated private extension of it. Keep them inaccessible to ordinary
applications. Do not implement a new resident-device framework or generic
window system merely to dispatch the second production device.

## Slice 1: keyboard and SIO coexistence gate

Use a minimal native fixture with a client and the existing SIO worker. Hardcode
one upper-RAM event ring and a known notification target. The client can wait
on serial replies OR keyboard notification while draining both durable queues.
Skip console OpenDevice, the full keymap, screen rendering and window APIs.

- Inject press/release, modifiers, held keys and BREAK through the emulator's
  actual keyboard scan path. Establish the expected raw events first with SIO
  idle. Writing ROM `CH`, a console FIFO or IRQ result registers is not a
  hardware keyboard test. Pin and record the injection method and event timing.
- Repeat during back-to-back 128/256-byte FASTEST125 reads, with injection at
  SIO setup/reset, serial phases, retirement and recovery. Include simultaneous
  serial/keyboard sources, native IRQ entry and the emulation callback path.
- Audit `SKCTL = 0`, later `$23`/`$13` writes, `SKREST`, IRQEN/shadow merges and
  both service claim/release orders. Capture shared error state before clearing
  it. Resolve lost or duplicated keypresses in the native ownership/reset path;
  make the smallest necessary SIO change and retain its existing error policy.
- Measure combined IRQ occupancy and masked intervals. If tracing or keyboard
  control needs a backend change, pin it and preserve an unobserved replay.

**Acceptance:** raw and optimized fixtures receive the expected key events
below ring capacity without phantom held-key repeats, preserve unrelated state
on safe release, and pass the existing serial byte/phase timing and data checks.
Re-run relevant SIO recovery tests for any changed reset/error path. No new
successful-transfer sleep, ROM polling fallback or relaxed timing threshold is
allowed. A failure keeps dependent hardware integration blocked for redesign.

**Evidence:** `docs/qualification/console-coexistence.json`, including raw event
sequences, injection checkpoints, both entry modes, timing and replay hashes.
This small probe does not qualify the eventual console worker or eight tasks.

## Slice 2: instance state and terminal core

Define generated private service, instance and presentation records. Freeze the
64-slot raw event layout, byte-index publication convention, 128-byte input
FIFO, `CONERR_INPUTOVERFLOW = 1`, cursor, queue and dirty-region storage. Place
state in upper RAM relative to the configured kernel bank or in admitted heap
allocations; keep ownership explicit. Record exact allocations and reservations.

Implement instance-based processing of printable bytes and the design's BS,
HT, LF, FF and CR behavior, wrapping and scrolling. Unsupported controls and
high-bit bytes follow the documented subset. Process at most 64 source bytes
or 40 cells of a scroll per quantum. Finish a logical scroll before processing
the next source byte. Do not retain caller buffers in a pending redraw.

Use a 960-byte retained cell buffer for the initial full-screen instance, with
cursor state outside the cells. Make width/height instance properties and
validate dimensions and cell extents with widened arithmetic. No output path
in this core may address the physical screen.

**Acceptance:** emitted raw/optimized layout probes agree with generated
offsets and the unchanged 42-byte IOStdReq. Terminal fixtures compare final
cells, cursor and consumed counts with explicit expected results, including
boundary controls and multi-quantum scrolling. Exercise two small private
instances with different dimensions and interleaved writes to catch global
state leakage; this is a core isolation test, not a public multiwindow API.
Package checks reject overlapping reservations and invalid extents in kernel
banks 1 and 3. All stack/domain and buffer guards survive.

**Evidence:** `docs/qualification/console-core.json`, with layout, isolation,
control-byte, progress and storage results.

## Slice 3: native input delivery

Promote the proven capture/ownership path into the console adapter. Add an
independent upper-RAM worker binding while sharing the direct-post algorithm;
never replace the serial binding. Extend routing for keyboard/BREAK without
adding Task scans, another worker or per-Task signal reservations.

Publish complete event slots before their head index. The worker copies before
releasing the tail. Use a coherent native tick snapshot across NMI entry;
NMI does not produce ring entries. Bind before enabling sources, and disable,
retire callbacks and drain pending wakes before releasing state. Test fixture
teardown and failed claim rollback are required in this slice already.

Implement the fixed keymap, modifiers, Caps Lock, Return-to-LF, BS, Tab, Escape
and Ctrl-C/BREAK bytes. Debounce with captured ticks, independent of ROM `CH`
and stage-two VBI. Leave repeat and special-key sequences unsupported. Translate
into the instance FIFO, with defined drop-new/loss behavior for both software
overflow and detected hardware overruns; never silently overwrite input.

**Acceptance:** real native/emulation IRQs wake a waiting consumer while SIO
also posts to its own worker. Cover ring wrap, coalesced notifications, input
arriving at Wait publication, coherent timestamps, held keys, both overflow
sources, stop/post races and callback retirement. Controlled fixture injection
may test rare ring races but is recorded separately from hardware-key tests.
Check register/DP restoration, IRQ/NMI nesting and guards in raw/optimized code.

**Evidence:** `docs/qualification/console-input.json`. Repeat slice-1 timing
checks for changes to shared routing/posting; a synthetic signal alone is not
the keyboard acceptance result.

## Slice 4: queued device requests and shared worker

Add test-enabled resident dispatch and one worker over the actual generic Exec
calls. Bind opaque `io_Unit` to the default instance. Reject second opens of
that instance, unsupported full-width unit/flags, undersized requests and
invalid buffers/offsets according to the design. Do not add a public request
extension or another set of wait/collection rules.

Implement one pending nonempty read per instance and FIFO writes alongside it.
READ returns an available short prefix or waits; WRITE commits effects to cells;
CLEAR resets input/loss state without cancelling the pending read or clearing
the screen. Preserve Data/Length and report Actual. Test zero-length operations,
the rejected `$FFFFFFFF` write sentinel and genuinely bank-crossing buffers,
including a write longer than 64 KiB so length narrowing cannot pass unnoticed.

Keep protected entry points short and IRQ-permitting. The worker processes
input between output quanta and waits only with no runnable work. Nonempty
reads/writes reply once; quick completion is limited to allowed immediate
cases. Implement queued and active cancellation in the same slice, including
finishing an in-progress logical scroll and reporting the committed prefix.

**Acceptance:** raw/optimized public-call fixtures cover specific-request
collection, unrelated replies on a shared reply port, SendIO versus DoIO/quick,
input loss/clear ordering, FIFO writes, duplicate read rejection, and completion
versus abort races. A pending empty read must not stall another task's write.
Free or overwrite a source buffer after collection and prove later work uses
only retained cells. Every deferred request has exactly one terminal reply,
and the worker never touches it afterward. Use the real input path as well as
deterministic fixtures; physical screen presentation remains slice 5.

**Evidence:** `docs/qualification/console-device.json`, including exact request
states, actual/error values, guard results and bounded completion limits.

## Slice 5: borrowed-screen presentation

Validate the pinned GRAPHICS 0 display list, 40-by-24 screen extent, font and
hardware/shadow state before takeover. Reject an unsupported mode or unsafe
address without changing ownership. Save the existing 960-byte OS screen and
editor state separately from the console's retained cells; remove the ROM
cursor and restore all changed state on safe fixture shutdown.

Implement the presentation layer as the only writer of physical screen RAM.
Copy dirty cells with the explicit glyph map and draw a nonblinking cursor
overlay without changing retained text. Clip to the supplied presentation
bounds, initially the full screen. Bound each redraw quantum to 40 cells and
allow serial IRQs/preemption throughout. Audit retained ROM attract/color and
shadow updates rather than relying on CRITIC to suppress them indefinitely.

**Acceptance:** raw/optimized tests check the glyph table, controls, wrap,
scroll, clear, cursor movement and restoration against both retained cells and
screen RAM, with a visual capture for the pinned configuration. Redraw after
the request buffer is freed and after a fixture suppresses/resumes presentation;
write completion must not depend on presentation being visible. Input and
redraw progress under sustained output, with no long masked copy. An unrelated
screen/cell guard must never change. No successful ROM CIO call counts as this
display result.

**Evidence:** `docs/qualification/console-display.json`, including validated
screen addresses, mapping expectations, screenshots and restore comparisons.

## Slice 6: service lifetime and ordinary publication

Add explicit console enablement to packaging/provenance and a task-context
startup hook after root and memory initialization. Admit the worker through the
existing checked entry/context mechanism; a heap Task record alone does not
make a task admissible. Allocate its ports, signals, cells, input storage and
OS snapshot, complete hardware takeover, then publish device readiness.
`OpenDevice` only binds an available instance; unlike the current SIO-specific
lazy start in IOCORE, it must not allocate this worker.

Complete allocation/capacity/binding failure rollback. Close requires all
borrowed requests collected, clears input and permits reopening the default
instance without expunging the resident worker. Serialize closed-state input
discard and reopening with the producer. Reject conflicting `EXECOS.Write`
while the native console is resident, including when SIO is absent.

Update SIO/DOS last-client detection and worker-removal guards for the console
service. Workers waiting on each other must not keep the system alive after
all application clients retire. Keep this service accounting small; no general
service manager is required. Test root exiting before another live client.
At stop, reject new work, settle requests, stop sources and drain delivery,
restore shared hardware/display state, then release worker/resources. Do not
turn an outstanding client request into automatic unsafe task reclamation.

**Acceptance:** raw/optimized tests cover each acquisition failure, exhausted
task slots, closed input, close/reopen, abort/collect before close, last-client
exit and attempted worker removal. Test console-only, SIO-only and combined
configurations, both start/stop orders, and return to ROM after safe release.
Unsafe SIO still parks at `$FF93` with required ownership retained; require a
cleanup checkpoint so that an earlier fault cannot masquerade as expected
shutdown. Confirm no callback or redraw references freed memory. Disabled
console builds admit no console worker and preserve existing behavior.

**Evidence:** `docs/qualification/console-lifetime.json`. Enable the device for
ordinary explicitly configured builds only when this slice passes.

## Slice 7: resident console and DOS example

Add `examples/console.act` and reproducible build/run instructions. Demonstrate
separate read/write requests, asynchronous input, prompt/echo and a simple
bounded line buffer above the device. Use CR/LF and BS-space-BS consistently;
do not imply an editor can backspace across a wrap. Exercise a known MyDOS file
read and explicit ATASCII-to-console newline conversion outside DOS.

Use a separate client in the integration fixture to keep issuing console reads
while another client performs one large DOS Read. This demonstrates independent
task progress without promising that a shell blocked in DOS can process Ctrl-C.
Keep command parsing minimal: this example is not a complete shell, process
model, binary loader, `CON:` handler or window manager.

**Acceptance:** raw/optimized runs on 128- and 256-byte media verify actual file
bytes, console output, continued typing/echo, unrelated task progress and safe
cleanup. Exercise an ordinary DOS error while the console remains usable.
Record the first-open and steady-state worker counts; no task appears per
request, file, open or display operation.

**Evidence:** `docs/qualification/console-dos.json`, including source/image/media
hashes, interaction script, screen observations and client progress counters.

## Slice 8: eight-task and serial timing qualification

Run eight simultaneously live public Tasks plus private idle: console, SIO and
filesystem workers, a console client, a large-read client and three independent
kernel-work clients. Include a workload mixing allocator, message and signal
operations. Waiting tasks still count toward eight; sequential reuse is not
capacity evidence. Cover kernel banks 1 and 3 functionally in raw/optimized
code, with timing on the recorded bank-1 profile unless a different profile is
explicitly qualified.

Combine typing, wrapping/scrolling output and refresh with FASTEST125 reads on
128/256-byte media, including the single large file read. Also cover STOCK810
128-byte operation and the existing SIO TX/turnaround cases when exercising
shared IRQ routing. Preserve the assertions and bounds from
`tools/sio_concurrent_trace.py`, `tools/sio_adapter_trace.py` and sector tests;
record zero serial refill misses, verified payloads and phase timing. Replay
the identical image/input schedule with observation disabled. Do not substitute
a different program or change thresholds to make the console workload pass.

Measure keyboard capture-to-read-reply and input-to-visible-echo latency, output
progress, redraw progress, maximum masked/Forbid intervals and stack headroom
separately from the SIO byte deadline. Give each scripted interaction a finite
timeout and record it before execution. Report distributions/maxima instead of
claiming a new hard real-time keyboard guarantee from one observed run. A stalled
client, lost key below capacity or corrupt payload fails the workload regardless
of its average throughput. Record large-read throughput with the disk mechanics
setting explicit; this slice is not another broad throughput optimization.

**Acceptance:** all initial-milestone design cases pass with bounded completion,
safe shutdown or the expected independently verified fail-stop, intact guards
and unchanged-image replay. Include relevant regression checks for generic I/O,
signals, SIO recovery, DOS lifetime and the ROM adapter paths changed by this
work. Retest a wider component only when a change or unresolved failure warrants
it. Document the exact scope; no physical-hardware claim follows automatically.

**Evidence:** `docs/qualification/console-concurrency.json` plus a final
implementation-record summary linking all eight records and their commits.

## Memory and evidence accounting

The target is **zero added bank-zero reservation**, both fixed and per Task.
One console worker occupies an existing slot: 1,568 already reserved bytes in
the eight-task profile, including stack/DP, guards and padding. A typical
shell/root + console + filesystem + SIO configuration uses four of eight slots.
The final stress workload deliberately uses the remaining slots too.

The first console needs 960 bytes of retained cells, a separate 960-byte OS
screen snapshot, a 128-byte translated FIFO, 64 raw event slots and generated
service/instance/presentation metadata in upper RAM. Include the shared Task
record, ports, binding, tables, alignment and allocator overhead in the actual
accounting. Use the existing physical screen; no second bank-zero screen/font
or large stack-local cell array. Keep the compiler's 254-byte frame limit and
nested IRQ/NMI headroom in the measured stack budget.

For each slice, compare full loading/runtime reservations against the current
eight-task totals: 57,232 and 61,536 bytes including OS, respectively. Report
adapter growth even when it fits existing reserved space. If a callback or
worker cannot fit safely, update the design/map and justify the reservation
change before claiming the target met. Keep metadata/code/heap extents disjoint
for the selected kernel bank; do not assume unused bytes in an arena are free.

Use one `build/console-sliceN` artifact root per slice, with separate raw/opt
subdirectories and a compact tracked qualification record. Keep the inputs,
commands, hashes, bounded results and necessary traces/screenshots; avoid
duplicating compiler/emulator checkouts or restoring every historical run.
Follow [artifact restoration guidance](../history/build-cleanup.md) when an older result
is needed. Normalize host text before newline-sensitive parsing, preserving
binary screens, ATRs and ATASCII fixture bytes exactly.

## Required multiwindow follow-up

The initial milestone deliberately prepares this path without implementing a
speculative public Window ABI. After its qualification, execute these separately
specified stages, with their own executable slices and commits:

1. **Window binding and lifetime.** Define and document console creation,
   window selection at OpenDevice, ownership, geometry and admission limits.
   Bind requests through per-instance `io_Unit`, admit multiple instances and
   preserve the default-console path. Test independent queues/cursors/cells,
   hidden output, allocation failure and closing one instance while others run.
2. **Tiled presentation and keyboard focus.** Present multiple windows at once
   with clipping, dirty redraw and a focused cursor. Define the focus-change
   ordering with raw input before enabling it; already captured keys retain
   their destination, and closed-instance events cannot target a reused one.
   Test background pending reads, foreground input, exposure redraw and continued
   output without focus. Overlap, movement and resize/reflow need further design.
3. **Fairness and capacity qualification.** Rotate runnable instances at bounded
   quanta while keeping FIFO order within each. Stress a flooding producer,
   small writes in other windows, focus changes and SIO/DOS together. Measure
   per-console upper-RAM costs and progress bounds. Demonstrate multiple windows
   owned by one application, with no worker/stack/DP or physical screen per
   window and no IRQ-side window scan.

Keep those future stages visibly incomplete until their own evidence exists.
The two-instance terminal-core fixture in slice 2 and hidden-presentation test
in slice 5 prove useful boundaries; they do not qualify a multiwindow service.

## Completion boundary

The first milestone is complete when all eight slices pass, a resident client
can read native keyboard input and write native text during qualified SIO/DOS
work, and startup, request lifetime, shutdown and memory costs are documented.
Update README, roadmap, design status and implementation records together.
Keep multiple windows marked as required future work until the follow-up is
implemented. Do not mark shell, DOS console handles, executable loading,
12–16-task capacity or physical hardware complete as a consequence of this work.
