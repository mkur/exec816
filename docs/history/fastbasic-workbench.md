# FastBasic workbench development

[Implementation plan](../plans/fastbasic-workbench-implementation-plan.md) ·
[Current FastBasic contract](../reference/fastbasic.md) ·
[Machine-readable slice index](../development/fastbasic-workbench.json)

This is development evidence, not hosted-system or hardware qualification.
Each slice retains its input hashes, pins, actual machine configuration and
execution scope in a separate record.

## WB0 — runnable application

[WB0 evidence](../development/fastbasic-workbench-wb0.json) records 73 emitted
checks, two independently relocated instances, signed results, repeated
load/close, image-busy refusal and resource exhaustion. The combined GEM/guest
fixture compiles and runs FastBasic. The exact extracted OF816 demo also runs
FBCI and its generated command alongside BASIC.APP, then exits normally.
The normal desktop starts six Tasks; BASIC.APP and one sequential child use
the two remaining slots. Close another application before Run if necessary.
Task exhaustion reports 103 and succeeds after an application closes.

The capacity run completed its machine checks and normal EXIT; report creation
then encountered a missing screenshot. Its recovered report identifies that
host-side finalization failure and hashes the preserved runner, machine state
and execution log. The helper now saves the required screenshot; the subsequent
coexistence run completed report creation normally.

The live Desktop lazily retains a 256-byte resolved-path buffer and 112 bytes
of timer request records after its first launch. Capacity comparisons warm
that path and verify exact subsequent heap restoration. These allocations retire
with the Desktop context at EXIT. All Task/console/AES ownership and guards
return. The full reserved bank-zero map matches the preceding FP graphical
build: **0 fixed, 0 root/kernel, 0 per Task and 0 idle bytes added**, including
guards, alignment, unused capacity and the existing 544-byte guest pool.

The opt-in `--basic-workbench` demo selection retains the standard startup and
five-second OF816 autoboot. WB0 provides only an empty window and Quit; editing
and integrated compiler controls land in subsequent slices.

## WB1 — document and undo

[WB1 evidence](../development/fastbasic-workbench-wb1.json) records 130 emitted
checks of the actual application document implementation. The 32,768-byte gap
buffer, 4,097-entry line index and 16 KiB undo/redo log request 65,540 upper-RAM
bytes (65,544 after allocator rounding). There is no hidden allocation header.
The fixture adds 96 upper-RAM canary bytes and checks every allocation returns.

Checks cover empty/full/overflow documents, 4,096 lines, 255-byte lines, tabs,
split/join, cross-line replacement, redo invalidation, whole-group undo eviction,
failed allocations, rejected edits, generation overflow and maximum gap moves.
Large moves yield after at most 1 KiB while preserving logical contents.
All reserved bank-zero deltas, including per-Task costs, remain zero.

## WB2 — window editing

[WB2 evidence](../development/fastbasic-workbench-wb2.json) records 29 logical
editing checks, 25 native integration checks and 11 independently compared
physical pixel cases. Physical Atari keyboard/mouse input covers tabs,
selection replacement, Undo/Redo, keyboard menu Undo, horizontal panning,
minimum-size and partial-row resize, focus/cover/exposure, close/relaunch and
a maximum-distance gap move with a one-byte gap in a 32,767-byte document.
Both raw and optimized emitted private-layout probes and relocation through
all 62 admitted banks pass.

The maximum-gap Backspace reaches matching scanout in 49 PAL frames (980 ms),
below the preselected 120-frame bound; a native peer advances 286 times during
that interval. This upper-bound observation includes debugger/probe overhead,
not just application CPU. Five physically typed characters and their scanout
check take 36 frames, including the scripted press/release intervals. These
samples are development measurements, not latency qualification. Stack guards,
complete ownership and allocation return pass. Added reserved bank-zero costs
remain zero in every category, including each public Task.

## WB3 — files and replacement decisions

