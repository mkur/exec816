# FastBasic source interpreter on Exec816

Status: original FI0–FI7 delivery implemented, 21 October 2026.
The [persistent-session follow-up](fastbasic-session-plan.md) supersedes this
note’s per-Run Process lifetime for BASIC.APP. Shell commands remain one-shot. FB/FBI and BASIC.APP source Run follow
this design. The [delivery record](../history/fastbasic-interpreter.md) records
development checks and measured limits; hosted release qualification is separate.

[Plan index](README.md) · [Implementation plan](fastbasic-interpreter-implementation-plan.md) ·
[Current FastBasic contract](../reference/fastbasic.md) ·
[Current workbench](../reference/fastbasic-workbench.md) ·
[Task capacity](../architecture/task-capacity.md)

## Decision and first delivery

Run FastBasic source directly on Exec using the maintained parser and bytecode
interpreter. The first milestone is:

```text
Load .BAS source → translate in the private bank → execute → return
```

FastBasic translates source before interpreting bytecode. That internal step is
part of the interpreter. Standalone executable generation and a new compiler
workflow are deferred. Run creates no source, COM or diagnostic scratch files.
Host tools still build the interpreter itself from the pinned sources.

Provide `FB source` and `FBI source` commands: FB accepts the existing
integer/FP language; FBI selects its integer-only variant. A source path is
required and may be quoted. Bare invocation prints usage; source does not come
from standard input, which remains available to the BASIC program. Native paths,
Process directory and command-tail limits apply. Automatic execution of `.BAS`
by filename and an immediate-command prompt are outside this delivery.

First prove shell use in text and graphical consoles. Then make BASIC.APP Run
submit an immutable unsaved buffer to the same engine. Each admitted Run owns
one ordinary Process and at most one shared guest slot. Its lifetime ends after
execution and cleanup; the next Run starts fresh. A permanently waiting engine,
retained variables after END, Pause/Continue, source debugging, direct mode,
native graphics and native 65816 BASIC code generation have separate designs.

The existing FBC/FBCI commands and workbench Check/Build remain available through
their current implementation. This work replaces the workbench's Run path;
there is no selectable legacy Run backend. It does not remove delivered tools
or require new standalone compiler features before the interpreter works.

## Source baseline and reuse

Keep FastBasic 4.7 and mini65 at [upstream.json](../../ports/fastbasic/upstream.json).
Make donor changes in the maintained
[patch](../../ports/fastbasic/patches/exec6502.patch), added target sources and
generators, rather than disposable `build/fastbasic/source` files. Preserve
notices and update corresponding-source delivery when implementation lands.

The important source boundaries are:

| Existing component | Use in this delivery |
| --- | --- |
| Donor `src/compile.asm` | Starting reference for zero-relocation parse-and-run, program variable placement and END return. Remove BRKKY/vector ownership and Atari editor assumptions. |
| Donor `src/cmdmenu.asm` and the port's [cmdline.bas](../../ports/fastbasic/target/cmdline.bas) | Reuse parsing, normalization and error rules; executable writing and output-name prompts are outside interpreter Run. |
| Donor `src/parse.asm`, `src/alloc.asm`, `src/vars.asm` | Keep grammar, parser allocation and actual variable/type conventions. Parsing and execution use their workspaces sequentially. |
| Donor `src/interpreter.asm`, `src/interp/clearmem.asm`, `src/interp/jump.asm` | Keep dispatch, variable initialization and END semantics, with an explicit return to the source-run wrapper. |
| [FBPROGRAM](../../lib/dos/fbprogram.act), [FBSERVICE](../../lib/dos/fbservice.act), [FBSTATE](../../lib/dos/fbstate.act) | Reuse Image ownership, one-bank allocation, native services and final cleanup; add source-run admission/results above Exec. |
| [Guest state](../../lib/dos/sdxstate.act) and bridge | Keep D, page-one, native context, IRQ/NMI and guest-slot ownership unchanged. |
| [Workbench controller](../../examples/gem-basic/build.c) | Reuse snapshots, console, child completion and Stop; replace Run's scratch-file/compiler/program sequence. |

The donor's [integrated execution routine](https://github.com/dmsc/fastbasic/blob/55dc52f74fcfcf3e8afd29bb5b984ee1dc9b6a6f/src/compile.asm)
demonstrates the mechanism, but its partial editor-state save is not a complete
Exec context protocol. It must not be linked unchanged. Current FBC/FBCI use the
command-line path, so their success does not establish source-run correctness.

## Execution architecture

Build separate integer and FP engine images, `FBI.COM` and
`FB.COM`, using the current FB65 loader and native provider. Each includes its
parser and every runtime handler admitted by its user grammar. The bootstrap's
own referenced tokens must not accidentally determine the available language.
Generate matching parser token numbers and dispatch tables in one build.

Use an assembly source-run wrapper rather than interpreting a BASIC frontend
and nesting another interpreter without a complete state save. The wrapper:

1. Requests source admission through a bounded native service. Command mode
   obtains the required path from Process arguments; an attached buffer selects
   editor mode. Both feed the same normalization and parser path.
