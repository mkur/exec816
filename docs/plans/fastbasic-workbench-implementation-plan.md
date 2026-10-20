# FastBasic GEM workbench implementation plan

Status: proposed, 20 October 2026. Implementation has not started.

[Design note](fastbasic-workbench-design.md) · [Plan index](README.md) ·
[GEM integration](gem4xe/README.md) · [Migration plan](fastbasic-6502-migration-plan.md) ·
[Current FastBasic contract](../reference/fastbasic.md) ·
[Testing policy](../contributing/testing.md)

Deliver `C:BASIC.APP`, a native 65816 GEM editor and controller around the
existing FastBasic integer/FP compilers and runtime. The first milestone is
**edit an unsaved buffer → Run → use output/input → return to the same editor
position**, including error navigation and Stop. This completes FB7. Source
debugging and native graphics follow as separately executable deliveries; the
complete workbench requires all three and final package acceptance.

Keep the design's language and ownership decisions. Do not port `editor.bas`,
replace FastBasic, implement GFA compatibility or enlarge BASIC addressing.
Changes to the native launcher, event waits, console windows and graphics must
be reusable public interfaces above Exec. Compiler changes belong in the
maintained source port under `ports/fastbasic/`; compiler/emulator defects belong
in their owning repositories with focused regressions.

## Sequence and dependencies

| Slice | Executable result | Depends on |
| --- | --- | --- |
| WB0 | Minimal loadable BASIC.APP and recorded resource baseline | Current FP delivery |
| WB1 | Editable document and undo model exercised through emitted code | WB0 |
| WB2 | Keyboard/mouse editing in a resizable GEM window | WB1 |
| WB3 | Open/Save/Save As with recovery and exact EOL behavior | WB2 |
| WB4 | Find/replace, indentation, colouring, procedure navigation and folding | WB3 |
| WB5 | Public C launcher with explicit streams, directory and independent console cancellation | WB0 |
| WB6 | Public combined AES/Exec event wait | WB0 |
| WB7 | Application-owned console window with interactive child and GUI control | WB5, WB6 |
| WB8 | Structured compiler diagnostics and immutable build artifacts | WB0 |
| WB9 | Complete editor/Check/Run/Stop/Build workflow and first FB7 package | WB4, WB7, WB8 |
| WB10 | Debug metadata and statement hooks from both compiler paths | WB8 |
| WB11 | Pause, Continue, Step Into, breakpoints and variable inspection in the IDE | WB9, WB10 |
| WB12 | Public retained graphics facade exercised by ordinary native clients | WB0 |
| WB13 | BASIC graphics commands, events and standalone execution | WB9, WB11, WB12 |
| WB14 | Final workbench docs, reproducible source delivery and exact-package acceptance | WB11, WB13 |

Follow this order for implementation and review. The dependency column identifies
which results must exist before a slice can run. Each row is a suggested commit
boundary after its development gate. Split an oversized row into smaller
executable changes without dropping its acceptance requirements. Update the
status and evidence after each passing slice.

WB0 should be a short setup slice with a runnable APP, not a separate framework
or broad qualification campaign. WB9 is the first useful integrated delivery.
Do not label WB9 as complete debugging/graphics support.

## Shared implementation rules

- Retain the pinned FastBasic/mini65 inputs and native toolchain contracts.
  Freeze working-source hashes as well as commit IDs; HEAD alone need not
  identify the delivered FP inputs. Preserve that work and its evidence.
  Use [upstream.json](../../ports/fastbasic/upstream.json),
  [actionc.json](../../toolchain/actionc.json) and the recorded Calypsi inputs;
  document any local override.
- Target **0 added fixed, root/kernel, per-public-Task and idle reserved
  bank-zero bytes in every slice**, including guards, alignment and unused
  capacity. Reuse existing Task pools and the 544-byte shared guest D pool.
  The native IDE uses one existing Task slot and one sequential child another;
  neither is an additional reserved stack/DP pool.
- Keep one current ABI. Generate shared records/constants, advance affected
  identities and rebuild providers, applications, compilers and fixtures
  together. Existing launcher convenience paths must use the same Process
  implementation, not an old signature or compatibility profile.
