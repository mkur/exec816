# FastBasic source interpreter implementation plan

Status: FI0–FI7 implemented, 21 October 2026. The
[delivery record](../history/fastbasic-interpreter.md) and
[frozen evidence](../development/fastbasic-interpreter.json) identify the selected
development checks, final packages and measurement limits. Release qualification
is separate.

[Design note](fastbasic-interpreter-design.md) · [Plan index](README.md) ·
[Current FastBasic contract](../reference/fastbasic.md) ·
[Workbench implementation](fastbasic-workbench-implementation-plan.md) ·
[Testing policy](../contributing/testing.md)

## Scope and sequence

Implement the design's source interpreter first: `FB source` / `FBI source`,
then unsaved-buffer Run in BASIC.APP. Source translation and execution happen
inside one private guest bank in one ordinary Process. Normal Run writes no
source, COM or diagnostic scratch files. Existing compiler commands and
workbench Check/Build continue through their current code; new standalone
compilation, persistent sessions, debugging, direct mode and graphics are deferred.

| Slice | Executable result | Depends on |
| --- | --- | --- |
| FI0 | Integer and FP engines parse and run embedded source under Exec | Current FastBasic and twelve-Task delivery |
| FI1 | Shared bounded source admission and structured completion | FI0 |
| FI2 | Usable shell `FB` / `FBI` source commands | FI1 |
| FI3 | Public source-buffer attachment through the normal Process lifecycle | FI1 |
| FI4 | Failure, cancellation, guest concurrency and selected interrupt gates | FI2, FI3 |
| FI5 | BASIC.APP Run uses the source interpreter | FI4 |
| FI6 | Boundary, latency and memory acceptance on final integration | FI5 |
| FI7 | Documented interpreter and verified OF816/source packages | FI6 |

Implement FI2 before FI3 so shell execution is useful before editor work. Each
row is a suggested commit boundary after its gate passes. Split a row if needed
to keep changes executable.
Update slice status and its evidence before starting the next dependent row.

## Implementation record

| Slice | Delivered behavior and development evidence |
| --- | --- |
| FI0 | Source-run assembly engines, full user runtimes, generated records and reviewed linked-code inventories; integer/FP corpus execution. |
| FI1 | Shared 1 KiB admission/normalization, checked Close, first-cause completion; 271 boundary checks and 189 fault checks. |
| FI2 | FB/FBI on SYS, native arguments/streams/directory, actual graphical-shell invocation and existing FBC/FBCI compile/run controls. |
| FI3 | Public native/C attachment, borrowed upper buffers and ordinary Process ownership; 164 checks each in raw and optimized builds, including setup failure, plus emitted C record probes. |
| FI4 | Admission/Close/parser/execute-transition cancellation, two source guests/native peer, MD5/ARC, Task exhaustion/high pools, decimal VBI and native-return NMI gates. |
| FI5 | One-child unsaved-buffer Run, no Run scratch names, structured error selection, physical input, Stop/repeat/output close and orderly Quit. |
| FI6 | Full-width source limits, parser/runtime OOM, byte-array boundaries, unchanged bank zero, measured stacks and first/repeat phase timing. |
| FI7 | Current contracts/guides, matching OF816 demo and separate corresponding-source ZIP with clean rebuild verification. |

The baseline retained prior WB9/twelve-Task records and compiler maps; it did
not capture comparable fresh WB9 stage timings. The implementation records
first/repeat source-engine timings on RAM files and makes no before/after
speedup claim. Selected IRQ/NMI and desktop checks do not constitute the full
release matrix. The sections below preserve the implementation requirements
and suggested slice boundaries.

## Shared rules and baseline

- Use [FastBasic/mini65 pins](../../ports/fastbasic/upstream.json),
  [actionc inputs](../../toolchain/actionc.json), the current Calypsi bindings
  and the selected pinned [platform](../reference/platform.md). Record actual
  source, tools, ROM, emulator, machine and media hashes, including local overrides.
  Do not update donors or rewrite historical evidence as part of this work.
