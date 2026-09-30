# Resident shell implementation plan

Status: complete, 2026-09-23; all eight slices implemented and qualified. The
[shell design](../history/shell-design.md) defines public behavior, ownership and deliberate
AmigaDOS differences. This plan delivers it in executable slices, with a separate
commit after each major slice. The [implementation record](../history/shell-implementation.md) records completed gates.

Start with DOS current-directory support. The shell then runs resident built-ins
in the root Task, borrowing its DOS streams. It uses the existing console,
filesystem and SIO workers, retains read-only MyDOS and targets zero additional
fixed or per-Task bank-zero reservation. External o65 commands, Process/handle
inheritance, cooked CON:, asynchronous break delivery and windows remain follow-ups.

## Baseline and commit discipline

The starting implementation is `f8710d0`, the completed DOS-streams qualification
on main. Use the compiler revision in [toolchain/actionc.json](../../toolchain/actionc.json):
currently `ae1f555e77d0ae6caffbfc7453cbf06e3d098bee`, native ABI
`action65816.native.v1`, image format 3. The clean `build/compiler-ae1f555`
checkout is the documented local compiler input. Pass it explicitly to build/test
tools; record and qualify any later override rather than silently using another
checkout. Read the [platform contract](../reference/platform.md) before platform edits.

Use the [console machine/ROM pin](../../toolchain/altirra-console.json), accurate
drive timing, SIO patch off and burst I/O off for combined runs. Keep the
original [MyDOS media](../../tests/fixtures/mydos/manifest.json) immutable; build
additional path/corruption cases in isolated output directories and hash them.
The existing 128-byte file is 777 bytes, while the 256-byte fixture supplies the
full 70,003-byte file. They are separate coverage claims.

Before implementation, commit the design and this plan together. For each slice:
implement its behavior and basic rollback/cleanup, run its acceptance checks,
record compiler/source/image/map/result provenance, update the implementation
record and status, then commit. A later failure-testing slice expands coverage;
it does not defer safe cleanup of newly introduced resources. Do not publish
success stubs for calls or commands that a later slice will implement.

The prior full host run passed 145/146 tests, with the existing historical SIO
sector source-hash mismatch in `test_sio_sector_record`. Recheck and report that
baseline when executing; do not rewrite old evidence or treat unrelated new
failures as part of it. Compiler defects belong in actionc with focused native
regressions, not shell-specific compiler workarounds.

| Slice | Executable outcome | Suggested commit |
| --- | --- | --- |
| 1. Current-directory ownership | CurrentDir exchanges valid owned directory locks with guarded lifetime | `Add DOS current-directory selection` |
| 2. Named locks | NameFromLock returns canonical names; variable-sized locks free correctly | `Add canonical DOS lock names` |
| 3. Relative filesystem paths | Open/Lock resolve current, parent and current-volume-root forms | `Resolve DOS paths relative to current directory` |
| 4. Resident shell core | Real keyboard editor and HELP/ECHO/CD/EXIT work through DOS streams | `Add resident shell and CD command` |
| 5. Filesystem and memory commands | DIR/TYPE/MEM run with bounded memory and checked results | `Add shell directory text and memory commands` |
| 6. Redirection | Per-command Input/Output redirection restores defaults on all outcomes | `Add shell stream redirection` |
| 7. Failure and lifetime qualification | Deterministic faults preserve directories, streams and service ownership | `Qualify shell ownership and failure cleanup` |
| 8. Integrated qualification | Eight live Tasks meet shell, stack and SIO coexistence gates | `Qualify resident shell under concurrent SIO` |

Execute in order. Slices 1–3 are independently tested DOS changes, without a
shell dependency. Slice 4 provides a usable CD shell; slice 5 completes its
command set. Keep one shared resident implementation exercised by fixtures,
with test rendezvous kept out of production code.

## Repository integration