- Establish resources at open/load/start. Trust valid live caller-owned handles
  through dispatch; retain synchronization, IRQ/NMI guards and normal operational
  errors without adding repeated pointer/handle audits.
- Use ordinary Exec messages, signals and request retirement. Never retain
  UPDATE, physical display ownership, Forbid or a kernel/OS activation while
  waiting for a child, user input, debugger command or disk operation.
  Keep Exec COP #$50, OS #$00 and the WDC-reserved #$80–FF signatures unchanged.
- Keep public contracts in reference and usage in guides as behavior lands.
  Record measurements and actual scope under development/history; a plan or
  passing compiler test does not qualify the hosted system.

Paths named below for new modules, fixtures, formats and tools are proposed
locations. Existing source files are the starting points, not generated caches.

## WB0 Runnable application and resource baseline

Start `examples/gem-basic/` with `main.c`, an application model and a minimal
window/event loop. Build through `tools/build_c_program.py` and its ordinary
relocation checks. Launch through the existing Program/Process path, open one
window and private workstation, and close cleanly. Put application state in its
loadable image/upper heap, not resident GEMSYS globals.
Use the combined GEM desktop/guest build profile and smoke one known FBC/FBCI
shell command there; earlier bitmap-console evidence alone does not establish
that the combined profile is integrated.

Record current FastBasic compiler/runtime hashes, C/native provider inputs,
actual ROM/emulator configuration and a minimal desktop's available Task,
guest, AES, window and console slots. Include Image backing/alignment, native
stack peaks and free upper RAM. Use source pins and `memory.json` from the
selected build rather than copying historical stack sizes or ABI numbers.
Count space for both the IDE and its child on the normal demo. If other startup
applications occupy those slots, document which the user must close through
ordinary controls before Run; do not silently substitute a slim test desktop
or enlarge Task pools to make the packaged workflow pass.

Create a selectable workbench runner, provisionally `tools/test_fastbasic_workbench.py`,
by reusing APP packing, physical input, snapshot and ownership helpers. Keep
ordinary outputs under `build/fastbasic-workbench/wb0/` and corresponding slice
directories. Reuse passing baselines while their relevant input hashes match.

Gate: load/close/relaunch two copies at different placements on a capacity-suitable
fixture; verify private state, signed result, AES detach, heap/slot restoration
and guards. Also test a normal resource refusal on the target desktop. No menu
item should advertise an operation that has not been implemented.

## WB1 Editable document and undo

Add application-local `document.c/.h` and focused emitted C fixtures, following
the existing `tools/test_text_document.py` approach. Use actual application
routines in the fixture and independent expected byte strings/offsets.

Implement the design's 32,768-byte counted gap buffer, up to 4,096 editable
lines and 255 bytes per line, and 4,097 32-bit line offsets including the
sentinel. Represent empty input as one editable line and preserve an editable
trailing line after a delimiter. Track logical byte positions separately from
the viewport's tab-expanded columns. Reject unsupported source bytes explicitly.

Add atomic insert/delete/selection replacement and a 16 KiB undo/redo log
including metadata. Admit capacity before modifying text, discard oldest whole
undo groups when needed, and reject a single edit too large for that budget.
Keep dirty/snapshot generations and pending work separate. Bound large gap moves,
reindexing and search work while preserving a coherent model for repaint.

Gate: empty/full/one-past byte, line and line-length boundaries; first/last
positions; split/join lines; tabs; selections spanning lines; undo/redo and redo
invalidation; undo-capacity rollover; failed allocations and rejected bulk edits.
Exercise maximum gap movement and index updates through emitted code. Require
unchanged text on rejection, matching offsets, no out-of-bounds access and full
allocation return. Add a small raw/optimized layout probe only for externally
observed C/native fields.

## WB2 GEM editor window

Use the viewer's window, visible-rectangle and bounded-paint patterns without
turning TEXT.APP into an editor. Share a helper only when both applications
actually use it. Implement caret movement, insertion, deletion, selection,
Undo/Redo, vertical scrolling and horizontal caret panning. Choose supported
Atari shortcuts and keep all actions available in menus.

