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