2. Sets the source start/end and zero relocation, then invokes the donor parser.
3. On success, captures bytecode bounds and variable count, places variables at
   the required aligned boundary and calls `interpreter_run` at the emitted code.
4. Receives END through a valid saved guest CPU stack and reports completion.
   Parser failure never enters the user program.
5. Returns through the existing guest exit and native cleanup path.

The wrapper's control records must remain outside the user variable/array heap.
Audit `saved_cpu_stack`, code/variable pointers, integer and FP expression stacks,
math workspace and the private mutable dispatch operands. Parser symbol tables
may be reclaimed by runtime allocation only after every required result has
been captured. This delivery does not retain symbols for later inspection.

The whole bank and D are initialized once at fresh Process execution, using the
existing FBSERVICE/SDX preparation path. Do not call FBSERVICE.Run again between
parsing and user execution: it clears the bank. The source wrapper performs the
phase transition within that invocation. No suspended program is resumed by
relaunching an Image; relaunch always starts from its immutable engine snapshot.

Keep the shared native service implementation for ordinary COM programs and
source engines. Source-specific state belongs in a language session extension;
avoid a second console/file/timer implementation or interpreter-specific kernel
operation. Exec keeps COP #$50; OS #$00 and WDC-reserved signatures are unchanged.

## Source admission and public buffer interface

The first engine accepts at most **32,768 input bytes**, matching the editor's
document-byte capacity. File input counts original bytes, so CRLF consumes two
bytes of that limit. Normalize LF, CRLF, CR and ATASCII to guest ATASCII EOL.
Reserve one additional guest byte for a missing final EOL, including empty input.
Source lines contain at most 255 non-EOL bytes; tab is accepted and counts as one
source byte. Other accepted source bytes are printable ASCII. Embedded NUL and
unsupported bytes are rejected before parser entry. The shell engine does not
inherit the editor's separate 4,096-line indexing limit.

Read/copy/normalize in bounded units of at most 1 KiB, observing cancellation
and yielding at safe native boundaries. A file exactly at the source cap needs
an explicit EOF probe; filling a read buffer alone is not proof of excess size.
Check Close before parsing. Failed Read/Close never executes partial source.
Source admission also respects the actual guest-bank workspace limit; a source
within 32 KiB can still fail allocation during parsing or execution.

Add a public, language-level source attachment to an owned, unstarted engine
Image. The `ExecBasicAttach` helper takes the Image and a counted source
descriptor containing a writable completion-record pointer. This is a native library/provider
entry usable by ordinary applications through public Process primitives, not a
new kernel gateway service. Use the existing cooperative Image loader for the
engine file and ordinary StartLoaded/Collect/Break for execution.

The selected engine determines the variant. The attachment copies source
pointer/count, nonzero run identity and
source generation into session-owned storage. It borrows an immutable
upper-memory snapshot and writable result until either the final unstarted
Image reference is released or the started Process is collected. Admission
failure acquires no new borrow and preserves an existing attachment. A valid
replacement on an unstarted Image releases the old buffers only after the new
attachment is admitted. Failed Start preserves the admitted attachment for
retry or release; successful Start consumes it. The caller may release its load
reference after Start; the execution reference retains the attachment. A
retained Image cannot be relaunched with an old attachment after collection:
consume it on the first Start and require a new attachment for another buffer
run. File mode remains the bare command behavior.

Establish the engine capability, complete descriptor and result capacity once
at attachment. Check source counts at full width before narrowing guest
addresses. Trust live caller-owned pointers afterward, retaining ownership and
transition checks. Copy results before Process completion is published; callers
read them after Collect. No GUI pointer enters executing guest bytecode.

Define shared source/result records and engine capabilities in a machine-readable
input, `abi/fastbasic-interpreter.json`, generating assembly,
Action! and C definitions. Resolve the exact provider binding and capability
record in the first implementation slice. If common guest services or layout
change, advance the affected current target and rebuild FBC/FBCI, engines,
examples and consumers together. Keep one current ABI, with no old-profile
execution branch. An engine capability is not inferred from a filename alone.

## Language, I/O and results

Preserve the [current language and numeric contract](../reference/fastbasic.md):
16-bit integers, counted strings, arrays/procedures and the existing six-byte FP
provider. Integer and FP engines use the same native files, Process streams,
INPUT/GET/KEY, clock, PAUSE, random and cancellation behavior. Atari hardware
statements, external USR and ROM console entry remain unsupported. The engine's
own assembly wrapper is not permission for user assembly calls.

Each source run progresses through admission, source read/normalization, parse,
execution, cleanup and completion. Return primary 0/cause 0 for success; retain
existing fatal-service primary 20 and native causes, including bad arguments
115, allocation 103, source/parse error 306, unsupported service 307 and BREAK
304. Preserve loader cancellation results if BREAK arrives before execution.
Handled BASIC ERR behavior does not become a fatal native error.

