# Resident shell implementation

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/README.md) and [history index](README.md).

Implementation follows the [eight-slice plan](../plans/shell-implementation-plan.md),
starting at `f8710d0` with compiler `ae1f555`. The [design](shell-design.md)
defines public behavior. All eight slices are complete.

## Slice 1: DOS current-directory ownership

CurrentDir accepts a caller-owned filesystem directory lock or null. It checks
owned-list membership before reading backend, generation or directory metadata.
The exchange does not allocate, send a packet or add a mount reference. A null
old selection and IoErr zero means success. Invalid, foreign, file, busy or active
selections leave the existing directory untouched. A retained directory can be
selected and detached after its mount goes offline.

UnLock refuses the selected directory with ERROR_OBJECT_IN_USE before preparing
a filesystem packet. ReleaseContext explicitly refuses a non-null directory,
even if the object list is empty. The existing Task removal guard requires the
entire DOS context to have been released; no public Task fields changed.

The directory pointer is at offset 80. Emitted SIZEOF is 84 (83 bytes of fields
and one alignment byte); the upper-RAM allocation grows from 80 to 88 bytes.
Packet, port, standard-stream and request offsets stay unchanged. There are no
new DOS slots, Tasks, signals or ports. Fixed and per-Task bank-zero reservation
deltas are zero; the eight-slot loading/runtime budgets remain 57,232/61,536
bytes including OS, guards, alignment and reserved capacity.

`tools/test_dos_directory.py` runs current-directory checks in kernel banks 1
and 3, selected-directory removal refusal, current native ABI, existing client
and standard-stream checks, Task reuse, filesystem lifetime/concurrent access
and a single complete 70,003-byte absolute Read in raw and optimized modes.
The far-identity fixture uses explicitly mapped test-owned storage at $0E0000;
it links/unlinks this storage without passing it to FreeMem. Its closed-pointer
check does not claim to detect address reuse.

The full host suite has 145 passes and the previously recorded historical
`test_sio_sector_record` source-hash mismatch. All 36 DOS host checks pass, including the new qualification-record checks.
Earlier native fixture attempts corrected a CARD loop bound, the record's
alignment byte and a task-creation count that excludes the root Task; they did
not require a production compiler workaround.

All 22 raw/optimized cases pass. The [qualification record](../qualification/dos-current-directory.json)
records compiler, source, image, machine, map and result provenance. Each directory
fixture completes 40 assertions; the removal probe stops at the expected Task
misuse status 4 with its directory/context retained. The existing reuse fixture
completes 260 Task lifetimes and 2,081 assertions in each mode.

Both absolute large reads verify all 70,003 bytes. Their root/filesystem/SIO/kernel
stack observations are 242/187/162/325 bytes raw and 220/173/140/303 optimized.
Every protected 256-byte reserve and stack/domain guard remains intact. Across
these cases the root maximum is 298 raw and 273 optimized; these are observations,
not whole-program bounds. The directory fixture uses 224 bytes of the already
reserved near-image arena; the library adds no near global state.

Reproduce with:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_dos_directory.py --compiler-dir build/compiler-ae1f555
python3 tools/dos_directory_record.py build/dos-current-directory --output docs/qualification/dos-current-directory.json
```

The record validator also rejects missing cases, truncated pointer/results,
stack-reserve damage and changed layouts.

## Slice 2: canonical lock names

NameFromLock reads cached lock metadata after owner, kind, backend and generation
validation. It validates signed capacity and the complete mapped extent before
copying. Capacity includes NUL; a short buffer reports ERROR_LINE_TOO_LONG without
writing a prefix. Naming retained locks works offline and creates no context or
filesystem service merely to reject an invalid lock.

The 112-byte filesystem object stays the complete allocation for ordinary files.
A lock appends a two-byte length and NUL-terminated name, constructed from the
configured alias and the actual matched entries. Free and rollback paths use the
same allocation size. The maximum request is 370 bytes, rounded to 376. The
boundary fixture constructs a private synthetic 255-byte cached name to exercise
that storage ceiling; it does not claim that this name was resolved from media.

The serialized worker keeps one 256-byte name buffer and a two-byte length.
Service grows from 170 to 428 bytes, with heap allocation 176 to 432: existing
padding means the actual increase is 256 bytes. Client allocation stays 88 bytes.
There are no new library globals or fixed/per-Task bank-zero reservations.
The generated interface now includes NameFromLock and ERROR_LINE_TOO_LONG (120).

All 22 raw/optimized cases pass in the [lock-name qualification record](../qualification/dos-lock-names.json).
The bank-1/bank-3 name fixtures each complete 53 assertions, including simultaneous
RAW/NIL/file/lock ownership, exact and short capacities, zero-low-word and crossing
buffers, invalid extents, offline naming and generation-exhaustion rollback.
A generated one-shot allocator override qualifies failure and successful retry
with exact heap/reference balance (six assertions). The depth fixture resolves
actual 239-byte directory and 252-byte file names, rejects a seventeenth directory,
and checks malformed/ambiguous and 255/256-byte inputs (12 assertions). Its media
are isolated, hashed derivatives; original MyDOS images remain unchanged.

The remaining cases cover the current 18-call ABI, CurrentDir, directory enumeration,
corrupt names, concurrent file calls, mount lifetime and one complete 70,003-byte
Read in each mode. Large-read root/filesystem/SIO/kernel stack observations are
242/187/170/325 bytes raw and 220/173/134/303 optimized. All protected reserves and
guards remain intact. The maximum observed root usage across this slice is 290
raw and 250 optimized. Name fixtures use 130 near-image bytes; library globals
and fixed/per-Task bank-zero deltas remain zero, with full eight-slot budgets
57,232/61,536 bytes during loading/runtime including OS.

The four real locks request names of 3/12/21/11 bytes and allocate 120/128/136/128
bytes, totaling 512. The synthetic storage-boundary phase holds those locks plus
the 376-byte maximum lock: 888 bytes of live lock storage. Its ordinary file
adds 112 bytes and its test-only workspace adds 432, separately from the production
worker. These are accounted fixture allocations, not an application memory bound.

No compiler change was needed. A local variable initially shadowed the Text
helper, and a generated include needed its fixture copied beside it. The older
directory/lifetime fixtures now assert the new Service size; archived evidence
retains its historical layout. All 37 DOS host checks pass.

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_dos_lock_names.py --case raw
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_dos_lock_names.py --case opt
python3 tools/dos_names_record.py build/dos-lock-names --output docs/qualification/dos-lock-names.json
```

