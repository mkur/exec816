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