[WB3 evidence](../development/fastbasic-workbench-wb3.json) records 148 controlled
file-engine checks, 70 checks on each of RAM/SDFS/MyDOS, 103 controller checks and
43 native integration checks with seven physical file workflows. Exact persisted
ATASCII bytes are read by an ordinary native client after the editor exits.
Tests cover EOL normalization and preservation, capacity boundaries, split CRLF,
short/failed transfers, consumed Close failures, each publication stage,
allocation failures, cancellation, recovery copies and successful retries.

Physical input exercises Save, Save As, Open, New Cancel/Save, Open Discard plus
selector Cancel, and reopening saved documents. The fixture occupies the smaller
native pools with ordinary clients so the APP runs in an existing large application pool,
as it does after normal demo startup. An earlier undersized-fixture run completed
its file checks but failed the reserved interrupt-headroom check; it is not
counted as passing evidence. No pool was enlarged. All final guards and ownership
checks pass, with zero added fixed, root/kernel, per-Task or idle bank-zero bytes.

The minimum client is 288×128 so Save/Discard/Cancel fits after resizing.
Recovery names use separate alerts with 32-character lines, escaped delimiters
and no truncation. A 127-byte path case exercises failed final publication,
complete temporary/backup recovery, literal `]`/`|` bytes and the File menu's
Recovery paths action through the actual GEM alert parser. Failed presentation
parks the alert until requested again instead of spinning the event loop.

The file-enabled editor also passes 28 native checks and all 11 existing physical
pixel cases, including minimum-size dirty close. A live Counter and native peer
continue while editing and dialogs run; the maximum-gap delete reaches matching
scanout in 57 PAL frames (1,140 ms including probes), with peer progress 151.
Warm heap restoration, final AES detach, guards and ownership all pass.

## WB4 — editing assistance

[WB4 evidence](../development/fastbasic-workbench-wb4.json) records 506 emitted
model checks with optimized code and another 506 with the assistance module
compiled raw. Cases cover repeated-prefix searches, full source capacity,
replacement admission and cancellation, atomic Undo/Redo, lexical precedence,
automatic indentation, exact procedure names, index overflow and presentation-only
folding. The shared editor layout is checked with raw/optimized C emission and
relocation through every admitted bank. All 544 host checks pass.

The model regression exposed a Calypsi 5.18 code-generation defect under pointer
register pressure: arithmetic assigned between fields through a spilled huge
pointer could read the old destination instead. Both raw and optimized affected
listings and failed observations are retained under
`build/fastbasic-workbench/wb4-calypsi-diagnostic/`. Staging the arithmetic through
a volatile scalar preserves the required load/store boundary. The emitted
replacement regressions exercise those expressions in both modes. This is a
Calypsi issue; no Action compiler semantics or optimizer policy was changed.

Physical replay waits for each accepted edit rather than treating a completed
paint as evidence that queued input has drained. Its timing observations include
the physical key intervals and debugger overhead. The editor regression passes
28 native checks and 11 pixel cases; assistance/file replay passes 43 native
checks and 23 source/pixel cases. Accepted keys take at most 14 PAL frames in
these fixtures. Deferring procedure indexing behind pending repaint reduces the
maximum-gap delete to matching scanout from 119 to 97 PAL frames (1,940 ms),
below the 120-frame development bound; its native peer advances 129 times.
All guards, warm heap restoration, AES detach and ownership checks pass.
Source, menu, index and job state live in the APP or
upper heap. Added reserved bank-zero bytes remain **0 fixed, 0 root/kernel,
0 for each public Task and 0 idle**, including guards, alignment and unused
capacity; the existing guest pool remains 544 bytes.

## WB5 — explicit child launch

[WB5 evidence](../development/fastbasic-workbench-wb5.json) covers the generated
24-byte C/20-byte native launch descriptor, explicit streams and directory,
retained Image ownership, copied arguments, setup acknowledgment and independent
console cancellation. The single current C ABI is 21 and Process ABI is 8.
The existing Process row remains 128 bytes. New C `Input` and `AvailMem` imports
expose existing public operations; no kernel operation or signal bit is added.