## Slice 3: relative paths

Open and Lock classify explicit aliases, relative names and initial-colon paths
separately. RAW/NIL/CON classification remains independent of CurrentDir. An unset
default reports ERROR_NO_DEFAULT_DIR before creating a filesystem service. A
relative call validates its owned directory and acquires a mount reference under
the same publication/quiescence rules as an absolute call; success transfers the
reference to its new object, while failure releases it.

The packet carries the caller's base lock in FINDINPUT argument 2 or LOCATE_OBJECT
argument 1. The worker validates pointer encoding, membership, backend, generation,
mount, directory type and complete stored ancestry. Existing directory cursors
already include the locked directory itself; relative children preserve that
invariant and the 16-directory limit.

Empty Lock creates a separate owned lock. Initial `:` starts at the current
volume's root; leading `/` steps to parents and clamps at root. Parent resolution
scans the actual parent directory for a unique matching extent, reconstructs the
entry and canonical name, and preserves the remaining path and ancestry. It
returns between physical reads, keeping helper frames off the blocking stack.
Unsupported embedded/trailing separators and dot aliases still fail explicitly.

Service adds a two-byte parent-sector field and three-byte continuation pointer:
434 bytes, rounded to 440, versus 428/432. The 256-byte name workspace is reused.
Client and object allocation rules are unchanged. No library globals, public Task
fields or fixed/per-Task bank-zero reservations are added.

The [qualification record](../qualification/dos-relative-paths.json) contains 26
native cases. Eight functional cases cover banks 1/3, both media sizes and both
compiler modes, each with 82 assertions. Distinct D1/D2 payloads establish that
an already-open handle keeps its original volume after CD. Private packet tests
reject invalid pointer encoding, unknown/foreign identities, wrong kinds/mounts,
stale generations and malformed ancestry without leaking references.

Depth tests execute 14 assertions against actual 16-level directory chains,
including parent metadata/enumeration, another relative Open and the rejected
17th directory. Corrupt ancestry tests execute ten assertions for self-cycles,
overlapping extents and a file overlapping its base directory. Remaining cases
exercise the current ABI, headless/mixed streams, lifetime, directory regressions
and matching complete relative/absolute 70,003-byte reads in both compiler modes.

