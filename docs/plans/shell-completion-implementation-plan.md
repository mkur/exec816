# Shell TAB completion implementation plan

[Plans](README.md) · [Roadmap](../roadmap.md#commands-and-cli) ·
[Shell guide](../guides/shell.md) · [Cooked input contract](../reference/cooked-console.md)

Status: SC1–SC3 implemented and checked at the development tier. See the
[execution and measurement record](../history/shell-completion.md) for the
actual selections, resource deltas, timing limits and tested OF816 distribution.

Add prefix completion at the interactive shell prompt, reusing the existing
cooked editor, history and bounded redraw. Completion belongs to the shell;
the editor supplies a reusable pause/resume operation so directory access can
run outside a busy DOS Read. Implement three executable slices, validating
each before continuing. The current input contract is documented in
[DOS](../reference/dos.md#resumable-console-editing) and the
[shell guide](../guides/shell.md#editing-and-break).

## Scope and behavior

Match ASCII prefixes without case sensitivity. Preserve the bytes already
typed and insert the missing suffix using the candidate's spelling. Completion
never submits or executes a command.

| Context | Candidates |
| --- | --- |
| First command word, without a path separator | Built-ins, session aliases, regular files in the current directory and then PATH directories |
| Explicit command path containing `:` or `/` | Entries in its named parent directory; directories allow further path entry |
| Ordinary argument or `<`, `>`, `>>` target | Files and directories in the current or explicitly named parent directory |

Use the following bounded first-version rules:

- Require a nonempty, unquoted token and a nonempty final path component. The
  cursor must be at the token's end; completion before existing whitespace or
  an operator preserves all following text. A cursor inside a token is a no-op.
- One distinct matching name inserts its missing suffix. Add `/` for a
  directory. Add a space for a completed file, builtin or alias only at line
  end; an existing delimiter is already sufficient. Do not duplicate separators.
- Several distinct names extend only to their longest common prefix. With no
  extension, leave the line unchanged. Empty prefixes and unmatched prefixes
  also leave it unchanged, without inserting a space or listing candidates.
- An exact name remains ambiguous if another candidate extends it. Repeated
  TAB recomputes candidates; there is no cycling or retained directory cache.
- Check the complete replacement before changing the edit. If the name would
  exceed 255 bytes, leave the line intact. A trailing space is optional when
  only that space would overflow; a directory's `/` is part of its replacement.
  Ordinary typed-character overflow retains its current discard-through-Return
  behavior.
- Keep generic file completion for arguments. Do not infer command templates,
  expand aliases to choose argument types, or restrict CD to directories yet.
- Command words after RUN or `|` are deferred and are no-ops in this version;
  recognize those positions so they are not mistaken for file arguments.
  Their ordinary file arguments and redirection targets may still complete.
- Quoted/escaped tokens, wildcard tokens, volume/ASSIGN-name suggestions,
  candidate listing, fuzzy matching and completion inside scripts are deferred.
  Existing explicit volume and ASSIGN prefixes still resolve normally.

Ordinary CON readers keep TAB-as-space. Shell history remains enabled only
during prompt acquisition, and records the final submitted text once. Editing
a recalled line through completion does not modify its stored history entry.

## Implementation boundary

[COOKEDLINE.Feed](../../lib/dos/cookedline.act) currently converts TAB to a
space. [DOSCOOKED](../../lib/dos/doscooked.act) acquires and echoes a whole line
inside Read; [ShellReadStep](../../examples/shell/shell-session.inc) sees only
submitted bytes. The DOS client rejects recursive public operations while
busy. A filesystem callback from inside AcquireLine would therefore fail.

Introduce a native DOS operation, provisionally `ConsoleEdit(handle, edit)`,
for an owned CON handle. Define its constants and record in
[abi/dos.json](../../abi/dos.json), with generated declarations. Finalize names
and numeric allocations in SC1 against the then-current ABI. Its contract is:

| Request or result | Meaning |
| --- | --- |
| START | Begin prompt acquisition, using the existing editor and prompt snapshot |
| COMPLETE result | TAB paused acquisition; return a NUL-terminated copy, length and cursor, without LF, submission or history recording |
| RESUME | Continue the same edit, optionally replacing its text/cursor from the caller's bounded buffer |
| LINE result | Return the submitted text without its LF, with an explicit flag distinguishing Return from partial Ctrl-D |
| EOF result | Empty Ctrl-D, or the one-shot EOF following partial Ctrl-D |
| CANCEL | Abandon the owned continuation and retire its input ownership without submitting it |
| Error result | Report an ordinary DOS error after required I/O retirement; never expose a partial command as a successful line |

The caller supplies at least 256 bytes for snapshots and replacement text;
the adapter borrows that buffer only during each call. Keep the authoritative
line, cursor, history and rendering state in the existing cooked session.
RESUME with no replacement must preserve the edit exactly. Invalid lengths or
cursor positions reject the replacement without damaging the continuation.
LINE and EOF release edit ownership. Partial Ctrl-D returns its text once,
followed by EOF on the next START, matching the shell's existing behavior.

This is an Exec816 native DOS extension for application-driven editing, with
the reason for extending the line-oriented CON interface documented in the
cooked reference. Keep ordinary Read semantics and one shared editor
implementation. No new Exec selector, console worker, compiler bridge or loaded
COMMAND/C import is needed for the resident shell consumer.

### Ownership across a pause

Retain the cooked-session lease and the endpoint's exclusive input ownership
through COMPLETE and RESUME. Record the owning handle/Task in upper-memory
state so another reader, including an inherited CON handle or a separate RAW
handle, cannot consume the suspended edit's input. Other console writers retain
the existing documented ability to disturb the displayed row.

Before returning COMPLETE, collect every console reply, detach the reusable
request's transfer fields and clear the DOS client's busy flag. Separate this
request retirement from releasing the retained input lease. Filesystem calls
can then use the ordinary Task-local DOS context. RESUME reattaches the settled
request to the existing lease; it must not acquire a second input lease.
Use small internal DOSRAW helpers shared with ordinary retirement as needed.

CANCEL, normal submission, EOF, transport failure and shell shutdown must
release the retained ownership exactly once. Reject Close of the continuation's
owning handle while it remains active; callers cancel before closing. History
toggles and competing acquisitions retain busy rejection. Audit inherited
wrapper release and context teardown so they cannot free live state. Validate
ownership and bounds at the public boundary, without repeating pointer checks
through every helper.

BREAK during a scan cancels the whole prompt through the existing foreground
scope. Retire filesystem operations/locks first, then cancel the edit, clear
queued typeahead as the current cancellation path requires, and restore a fresh
prompt. Do not route this through an ordinary Read while the edit lease is held.
An input-loss flag accumulated during suspension must still invalidate the
whole line when acquisition resumes, before any submission. Replacement and
CANCEL cannot clear an existing discard-through-Return requirement.

Preserve the original prompt snapshot, width, drawn extent and physical cursor
across COMPLETE; RESUME must not rerun Begin as if a new prompt had been written.
Keep IRQ/NMI capture and routing unchanged. Forbid covers only short ownership
transitions, never a directory scan, console wait or cancellation wait.

## Slice sequence

| Slice | Executable result | Acceptance evidence |
| --- | --- | --- |
| SC1 | Resumable editor and builtin/alias TAB completion | Native ABI/ownership probes, emitted editor cases and a physical prompt smoke |
| SC2 | File and PATH completion through ordinary DOS enumeration | Matching, paths, incomplete scans, BREAK/loss and resource cleanup |
| SC3 | Documented behavior and refreshed standard OF816 demo | Packaged physical-key walkthrough, resource and latency report |

## SC1 Resumable editor and resident names

Primary files: `abi/dos.json`, `tools/generate_dos.py`, native DOS declarations
and implementation wrappers, `lib/dos/cookedline.act`, `doscooked.act`,
`dosraw.act`, `doscalls.act`, and `examples/shell/shell-session.inc`.
Put completion-specific shell routines in a new `shell-completion.inc`.

1. Add the native edit operation and generated records/constants. Advance the
   native DOS revision from its actual baseline and rebuild affected callers;
   do not retain an old implementation/profile. Keep loaded provider versions
   unchanged unless their actual interface changes.
2. Refactor acquisition into shared start/continue/finish paths. Ordinary Read
   still consumes TAB as a space; only the edit operation yields COMPLETE.
   Add an atomic bounded text replacement helper using the existing redraw.
3. Implement retained input/session ownership and explicit cancellation. Keep
   normal reads, small drains, EOF and optional history on the shared code.
4. Add a nondestructive token-context scanner. It must tolerate unfinished
   input and recognize quoting and operators before selecting a token. Do not
   call ShellParse: it rewrites the line and requires completed syntax. Test
   unsupported contexts as deliberate no-ops, including RUN/pipe command words.
5. Add a streaming match accumulator retaining the first matching name, common
   prefix length, and a flag for a distinct second name. Fold comparisons only;
   identical names from multiple sources remain one candidate. No match array,
   sort or per-candidate allocation is necessary.
6. Use one resident command-name definition for classification and completion
   so adding a builtin cannot silently omit it from TAB. Preserve command IDs,
   existing dispatch and builtin precedence. Read current alias names without
   expanding or modifying their replacements.
7. Migrate ShellReadStep to the explicit edit results, reusing ShellLine for
   snapshots/submission. Keep completion separate from command parsing and
   command result fields. Disable history before dispatch and on terminal
   outcomes, with its existing optional-allocation behavior. Update
   ShellRetireBreak and ShellFinish for an active continuation.

Extend `tools/test_cooked_line.py` and the public CON fixture, and add focused
`tests/programs/shell_completion.act` / `tools/test_shell_completion.py` coverage.
Give the new runner selectable editor, matching, filesystem and lifetime groups
so later slices can reuse emitted images instead of repeating broad scenarios.

SC1 checks:

- Unique, ambiguous, exact-prefix and case-insensitive builtin/alias matches;
  alias replacement/removal; preservation of following text and typed spelling.
- Atomic replacement at 254/255 bytes, a rejected oversized suffix, short/narrow
  viewports, 36/37-column transitions and no new prompt or newline on TAB.
- Completion in a recalled line, draft restoration, final text recorded once,
  and unchanged optional-history allocation failure.
- Repeated pause/resume, RESUME without changes, CANCEL, EOF after partial
  Ctrl-D, busy rejection and owning-handle Close rejection. Another Task's CON
  and RAW reads must not steal keys during a pause; both work after retirement.
- A real filesystem operation by the same Task between COMPLETE and RESUME,
  proving the client is available, plus another operation after cancellation.
- BREAK and input loss during suspension, existing discard recovery, echo
  failure and exact reference/lease/heap restoration. Ordinary inherited CON
  reads still insert a space for TAB after prompt ownership is released.

Use a small raw/optimized probe for the new record layout, pointer arguments,
result flags and register/context restoration. Run behavioral checks optimized.
Update the cooked contract and shell HELP/guide for the behavior delivered in
this slice. Acceptance requires a physical `HE<TAB>` prompt completing to
`HELP ` and execution only after Return, with intact guards and OS restoration.

## SC2 Filesystem and PATH candidates

Primary files: `shell-completion.inc`, `shell-path.inc`, the shell allocation
layout and the completion fixtures. Use public DOS services; keep filesystem
and driver policy in their existing owners.

1. Split an explicit token at its final `/` or `:` and resolve its parent through
   ordinary Lock. Bare arguments use the current directory. Preserve the user's
   logical prefix, including ASSIGN spelling; never change CurrentDir.
2. For a bare first command word, offer built-ins and aliases, then regular
   filenames from the current directory and each current PATH entry. Explicit
   command paths bypass that search. Resolve PATH names on every attempt so CD,
   PATH and ASSIGN changes take effect. Do not open/load candidate executables;
   directory metadata cannot establish executable validity.
3. Lock and Examine each directory, then enumerate to EOF. Use ExNextBatch with
   capacity four: its 474-byte payload fits the existing 512-byte ShellTransfer
   buffer. Save both count and IoErr before consuming records. A full batch
   requires another call; a final partial batch is valid only with normal EOF.
4. Feed names into the same accumulator. Across command directories, identical
   folded names count once and the earlier source supplies spelling. Built-ins
   and aliases retain their normal precedence. For explicit/argument paths,
   retain the unique candidate's directory/file kind for suffix selection.
5. Missing search directories and absent current-directory context may be
   skipped as in command lookup. An explicit missing parent gives no candidates.
   An unavailable volume, enumeration-epoch change, I/O failure or failed scan
   invalidates the whole accumulated result, including earlier memory matches.
   Never infer uniqueness from an incomplete candidate set. Do not automatically
   retry a changing directory or impose a silent candidate-count cutoff.
6. Release each temporary lock before moving to the next directory and all
   locks before applying a replacement. On ordinary discovery errors, resume
   with the original line unchanged. Preserve the shell's previous command
   status and IoErr around completion. BREAK uses prompt cancellation; cleanup
   failures retain reachable ownership and the existing fatal-cleanup policy.
7. Poll foreground BREAK between batches and directories, using the existing
   cancellable DOS transfers within a batch. Avoid ShellPoll/ShellFail for
   ordinary completion misses because they change command-result state.
   Keep background-job collection serviceable during DOS waits; its callbacks
   must not overwrite borrowed completion scratch or print into the edit row.

Reuse ShellScratch for the 260-byte FIB, ShellTransfer for the four-entry batch,
and ShellDrawBuffer for the first name (at most 107 bytes plus NUL). Keep the
common prefix as a length into that name. Add one 256-byte upper-memory parent
path buffer to the shell allocation, plus measured bookkeeping. Audit the
lifetime of all reused buffers against job collection and diagnostics. Do not
put these arrays on the native stack or allocate them per TAB.

SC2 checks:

- Files and directories, nested relative paths, explicit volumes, ASSIGN paths,
  mixed case, duplicate names across PATH, local-command shadowing and changes
  to CD/PATH/ALIAS/ASSIGN between attempts. Nonexecutables remain filename
  candidates; completion neither loads them nor changes dispatch behavior.
- Empty directories, 1/4/5/8 entries, exact full batches followed by EOF, more
  candidates than any batch, and a late match that changes apparent uniqueness.
- Argument and redirection completion, existing delimiters, no added duplicate
  space, retained suffix text, and unsupported quoted/wildcard/empty contexts.
- Failure before the first result and after a matching prefix, a missing PATH
  directory, an unavailable volume, mutation during enumeration and UnLock
  failure. Rejected/incomplete results leave the original edit unchanged.
- Physical BREAK during disk access, FIFO loss while suspended, then successful
  prompt recovery. Check no retained mount lock, stale client busy flag, leaked
  endpoint lease, duplicate reply or command execution from discarded input.

Use optimized emitted matching fixtures plus small real-media cases for RAM,
MyDOS and SpartaDOS; reuse the same relevant images across cases. Preserve
stack/domain guards and normal interrupt activity. Acceptance includes
`TYPE REA<TAB>` and `TYPE SYS:WO<TAB>` against controlled fixture names, and
external-command completion through default C: and a replaced C: assignment.

## SC3 Integration measurements and demo delivery

1. Extend the existing physical editing walkthrough with completion, subsequent
   cursor editing, history, a completed file redirection, BREAK during a scan,
   EOF and a foreground program reading inherited CON. Observe retained cells
   and the physical caret. Add a focused bitmap-console check for shared editor
   redraw; keep unrelated desktop qualification outside this task.
2. Measure accepted TAB through visible redraw for builtin/alias-only matching,
   default command search, current-directory files and an explicit disk path.
   Record candidate/directory/batch counts, cold and warm media behavior and
   cancellation latency using the pinned accurate timing configuration. Separate
   resolver CPU from disk wait and redraw. Do not publish an unmeasured latency
   target or substitute fast-media timing for normal operation.
3. Run the host suite and affected generators with `--check`; run content/link
   checks for documentation. Update shell HELP, the shell guide, cooked/DOS
   references and testing guidance with actual behavior and deferred contexts.
   Keep accepted contracts separate from implementation/measurement notes.
4. Record per-slice source/artifact hashes, pins, test selections, memory costs,
   stack margins and timing in `docs/development/shell-completion.json` and
   `docs/history/shell-completion.md`. Add the history index entry when that
   record exists; update this plan/index and the roadmap to the actual status.
5. Build with `tools/build_demo.py`, including OF816, the five-second standard
   shell/prime autoboot, matching system disk and pinned ROM with upstream
   notices in `of816/`. Exercise TAB in the extracted final distribution and
   verify normal EXIT, checksums and ownership/OS restoration.
6. Deliver `exec816-demo.zip` containing only boot files, the short user guide,
   license notices and checksums. Keep build intermediates, manifests and test
   output under `build/shell-completion/`, outside the ZIP.

## Resource and validation gates

Every slice targets **0 additional fixed, 0 per-public-Task and 0 idle reserved
bank-zero bytes**, counting guards, alignment and unused reserved capacity.
Keep Task/stack/DP pools unchanged. Report actual deltas, including zero, for
each executable slice against its parent build and for the final package.

The current cooked payload is 410 bytes, rounded to 416, and optional history
is 2,824 bytes. Measure continuation/ownership fields and allocation rounding
in SC1; the parent-path payload adds 256 upper-RAM bytes per shell in SC2.
Count shell bookkeeping, resident code, static data arenas and unused reserved
capacity separately. The four-entry batch and candidate buffer reuse existing
shell allocations. There is no new worker, DP, stack or per-candidate allocation.

Use [development-tier checks](../contributing/testing.md) throughout. Compiler
and ABI inputs come from [the actionc pin](../../toolchain/actionc.json); record
any authorized local override. Physical checks use the pinned
[paced shell emulator and ROM](../../toolchain/altirra-shell-paced.json), recording
the actual configuration/media and package hashes. Small ABI probes use raw
and optimized emission; functional, failure, integration and timing cases use
optimized builds. Add deeper interrupt/ownership cases only where the retained
lease transitions require them. Full release matrices and hardware qualification
remain separate from this work.

SC1–SC3 are complete only when the selected behavior, public lifecycle contract,
focused emitted-code checks, measured resource costs, documentation and tested
OF816 distribution are delivered. Record unmet timing or scope limits explicitly.