- Edit target sources, maintained patches and generators. Keep compiler defects
  in actionc and emulator defects in actionc-vm, with focused regressions.
- Target **0 added fixed, root/kernel, per-public-Task and idle reserved bank-zero
  bytes for every slice**, counting guards, padding and unused reservation.
  Reuse existing native pools and the 544-byte two-guest DP reservation. Report
  actual deltas even when zero, plus upper occupancy and allocation changes.
- Follow the current [Task layout](../architecture/task-capacity.md). A source
  engine takes one guest slot and one Process; no compiler child or idle engine
  is required. Prefer the measured ordinary stack if it fits. Prove complete
  stack depth above the interrupt reserve; use an existing large pool if needed
  and record the resulting admission constraint.
- Generate assembly/Action!/C ABI records from machine-readable inputs. Rebuild
  all affected consumers when the common target/service contract changes. Keep
  one current ABI and shared I/O implementation. No BASIC-specific kernel call.
- Use ordinary Process streams, directory, BREAK, Image references and collection.
  Retain exact ownership through asynchronous I/O and completion. Never wait
  with UPDATE, Forbid, OS_BUSY or a hardware mapping/activation held.
- After coherent code slices, run the host suite, affected generator checks and
  focused optimized emitted-code checks. Add small raw/optimized cases for new
  layouts, calling conventions or context transitions. Do not duplicate full
  system scenarios in raw mode or automatically run release matrices.

Before FI0, record the current runtime/compiler maps and a matching WB9 Run
baseline: stage latency, native stack peaks, Task/guest counts and upper-RAM
reservations. The [twelve-Task record](../history/twelve-task-layout.md) supplies
prior evidence, not a measurement of the proposed engine. Existing current
reference prose containing eight-Task workbench limits must be updated when
the new contract is published, rather than copied into new assumptions.

## FI0 — Executable parse-and-run engines

Start in [ports/fastbasic](../../ports/fastbasic/README.md),
[build_fastbasic.py](../../tools/build_fastbasic.py),
[FBSERVICE](../../lib/dos/fbservice.act) and
[FBPROGRAM](../../lib/dos/fbprogram.act). Add an assembly source-run wrapper
and engine build targets, provisionally `FB.COM` and `FBI.COM`.

Use the donor `compile.asm` zero-relocation mechanism as a reference. Remove
BRKKY/vector writes, screen clearing, editor returns, output-file headers and
executable writing. Set source/code/variable bounds explicitly, call the parser
and then `interpreter_run`, and return END through the existing bridge. Keep
wrapper state outside parser output and the user heap. Initialize bank/D once;
do not clear the generated code between parser and interpreter entry.

Link the complete restricted user runtime for each grammar and generate its
parser/token/dispatch identities together. The assembly bootstrap does not
select the user language by its own token references. Audit private mutable
jumps and absolute operands, saved CPU stack, variable-page patching, parser
table reclamation, expression stacks and FP state. Keep external USR excluded.

Define the source/result/capability schema in `abi/fastbasic-interpreter.json`
and its generator. Freeze version/size fields, engine capability location,
variant, source service/phase markers and completion ownership before exposing
attachments. A capability record must be covered by admitted initialized-image
bounds; a filename is not proof that an Image is a source engine. Append native
services through the existing guest service mechanism. Advance/rebuild the
common target if required; do not invent another executable file format.

For this slice, use test-only embedded source instead of depending on file
admission or the editor. Keep that source injection out of shipping engines.

**Gate:** emitted integer and FP programs parse and execute arithmetic, a loop,
procedure calls and END; invalid source never enters execution. Exercise a
runtime handler absent from the bootstrap, source/output page boundaries and
two different fresh sources in repeated runs. Check exact output, full guest
and native restoration, bank/stack guards, resource return and OS shutdown.
Use focused raw/optimized schema and entry/END probes. Record maps, D use,
source/code/heap bounds, engine sizes and stack peaks.