The complete relative Read observes root/filesystem/SIO/kernel stacks of
250/187/162/325 bytes raw and 232/173/134/303 optimized. The functional fixture
observes root/independent-client stacks of 268/254 raw and 248/238 optimized.
All guards and protected reserves remain intact. Functional fixtures use 212
near-image bytes; the relative large-read fixture uses 120. Fixed/per-Task
bank-zero deltas are zero, retaining eight-slot 57,232/61,536-byte budgets.
All 38 DOS host checks pass, including evidence negative controls.

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_dos_relative.py --case raw
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_dos_relative.py --case opt
python3 tools/dos_relative_record.py build/dos-relative --output docs/qualification/dos-relative-paths.json
```

## Slice 4: resident shell core

The [resident entry](../../examples/shell/shell.act) and native fixtures share
[shell-session.inc](../../examples/shell/shell-session.inc). The root Task opens/selects
one owned RAW handle, optionally selects D1's root, and runs HELP/ECHO/CD/EXIT
synchronously. Failed initial CD leaves the console usable. EXIT restores borrowed
stream defaults, detaches its directory, releases owned resources and returns
through the existing service shutdown. A lock awaiting release remains explicitly
tracked if cleanup fails.

All reusable state occupies one 1,288-byte ordinary upper-RAM allocation:
128 bytes of state/word pointers, 256 line, 128 redraw, 264 name scratch and 512
reserved for later TYPE transfers. The state layout is checked by emitted SIZEOF;
the sixteen word pointers and retained-lock cleanup pointer fit the 128-byte
header. Numeric output uses bounded decimal-place subtraction because the pinned
native backend explicitly rejects multiplication/division/remainder. Single-byte
RAW writes use the final scratch byte: application stack bytes are not in RAW's
admitted image/heap buffer ranges.

The editor emits each redraw in one Write, keeping the 36-character tail and
continuation marker inside columns 0–38. Its 255-byte logical bound is separate
from screen width. Overflow invalidates the whole line. Input loss has a distinct
resynchronization state that only Return clears; Ctrl-C cannot admit a suffix.
The parser compacts whole-word quotes in place and rejects malformed or unsupported
syntax before dispatch. Command status and secondary error survive diagnostics
and resource cleanup.

The shell key-test pin adds bridge names for Atari matrix keys `*`, `<` and `>`:
[additional patch](../../toolchain/patches/altirra-shell-keys.patch),
[pinned binary/configuration](../../toolchain/altirra-shell-console.json). Codes come
from Altirra's existing keyboard map. CPU/peripheral semantics and the original
console test pin remain unchanged. Backtick parsing has emitted-byte coverage;
the current production keymap has no physical backtick mapping.

Physical fixtures copy each actual Write payload into private reserved image
memory and then call the unchanged production Write helper. Their generated
wrapper also provides test-only pauses for typeahead/FIFO overflow. The shipped
entry is built and executed separately without these hooks. Capturing NIL writes
this way will also permit independent content checks in the following slice.

The [core record](../qualification/shell-core.json) contains twelve passing cases:
physical, parser/editor, heap sampling, console-startup failure, and uninstrumented
entry with/without mounts, each raw and optimized. Each physical session consumes
818 input bytes and verifies all 55,871 Write bytes plus fourteen retained/physical
screen checkpoints. It covers quoted commands, parent/root CD, invalid commands,
1/36/37/255-byte editor boundaries, Backspace, overflow, Tab, both Ctrl-C/BREAK,
queued input and actual 129-key FIFO overflow. A following `exit` suffix and
Ctrl-C remain discarded until Return; the next complete command works normally.

The parser/bounds probe checks 32 parser cases and 100 assertions in each mode,
including the sixteen-word limit, empty quotes, escape rejection, literal
asterisk/backtick bytes, overflow cancellation and loss resynchronization. Console
startup failure releases shell/context state with five assertions and no workers.
The actual entry executes HELP/ECHO/CD/EXIT in all four mounted/unmounted compiler
combinations, without instrumentation. Mounted sessions create exactly three
workers, giving four public Tasks plus private idle; unmounted sessions create
only the console worker. Repeated commands create no additional Tasks.

The observed heap maximum above the existing console baseline is 3,056 bytes in
both modes. Samples follow completed Writes and candidate Lock, before releasing
the previous directory. The maximum owned-object count is three: RAW plus both
CD locks; their largest simultaneous storage is 264 bytes (128 + 136). These are
observed operation-boundary values, not a bound on arbitrary transient allocations.
Every normal fixture returns the heap to its initial value. Shell-private storage
is exactly 1,288 bytes, rounded without extra payload padding; context, endpoint,
request and filesystem allocations remain separate existing DOS resources.

The shipped entry uses 237 near-image bytes. Its root/console/filesystem/SIO/kernel
stack observations are 446/168/180/162/344 bytes raw and 415/150/168/121/328 optimized.
The longer instrumented physical runs observe 506/174/195/162/337 raw and
477/158/173/121/334 optimized. All guards and 256-byte interrupt reserves remain
intact; fixed/per-Task bank-zero reservation changes are zero, retaining the
57,232/61,536-byte eight-slot loading/runtime budgets. Physical scripts span
6,835 guest frames raw and 6,594 optimized; these functional observations do not
qualify concurrent SIO timing or asynchronous command cancellation.

The full host run passes 148/149 checks, retaining only the documented historical
SIO-sector source-hash mismatch. The additional core-record negative controls
pass. Build/use instructions are in [the shell guide](../guides/shell.md).

```sh
# Repeat with --case opt. Each runner also accepts an explicit --compiler-dir.
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_shell_core.py --case raw --output build/shell-core/raw/physical
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_shell_parser.py --case raw --output build/shell-core/raw/parser
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_shell_heap.py --case raw --output build/shell-core/raw/heap
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_shell_start_failure.py --case raw --output build/shell-core/raw/start-failure
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_shell_entry.py --case raw --output build/shell-core/raw/entry
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/test_shell_entry.py --case raw --no-mount --output build/shell-core/raw/entry-no-mount
python3 tools/shell_core_record.py build/shell-core --output docs/qualification/shell-core.json
```

## Slice 5: directory, text and memory commands

DIR holds a private lock/FIB and enumerates on-disk order. It prints a trailing
slash for directories and the exact byte count for files; only error 232 ends
enumeration normally. TYPE uses the reserved 512-byte transfer area and compacts
text in place after successful Read calls. CR is dropped, ATASCII 155 becomes LF,
printable ASCII/TAB/LF pass, and other bytes become dots. A failed Read contributes
no output, including any partial data already copied into the caller buffer.
Explicit input is owned by the command; default Input is borrowed and must be
noninteractive. NIL ends immediately. MEM labels ordinary and linear total/
largest values separately, using the public queries without adding overlapping
views together.

The 128-byte state header now includes a separate owned command-input pointer,
using three formerly reserved bytes. The 1,288-byte allocation is unchanged.
Decimal formatting moves to the redraw area, preserving DIR's live FIB and
ExNext ticket throughout enumeration. Cleanup retains failed-to-close identities
and the first causal error, stopping dispatch when ownership cannot be retired.

The larger command fixture exposed the loader's 64-extent limit: small adjacent
initialized data objects each used a descriptor. The packager now combines only
adjacent regions with equal loading kind/owner, including initialized data and
zero-fill. It preserves gaps, validates original regions before combining them,
and keeps bank splitting and all size/ownership rules. Independent XEX replay
checks exact initialized/zero bytes and rejects malformed regions. The manifest
and fixed/per-Task bank-zero reservations do not grow. This is a packager change,
not a compiler defect.

A separate test-server issue made each partial video-frame advance sleep for a
full frame interval. The [host pacing patch](../../toolchain/patches/altirra-headless-frame-pacing.patch)
now paces completed frames only, retaining command polling and paused behavior.
The [paced shell test pin](../../toolchain/altirra-shell-paced.json) preserves guest
CPU/peripheral semantics. A [same-image comparison](../qualification/headless-pacing.json)
executes the same fifty-tick sleep on both binaries, with matching guest tick
counts and intact contexts/guards/ownership. Host elapsed time improves; this
is not a change in guest SIO throughput or a substitute for cycle-based timing
qualification. The earlier console/key pins and records remain historical.

The [command record](../qualification/shell-commands.json) contains 22 passing
raw/optimized cases: both sector sizes in banks 1/3, full TYPE, exact RAW text,
corrupt Read and invalid-name enumeration. Each basic run completes 17 commands
and 63 assertions. The 70,003-byte input produces exactly 69,730 converted bytes,
observed at command Write boundaries even though the selected destination is
NIL. The 1,025-byte RAW input produces 1,021 bytes with exact retained/physical
screen and cursor checks. DIR checks all root names/sizes, nested/empty directories
and errors 212/210; the corrupt file reports 213 without a failed-call prefix.
MEM matches four public queries before/during/after a 513-byte allocation,
including its 520-byte rounded charge and complete free balance.

Maximum observed root/console/filesystem/SIO/kernel stack use across these cases
is 522/166/194/182/338 bytes raw and 473/148/192/134/321 optimized. All guards and
256-byte reserves remain intact. The fixture uses 409 near-image bytes; fixed
and per-Task bank-zero deltas remain zero. The actual shipped entry also passes
in both modes, with root maxima 446/415 bytes and three created service Tasks.
Every command returns to balanced client objects/heap, and teardown restores
console/OS ownership. These are measured workload maxima, not universal bounds.

The 256-byte root fixture contains a 278,300-byte PAD.BIN as well as LARGE.BIN;
exact DIR sizes require walking their chains. The longest case takes 14,518
raw / 14,502 optimized guest frames, below the 30,000-frame completion gate.
The raw bank-3 executable occupies the original test capture address, so that
case moves capture to D0000–EFFFF and command text to F8000, clear of code and
Task metadata. This is fixture storage, not shell allocation. Results bind both
harness revisions and generated images; the recorder now hashes its loaded source
at import instead of reading a potentially edited runner at completion.

Validation also passes all 38 DOS host checks and 11 banked-package checks.
The qualification collector has negative controls for missing cases, wrong
conversion/output, memory/error mismatches, capacity and reserve changes.
Reproduce the command matrix with `tools/test_shell_commands_suite.py --case raw`
and `--case opt`, passing `--compiler-dir build/compiler-ae1f555`; collect it with
`tools/shell_commands_record.py`. The paced server is pinned explicitly.
The full host suite passes 152/153 checks; the sole failure remains the historical
SIO sector record's source-hash mismatch described in the baseline. No historical
evidence was rewritten. Documentation link checks and `git diff --check` pass.

## Slice 6: command stream redirection

The parser accepts one input and output target, optionally quoted, and removes
them from the built-in arguments. All sixteen words, syntax and command arity
are checked before opening anything. Targets use the pre-command current
directory. Setup saves borrowed defaults, opens all targets, then selects them;
cleanup restores both defaults before closing either temporary handle. It also
runs after setup/command errors and EXIT. Successful CD remains selected.
Restoration failure retains both handles and stops further dispatch; final cleanup
can retry restoration without losing the first causal error. A failed Close
retains its unresolved identity. No new worker, buffer or bank-zero reservation
is introduced; one reserved header byte tracks setup/selection/cleanup state.

The [redirection record](../qualification/shell-redirection.json) contains 14 passing
raw/optimized cases. Each basic fixture executes 35 commands and 321 assertions,
checking defaults, selected directory, exactly two owned objects between commands,
one RAW endpoint reference, no active reader, an empty reply queue and an unbound
reusable request. It covers both open failures, read-only output, unsupported CON:,
NIL EOF, quoted operators/targets, successful CD, repeated handles, output error
206, invalid syntax and redirected EXIT. Error 213 during TYPE is followed by a
successful command with restored defaults. The full syntax-driven TYPE verifies
all 70,003 source / 69,730 converted bytes at actual emitted DOS.Write boundaries.
A deliberately missing Output also records the failed Write attempt separately
from its console diagnostic; skipped later writes are not counted as emitted I/O.

The shipped entry accepts physical `<`/`>`/quote keys for TYPE, CD, ECHO and EXIT,
with exact terminal/cursor restoration in both modes. The emitted parser runs
35 cases / 165 assertions, including sixteen-word bounds counting targets and
exact compacted target offsets. Maximum observed root/console/filesystem/SIO/
kernel stacks are 484/174/195/182/350 bytes raw and 445/148/192/134/334 optimized.
Guards and all protected interrupt reserves remain intact. These are workload
observations, not universal bounds. The shell still allocates 1,288 upper-RAM
bytes with zero fixed/per-Task bank-zero change.

Run `tools/test_shell_redirection_suite.py --case raw` and `--case opt` with the
pinned compiler; `tools/shell_redirection_record.py` collects the complete matrix.
All four shell host-record checks, generated DOS checks and documentation/link
checks pass. Broader deterministic cleanup failures are the next slice.

## Slice 7: failure and lifetime qualification

The [lifetime record](../qualification/shell-lifetime.json) contains 26 passing
raw/optimized cases. Private generated hooks fail combined lock/name allocation,
the candidate directory exchange, output restoration and temporary Close. Public
heap/signal exhaustion separately reaches shell allocation, client allocation,
port allocation and signal failure, with no partially published client. The
port probe leaves exactly the current 88-byte client allocation available before
its port attempt. Lock and canonical name share one allocation, so there is no
independent name-allocation phase to inject.

Real shell commands cover mount-reference and generation saturation, cross-mount
rollback, busy/reentrant selection/release, selected-lock UnLock refusal, cached
names while offline and offline cleanup. Snapshots retain the old directory,
two objects and one RAW endpoint reference after recoverable errors. Failed
Output restoration leaves its temporary handle selected, with status 20/error
202; failed temporary Close after unsupported CON: preserves the first error 209.
A subsequent command cannot clear either fatal result. Final cleanup retries the
failed operation and balances ownership. Returning with a live shell instead
reaches exactly the existing Task misuse status 4 with its directory/RAW retained.

The existing generated RAW delivery hooks now execute with two independently
selected directories through queued and collected replies, plus foreign-directory
selection rejection. They retain the exact checkpoint order 1/2/6/5/3/4/3/3,
stale-signal filesystem reads, request unbinding and endpoint/port cleanup.
Both startup orders and banks 1/3 pass. Headless directory clients, an unmounted
physical shell session, and 260 Task/context admission-release cycles also pass;
all use the eight-slot reservation profile. The reuse case records 2,081 native
assertions with full stack coloring and upper-bank ownership checks.

Four real 128/256-byte responder runs cover checksum, device error, short reply,
first-cause retention, framing and protocol faults. The shell has a selected
MyDOS directory and RAW endpoint during each fault. Cleanup first detaches the
cached lock and stops the filesystem, whose open SIO request must be released
before transport shutdown. Safe cases then restore console/OS ownership. Unsafe
cases reach exactly `$FF93` before ShellFinish, retaining the shell allocation,
RAW endpoint and console cells. The host checks both checkpoints and retained
state. One initial MyDOS transaction is recorded as a baseline; actual serial
post counts are checked against that baseline plus the existing fault oracle.
The original pinned fault responders and byte/error oracles are unchanged.

Maximum observed root/worker/kernel stack use is 480/314/344 bytes raw and
451/293/325 optimized. Guards and protected interrupt reserves remain intact;
the largest instrumented near image is 665 bytes. Fixed and per-Task bank-zero
reservation deltas are zero. No production policy or compiler workaround was
needed. Private recovery helpers take a dummy fixture argument to stay out of
the fixed Task-entry table; the resident shell itself is unchanged.

Run `tools/test_shell_lifetime_suite.py --case raw` and `--case opt` with the
pinned compiler, then collect with `tools/shell_lifetime_record.py`. All five
shell host-record checks pass, including missing-fault, wrong-first-cause,
continued-dispatch, retained-state, race, reuse and reserve negative controls.
Generated DOS definitions, documentation links and `git diff --check` pass.

## Slice 8: integrated shell, capacity and timing qualification

The integrated fixture runs the actual shared shell editor, parser and commands
with eight public Tasks: root shell, console/filesystem/SIO services, a relative
file reader, and allocation/message/signal peers. Private idle is additional.
Nine physical keys enter `echo ok ` and Return. Four subsequent calls pass whole
command lines through ShellCommand: `CD TOOLS/SUB`, `TYPE DATA.BIN >NIL:`,
`CD :` and `DIR TOOLS >NIL:`. The reader owns its own current directory and makes
one Read for the complete file. Every command checks restored defaults, selected
directory, two owned objects, an empty reply queue and an unbound reusable request.
The host checks all 1,259 root Write bytes, every file byte, eventual retained/
physical screen agreement, and cleanup back to the initial heap/OS ownership.

All test clients retain their existing slots; the production shell still needs
four public Tasks including its services. The fixture selects its five actual
application entry routines through the original Task-entry validator, excluding
ordinary private helpers from the fixed sixteen-entry table. It preserves the
compiled function bodies, signature/address checks, public capacity and runtime
ABI. Generated entry metadata and the 8 KiB test-only Write capture are hashed.
The same capture code executes in observed and replay images. Passive CPU/mask
observers are disabled for replay; image, physical-key schedule, root Write bytes
and final screen must remain identical.

The first optimized 70,003-byte run exposed a watchdog service at 100.298994 µs
against the existing 100 µs gate. The [rejected observation](../qualification/shell-watchdog-regression.json)
retains its original source/image/trace hashes. Payload, native cleanup and RX/TX
deadlines passed, but this result was correctly rejected. The timer asserted
after the IRQ route's initial scan, during keyboard delivery. Two bounded RX
checks and full IRQ return/re-entry delayed its service.

The console service helper now checks at most one enabled pending watchdog
after RX, both before the keyboard wake post and before IRQ return. It rechecks
the current enable shadow because RX may have completed the request and disabled
the timer. There is no loop, extra persistent state, ABI change or compiler
workaround. Fixed and per-Task bank-zero reservation deltas remain zero. The
timing matrix, TX/readback and all four real serial recovery runs are rebuilt
for this platform change; the original byte and alarm limits remain unchanged.

The [completed concurrency record](../qualification/shell-concurrency.json) contains
seven passing workloads, five identical-image/input replays, two transport TX
runs with replays, and four rebuilt six-fault serial responder runs. FASTEST125
covers both sector sizes and compiler modes in bank 1; STOCK810 covers optimized
128-byte media. Bank 3 covers both compiler modes functionally, retaining earlier
256-byte bank-3 coverage from slices 3/5. All guards and protected reserves pass.
Four edited-trace controls reject a missing key, missing command, delayed SERIN
service and corrupted wire data. They change copies of observations, not guest
execution. The original watchdog rejection is a separate real execution record.

| Case | File bytes | Read bytes/s | Capture → collected, ms median / max | Capture → completed editor Write, ms median / max |
| --- | ---: | ---: | ---: | ---: |
| target128-raw | 777 | 860 | 31.46 / 54.59 | 200.50 / 1916.19 |
| target128-opt | 777 | 894 | 27.68 / 54.78 | 150.00 / 1855.34 |
| target256-raw | 70,003 | 1,433 | 26.92 / 70.05 | 211.85 / 2226.72 |
| target256-opt | 70,003 | 1,432 | 34.08 / 60.02 | 144.14 / 1981.38 |
| stock128-opt | 777 | 358 | 29.59 / 47.28 | 424.67 / 1798.96 |

The full-file Read takes 48.86/48.88 seconds raw/optimized. The first queued CD
completes in 45.48/46.03 seconds.
The previous DOS-stream workload measured 1,436/1,438 bytes/s. Read timing spans
its emitted call/return, excluding Open, verification and cleanup. A CD submitted
during another Task's whole filesystem request waits behind that request.
Other runnable Tasks continue; the foreground shell is synchronous and does not
collect another command while CD is pending. The workload deliberately lists
TOOLS rather than the root containing the unrelated 278,300-byte PAD.BIN.

Each keyboard row contains nine samples. Collection ends after DOS.Read returns;
editor timing ends just after the specific ShellRedraw DOS.Write completes.
That proves retained output, not physical scanout or an isolated edit row.
Return includes ECHO and the following prompt redraw, so its latency includes
command output and scrolling. The previous stream workload's 1.7-second physical
echo observation uses a different boundary. This result preserves the measured
scrolling limitation; it does not qualify faster rendering or asynchronous break.
Final retained cells, physical screen/cursor and replay display are checked separately.

| Case | RX max, µs | TX refill max, µs | Watchdog max, µs | Endpoint / all Forbid max, ms | CPU / idle masked overlap max, µs |
| --- | ---: | ---: | ---: | ---: | ---: |
| target128-raw | 67.66 | 64.85 | 85.64 | 1.63 / 6.88 | 130.68 / 3931.47 |
| target128-opt | 66.54 | 64.85 | 81.13 | 1.37 / 6.71 | 127.44 / 3996.24 |
| target256-raw | 72.74 | 65.97 | 90.15 | 5.30 / 6.88 | 185.80 / 4043.18 |
| target256-opt | 72.18 | 68.79 | 90.15 | 2.69 / 6.56 | 152.74 / 4000.47 |
| stock128-opt | 63.15 | 64.28 | 88.95 | 1.65 / 6.71 | 120.81 / 3993.63 |

There are zero RX/TX deadline misses or TX gaps. FASTEST125 retains the
78.942286 µs physical RX byte deadline and 100 µs alarm/watchdog limit; phase,
collection, next-start and Forbid limits are unchanged. Endpoint Forbid permits
IRQs and is attributed to emitted DOSRAW call sites. CPU-masked work is separated
from the SEI/WAI/CLI idle path. A whole-transaction masked maximum can include
control phases or idle wait; it is not substituted for the physical-byte oracle.
Separate transport writes verify the sector payload, acknowledgements, exact
media mutation/readback and 1,000–1,800 µs write turnaround in both modes.

Maximum observed root/worker/kernel use is 468/337/363 bytes raw.
Maximum observed root/worker/kernel use is 433/303/341 bytes opt.
The mixed fixture uses 582 near-image bytes.
These are workload observations, not universal bounds. Root/worker/idle/kernel
reservations remain 1,536/1,024/512/1,536 bytes, including protected 256-byte
reserves. The shell still owns 1,288 upper-RAM bytes. Fixed and per-Task bank-zero
deltas are zero, with eight-slot loading/runtime totals unchanged at 57,232/61,536
bytes including OS and reserves.

Reproduce the seven workloads and four recovery runs with explicit compiler inputs:

```sh
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
python3 tools/test_shell_concurrent_suite.py --compiler-dir build/compiler-ae1f555 \
  --output build/shell-concurrency-final