| Location | Planned work |
| --- | --- |
| `abi/dos.json`, `tools/generate_dos.py`, generated DOS module/includes | Add CurrentDir, then NameFromLock and ERROR_LINE_TOO_LONG when implemented; update native signatures, imports and binding generation. |
| `lib/dos/dosclient.act`, `lib/dos/doscalls.act`, `lib/dos/dosobjects.act`, `lib/dos/task-dos.inc` | Add the client directory field, validate owned identities, guard selected-lock release/context lifetime and preserve direct DosSlot association. |
| `lib/fs/fstypes.act`, `lib/fs/fspacket.act`, `lib/fs/fsregistry.act`, `lib/fs/fsdirectory.act` | Add lock-only canonical storage and correct allocation/free sizes, preserve mount/generation and enumeration semantics. |
| `lib/fs/fsnames.act`, `lib/fs/fshandler.act`, `lib/mydos/mydos.act`, `lib/mydos/mydosnames.act` | Separate namespace classification from base selection; extend private base-lock arguments and iterative resolution with actual ancestry. |
| `tools/native_program.py`, generated DOS/task metadata, `tools/dos_abi_fixture.py`, `tools/test_dos_abi.py` | Keep source provenance and packaging current; measure private layouts and execute all implemented public calls. |
| Proposed `examples/shell/shell.act` and shared application modules beside it | Resident entry point, upper-RAM shell state, editor/parser, commands and cleanup; use the same code from native fixtures. |
| `tests/programs`, `tools/test_dos_*.py`, console/stream harnesses | Focused directory/shell probes, physical-key scheduling, deterministic faults, maps/stacks and existing serial oracles. |
| Proposed `docs/history/shell-implementation.md`, `docs/guides/shell.md`, qualification records | Slice evidence, public build/use commands, actual budgets, qualified matrix and limits; update README/roadmap. |

Module/file subdivisions are implementation choices, not public interfaces.
Keep shell parsing out of DOS, filesystem workers and Exec. Do not add a generic
VFS, public Process record, ParentDir API or executable command ABI to complete
these slices. Preserve the existing native context and IRQ/NMI protocols.

## Memory, stack and evidence gates