**Suggested commit:** `Add FastBasic parse-and-run source engines`.

## FI1 — Source admission and results

Add shared source loading/normalization and result handling in language modules,
provisionally `lib/dos/fbsource.act` and `fbresult.act`, extending FBSTATE only
for interpreter-owned state. Both command-file and attached-buffer input must
join this path. Reuse the existing file, console, timer and finalization code.

Enforce 32,768 original input bytes at full width, reserve one final-EOL byte,
normalize LF/CRLF/CR/ATASCII and reject NUL, unsupported bytes and lines over
255 non-EOL bytes. Preserve tabs and source byte columns. Transfer/process at
most 1 KiB before a safe yield/cancellation observation. Maintain pending CR
across reads; exact-cap files require an EOF probe. Check final Close before
parsing and reject insufficient bank workspace without executing partial source.

Capture normalization/parser error and location before workspace reuse. Complete
the bounded result after native cleanup, before publishing Process completion.
Retain the first fatal cause and distinguish a cleanup-only failure from success.
Print equivalent diagnostics for file-command mode. Do not change handled ERR
semantics or fabricate runtime source locations. No diagnostic-file writer is
used for source Run.

**Gate:** focused emitted tests cover empty and unterminated source; all EOLs
and mixed EOLs; CRLF across the 1 KiB boundary; tabs; 255/256-byte lines; NUL
and unsupported bytes; first/last-line errors; exact 32 KiB and one-past input;
available-workspace and parser OOM; Read/Close failure and recovery. Use a small
source with an observable side effect to prove each rejected input never runs.
An exact-cap input can pass source admission yet fail later parser allocation;
assert those phases independently. Verify result identity, location validity,
first-cause cleanup, guards and all allocations returning.

**Suggested commit:** `Add bounded FastBasic source admission and results`.

## FI2 — Shell interpreter delivery

Install FB/FBI through the existing disk-command and Process path. Each engine
accepts exactly one quoted or unquoted source path; no path prints usage and
fails with the design's bad-argument result. Reject excess/malformed arguments.
Read source through native DOS independently of inherited standard input.
Preserve Process directory for both the source path and BASIC relative files.

Exercise both variants through the ordinary loader, not the FI0 injection.
Use the existing native PRINT/PUT, INPUT/GET/KEY, channels 0–3, clock/PAUSE/random
and FP provider. Remove engine-only donor assumptions from actual linked paths.
Update [audit_fastbasic.py](../../tools/audit_fastbasic.py) to select the new
engines and review newly reachable code and service transfers.

**Gate:** shell source execution in text and bitmap console fixtures; integer
and FP values/arrays/strings/procedures; INPUT/GET/KEY; native file read/write;
relative/quoted paths; output redirection with exact ATASCII bytes; missing
source; unsupported grammar and invalid arguments. Run integer and FP no-I/O
loops, BREAK, then a valid source and MD5/ARC command. No output filename is
requested, no scratch executable is created, and one source Process/guest is
observed. FBC/FBCI still compile one focused existing control each.

**Suggested commit:** `Expose FB and FBI source interpreter commands`.

## FI3 — Public buffer attachment

Add the design's language-level attachment helper, provisionally
`ExecBasicAttach`, through normal native provider bindings. Generate C and
Action! declarations and attach source/result state to an owned unstarted
engine Image. Reuse cooperative loading and StartLoaded/Collect/Break; no
additional controller Task or kernel selector is introduced.

On admission, establish engine variant/capability and exact descriptor/result
extents once. Copy descriptor fields into session-owned storage and borrow the
immutable source snapshot and result through collection or final unstarted
release. A failed attachment leaves the caller's Image and buffers unchanged.
Implement the design's atomic replacement of an unstarted attachment, preserved
attachment after failed Start, consumption at successful Start and explicit
reattachment after collection.
The child execution reference must cover the common early release of the
parent's load reference. Never reuse a consumed source pointer on a later run.