Obtain cell metrics and outer/work geometry through GEM. Preserve logical
caret, selection and top line across resize, move and focus changes. Use one
application-owned damage/paint continuation, at most four text rows per UPDATE
section, fresh visible rectangles after release, and local caret/selection
damage. Input loss cancels an in-progress pointer selection; it cannot commit
an edit from stale capture. Keep model and menu storage alive through AES detach.

Gate: physical keyboard and mouse editing, navigation across tabs/long lines,
drag selection, undo/redo, resize limits, partial-row clipping, overlap/exposure,
focus switching and close/relaunch. Compare cells/pixels against independent
source/selection expectations. Measure worst-case edit-to-scanout and peer
progress during a maximum-size edit; reduce/bound work before adding caches.

## WB3 File transactions and document replacement

Add a begin/step/cancel file job with at most 1 KiB per load/serialization unit.
Normalize LF/CRLF/CR/ATASCII internally and preserve uniform input delimiter and
final-EOL choice on Save. New documents save as ATASCII; mixed delimiters make
normalization a visible document change. Keep Open candidates separate and
publish only after checked EOF and terminal Close. Measure normalized capacity,
not the viewer's unrelated raw-file limit.

Implement Open/Save/Save As and New/Open/Quit Save/Discard/Cancel decisions with
the standard file selector. Respect `AES_PENDING` policy delivery before repair.
Retain selector fields separately from the committed path and reject overlong
paths instead of truncating them. Keep the current 127-byte application path
bound unless a separately tested public path change is necessary.

For Save, exclusively create an 8.3 temporary in the destination directory,
serialize a snapshot, and check every Write and Close. Publish a new target by
rename. For replacement, move the old target to an unused backup and rename the
completed temporary into place. Follow same-directory/no-replace Rename and
offline-mount rules; retain/report complete recovery copies on failure. Do not
claim atomic replacement. Commit Save As spelling only after publication; clear
dirty state only when the saved generation still matches the document.

Gate: exact file bytes for each EOL style, mixed EOL, empty/missing-final-EOL,
CRLF split between reads, maximum normalized source and overflow, unsupported
bytes, read-only/full/colliding media, positive short transfers, failed Close
and failed rename at each publication stage. Inject allocation/I/O/cancellation
failures and edits during Save. Verify recovery copies, old-document preservation,
dirty state, consumed-handle rules, exact heap/handle return and a subsequent
successful Save. Exercise RAM plus disposable SDFS/MyDOS media for their actual
mutation semantics.

## WB4 Editing assistance

Add Find/Replace, automatic indentation, lexical colouring, procedure navigation
and folding as bounded operations on the same document model. Recognize strings
and comments before keywords; keep classification independent of case/display
formatting. Preserve source bytes and use the compiler for semantic checking.
Replacing several matches is one undo group only when it fits the declared undo
capacity; otherwise reject it before mutation with an explicit capacity result.

Gate: keywords inside strings/comments, unfinished constructs, blank lines,
tabs, case variations, procedure names with common prefixes, folded selections,
undo after replace and navigation at document limits. Independently compare the
exported source before/after pure colouring/folding operations. Selecting a
diagnostic or future stop in a fold must reveal the exact destination. Publish
the standalone editor's supported controls and limits once WB1–WB4 pass.

## WB5 Public child launch and ownership

Start in `c/include/exec816/program.h`, `c/calypsi/dos.c`,
`c/calypsi/dos-bridge.inc`, `lib/dos/process.act`, its context/scope helpers and
the current generated C/Process ABIs. Extend the current C start interface with
one descriptor defining copied arguments, optional owned directory, selected
input/output and independent cancellation/console binding. Preserve normal
desktop NIL/shell defaults and update every caller on the single current ABI.

Expose ordinary Image load/reference release and starting a retained Image to
C callers where required by build/debug attachment. Reuse PROGRAM/PROCESS;
do not introduce another loader or language-specific Task dispatch. Document
whether a start accepts a path or an owned Image and who releases each reference.
The current path launcher already drops its temporary load reference after
Start; do not add a second Unload of that reference. Execution/collection must
leave no retained compiler Image or guest slot.

