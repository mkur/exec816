# Command usability implementation plan

Status: U1–U5 implemented; U6 distribution validation in progress. This follows the completed
[first toolbox](command-toolbox-implementation-plan.md). Use the
[development testing tier](../contributing/testing.md) and preserve the
[platform memory budget](../reference/platform.md#bank-zero-memory-budget).

## Outcome and scope

Make installed commands usable after changing directory, explain failures in
words, and provide argument help without consuming the command's data stream.
Deliver a bounded shell PATH, shared Fault/PrintFault services, and `COMMAND ?`
help for the ten commands shipped with the demo.

The expected interaction is:

```text
CD SYS:WORK
HEAD SYS:STORY.TXT LINES 3
HEAD MISSING
HEAD ?
```

HEAD is found through the default PATH. The second HEAD invocation reports an
object-not-found explanation with error number 205. The third displays its
template and returns OK without reading Input. These interactions are implemented; the final distribution check is recorded below.

Multiple-file `/M` arguments, wildcard expansion, TAIL, FIND, SORT, UNIQ,
ASSIGN/C:, scripts, environment variables, longer pipelines, background jobs
and writable filesystems remain separate milestones. Keep the existing command
locations on the disk; this slice does not require a C directory or alias.

## Boundaries at the start of this plan

- [ShellExternal and ShellPipeline](../../examples/shell/shell-session.inc)
  call [PROGRAMFILE.Load](../../lib/dos/programfile.act) with exact filenames.
  Put search policy in a shared shell helper; keep the public loader exact.
- ShellDiagnostic currently prints a numeric error on the retained shell
  console after stream restoration. Extend this reporting point without
  moving command diagnostics into redirected Output.
- [ReadArgs](../reference/command-arguments.md) parses the copied Process tail
  and never consumes Input. Keep that low-level contract. Add help as an explicit
  command-facing wrapper, rather than giving existing Boolean callers a new
  success value that lets them accidentally continue execution.
- [command-common.inc](../../examples/commands/command-common.inc) currently
  prints templates on parse failure for the seven new commands. CAT/WC call
  ReadArgs directly and HELLO has no argument parser. Migrate all ten commands
  together when adding the shared help wrapper.

## Selected behavior

### PATH and command lookup

Each shell owns at most four search-directory strings, each with a 255-byte
payload plus NUL. The initial explicit list is `SYS:`. The current directory
is always searched first and does not occupy a list entry. PATH is session
state; child Processes retain their existing directory/stream inheritance and
do not gain a PATH field in this slice.

| Built-in | Effect |
| --- | --- |
| `PATH` | Print that the current directory is searched first, followed by the explicit entries in order. |
| `PATH ADD directory` | Append one validated directory. An existing stored entry is a successful no-op. |
| `PATH SET directory` | Replace the explicit list with one validated directory. |
| `PATH CLEAR` | Remove explicit entries; current-directory lookup still works. |
| `PATH RESET` | Restore the single `SYS:` entry. |

Subcommands ignore case and use the shell's existing word/quote rules. Reject
extra words and a fifth distinct entry. SET/ADD temporarily Lock and Examine
the directory, obtain its canonical absolute name with NameFromLock, then
release the lock before publishing the new list. Failure, BREAK or failed
cleanup preserves the previous list and the causal error. Relative entries
therefore keep their meaning after a later CD. PATH never changes CurrentDir.

Store names, not persistent locks: PATH does not pin mounts or require a new
resource lifetime protocol. Re-resolve names on each command invocation; after
media replacement they may name a different object. The default/reset `SYS:`
entry is deliberately lazy, so a missing startup disk does not prevent shell
creation. Preserve a validated `SYS:` root as that symbolic spelling; other
user entries use canonical physical names. Compare stored entries ignoring
ASCII case; no general alias-equivalence or duplicate-search cache is required.

Lookup rules are fixed before implementation:

1. Built-ins retain precedence. A token containing `:` or `/` is an explicit
   path and gets exactly one loader attempt, including relative `/NAME` paths.
2. For a bare token, try CurrentDir, then each PATH entry. Join a volume root
   directly with the name; insert `/` after a non-root directory. Enforce the
   existing 255-byte path limit before loading, with no truncation or extension
   guessing. A too-long candidate fails explicitly.
3. Continue only after ERROR_OBJECT_NOT_FOUND or ERROR_DIR_NOT_FOUND. A missing
   CurrentDir (ERROR_NO_DEFAULT_DIR) skips that implicit attempt. All other
   failures stop the search: bad executable/provider, resource failure, wrong
   object type, unmounted/offline volume, I/O error and BREAK keep their cause.
   A broken local executable must not be hidden by a working SYS copy.
4. If all eligible attempts miss, return ERROR_OBJECT_NOT_FOUND. A successful
   load clears stale search errors. Poll BREAK between attempts and retain the
   loader's cancellation checks within an attempt.
5. Use the same helper for serial commands and both pipeline stages. Arguments,
   redirected filenames and the child's working directory keep their original
   meanings; only the executable token is searched. A second-stage load failure
   unloads the first Image before reporting its original error.

### Shared fault text and printing

Add English descriptions alongside the machine-readable DOS and program-loader
error definitions in [dos.json](../../abi/dos.json) and
[program.json](../../abi/program.json). Generate one resident lookup table, with
generation checks for duplicate numeric meanings, missing descriptions and size
limits. Include ordinary filesystem, argument, console and o65 errors. Unknown
signed codes get a deterministic numeric fallback. Keep formatting and number
conversion shared; use the compiler-owned CSTRING primitives.

Public contracts, published through DOS and checked COMMAND bindings:

| Operation | Contract |
| --- | --- |
| `Fault(code, header, buffer, capacity)` | Format into caller-owned storage. Return payload length excluding NUL, or -1 for invalid arguments/insufficient capacity. Empty/null header omits the prefix. Code zero produces an empty string. No newline or partial successful message. |
| `PrintFault(handle, code, header, buffer, capacity)` | Format with Fault and completely write the message plus LF to the explicitly supplied borrowed console handle. Return DOSTRUE/DOSFALSE. Code zero writes nothing. Never select, open or close streams. |

For nonzero known codes, use `header: description (code)` or omit the header
and separator. Unknown codes use `header: Error code n`. Bound header text to
255 bytes and descriptions to 80; publish a 384-byte scratch bound covering
the header, signed number, punctuation, LF and NUL. Validate capacities and
pointer requirements and leave a valid nonempty destination terminated on
failure. PrintFault buffers must satisfy the existing upper-RAM transfer rule.
Neither operation allocates or uses mutable global scratch.

Both helpers preserve the caller's entry IoErr on success and failure. Their
return values indicate a reporting failure, which must not replace the command's
original cause. Test partial writes and failure without recursive diagnostics.
Callers needing the output failure as their primary operation can use Fault
followed by the ordinary WriteAll API themselves.

This is an explicit Exec816 adaptation. Amiga
[Fault](https://developer.amigaos3.net/autodocs/dos.library/Fault.html) returns
the formatted length and sets IoErr to the supplied code;
[PrintFault](https://developer.amigaos3.net/autodocs/dos.library/PrintFault.html)
chooses an error/output channel. Exec816 instead preserves IoErr and takes a
destination and scratch buffer, keeping ownership and memory cost visible and
preventing pipeline data from receiving diagnostics. Do not claim binary or
source compatibility with those signatures.

### Template help and diagnostic ownership

Add `ReadArgsOrHelp` with ReadArgs's template/slot/storage parameters and three
generated results: ARGS_ERROR=0, ARGS_PARSED=1 and ARGS_HELP=2. Migrate command entry
points to branch on all three: only PARSED runs command work; HELP returns OK
with IoErr zero; ERROR returns ERROR with the original cause. Keep ReadArgs as
the ordinary parser for callers that do not want command UI behavior.

Recognize help only when the raw argument tail is a sole, unquoted `?`, allowing
surrounding spaces/tabs. A quoted `"?"`, an embedded question mark, or `?` among
other arguments retains normal parsing semantics. Validate the template and
caller storage contract before handling help, and clear result slots when no
arguments are returned. Implement this recognition once in resident DOS support.

Display `Arguments: <template>` plus LF on an owned OpenConsole handle, then
close it. An empty template displays `Arguments: (none)`. Do not read Input,
open a data file, emit data Output or wait for further arguments. Help without
an associated console, or a failed help write/close, returns ARGS_ERROR with
the causal error. Existing shell redirection validation still occurs first.
The original ReadArgs remains useful to headless callers without these UI steps.

The same wrapper may print the template after a parse failure, preserving that
parse error even if diagnostic output/cleanup fails. ShellDiagnostic owns the
final error explanation; commands return operational errors without printing
them independently. This gives one explanation per failed invocation and keeps
an expected producer broken-pipe result quiet after a successful early consumer.

The shell reports ERROR/FAIL with the failing entered command token as header;
syntax/redirection errors use a shell header. Pipelines select the stage whose
result supplies the combined error, retaining both individual results. WARN
with secondary zero and interactive BREAK remain quiet. A nonzero failing
primary result without a secondary code gets a numeric status explanation.
Diagnostic failure never overwrites lastStatus/lastError; an unusable console
may end the session through existing cleanup rules. No diagnostic fallback to
selected Output is permitted.

## Executable slices

### U1 Bounded PATH state and PATH command

Implement PATH storage and mutation in a shell fragment, leaving the existing
header's observed fields stable where practical. Add classification, HELP output
and argument validation. Put storage in the shell's upper-RAM allocation and
clean it up with that allocation. Stage one mutation before committing it.

Acceptance: raw/optimized emitted tests for default/list/add/set/clear/reset,
case/quotes, duplicate/capacity limits, relative-path canonicalization, invalid
or non-directory entries, BREAK, allocation/setup failure, rollback and two
independent shell states. PATH inspection does not access media; temporary locks
are released on every path, and the current directory is unchanged.

### U2 Search serial and pipeline executables

Introduce one shell load helper implementing the lookup rules above. Replace
the three exact loader call sites, preserving PROGRAMFILE.Load's public meaning.
Keep candidate-building scratch separate from copied argument tails and queued
pipeline stage names. No loader cache or new service is needed.

Acceptance: current-directory precedence, SYS fallback after CD, two custom
directories in order, explicit paths bypassing PATH, all-missing results,
too-long candidates, bad local executables, provider mismatch, unavailable
volumes, no default directory and BREAK. Raw/optimized physical-shell cases
must exercise both pipeline stages through PATH, second-load cleanup, exact
argument/stream inheritance and a working prompt after each recoverable error.
Test a non-D1 system-volume selection to rule out a hard-coded drive.

### U3 Shared fault services

Add the message definitions, generator checks, resident formatter/writer and
public bindings. Record API revisions and provider-manifest size. The current
1,664-byte provider reservation must fit the resulting imports or be reviewed
explicitly as an upper-RAM ABI cost; do not silently change a reservation.

Acceptance: raw/optimized emitted cases for every defined message, zero and
unknown codes, signed extremes, absent/empty/long headers, exact/short buffers,
invalid pointer/capacity pairs, independent buffers, partial writes, BREAK and
output failures. Assert IoErr preservation, intact canaries and no allocation
or handle-ownership changes. Host checks validate generated bindings and tables.

### U4 Shared command help

Implement ReadArgsOrHelp and migrate HELLO, CAT, WC and all seven toolbox
commands. HELLO gains an empty template so extra arguments are rejected
consistently. Keep command parsing algorithms resident; the command include
contains only result/cleanup policy. Rebuild commands against the current ABI.

Acceptance: each command's help returns promptly without command work. Cover
`HEAD ?`, `WC ?`, `GREP "?"`, malformed templates, surrounding whitespace,
ordinary argument errors, redirected Input/Output, no foreground console,
failed help output/close and BREAK. `CAT LONG.TXT | HEAD ?` must print help only
on the console, retire both children and preserve early-consumer success;
`HEAD ? | WC` must deliver zero help bytes to WC. Retain the existing parser,
CAT/WC and toolbox behavior regressions in raw and optimized code.

### U5 Shell error reporting

Use the shared fault services from ShellDiagnostic after stream restoration and
foreground-scope recovery. Capture the causal command/stage before cleanup can
replace IoErr. Preserve the current pipeline aggregation; add only the reporting
context needed to identify its selected error. Remove duplicate reporting paths
and update tests that currently expect numeric-only `Error n` output.

Acceptance: exactly one readable explanation for missing commands/files,
malformed arguments and bad Images, including redirection to NIL and failures
in either pipeline stage. Check silent WARN/BREAK/expected broken pipe, producer
WARN plus consumer ERROR, secondary-zero failures, output failure and successful
recovery. Verify exact data-stream bytes, original primary/secondary results,
handle/Image retirement, stack/domain guards and OS restoration.

### U6 Integration and distribution

Update the shell/toolbox/writing-command guides, DOS/argument/program-loading
contracts, demo examples, indexes and the plan's completion record. Remove stale
exact-only lookup descriptions in the current references; distinguish proposed
work from implemented behavior throughout. Record source hashes, pins, report
paths, provider size, upper-RAM cost and bank-zero deltas in development evidence.

Refresh through tools/build_demo.py with all ten rebuilt commands, OF816, the
matching system disk, pinned ROM, notices and the five-second shell/prime boot.
Keep the existing disk layout and distribute only exec816-demo.zip with boot
files, short guide, licenses and checksums. Run the acceptance interaction at
the start of this plan through the packaged system, plus OF816 autoboot/manual
handoff, a PATH-loaded pipeline and EXIT/OS restoration. Audit archive contents
and checksums; keep all build reports outside the ZIP.

## Memory ownership and validation

Target reservation change for every slice: **0 fixed bank-zero bytes and 0
bank-zero bytes per Task**, including guards, alignment and unused capacity.
Do not enlarge Task/DP/stack pools or add an IRQ/NMI protocol. PATH's four strings
need 1,024 upper-RAM bytes per shell plus count/state bookkeeping; fault scratch
needs up to 384 bytes per concurrent reporting caller. Reuse existing workspace
only where lifetimes do not overlap. Report requested and rounded allocations,
any enlargement of resident upper-RAM data reservations, and measured stack
headroom rather than assuming a zero cost from unchanged reservation sizes.

U1 precedes U2; U3 supplies shared diagnostics for U4/U5; U6 follows all five.
Commit coherent slices after their affected checks. Use the pinned compiler
without an override unless an independently fixed compiler defect requires one.
Reuse the toolbox's controlled native fixtures and physical shell runner where
appropriate, with raw/optimized coverage and bounded completion. Mocked streams
do not replace real loader, console, filesystem lifetime and OS-return checks.

Run host tests and affected generator checks for implementation changes. This
plan-only change requires content/link checks, not executable tests. During
implementation, run the selected development cases rather than an exhaustive
qualification matrix; full release/hardware qualification remains a separate
gate. Leave an execution record here with completed slices and linked evidence.