**Gate:** actual C and Action! callers exercise a buffer in an upper bank,
empty source, 32-bit count/overflow rejection, integer/FP selection, wrong Image
capability, unstarted release, failed Start/retry, release-after-Start, completion
publication and repeat attachment. Read results only after ordinary collection.
Use small raw/optimized layout/calling/context probes and optimized ownership
checks; prove there is no scratch filesystem traffic. Rebuild external provider
consumers with the current ABI and verify no new reserved bank-zero bytes.

**Suggested commit:** `Add public FastBasic source-buffer attachment`.

## FI4 — Cancellation, concurrency and transitions

Extend focused FastBasic lifetime/fault fixtures for source admission, parse and
execution phases. Use test-only bounded injection at the existing I/O/allocation
seams; no production fault API. Stop must retire the admitted run, with a later
run succeeding from fresh state. A waiting input or PAUSE operation must observe
the existing Process cancellation route rather than requiring another bytecode.

**Gate:** source Read/Close/normalization cancellation; parser-loop and large-copy
cancellation; integer and FP busy-loop Stop observation within two PAL ticks;
INPUT/GET/PAUSE cancellation; short/failed output and late cleanup failure;
unchanged earliest cause; fresh random/DEG/error/variable state on another run.
Measure full request/Process retirement separately from observation latency.

Run two distinct source guests plus a progressing native peer, one source guest
plus MD5 and a focused ARC operation, guest-slot overflow/recovery, and native
Task exhaustion/recovery on the twelve-Task map. Only one guest is occupied by
each source engine, including engine loading. Retained-image relaunch and
buffer reattachment must preserve slot/reference accounting.

Force selected actual IRQ/NMI entries during parser work, decimal math,
parser-to-runtime variable/stack transition and the existing native return gate.
Preserve P/decimal/carry/hidden B, D, DBR, S, page-one frames and guard domains.
Exercise upper native Task DP/stack placement using generated maps. Use small
raw/optimized probes for changed context-facing code; optimized concurrency and
fault scenarios suffice. Report the selected boundaries, peer progress, heap,
requests, handles, slot recovery and normal OS restoration. Do not label these
checks full guest interrupt qualification.

**Suggested commit:** `Validate source interpreter lifetime and cancellation`.

## FI5 — Interpreter Run in BASIC.APP

Replace the Run branch in [build.c](../../examples/gem-basic/build.c) and its job
state with snapshot → cooperative engine load → attachment → one child →
collection. Use the current integer/FP selection to choose the engine. Check
and Build keep their existing separate command-backed branches; there is no
legacy/compiler-backed Run option. Remove Run-only scratch reservation, source
writing, compiler-child, COM/diagnostic-file validation and program reload state.
Keep shared file publication code needed by Check/Build.

Borrow the immutable snapshot until collection; freeze its generation and
project directory at admission. Preserve source edit locking, navigation,
repaint, output focus/input and the existing combined event wait. Collect before
reading the interpreter result or releasing its buffers. Match run/generation,
reveal valid error positions through folds, and restore caret/selection/viewport
on other results. Stop/output close/Quit retain orderly child retirement.

**Gate:** physically type an unsaved integer and FP program and Run both; use
INPUT/GET/KEY; select an exact tabbed/folded parse-error location, fix and rerun;
Stop a busy program and rerun; close output during execution; Quit while source
is loading, parsing and waiting for input; resolve unsaved changes afterward.
Check that a failure cannot run old code. Observe zero scratch files or scratch
name reservations for Run and a peak of eight Tasks with the standard desktop,
or nine with its second shell. Refusal leaves the document unchanged. Execute
one existing Check/Build control and run its published command after IDE exit.