Prepare owned stream wrappers and directory copies, cancellation scope and the
console's input route before entry/publication. Keep the GUI parent's DOS/AES
context usable; a foreground loan which suspends it is insufficient. This new
DOS/Process contract is reusable by other graphical launchers and ordinary Tasks.
Use existing public Exec primitives and retain the IRQ/NMI transition protocol.

Gate: focused raw/optimized descriptor and return-layout probes, then optimized
native/C/FB65 children. Cover default launches, explicit file/NIL/private-console
streams, shared input/output wrappers, relative file operations, copied argument
lifetime, early BREAK and failure after every acquired resource. Verify parent
I/O remains usable, unrelated directories/streams do not change, first cause
survives cleanup, stale identities fail normally and collection occurs once.
Exercise capacity exhaustion and complete native/guest/Image reference recovery.

## WB6 Public combined event wait

Extend the public AES source binding and `c/calypsi/aes-events.c` so a caller
can wait for selected GUI events plus a caller-owned Exec mask. Freeze the
extension's input/result layout in generated definitions; preserve ordinary
GEM `evnt_multi` semantics. Return external readiness without consuming messages,
collecting children or freeing borrowed completion signals.

Use one readiness/recheck/wait protocol covering arrivals before arm, between
readiness and sleep, and during timer/request retirement. Preserve durable GUI
and input-epoch state. Include child, debugger and ordinary message signals in
the proof; they must not depend on a new keypress or periodic timer to wake.

Gate: small raw/optimized shared-layout checks and optimized emitted race cases
for simultaneous GUI/completion readiness, an already retired child, signal
coalescing, unrelated signals, cancellation and close. Use another native caller
or fixture as a second consumer of the interface. Verify no lost notification,
busy spin, stolen reply, timer leak or changed standard AES event behavior.

## WB7 Owned output console window

Add reusable C bindings for console instance lifecycle and an application-owned
console-content window. Start from `lib/console/consolewindows.act`,
`lib/desktop/deskconsole.act`, AES window policy and their generated ABI inputs.
Generalize presentation admission explicitly: current BIND_CONSOLE only controls
the Shell view. The IDE must neither borrow Shell private state nor become a
second painter of retained console cells.

Use a fixed 64×20 output console and one frame, created on demand. The console
worker owns cells/caret; the desktop owns frame, visibility, focus and input
routing. Retain the instance through binding and drawing completion. Open owned
CON/RAW streams, select ATASCII while readers are retired, and use WB5's child
scope to bind BREAK. Hidden/covered output retains its state. Source-window
resizing does not resize this console.

Gate: a small C/GEM launcher runs interactive FastBasic PRINT, INPUT, GET and
KEY on this console while its own menu, files and event loop remain active.
Use physical focus/key input, menu Stop without output focus, output close,
overlap/exposure, late paint, repeated child start and early cancellation.
Require exact redirected bytes, preserved completed glyphs, no duplicated/stale
keys, no Shell mode changes and correct route/endpoint retirement. Exhaust
console/window capacity and retry after release. Destroy must fail while a
binding/endpoint is live and succeed after their exact retirement.

## WB8 Structured diagnostics and build artifacts

Modify the maintained FastBasic target/compiler sources and build helper, not
generated source caches. Define a versioned bounded diagnostics record with
stage, native cause, BASIC error where applicable, source/job identity and
line/byte column/message. Deliver it to an optional diagnostic output file
supplied with the compile job before compiler entry; ordinary two-filename CLI
invocations keep their current behavior. Freeze the argument/record format before
consumers use it. A requested diagnostic-file failure fails the job, while
preserving an earlier compiler/I/O cause; a completed COM alone cannot make that
job successful.

Use an immutable normalized snapshot with a monotonically assigned job identity
and short, collision-free absolute RAM names. Serialize its source as ATASCII.
Both compiler paths must report the same logical numbering and bounds without
requiring equal optimized bytecode. The compiler must never announce a usable
COM before its complete Write/Close succeeds. Check can compile to disposable
output, using this same path rather than a second parser.

Gate: host/on-machine integer and FP syntax errors at first/last line, tabs,
same-line statements, missing EOL, empty input and malformed/oversized source.
Compare diagnostic records and source selection against independent locations.
Cover parser allocation, source read, partial COM write and Close failures,
diagnostic failure, stale job records and two compiler invocations. Re-run the
affected existing integer/FP compile-run and save-fault cases. Rebuild both
compiler variants together if the common target/service profile changes.