Raw and optimized argument/return probes each pass 22 checks. The optimized
Process lifetime regression passes 8,439 checks. The loader regression passes
102 checks across 12 C/native executions, including bad stack/reserved header
fields, allocation rollback, signed results, simultaneous instances and exact
resource return. The configured-launch fixture passes 78 native checks and
70 C controller checks, with 16 actual child-entry scope ownership checks.
It exercises native, C and FB65
children through actual emitted code, shared file position, project-relative
files, parent-handle closure, private and bound-console BREAK, wrong-console
setup failure, stack refusal/retry and failures at each acquired resource.
Recorded fixture copies inject failures; production modules contain no switches.

The graphical console worker uses an existing 2,560-byte pool. The workbench
uses the other; ordinary native/FB65 children use an existing smaller pool.
C images declare their requirement in the 36-byte ABI-21 header. The packer
defaults to 2,560 bytes; Panel, Counter and the measured small test programs
declare 1,312. Admission selects a fitting existing pool and reports 103 if
none fits, even with smaller slots free. No pool is enlarged.

Review found that a bound independent scope also needs Process ownership to
prevent public EndForeground from freeing the published cancellation pointer.
The existing ownership byte now distinguishes this state; Begin/End refusal
and pointer preservation are exercised in the actual child context. Scope and
client sizes remain 56 and 106 upper bytes. Image metadata grows from 72 to
74 requested bytes (80 rounded, **8 additional upper bytes per image**), and
the transient admission packet grows from 9 to 12 bytes. Added reserved
bank-zero bytes remain **0 fixed, 0 root/kernel, 0 for each public Task and
0 idle**, including guards, alignment, unused capacity and the existing guest
pool. These development checks do not qualify the hosted system.

## WB6 — combined GUI/Exec wait

[WB6 evidence](../development/fastbasic-workbench-wb6.json) records the generated
58-byte caller-owned descriptor and `ExecAESWait` in C ABI 22. The combined
fixture passes 38 emitted checks for pending/coalesced/unrelated signals, caller
message ownership, simultaneous GUI readiness, arrivals before sleep and during
timer retirement, error notification restoration, private-mask refusal, an
already retired Process, close delivery, a second ordinary caller and cleanup.
The input-event regression passes 705 checks, and the timer/event regression
passes 371. Public layout is checked with raw and optimized C emission. This
adds no AES context bytes, signal or worker.

The timer/event regression exposed an existing platform adapter defect when
the newly linked `ConsoleBitmapEntry` landed at `$0E0000`. The bitmap adapter
borrowed into the preceding bank while synthesizing an RTL target, but RTL
increments only its 16-bit PC. The previous event code passed 371 checks; the
new layout stalled during console startup, before either native or C test
entry. The adapter now preserves the original bank, as the ordinary Calypsi
bridge already did, and saves all 24 lower-DP bytes used by Calypsi helpers.
This is an Exec platform fix; compiler semantics were not changed.

The bridge probe places a fixture-only JML at an exact upper-bank boundary and
checks both stack parities, full registers, stack/direct-page restoration and
all 24 lower-DP bytes. Its 80-byte result allocation is unchanged: previously
unused result words now capture the additional four DP bytes. The adapter uses
10 more bytes within its existing console code reservation and four more
transient stack bytes per call. Added reserved bank-zero costs remain **0 fixed,
0 root/kernel, 0 per public Task and 0 idle**, including guards, alignment and
unused capacity. The boundary stub reserves one upper bank only in probe builds.

Raw and optimized context runs each pass 1,081 checks in each of two C contexts,
plus both boundary bridge calls. All 545 host tests pass. The context fixture
also checks the current 33-object menu record: 380 bytes, including alignment,
with 66-byte parent/x/y arrays. Its old 340-byte expectations were
stale and failed before reaching the C contexts; the corrected fixture keeps
the independent literal layout checks.