The optional completion record includes its version/size, run identity, source
generation, outcome phase, primary/native cause, BASIC/parser error, source
line/column validity and a bounded message. Parser/normalization positions use
one-based lines and zero-based byte columns, including tabs. Preserve the first
fatal cause through output flushing and Close failures. A cleanup failure fails
an otherwise successful run. Completion must distinguish a valid location from
no location; runtime statement locations are deferred with debugger metadata.

The native source path prints equivalent bounded diagnostics for shell callers.
Editor mode consumes the record without parsing console text or opening a
diagnostic file. There is no COM checksum gate because Run publishes no COM.
The run identity/source generation still prevents stale UI completion from
selecting a newer document. Identity wrap refuses reuse while references exist.

Stop uses the existing Process BREAK route. Observe it during native source
work, parser lines, dispatch/copy/fill checkpoints, FP checkpoints and blocking
native I/O. A pure integer or FP busy loop retains the existing two-PAL-tick
cancellation-observation target; measure full retirement separately. END,
failure and Stop close owned channels, flush output, restore console mode,
retire timer/I/O requests and release Image/guest/Process ownership in order.
No pointer may survive its exact request/reply or Process lifetime.

## Editor integration

Retain BASIC.APP's document, file transactions, assistance and output console.
Run freezes one source generation and its project directory, loads the selected
engine cooperatively, attaches the snapshot and starts one child. It never
starts FBC/FBCI or reserves scratch names. Compilation cannot execute a previous
program after a parse failure because each run begins from a fresh engine.

Keep source edits frozen until collection for this first delivery, while
navigation, repaint, output input, Stop and orderly Quit remain available.
Reveal a valid parse-error location, including folded text. Other completions
restore the retained caret/selection/viewport. Output close requests Stop; Quit
waits for collection before unsaved-document decisions and resource release.
Use the existing combined AES/Exec event wait rather than a polling Task/timer.
Check/Build retain their existing command-backed behavior and separate jobs.

## Memory and concurrency budget

The standard desktop starts six public Tasks. The editor plus one source-run
Process uses eight; adding the second shell uses nine, leaving three of twelve.
Root/service Tasks count; private idle does not. The delivery's extracted-ZIP
walkthrough measures the two-shell case. AES clients, windows, consoles and the
two shared SDX/FastBasic guest slots retain their independent limits.

Only the executing/loaded source engine claims a guest slot; there is no retained
compiler Image. The native editor consumes no guest slot. One BASIC run must
coexist with one MD5/ARC/EDX guest. Two BASIC runs can use both slots in a
capacity-suitable fixture; a third admission fails normally and later recovers.
Release the engine Image after each job rather than retaining an idle slot.

| Resource | Design budget |
| --- | --- |
| Added reserved bank zero | **0 fixed, 0 root/kernel, 0 per-public-Task and 0 idle bytes**, counting guards, alignment and reserved slack. |
| Native execution | One existing stack/DP pool per run; target the ordinary 1,312-byte stack and measure the complete native depth plus 256-byte interrupt reserve. A demonstrated larger need uses an existing 2,560-byte pool, with explicit admission accounting. |
| Guest direct page | One of the existing two pages; the shared guarded reservation remains 544 bytes. |
| Guest bank | One private 64 KiB bank, with the current 131,072-byte upper backing reservation including alignment capacity. |
| Other upper storage | Engine file snapshot, native session/Image, source snapshot where needed, result/attachment and ordinary Process/DOS/timer records. Record rounded allocations and transient loader copies. |
| BASIC address space | Existing private-bank bounds, load origin and service reservations; parser, source, emitted code, variables and arrays/strings compete for that bank. |

Do not consume the twelve-Task map's 10,528 unreserved bank-zero bytes for source
or bytecode; they are not automatically heap storage. Keeping the parser during
execution reduces available program heap relative to standalone COM output.
Measure that limit per variant; a 32 KiB editor document is not a promise of
successful compilation or allocation. Larger/banked BASIC storage is deferred.

## Acceptance and delivery

Use the [development tier](../contributing/testing.md): host/generator checks,
focused optimized emitted-code language, failure, ownership and integration
tests, plus small raw/optimized ABI/context probes. Exercise actual integer/FP
source, input/files, invalid source, exact/overflow bounds, no-I/O Stop, repeat
runs, two guests, selected IRQ/NMI boundaries, guards and OS restoration.
Preserve native decimal/hidden-B/D/DBR/S and page-one ownership. No OS_BUSY,
Forbid, UPDATE or hardware borrow spans a wait for input or child completion.

Measure read/normalize, parse, execution-start and complete Run latency,
cancellation observation/retirement, stack peaks, upper allocations and all
slot counts on recorded ROM/emulator/media pins. Separate language controls
from hosted execution; neither establishes general interrupt qualification.

Delivery uses `tools/build_demo.py` with OF816, its five-second standard
shell/prime autoboot, matching SYS/WORK disks, pinned ROM and notices. Test the
actual extracted ZIP with shell source execution and physical-key unsaved-buffer
Run/error/fix/Stop/repeat/close. Current XEX/OF816 packaging excludes CAR/BIN.
Refresh the corresponding FastBasic source ZIP separately. Publish reference,
guides and measured evidence only as slices pass; preserve historical records.