## WB9 Integrated Run and first FB7 delivery

Connect the document, file jobs and public launch/wait/console interfaces in a
concrete application-local controller. Implement Editing, Compiling, Preparing
execution, Running and Retiring states from the design; reserve Paused for WB11.
Use one live child, freeze source edits for the job, retain cursor/viewport and
project directory, and keep GUI policy, output viewing and Stop responsive.

Run and Check compile the unsaved snapshot with explicit FBC/FBCI selection.
Collect the compiler and release all its Image references before loading output.
Validate the fresh COM and run only after successful compilation and terminal
output Close. A failed/cancelled build must never fall back to an old COM.
Check discards its output; Build publishes a standalone release command with
WB3's recovery rules and no live dependency on BASIC.APP or the compiler.

Collect completion through WB6, preserve both Process results and the first
cause, translate the structured byte location to the exact visible source, and
unfold it if necessary. Keep ordinary handled ERR behavior. Stop requests
cancellation; Quit waits for retirement before resolving unsaved source and
closing resources. Remove owned RAM scratch only after all users retire;
report cleanup errors without discarding the source or hiding the causal error.

Gate: physical edit → unsaved Run → output → return at the same caret for both
language variants; Check, error → fix → rerun, cooked decimal input, GET/KEY,
project-relative files, failed admission and no-I/O BREAK. Inject Stop/Quit in
snapshot, compiler loading, parsing, output writing, program loading, execution,
input and retirement. Verify a fresh successful run after each recoverable error.
Measure synchronous startup I/O stalls; add a reusable resumable loader slice
before acceptance if the GUI cannot meet the recorded responsiveness budget.

Add an opt-in workbench selection to `tools/build_demo.py`, provisionally
`--basic-workbench`, selecting the GEM desktop and FastBasic services together.
Build BASIC.APP through the loadable-app build path and install it in SYS:C;
do not auto-start it or replace unrelated startup applications. Build and
clean-extract the first GEM workbench demo through that selection.
Prove Build's COM runs after the IDE exits and under the ordinary shell. Update
FB7, reference/guide, resource measurements and the slice evidence. This package
must describe debugging and graphics as pending until their gates pass.
Apply WB14's boot/source package contents and checksum rules to this first
delivery as well.

## WB10 Debug metadata and executable statement hooks

Define the debug sidecar schema in a machine-readable input, provisionally
`abi/fastbasic-debug.json`, with generated readers/writers for both compiler
paths and native/C clients. Tie it to canonical source generation/checksum,
complete COM checksum, target, compiler mode and runtime/token identity. Bound
counts, ranges, variable descriptions and complete metadata allocation before
attaching; reject mismatches without claiming execution resources.

Instrument compiler emission to describe statements, bytecode ranges,
procedure entries/exits and actual variable storage. Include empty-loop backedges
and source statements sharing a line. Do not reconstruct a map from printed
assembly. Add debug-only statement hooks with an unattached fast path; standalone
debug commands must still execute normally. Release builds omit those hooks.

Add an explicit FastBasic library attachment to an owned loaded Image/run before
the child executes its first hook. Reuse WB5's public Image lifetime so attachment
does not race a running program or leak a guest slot. Allocate run/stop identities
without reuse on wrap; rollback must release every unstarted attachment.

Gate: independent host/on-machine maps and executed stop-point markers for both
language variants, branches, loops, procedure calls, arrays, strings and floats.
Cover lines with no emitted code, multiple statements, same-location iterations,
full/oversized metadata, truncated/corrupt/mismatched sidecars and unattached
execution. Measure file/heap and runtime overhead against matching release
builds. Run focused raw/optimized guest/native record and state-preservation
probes; preserve all guards and the current native transition protocol.

## WB11 Debug protocol and IDE controls

Add the native debug session/port implementation, provisionally `FBDEBUG`, and
its generated message definitions. Use copied commands/replies tagged with run
identity and stopped generation. Pause/Continue/Step/breakpoint/inspection
commands operate through that session, not direct IDE reads of running guest
pointers. Define request occupancy, exact reply collection and close/Stop order.