## WB7 — application-owned console window

[WB7 evidence](../development/fastbasic-workbench-wb7.json) records the ordinary
loadable C application controlling its own 64×20 retained-cell console through
C ABI 23 and AES wire 17. The console remains bound until window deletion;
streams and cancellation scopes retain it until their exact retirement. The
existing worker renders each bound view with its own frame and focus route.

Two physical application cycles pass 176 application checks per cycle and 19
controller checks, plus 20 raw/optimized console binding checks. Eight independent
ROM-font pixel comparisons cover initial, exposed, moved and completed output.
Both exact transcripts include cooked numeric input, GET and KEY. Editor menu
Save remains usable during INPUT; menu Stop, output close and early Stop retire
children. Menu Stop takes 138 observed frames in each cycle, including the
physical menu approach and debugger overhead. Shell cells and mode are preserved,
warm heap returns exactly, and all stack/domain guards remain intact.

The optimized cell-I/O regression passes 316 checks and the layer regression
8,924. Existing native text-window lifetime cases also pass. CONCMD_GET_MODE
reads applied flags without claiming or consuming input. FastBasic restores the
previous console mode after retirement, keeping completed application output in
the ROM font. All 545 host tests pass. These are development checks, not hosted
system qualification.

The selected console identity adds four upper bytes, its private C bridge table
15, and the public import table 15. An owned console requests 1,664 upper bytes
(1,672 allocator bytes). No worker, signal or Task is added. Reserved bank-zero
growth is **0 fixed, 0 root/kernel, 0 per public Task and 0 idle**, counting
guards, alignment, unused capacity and the unchanged 544-byte guest pool.

## WB8 — structured compiler diagnostics

[WB8 evidence](../development/fastbasic-workbench-wb8.json) freezes the generated
224-byte FBD1 record and 18-byte borrowed guest registration. Both compiler
variants rebuild together for target `$4703`. The optional four-argument CLI
registers a nonzero hexadecimal job and exact immutable source path before I/O.
Ordinary two-filename and interactive compilation remain available.

The integer and FP paths pass 191 emitted checks across 20 source cases: first
and last line, tab, same-line statement, missing final EOL, empty input, CRLF,
long line, malformed byte and source capacity. Independent byte locations agree
for both variants. Testing exposed a donor parser loop for lines over 255 bytes;
the maintained frontend now rejects these before parser entry. ASCII tabs are
skipped between tokens without expanding source bytes. The parser stores its
message offset before human output, preserving its first cause.

A second fixture passes 191 checks covering 30 failure scenarios and recovery:
partial COM write, Close and combined first-cause failure, positive short writes,
source read/Close, diagnostic Open/Write/Close/allocation, malformed/zero jobs,
parser allocation exhaustion, and a syntax failure with failing diagnostic I/O.
Overrides are fixture-local and use real RAM files. The parser allocation probe
reduces MEMTOP at the real allocator prologue, with its trampoline outside BSS
and heap ownership. Both ordinary CLI fault/compile/run regressions pass 49
checks each, including FP output. Raw and optimized C layout/reader probes each
pass 16 checks, rejecting stale jobs, mismatched sources and malformed bounds.
All 547 host tests pass. Development checks do not qualify the hosted system.

The Session grows by six requested upper bytes: 2,304 → 2,310 requested and
2,312 → 2,320 allocator bytes. Record emission temporarily requests 224 upper
bytes. No Task, guest slot, signal or reserved bank-zero allocation grows:
**0 fixed, 0 root/kernel, 0 per public Task and 0 idle**, including guards,
alignment, unused capacity and the existing 544-byte guest pool. The complete
reserved map matches WB0. The controller must require successful Process results,
a matching complete record and a fresh validated COM before execution.