Compare full maps against the
[bank-zero budget](../reference/platform.md#bank-zero-memory-budget): eight-slot
loading/runtime totals are 57,232/61,536 bytes including OS. Count guards,
padding and unused reservations; report fixed/per-Task deltas for every slice,
including zero, and near-image use separately. Keep root stack 1,536 bytes,
worker stacks 1,024, private idle 512, kernel stack 1,536 and all protected
256-byte interrupt reserves. Do not reduce task capacity or enlarge stacks to
make a failing call chain pass.

The [DOS-streams workload](../history/dos-console-streams-implementation.md#slice-7-integrated-concurrency-and-timing-qualification)
observed root/reader/filesystem/SIO/kernel maxima of 369/232/190/172/371 bytes
raw and 349/216/173/134/321 optimized. These are baseline observations, not
whole-program bounds. Recheck the complete blocking chain after DOS layout/path
changes, then command dispatch and redirection. Returning from preparation
helpers before Wait reduces live frames; adding nested wrappers does not.

| Upper-RAM budget | Gate |
| --- | --- |
| Client context | One new 3-byte directory pointer; expected 80 → 88 rounded bytes. Keep the existing 16-byte DosSlot, reply port/signal and reusable request. |
| Filesystem objects | Ordinary FileHandle remains 112 bytes. FileLock gains a bounded canonical-name trailer, at most 376 rounded bytes including the base object. |
| Name construction | At most one 256-byte shared name workspace; report any associated control fields and actual allocation/reservation change. |
| Shell private buffers/state | At most 1,288 bytes: 256 line, 128 arguments/state, 128 redraw, 264 shared name/FIB scratch and 512 transfer buffer. |
| Existing RAW resources | Account separately for the shared endpoint, handle, context/port and lazy request; do not count them as newly invented shell workers. |

Freeze offsets only after emitted SIZEOF/field-address checks. Record allocator
rounding, metadata and peak simultaneous ownership, especially old/new CD locks
and temporary redirected handles. If a proposed budget proves insufficient,
document the concrete layout/design change before claiming the gate satisfied.

Every native result records raw/optimized mode, compiler/ABI inputs, production
and fixture hashes, image/XEX hashes, machine/media pins, bounds, exact expected
status, memory maps, stack observations and ownership state. Fault probes identify
private hook/override sources. Preserve old qualification records as historical
evidence; write new shell records. Reuse prior results only when their measured
scope and recorded relevant inputs still match.

## Slice 1: current-directory ownership

Status: complete; all 22 native cases pass in both compiler modes.

Add CurrentDir to the generated DOS interface and one zero-initialized pointer
to ClientContext. Implement local exchange without allocating a lock, doing I/O
or scanning Tasks. Validate owned-list membership before payload, then lock kind,
filesystem backend, generation and directory type. Keep busy/active validation
and IoErr rules from the design. Null is unset; a null old selection with IoErr
zero is successful exchange. Same-pointer exchange adds no ownership.

Reject UnLock of the selected lock before sending a filesystem packet; preserve
it and report ERROR_OBJECT_IN_USE. Add explicit directory checks to context
release and reset paths, keeping the existing removal guard. Detach/null and
valid unlock cleanup must work after a mount goes offline. Absolute paths retain
their present behavior; relative path support arrives in slice 3.

**Acceptance:** emitted raw/optimized calls cover null/no-context exchange with
unchanged heap/worker counts, select/swap/restore/clear, same identity, file-lock
versus directory-lock, foreign/closed/wrong-kind identities, valid far identities
with a zero low word, invalid generation, busy/active rejection and preserved
selections. Test two Tasks independently,
selected UnLock refusal, context/removal misuse and successful release/reuse.
Closed-pointer checks must not claim protection against later address reuse.

Check actual context offsets/rounding, unchanged packet/port fields and bank-1/3
maps. Rebuild current ABI/client/stream-default and filesystem lifetime probes;
run an absolute single 70,003-byte Read in both modes to establish the new context
baseline with all guards and reserves intact.

**Evidence:** proposed `docs/qualification/dos-current-directory.json` and the
slice-1 section of the implementation record.

## Slice 2: canonical names and lock storage

Status: complete; all 22 native cases pass in both compiler modes.

Add a lock-specific length/name trailer without changing ordinary FileHandle
allocation or its common prefix. Assemble full names using the configured alias
and actual matched directory entries, not the caller's spelling. Record each
variable allocation's correct free size. Update allocation, rollback, publish,
lookup, close and lifetime probes together; retain mount generations and ExNext
tickets. Do not publish a lock before all its storage is initialized.

Implement NameFromLock and ERROR_LINE_TOO_LONG through generation. Validate the
owned lock, signed capacity and complete admitted writable extent before copy.
Capacity includes NUL; insufficient capacity leaves the destination unchanged.
Naming a retained lock reads cached metadata and works offline without a media
scan. Null reports invalid lock. Do not allocate a context merely to reject an
invalid lock; reject reentrant calls consistently and do not start a service.

**Acceptance:** raw/optimized absolute root, nested directory and file locks;
stored spelling versus folded input; exact-capacity and one-byte-short outputs;
null, negative, unmapped, wrapped and bank-crossing extents, including valid
zero-low-word far buffers; length/depth bounds;
offline/generation checks; mixed file/lock/RAW/NIL ownership; allocation failure
and exact heap/reference balance after variable-sized frees. Corrupt/ambiguous
directory fixtures must retain their existing errors.

Execute current ABI/layout probes in both modes, functional bank-1/3 cases and
file/directory/lifetime regressions. Check canonical-name scratch survives worker
resumption and is not reused while a queued operation still refers to it. Confirm
ordinary files remain 112 bytes and rerun the full-read stack regression if its
allocation or blocking path changed.

**Evidence:** proposed `docs/qualification/dos-lock-names.json`, including actual
lock-size distribution, maximum name, peak allocation and all free/rollback paths.

## Slice 3: relative, parent and current-volume-root paths

Status: complete; all 26 native cases pass in both compiler modes.

Refactor bounded name classification so absolute mounts and RAW:/NIL:/CON: keep
their existing dispatch/startup rules, while valid relative, empty, leading
parent and `:` forms obtain the calling client's selected directory. Missing
defaults report ERROR_NO_DEFAULT_DIR without creating a filesystem service.
Explicit mount paths remain usable with no current directory. Preserve mode,
suffix, alias, 24-bit wrap and full-path validation before submitting work.

Populate ACTION_FINDINPUT argument 2 and ACTION_LOCATE_OBJECT argument 1 with
the validated base lock when appropriate. The private handler revalidates owner,
pointer encoding, kind, directory type, generation and mount. An explicit mount
root still uses a null packet base; it must not ask the worker for its own DOS
default. Snapshot/protect the base for the complete synchronous operation.
An acquisition reference transfers to the new object on success and is released
on failure; the selected lock's existing reference remains untouched.

Seed iterative traversal with the locked directory's own extent and validated
ancestors. Implement empty-name duplication, current-volume root and leading
parent runs with root clamping. Reconstruct actual parent entry/ancestry metadata
and canonical stored names. Preserve cycle/overlap and depth checks after the
base and each descent; never turn a relative call into an unchecked shell-side
string concatenation. Reject unsupported embedded/trailing separators and dot
aliases consistently with the design.

**Acceptance:** execute the same Open/Lock operations from non-shell Tasks with
different current directories, cross-mount switches, unchanged already-open
handles and failed candidate exchanges. Verify each parent result with
NameFromLock, Examine, ExNext and a subsequent relative Open, including root,
one-level and deepest admitted bases. An extra child must not reset the depth
budget. Cover empty paths, no default, alias collisions, malformed names,
matching ambiguity, missing objects, full-name overflow and malicious packet
bases with exact errors and unchanged ownership.

Use both media sizes and banks 1/3 in raw/optimized functional tests. Keep RAW/NIL
headless/no-mount regressions. Run the complete single 70,003-byte relative Read
and the matching absolute case in both modes, verifying every byte and measured
call/stack boundaries. The short 777-byte fixture is not a substitute.

**Evidence:** proposed `docs/qualification/dos-relative-paths.json`; this finishes
the DOS prerequisite for a real CD command.

## Slice 4: resident shell, editor and CD

Status: complete; all 12 native cases pass, including physical-key sessions and the shipped entry in both compiler modes.

Add the resident entry point and shared application implementation. Allocate
bounded state in upper RAM, open/select one owned RAW handle, and try the optional
explicit initial directory (`D1:` in the reference image). Initial directory
failure reports its saved cause and leaves a usable prompt with no default;
console/setup failure unwinds before exit. A build without an initial mount
must still permit HELP/ECHO/EXIT and an explicit CD attempt.

Implement the 255-byte append-only editor, 36-column horizontal tail, continuation
indicator and bounded single-request redraw. Use the existing RAW control bytes;
never rely on Backspace crossing row zero-column. Add Return, Backspace, tab,
prompt Ctrl-C and discard-to-Return overflow/loss recovery. Identify a real
physical-key route for every advertised key with the pinned keymap.

Implement one parser with at most sixteen words, whole-word double quotes and
the specified quote/asterisk escape subset. Validate the entire line before any
command operation. Recognize redirection syntax but reject it as not yet
available until slice 6; do not discard operators and execute a different line.
HELP advertises only implemented commands. Add ECHO, CD and EXIT with internal
status/secondary-error results. CD uses Lock → CurrentDir → release old lock;
CD display uses NameFromLock on the shell's tracked borrowed selection.

**Acceptance:** run the actual shared shell with physical key press/release
schedules in raw/optimized builds. Exercise absolute/relative CD, CD without an
operand, `/`, `:`, failed startup/candidate CD, quoted ECHO and clean EXIT.
Check 0/1/36/37/255-byte editing boundaries, Backspace at a tail transition,
256th-byte invalidation, unmatched quotes, unsupported escapes/operators and
unknown commands. A truncated prefix or suffix after input loss must not run.
Check retained cells, actual screen/cursor and exact output bytes; no accidental
autowrap on redraw. Pure parser/model checks supplement emitted execution.

Normal startup creates only the existing services, reaching four public Tasks
when filesystem/SIO are started. Verify repeated commands do not create Tasks,
and exit detaches/unlocks the directory, closes RAW, releases context and restores
OS ownership. Capture stack and heap peaks from startup through teardown. Package
the actual resident entry point, not just an instrumented fixture.

**Evidence:** proposed `docs/qualification/shell-core.json`, plus initial
`docs/guides/shell.md` build/run instructions and honest foreground/Ctrl-C limitations.

## Slice 5: DIR, TYPE and MEM

Status: complete; 22 command cases plus both shipped-entry builds pass.

DIR uses Lock/Examine/ExNext, reports entries in on-disk order and treats only
ERROR_NO_MORE_ENTRIES as normal completion. Keep its lock and FileInfoBlock
private to the invocation. TYPE uses at most 512-byte Read chunks, compacts the
specified text conversion in place and writes only successful Read data. It
closes an explicitly opened input and borrows default streams. With no operand,
require a valid noninteractive selected Input; NIL ends immediately, RAW is
rejected because it has no EOF. Keep saved causal errors through cleanup.

MEM queries existing Exec ordinary/linear availability with their documented
flags; label total versus largest eligible block accurately. These views can
overlap, so do not add them as independent RAM pools. None of these commands
allocates a full file or introduces another Task.

**Acceptance:** native DIR checks root/subdirectory, empty directory, file-as-
directory rejection and exact names/types/sizes, including failure during
enumeration. TYPE covers empty and short files, 511/512/513-byte boundaries,
missing/corrupt input and conversion of printable bytes, tab, LF, CR, `$9B` and
other controls. Check exact transformed bytes across chunk boundaries, not just
success counts. MEM results are compared with the public memory queries around
known allocate/free operations, with correct bank-boundary eligibility.

Verify a complete 70,003-byte TYPE through selected NIL Output from a native
command fixture; shell redirection syntax is not needed yet. NIL does not inspect
payload, so observe the actual converted buffers at emitted Write boundaries and
compare them with an independent expected byte stream. Record both source and
converted counts. Use a bounded 1,025-byte RAW text fixture for exact output,
cursor and scrolling checks. This separates full-file conversion/read coverage
from display throughput; the single large Read regression remains separate.

Run raw/optimized public shell commands, both media sizes and bank-1/3 functional
coverage. Repeat resource balance and full blocking stack observations, including
filesystem/SIO workers, and document the final command syntax.

**Evidence:** proposed `docs/qualification/shell-commands.json`, binding expected
source/conversion results and exact terminal output to the real command code.

## Slice 6: per-command redirection

Status: complete; 14 native/parser/physical cases pass in both compiler modes.

Enable one `<source` and one `>destination` using the existing parser. Operators
require the specified preceding boundary, work outside quotes and are removed
from the built-in argument list. Reject append, missing/duplicate targets and
attached operators before opening anything. Resolve all targets against the
pre-command directory, independent of their textual order and of a later CD.

Save borrowed defaults, open all requested targets, then select them. On failure,
restore any changed defaults and close all acquired handles before returning;
never invoke a command after partial setup. On completion capture command status
and error, restore both defaults before closing temporary handles, then report
through the shell's retained console. Preserve successful CD changes. EXIT first
uses this same unwind path, then final shell cleanup.

Input uses MODE_OLDFILE and output MODE_NEWFILE. Preserve DOS backend decisions:
RAW/NIL work, filesystem output fails read-only, and CON:/CONSOLE: remain
unsupported. Redirecting Input does not make the shell read a script. Successful
selectors clear IoErr, so result capture must precede restoration and reporting.

**Acceptance:** physical/native commands include `TYPE <D1:TEXT.TXT >NIL:`,
`DIR >NIL:`, NIL EOF, quoted targets and operators inside quoted ECHO arguments.
Test first/second open failures, command Read/Write failure, duplicate operators,
restoration after success/error, same console as command output, `CD ... >NIL:`
and `EXIT >NIL:`. Diagnostics remain on the retained console. Count exact owned
objects, endpoint references, empty reply queue and request unbinding before the
next prompt; repeated redirections must not leak signals, ports or contexts.

Execute both compiler modes, including the real full-file TYPE via shell syntax,
and measure the deepest command/redirection/cleanup call chain before proceeding.

**Evidence:** proposed `docs/qualification/shell-redirection.json` with exact
default/ownership snapshots and error pairs before setup, command and cleanup.

## Slice 7: deterministic failures and lifetime

Status: complete; 26 cases pass, including four six-fault real serial responder runs.

Extend existing DOS/stream lifetime harnesses with selected directories and real
shell invocations. Use private generated test hooks or fixture gates to make
allocation, mount acquisition, packet publication/reply collection, candidate
CD and redirection failures deterministic. Record those sources explicitly;
do not add production pause loops or public fault APIs.

Cover context/port/signal/lock/name allocation exhaustion, failed candidate CD,
mount reference/generation saturation, cross-mount rollback, offline selection
cleanup and two independent clients. Add reentrant selection/release attempts,
queued/collected replies and stale signals, selected-lock UnLock refusal, live
context/removal misuse and repeated admission/exit. A selector restoration error
must stop dispatch rather than print another prompt with invalid defaults.

Re-run affected real 128/256-byte serial fault responders in raw and optimized
builds with a live current-directory lock and RAW endpoint. Assert their exact
causal errors and recovery behavior. Safe cleanup must release shell/stream/DOS
ownership. Unsafe SIO must reach exactly `$FF93` with retained state before normal
console/heap teardown. Expected failures need resource snapshots and the exact
fault oracle, not merely nonzero status.

**Acceptance:** all bounded cases complete or reach their specified fail-stop;
safe cases balance heap/locks/mounts/ports/signals and restore selections and OS
state. Cover combined service startup orders, no-mount shell operation, headless
DOS directory clients and bank-1/3 lifetime cases. Verify command status versus
saved secondary error after failed cleanup and preservation of the first cause.
All task/kernel guards and interrupt reserves remain intact.

**Evidence:** proposed `docs/qualification/shell-lifetime.json`, with checkpoint
ordering, injected faults, resource deltas and separate safe/unsafe outcomes.

## Slice 8: integrated shell, capacity and timing qualification

Status: complete; seven workloads, five replays, raw/optimized TX, four rebuilt
serial recovery runs and negative controls pass.

Extend the existing console/DOS stream stress harness using the real resident
shell implementation. Keep eight public Tasks simultaneously live: shell,
console/filesystem/SIO workers, and four test application clients providing a
relative large read plus independent allocation/message/signal work and output.
Private idle is additional. The extra application clients belong only to the
test workload, not the shipped shell or a background-command implementation.

Exercise physical editing/command input and public CD/DIR/TYPE/redirection while
the other clients progress. A synchronous filesystem command may wait behind
another whole filesystem request; record that delay rather than claiming the
shell is polling input during it. Use explicit admission/read/command/cleanup
checkpoints and counters to prove overlap, per-client directories and stream
ownership. Validate exact prompt rows in controlled editor runs; shared-writer
stress must not promise an isolated edit line that the design does not provide.

| Profile | Media | Compiler modes | Kernel bank | Observation |
| --- | --- | --- | --- | --- |
| FASTEST125 | 128 bytes/sector | raw and optimized | 1 | Timing plus identical-image/input replay |
| FASTEST125 | 256 bytes/sector | raw and optimized | 1 | Timing plus replay; complete 70,003-byte relative Read |
| STOCK810 | 128 bytes/sector | optimized | 1 | Existing stock-drive regression scope plus replay |
| FASTEST125 | 128 bytes/sector | raw and optimized | 3 | Functional shell/CD/ownership and map coverage |

Keep earlier bank-3 256-byte functional coverage from slices 3/5. Preserve the
78.942286-microsecond FASTEST125 physical-byte deadline, zero RX/TX misses or
TX gaps, the 100-microsecond alarm/watchdog gate and existing phase/collection
limits. Retain separate transport write/readback coverage; MyDOS Read cannot
qualify sector payload TX. Rerun recovery cases if any integrated fix changes
their inputs; otherwise link matching slice-7 evidence with hashes.

Measure endpoint/all Forbid intervals separately from CPU IRQ masking and idle
SEI/WAI time. No parser, resolver or editor wait may hold Forbid. Keep physical
byte/phase checks as the serial oracle; a whole-run masked maximum alone is
insufficient. Negative controls must reject delayed byte service, corrupted file
data and a missing key/command observation without relaxing a deadline.

Measure keyboard capture → collected RAW reply and capture → observed editor
update separately from command completion and serial service. Use the actual
edit-row/write observation; a matching character somewhere in TYPE output is
not proof of echo. Record median/max and workload bounds, compare the existing
scrolling limitation, and investigate regressions. Each timing case replays the
same image and physical-key schedule with passive observers disabled.

**Acceptance:** the complete matrix passes payload/conversion/command results,
ownership, full-capacity overlap, maps/stacks/guards/reserves and preset bounds.
Publish commands to build/run the actual shell, initial-directory configuration,
supported syntax, error/cleanup behavior and measured limits. Update design/plan
status, README and roadmap only for gates actually completed.

**Evidence:** proposed `docs/qualification/shell-concurrency.json` and completed
implementation/user documents. The collector rejects missing modes/matrix cases,
shortened full-file verification, changed replay inputs, touched reserves,
unexpected Tasks and weakened serial bounds.

## Execution bounds and common checks

Set these limits in harness inputs before qualification, recording them with
the result. Split unrelated test sessions instead of growing a single unlimited
run. Earlier fixture-specific limits continue to apply when reusing a harness.

| New case/checkpoint | Host seconds | Guest frames |
| --- | ---: | ---: |
| Focused API, rollback and lifetime case | 240 | 12,000 |
| Ordinary physical shell/editor checkpoint | 240 | 12,000 |
| Full-file TYPE-to-NIL, single large Read or complete shell session | 1,800 | 30,000 |
| Eight-task short checkpoint | 180 | 9,000 |
| Eight-task completion | 1,800 | 30,000 |

These are failure bounds, not latency promises. Pin byte/media profiles and
workload sizes before runs. Diagnose a timeout from progress/ownership evidence;
do not increase limits silently or insert successful-transfer sleeps to pass.

Use fresh `build/shell-sliceN/<case>` directories and explicit compiler inputs.
Common existing checks include:

```sh
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
python3 tools/generate_dos.py --check
python3 tools/test_dos_abi.py --compiler-dir build/compiler-ae1f555 \
  --output build/shell-slice1/abi
python3 -m unittest discover -s tests -p 'test_dos_*.py'
git diff --check
```

Add shell-specific host discovery once those tests exist. Host parsing and record
validation supplement emitted-machine-code tests. Run the full host suite at
meaningful integration boundaries, report the known baseline separately, and
rerun native checks only for changed behavior or unresolved failures. Normalize
host text line endings; keep binary media, ATASCII fixtures and traces exact.
Keep filtered evidence and provenance without committing bulk emulator output
or credential-bearing logs; follow existing build-artifact retention instructions.

## Completion

The milestone is complete when all eight acceptance gates have passing evidence
and separate implementation commits, the real shell entry point is documented
and packageable, and normal/unsafe retirement and eight-task timing are qualified
on the pinned configuration. A parser demo or commands that work only inside a
test fixture do not meet that outcome.

The next designs can then add cooked CON: and asynchronous break behavior,
Process/default inheritance and o65 command launch, or independent windows.
They must preserve the shell/DOS/device boundaries established here.