Publish stops only at declared boundaries with a complete guest context,
decimal state preserved and no live I/O/display/UPDATE borrow. A requested Pause
can wait for INPUT to finish; Stop still cancels it. Step executes the current
statement and stops at the next boundary, including another statement on the
same line or the next iteration at the same location. Read-only inspection
decodes actual integer, six-byte FP, counted string and array storage; retain
the donor's procedure-parameter and scope semantics.

Wire Pause, Continue, Step Into and breakpoint actions into BASIC.APP. Highlight
the current statement, reveal folds, and show variables in an existing editor
pane. Report a breakpoint with no executable location explicitly. Omit Step Over,
conditional breakpoints, expression watches and variable mutation from this
delivery. A paused child retains open BASIC files and its Image until Stop/end.

Gate: first-line and loop breakpoints, Pause/Continue/Step, repeated same-location
steps, inspection of each type and array boundaries, pending INPUT, Stop while
paused, Quit, late replies, stale generations, queue exhaustion and owner
retirement. Force selected IRQ/NMI entries around hooks and native return while
integer/FP state is live. Exercise two independent sessions in a capacity-suitable
fixture and normal refusal on a full desktop. Require peer progress, full native
register/guest-D/page-one restoration and exact heap/endpoint/Image return.

## WB12 Public retained graphics facade

Implement a reusable native window/drawing library above desktop/renderer and
expose it to ordinary C and Action! clients before BASIC grammar. Reuse public
messages, window identity and lifecycle. No render Task or kernel operation is
added. Extend the retained-content contract explicitly; existing REPLACE's
32 commands/256 text bytes and resident VDI bars/text are not this interface.

Freeze the first surface contract: one window per BASIC invocation later,
sixteen pens, signed window-local coordinates with widened clipping, clear,
colour, filled rectangle, solid line, counted text and Present. Maintain a pending
frame separately from published content. Start with a bounded capacity of
256 drawing records and 4,096 copied text bytes per frame; charge all staging,
committed and queued capacity using generated record sizes. If measurements
require a different cap, update the design/contract before dependent grammar.

Present validates the complete frame before replacing the retained model;
overflow or malformed input preserves published content. Physical drawing remains
incremental, with bounded line/text/fill units, visible-region clipping and
pointer/console/driver fairness. Close/key/button events are copied, window-local
and generation-tagged; Close is durable under queue pressure. Event waits permit
cancellation and retire exact replies. No raw caller/guest pointer survives reply.

Gate: two ordinary native clients prove public use, private attributes/scenes,
and independent close/restart. Compare pixels for every primitive, negative/
off-edge/odd-pixel clipping, partial cover, exposure and movement; cover exact
frame/text capacity plus overflow. Inject new frames and Close during painting,
errors during admission/hardware completion and cancellation during event waits.
Require preservation of the last published model, bounded peer progress and full
request/window/scene/renderer cleanup. Keep unsupported hardware failure recovery
under the existing display contract.

## WB13 BASIC graphics and debugger coexistence

Add native service marshaling and a restricted Exec graphics grammar to both
FastBasic compiler paths and runtime libraries. Freeze BASIC command spellings,
argument/result layouts, event wait versus poll, glyph mapping, normal graphics
error access and native fatal-error handling before enabling those statements.
The operations are Open/Close, Clear/Colour, Bar/Line/Text, Present and events;
do not reuse Atari GRAPHICS mode numbers or enable external USR.

Use guest-side fixed request/result storage or copied bounded buffers, with
generated ownership/layout definitions. Carry scalar coordinates and counted
strings through the established guest/native transition. The native session
owns the public WB12 handle and retires it on normal end, fatal error and BREAK.
No presenter request may retain a BASIC pointer. Standalone built commands use
the same facade without an IDE; missing backend support reports unsupported
behavior. A paused program keeps its scene; first-profile exit closes it.

Gate: compile new integer/FP graphics examples on Exec and run them after the
compiler exits. Check literal and computed coordinates, strings and modified
arrays, scene overflow, every supported event, close/input loss and capacity
errors. Independently compare pixels, including cover/exposure and focus changes
beside shell/disk/pointer activity. Pause after a frame, inspect variables,
step/continue drawing and Stop from the IDE while waiting for an event. Verify
stale requests cannot target another run, no draw borrow spans a debug stop,
all guards/state/slots return and a later program succeeds. Rebuild all FB65
producers/consumers together and re-run affected integer/FP console/file cases.