python3 tools/test_shell_lifetime_suite.py --case raw --only serial-128,serial-256 \
  --compiler-dir build/compiler-ae1f555 --output build/shell-concurrency-final/recovery
python3 tools/test_shell_lifetime_suite.py --case opt --only serial-128,serial-256 \
  --compiler-dir build/compiler-ae1f555 --output build/shell-concurrency-final/recovery
python3 tools/test_shell_trace.py --probe build/shell-concurrency-final/target128-opt \
  --output build/shell-concurrency-final/controls
```

For TX/readback, pass the compiler object to the existing transport runner:

```sh
python3 - <<'PY'
import json, sys
sys.path.insert(0, 'tools')
from native_program import ROOT, compiler
from test_console_tx import run
pinned = compiler(ROOT/'build/compiler-ae1f555')
for mode in ('raw', 'opt'):
    out = ROOT/'build/shell-concurrency-final'/('tx-' + mode)
    result = run(out, mode == 'opt', pinned)
    (out/'results.json').write_text(json.dumps(result, indent=2) + '\n')
PY
python3 tools/shell_concurrency_record.py build/shell-concurrency-final \
  --output build/shell-concurrency-final/qualification.json
```

The collector binds production, fixture, compiler, image, emulator and media
inputs; it rejects incomplete modes, shortened reads, changed replays, missing
concurrency, weakened serial gates, enlarged stacks and touched reserves.
The [shell guide](../guides/shell.md) builds the actual resident entry point. External o65
commands, Process inheritance, cooked CON:, foreground asynchronous break and
independent windows remain later milestones.

Final host validation passes 155/156 tests, including the new qualification
record and eighteen corrupted-record controls. The sole failure remains the
pre-existing historical SIO sector record's source-hash comparison; the current
watchdog fix changes that source again, and the historical evidence is preserved.
Generated DOS checks, local documentation links and `git diff --check` pass.
Native execution scope is the matrix, TX/replay and real responder runs above;
the host suite alone is not the qualification claim.

## Resident boot messages and playground disk

The shipped entry now prints the Exec816 commit, console readiness, SIO readiness
and D1 mount progress before its first prompt. The build generates `execbuild.act`
and `exec-build.json`; provenance retains the full revision and dirty state.
Console readiness follows RAW setup, SIO readiness follows a successful public
device open/close, and mount readiness follows root-lock acquisition and selection.
Only configured geometry and the nominal serial profile are printed; there is no
CPU or memory detection. The SIO worker is started before the filesystem worker.
The temporary port/request are freed immediately after the device check.

The default [mount](../../config/shell-mydos.json) now matches a separate 720-sector,
128-byte playground ATR generated from [four small text files](../../examples/shell-disk/).
The disk is 92,176 bytes including its header. Large regression media are unchanged.
The [shell guide](../guides/shell.md) describes building and booting both files.

Validation used compiler `ae1f555`, the pinned ROM and
[paced Altirra bridge](../../toolchain/altirra-shell-paced.json), with Generic57600:

- Raw and optimized emitted resident entries: exact startup screen, physical-key
  HELP/ECHO/CD/DIR/TYPE/EXIT, nested paths, final screen, ownership cleanup,
  intact stack/domain guards and OS screen/cursor/keyboard restoration.
- Optimized invalid-media and no-mount builds: correct startup diagnostics,
  no false mount-ready message, usable prompt and clean shutdown.
- The host disk test independently walks all directories/chains, compares file
  bytes and verifies allocation/VTOC consistency. Native packaging and mount
  configuration checks also pass (seven host checks total).
- Git identity checks cover clean, modified, staged, untracked and non-Git input.

Root DIR took 150/148 guest frames raw/optimized, about three PAL seconds.
These are small-disk observations, not a new throughput or concurrency qualification.
Maximum observed root/kernel stack use was 498/350 bytes raw and 461/334 optimized.
Reserved bank-zero delta is **0 fixed bytes and 0 bytes per Task**, including
guards, alignment and unused capacity. No stack reservation changed.

Reproduce with the Cargo environment settings above:

```sh
python3 tools/test_shell_entry.py --case raw --paced --output build/shell-playground/raw
python3 tools/test_shell_entry.py --case opt --paced --output build/shell-playground/opt
python3 tools/test_shell_entry.py --case opt --paced --invalid-disk --output build/shell-playground/invalid-opt
python3 tools/test_shell_entry.py --case opt --paced --no-mount --output build/shell-playground/no-mount-opt
python3 -m unittest discover -s tests -p test_shell_disk.py
```

## Task and version commands

Startup now retains the configured baud profile and adds `exec: 8 task slots`
(using the actual build capacity). Disk geometry is omitted because it is supplied
by the build. Mount attempt/success/failure messages still reflect executed work.
The Exec816 commit remains a literal seven-character hexadecimal string without
`0x`; no numeric conversion discards leading zeros. VER prints the same identity
and the actionc commit from the compiler pin. Dirty/source-archive handling is
unchanged. The pin is labelled explicitly; actual local compiler overrides remain
recorded separately in build provenance.

TASKS copies live public contexts in slot order, including the shell and services,
then prints slot/state/name through DOS.Output. Private idle and free slots are
excluded. A generated internal TASKINSPECT module derives pool addresses, stride
and field offsets from the existing machine-readable Task layout. It adds no
gateway selector or public Exec ABI. This bounded diagnostic scan runs only on
an explicit command, never in IRQ signal delivery.

Snapshot uses nested Forbid/Permit with IRQs enabled, copies names before their
owners can be removed, and releases scheduling exclusion before console output.
Each copied record is 26 bytes, with at most 23 printable name characters and a
terminator. The shell reuses its 512-byte transfer buffer; its 1,288-byte allocation
and all bank-zero reservations remain unchanged. The root and filesystem worker
publish the names `shell` and `dos.filesystem` under scheduling exclusion.

Native validation with compiler `ae1f555` covers:

- Raw/optimized task inspection: 194 assertions per build, RUNNING/READY/signal
  WAITING/timed SLEEPING, removal, copied-name lifetime, null/short output buffers,
  unnamed/long/control-character names, nested Forbid restoration, and names and
  output crossing bank boundaries. Untouched-buffer and stack/domain guards pass.
- Raw/optimized parser: 187 assertions per build, including command case and
  operand rejection. Real shell runs cover TASKS/VER, NIL redirection, exact
  physical output after each command, file/directory commands and clean EXIT.
- Optimized no-mount and invalid-disk runs retain usable TASKS/VER and report the
  correct mount error without printing configured geometry.
- Fifteen host disk/package/binding checks and direct metadata checks for leading
  zero hex IDs, the pin, 4/8/16 slot labels, retained baud and omitted geometry.

The entry runs also check resource cleanup and OS screen/cursor/keyboard restoration.
Reserved bank-zero delta: **0 fixed bytes and 0 bytes per Task**, including guards,
alignment and unused capacity. This is command/startup validation, not a new
concurrent serial timing qualification.

```sh
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
python3 tools/test_task_inspect.py --case raw --output build/shell-status/inspect-raw
python3 tools/test_task_inspect.py --case opt --output build/shell-status/inspect-opt
python3 tools/test_shell_parser.py --case raw --output build/shell-status/parser-raw
python3 tools/test_shell_parser.py --case opt --output build/shell-status/parser-opt
python3 tools/test_shell_entry.py --case raw --paced --output build/shell-status/final-raw
python3 tools/test_shell_entry.py --case opt --paced --output build/shell-status/final-opt
```

Add `--no-mount` or `--invalid-disk` to the optimized entry command with a separate
output directory to reproduce startup failure cases.

## Runtime mount and device listings

`MOUNT` lists published records from the running DOS filesystem service, with
MyDOS handler identity, read-only access and mounted/offline state. It does not
start the service or report compile-time geometry. Empty or failed services
print `No mounted filesystems`. Mount/unmount operands remain unsupported.

`DEVICES` lists the compiled production drivers and their runtime state. It
includes an inactive SIO driver without initializing it, and omits the console
when console support is not built. The SIO offline latch overrides the ordinary
service state. Both commands accept ordinary output redirection and reject
operands before dispatch.

The internal `FSINSPECT` and `DEVICEINSPECT` snapshots hold Forbid only during
the copy, with IRQs enabled. Mount aliases are copied before releasing the
protection; starting/stopping/failed service pointers are not followed. Output
uses no retained mount pointers and can block normally. The current two drivers
need four snapshot bytes and eight mounts need 264, both within the existing
512-byte shell transfer buffer. The shell allocation remains 1,288 upper-RAM
bytes. Fixed and per-task bank-zero reservation changes are **zero bytes**;
guards, alignment, task pools and reserved capacity are unchanged.

The [qualification record](../qualification/shell-mount-devices.json) covers:

- Raw/optimized native inspection, 525 assertions each: full eight-mount
  capacity, a bank-crossing destination, 31-character names, copied lifetime,
  unpublished/absent/offline records, service transitions, short/null buffers,
  Forbid nesting, guards and no worker creation or heap allocation.
- Raw/optimized parser runs, 211 assertions each, including mixed-case names,
  exact singular/plural command spelling and operand rejection.
- Raw/optimized emitted shell entries on the paced pinned bridge, with real
  POKEY keyboard input, exact physical-screen output, NIL redirection and clean
  exit. Successful runtime mounts and both ready devices are displayed.
- Optimized no-mount and invalid-disk entries: no phantom mounts; inactive SIO
  without configured mounts, and a ready SIO driver after a filesystem-format
  failure. The shell remains usable and restores the OS console at exit.
- Five host checks for the small playground ATR and generated task bindings.

Representative commands:

```sh
python3 tools/test_system_inspect.py --case raw --output build/shell-mount-devices/inspect-raw
python3 tools/test_system_inspect.py --case opt --output build/shell-mount-devices/inspect-opt
python3 tools/test_shell_parser.py --case raw --output build/shell-mount-devices/parser-raw
python3 tools/test_shell_parser.py --case opt --output build/shell-mount-devices/parser-opt
python3 tools/test_shell_entry.py --case raw --paced --output build/shell-mount-devices/entry-raw
python3 tools/test_shell_entry.py --case opt --paced --output build/shell-mount-devices/entry-opt
```

Add `--no-mount` or `--invalid-disk` with a separate output directory for the
failure paths. The example disk's HELP guide documents both new commands and
retains its 90 KiB geometry and four small text files.