**Suggested commit:** `Run unsaved BASIC documents through the source interpreter`.

## FI6 — Limits and measured acceptance

On final composed inputs, freeze the input hashes and record both engine maps,
actual source admission/workspace limits, post-parse bytecode/heap capacity,
native/guest stack peaks and upper allocation peaks. Include full aligned-bank
backing, retained file snapshots, attachment/results, editor snapshot and loader
temporaries. Account for unused reserved arena/code capacity, not only used
bytes. Report zero or actual bank-zero deltas by fixed/root/kernel/public/idle.

Compare identical small integer and FP programs against the captured prior
workbench Run baseline. Measure cold and warm source acquisition, normalization,
parse, execution-start, final output and retirement separately. Record native
peer/pointer/console progress, Task/guest/client/window counts and physical
input-to-output timing. Do not claim a speedup from fewer files alone or set an
unsupported numerical factor as acceptance. Repeat only the affected cases if
measurement requires a code change, then refresh hashes and evidence.

**Gate:** document-sized input bounds, code-expanding/OOM source, maximum observed
array/string allocation, rejected one-past resources, repeated Run/error/Stop
without drift, preserved interrupt reserve, two-shell coexistence and stable
normal cleanup all pass. A 32 KiB document that fails parser workspace must
report the correct error and preserve editor source. Record remaining limits
explicitly; do not grow bank zero or silently discard other applications.

**Suggested commit:** `Record FastBasic interpreter limits and development results`.

## FI7 — Contracts, source and demo delivery

Publish implemented source-run behavior in [FastBasic reference](../reference/fastbasic.md),
the programming/workbench guides and workbench reference. Describe FB/FBI,
arguments, source/heap limits, the buffer API, errors, one-run lifecycle and
remaining unsupported behavior. Update workbench design/plan status and roadmap
so new Run uses this design while WB10+ debugging/graphics remain distinct.
Correct superseded eight-Task/two-large-pool claims in affected current pages;
preserve historical measurements. Put per-slice/final evidence in
`docs/development/fastbasic-interpreter*.json` and an indexed history record,
with exact inputs, actual test tier and unresolved qualification scope.

Package through the existing builder, for example:

```sh
python3 tools/build_demo.py --compiler-dir build/actionc --release-compiler \
  --gem-desktop --basic-workbench --output build/fastbasic-interpreter/demo
python3 tools/package_fastbasic_source.py \
  --output build/fastbasic-interpreter/exec816-fastbasic-source.zip
```

Extend the existing corresponding-source packager with the new inputs and
engine rebuild instructions. Include engines, examples and matching SYS/WORK
media; retain OF816, five-second standard startup, pinned ROM and notices. The
boot ZIP contains only boot files, short guide, licenses and checksums, with no
CAR/BIN or development output. Keep the complete modified FastBasic source ZIP
separate and prove its documented clean rebuild reproduces both engine payloads.

**Gate:** clean-extract the actual `exec816-demo.zip`, verify every checksum and
boot its own XEX, ROM and disks. Use physical keyboard/mouse input for shell
FB/FBI, unsaved editor Run, error/fix, INPUT, Stop/repeat, output close and Quit
beside two shells. Confirm language output and files independently, no Run
scratch artifacts, guards, ownership, final EXIT and restored OS state. Check
text/standalone bitmap source execution with focused fixtures; do not duplicate
the full desktop walkthrough or release matrix. Validate guide copies and links.

**Suggested commit:** `Deliver the FastBasic source interpreter demo`.

## Completion boundary

FI2 is the first shell interpreter milestone. FI5 completes integrated source
Run; FI7 completes the documented and packaged delivery. No stage requires a
new standalone compiler workflow, persistent engine, Pause/Continue, variable
inspection, direct mode or graphics. Those extensions need their own bounded
plans after this interpreter's execution, memory and lifetime behavior is known.