## WB14 Final documentation and delivery

Publish the editor, compiler-job, debugger and graphics contracts with explicit
limits, file formats, errors and unsupported controls. Add a short workbench
guide and source examples with independently known integer/decimal results and
graphics pixels/events. Update the migration plan, design status, roadmap,
indexes, licence map and upstream notices. Keep an implemented subset's status
distinct from full workbench completion.

Build the GEM demo through `tools/build_demo.py`, include BASIC.APP on its matching
system disk, and preserve the selected desktop plus standard shell/prime startup.
Keep OF816 and its five-second autoboot, pinned ROM/notices, matching XEX, old/new
Atarimax CAR and raw 1 MiB BIN. Refresh guards must reject mismatched native/
compiler/service profiles before mutating media. Boot ZIPs contain only boot
files, a short guide, notices and checksums; logs, manifests and source remain
outside. Retain a matching text demo for the existing FBC/FBCI command workflow.

Clean-extract the exact final ZIP. With physical keyboard/mouse input: open/edit
and save source, Run unsaved changes, select/fix a syntax error, enter a decimal,
use GET/KEY, Stop a busy loop, set a breakpoint, step/read variables, run graphics,
Build a release COM, close the IDE and run that COM from the shell. Exercise
ARC/MD5/native-command smoke, focus/cover/resize and normal EXIT. Verify persisted
source/output bytes, physical pixels, guards, ownership and complete recovery.

Package corresponding modified FastBasic and Exec sources separately with pins,
notices and offline build instructions. Rebuild BASIC.APP, FBC/FBCI, a release
example and debug metadata from a clean source extraction without reused tools;
compare deterministic artifact hashes and investigate differences. Record final
package/source checksums and launcher instructions. Full hosted release and
physical hardware qualification remain separate.

## Validation and evidence

Use development checks per coherent slice: host suite/generators for code
changes, then focused optimized emitted-code, interaction, failure and lifetime
cases. Pair raw/optimized only for changed ABI/layout/language bridges or a
focused compiler reproducer. Extend existing runners where practical; keep
independent numeric/file/pixel expectations and explicit deadlines. Test-only
fault/race hooks must be absent from distribution artifacts.
Normalize host text line endings before newline-sensitive parsing; preserve
exact binary and ATASCII fixtures as bytes.

Record evidence under `docs/development/fastbasic-workbench-wbN.json` and a
current summary `fastbasic-workbench.json`, with an execution note under history.
Each slice records input/output hashes, actual ROM/shadow and emulator/bridge
identity, effective speed/devices, memory map, emitted optimization mode,
executed case counts, observed failures/injections and deadlines. Retain earlier
records rather than rewriting their inputs to match a later build.

For every slice report all reserved bank-zero deltas separately: fixed,
root/kernel, per public Task and idle, including guards/alignment/unused
capacity. Report upper allocations at peak overlap: editor/index/undo and load
candidate, immutable source and RAM-file copies, C Image alignment, compiler or
program backing/session/file snapshot, diagnostics/debug metadata, console,
scene staging/committed copies and pending requests. Measure native stack and
free Task/guest/AES/window/console capacity, not just file sizes.

Measure input-to-scanout, worst bounded editor/paint turn, cold/warm compile/load/
Run stages, and release versus debug overhead. Preserve the current no-I/O
BREAK observation target of two PAL VBLANK ticks, while reporting I/O completion
and full retirement separately. Pause has the documented statement-boundary and
blocking-input limits. Set a numerical editor/startup responsiveness budget from
WB0–WB2 measurements before accepting WB9; fix an exceeded bound through a
focused executable slice rather than hiding it with a broad timeout.

This planning change reserves **0 fixed, 0 root/kernel, 0 per-public-Task and
0 idle bank-zero bytes**. Its validation is content/link checking; preparing the
plan requires no executable or full qualification run. Implementation completion
requires the actual gates above, not merely files being linked into an APP.
