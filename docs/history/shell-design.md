# Resident shell and DOS current directory

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/README.md) and [history index](README.md).

Status: implemented and qualified, 2026-09-23. All [eight slices](shell-implementation.md)
are complete: DOS current-directory support, canonical lock names, relative paths,
the resident HELP/ECHO/CD/DIR/TYPE/MEM/EXIT shell, redirection, lifetime tests and
eight-task SIO qualification. This sits above the completed
[DOS console streams](../reference/streams.md) and
[read-only MyDOS service](../reference/dos.md). The
[implementation plan](../plans/shell-implementation-plan.md) records the slice boundaries.

The result is a useful resident command shell: navigate directories, list files,
display text, inspect available memory and redirect command streams. Commands
are linked into the system image initially. The chosen o65 loader can later
add external commands without replacing the shell's DOS-facing interfaces.

## Scope and ownership

The shell owns command input, parsing, built-in dispatch and diagnostics.
The cooked CON: session owns line editing and echo.
DOS owns current-directory state, relative-path resolution, handles, locks and
stream selection. The filesystem owns directory traversal and media validation.
Exec and its existing workers retain scheduling, console and SIO ownership.

Run the shell in the root application Task and execute built-ins as ordinary
calls in that Task. Shell + console + filesystem + SIO uses four of the eight
public slots, with private idle additional. There is no command Task, new shell
worker or new input worker per invocation. A synchronous command blocks the
shell while other runnable Tasks and services continue. The prompt returns
when that command finishes.

Use public DOS calls and the existing memory API from commands. Keep shell code
as an application component in this repository, separate from library modules;
do not put command dispatch in Exec or the filesystem worker. Helpers may share
an internal argument/result structure, but this is not an executable-entry ABI.
No public Process structure, inherited handles or child-launch convention is
frozen by this milestone.

The shell now uses [CON:](../reference/cooked-console.md) and its reusable cooked editor.
The migration is tracked separately in the [console record](console-interaction-implementation.md). Scripts, pipelines, background jobs,
wildcards, command search paths, aliases, environment expansion, disk writes and
multiple windows remain later work. Each is a scope limit, not a claim that
the 65816 cannot support it.

## DOS current-directory API

Add these calls to the existing generated [DOS contract](../../abi/dos.json):

| Call | Native signature | Result |
| --- | --- | --- |
| CurrentDir | FileLock pointer (FileLock pointer lock) | Exchange the calling Task's current directory and return its previous lock. |
| NameFromLock | LONGINT (FileLock pointer lock, BYTE pointer buffer, LONGINT length) | Write a fully qualified NUL-terminated name; DOSTRUE on success, DOSFALSE with IoErr on failure. |

Keep the classic exchange model from
[CurrentDir](https://developer.amigaos3.net/autodocs/dos.library/CurrentDir.html)
and bounded naming interface from
[NameFromLock](https://developer.amigaos3.net/autodocs/dos.library/NameFromLock.html).
Use opaque native 24-bit pointers and signed 32-bit lengths/results, as for the
current DOS API. Calls are task-only. Generate imports, signatures and constants
together; update callers rather than retaining another ABI profile.

### Selection and lifetime

Each DOS client has one current-directory pointer, initially null. CurrentDir
accepts null or a live caller-owned filesystem directory lock. It validates
owned-list membership before reading payload fields, then kind, backend,
generation and directory type. A file lock is not necessarily a directory lock.
Foreign/stale/wrong-kind locks fail with ERROR_INVALID_LOCK; a valid lock on a
file fails with ERROR_OBJECT_WRONG_TYPE. Busy/active clients fail with
ERROR_OBJECT_IN_USE. Failure preserves the old directory and returns null.
Opaque pointers retain the existing lifetime contract: a closed address later
reused for another live object is not protected by an external generation token.

Success clears IoErr, including when the previous directory was null. Therefore
the caller distinguishes a null previous selection from failure using IoErr.
Exchanging the same pointer succeeds but does not create another lock or reference.
CurrentDir performs no disk I/O or lock allocation. With no client context,
CurrentDir(null) succeeds without creating one.

The selected lock stays in the caller's existing owned-object list and retains
its existing mount reference. Selection neither duplicates it nor frees the old
lock. The returned previous lock remains owned by that caller and may be restored
or unlocked. While selected, UnLock rejects it with ERROR_OBJECT_IN_USE, leaving
both the lock and selection intact. This explicit misuse check prevents a dangling
directory; it is not automatic lock duplication or an additional owner.

ReleaseContext refuses a selected directory as well as existing live objects,
streams and requests. Task removal keeps the existing DOS misuse guard. Before
exit, exchange null, unlock the returned directory, close owned streams and
release the context. Failed command cleanup must not free a selected lock.
Task-slot reuse starts with no directory, handles or inherited defaults.

Null means **no default directory** in Exec816. Relative operations then fail
with ERROR_NO_DEFAULT_DIR (201); explicit mount paths still work. Classic Amiga
uses a null current-directory lock as its boot filesystem root. Exec816 has no
DOS boot-volume/Process model yet and must not silently pick one configured disk.
The resident launcher supplies an optional explicit initial path; the reference
shell image uses `D1:`. If initial locking fails, report the error and retain a
usable CON: prompt with no directory, allowing a later explicit CD retry.

Offline media must not prevent CurrentDir(null) and valid UnLock cleanup.
Operations requiring disk access preserve the mount's causal error and recovery
rules. CurrentDir never remounts or changes mount generations implicitly.

### Naming a lock

NameFromLock accepts any valid caller-owned filesystem lock, including a lock
on a file. It returns the configured mount alias and resolved stored component
names, such as `D1:TOOLS/README.TXT`; a root is `D1:`. This uses the unique mount
alias rather than an Amiga volume label, which the MyDOS service does not expose.
The lock and mount generation establish identity; the returned string does not.

Validate the lock, signed capacity and mapped writable buffer before copying.
Capacity includes the terminator. Reject null/invalid buffers, nonpositive
lengths and address wrap with ERROR_BAD_NUMBER. Insufficient capacity reports
ERROR_LINE_TOO_LONG (120), with no partial copy; success clears IoErr. Keep the
255-byte full-path limit, so capacity 256 always suffices for a valid lock name.
NameFromLock(null) reports ERROR_INVALID_LOCK, without synthesizing `SYS:`.
Add the error constant from the classic
[DOS header](https://d0.se/include/dos/dos.h) to generated definitions.

Store a bounded canonical name with each lock, assembled from actual resolved
entries when it is created. Copying that name requires no media scan; an offline
but still valid retained lock can be named for diagnostics. Renames, external
media mutation and automatic media-change detection retain their existing
unsupported status. Do not grow ordinary FileHandles merely to name FileLocks.

## Paths and CD behavior

Open and Lock share DOS path classification and filesystem resolution. The
shell passes the original operand; its displayed path is never the authority
for resolving another command. All library callers receive relative paths,
including callers that are not shells.

| Input form | Meaning |
| --- | --- |
| `D1:TOOLS/README.TXT` | Absolute path within the explicitly named mount. |
| `README.TXT`, `SUB/README.TXT` | Relative to the calling Task's selected directory. |
| Empty string | Current directory; Lock returns a new owned lock, Open rejects the directory as a file. |
| `:`, `:TOOLS` | Root of the current directory's mount, optionally followed by a path. |
| `/`, `//`, `/OTHER` | One/two parent steps, optionally followed by a relative path. Parent steps at the root stay at the root. |
| `RAW:`, `NIL:`, `CON:` | Existing stream classification, independent of the current directory. |

The command behavior follows the documented
[AmigaDOS CD forms](https://wiki.amigaos.net/wiki/AmigaOS_Manual:_AmigaDOS_Command_Reference#CD):
CD without an operand displays the current directory; CD with an operand changes
it. `/` selects the parent and `:` selects the current volume's root. Bare-path
implicit CD and pattern matching are deferred. `.` and `..` are not special
aliases. Initially support parent steps only as a leading slash run; reject
embedded empty components, trailing separators, multiple colons and malformed
8.3 names. These parser limits preserve a small explicit path grammar and must
be reported rather than silently normalized into another target.

Preserve the existing 255-byte input/full-result bounds, mapped-name validation,
exact-then-case-folded matching and ambiguous-match rejection. Counting starts
from the selected directory: neither relative paths nor parent steps reset the
existing depth/cycle checks. A child under the deepest admitted directory must
not bypass the 16-directory traversal bound. Name limits never truncate a target.

Use the existing lock's mount and ancestor extents as the base for relative
resolution. The current cursor records ancestors of the resolved entry; starting
inside a locked directory must correctly include that directory itself. Validate
the base lock on both sides of the private packet boundary, including owner,
generation, directory type and selected mount. Keep it protected for the whole
operation by the client busy/lifetime rules, and retain/release the ordinary
per-operation mount reference on every outcome.

Extend the existing packet base-lock slots: ACTION_FINDINPUT's second argument
and ACTION_LOCATE_OBJECT's first argument currently require zero. A null base
still means the explicitly selected mount root at this private boundary; it does
not choose a DOS default. Nonzero bases are validated owned directory locks.
Use iterative traversal and the existing filesystem state machine. Parent steps
must resolve the actual ancestor directory and reconstruct valid entry/ancestry
metadata, not only alter the displayed name. Share that resolution primitive;
a public ParentDir API is not required for this shell milestone.

CurrentDir commits only after successful Lock of the complete target. The shell
then releases the old directory, unless it is the same identity. A failed Lock
or exchange leaves the previous directory selected and releases any new candidate.
The shell keeps a borrowed pointer to its selection for CD display and verifies
exchange results; it owns no competing string-based directory model.

Example session:

```text
> CD D1:TOOLS
> CD
D1:TOOLS
> DIR
> TYPE README.TXT
> CD SUB
> CD /
> CD :
> CD D2:WORK
```

Changing current directory does not retarget already-open files, locks or
redirected streams. Cross-mount CD retains the new mount before releasing the old.

## Command language and built-ins

Accept one command per Return, with at most 255 bytes and 16 words including the
command and redirection targets. Command names are ASCII case-insensitive; do
not uppercase operand bytes. Space/tab separate words outside double quotes.
Support empty quoted words and literal spaces in quoted strings. Quotes delimit
a whole word initially; adjacent quoted/unquoted fragments are syntax errors.

Inside quotes support `**` for a literal asterisk and `*"` for a literal quote;
reject other escape sequences explicitly. Outside quotes an asterisk is literal.
This is a subset of the
[Amiga DOS parsing conventions](https://developer.amigaos3.net/sites/default/files/downloads/2024-10/Amiga_ROM_Kernel_Reference_Manual_DOS.pdf),
not a public ReadArgs implementation. Backticks remain literal, preserving legal
MyDOS name bytes. No substitutions, expansion or execution happen while parsing.
Unquoted pipeline/command-list operators, `>>`, missing targets, duplicate
redirections, unknown commands and invalid argument counts fail before dispatch.
Never execute a truncated or partially parsed line.

| Command | First implementation |
| --- | --- |
| HELP | List supported commands and syntax limits. |
| ECHO [words...] | Write words separated by spaces and finish with LF. |
| CD [path] | Display or change the DOS current directory as specified above. |
| DIR [path] | Lock the named/current directory; Examine and ExNext; print entries in on-disk order without recursion or sorting. |
| TYPE [file] | Stream a text preview of the named file, or a noninteractive selected Input when no file is supplied. |
| MEM | Report available ordinary and linear memory using existing Exec allocation queries and their actual semantics. |
| EXIT | Finish cleanup and return from the resident application. |

DIR releases its temporary lock and treats ERROR_NO_MORE_ENTRIES as normal end.
TYPE closes only a file it opened; it borrows selected Input/Output. Without a
file, interactive Input is rejected so TYPE does not acquire keyboard lines.
NIL Input ends immediately. Process data in bounded 512-byte chunks; never
allocate the whole file or one Task per command. TYPE maps ATASCII `$9B` to LF,
passes printable ASCII, LF and tab, ignores CR, and displays other bytes as `.`.
This is a text display command; DOS Read continues to return original bytes.
Do not silently retry a failed Read/Write or print bytes from a failed Read.

Built-ins return a command status and a saved signed secondary error. Use 0 for
success, 10 for command/syntax/I/O errors and 20 for shell-fatal failure, following
the classic return-code convention in the DOS header. A later successful Close,
selector or diagnostic Write must not overwrite the saved causal error. Unknown
secondary codes remain printable numerically. Fatal output failure exits through
cleanup rather than trying to print errors indefinitely.

## Cooked input and foreground execution

The shell writes a fixed `> ` prompt and reads its owned CON: stream in chunks
of at most 64 bytes. A complete line fits its 256-byte upper input buffer;
LF is replaced with NUL before parsing. CON: retains the unreturned remainder
between reads and owns all echo, tail display, editing and resynchronization.
The shell retains no second editor implementation.

Ctrl-D exits at an empty prompt. A partial final command is accumulated without
LF, dispatched when EOF arrives, and followed by normal cleanup. Break clears
the accumulated command and redraws the prompt. Overflow and input loss report
errors only after CON: has discarded through Return; neither Ctrl-C nor Ctrl-D
can execute a surviving suffix. Other I/O failures end dispatch and run cleanup.

Prompt and diagnostics use the owned CON: handle. Per-command file/NIL input
redirection remains ordinary byte input, and echo follows the edited console
regardless of selected Output. Keyboard typeahead remains bounded while a
synchronous built-in runs.

Prompt editing and each built-in have separate [foreground scope](../reference/foreground-break.md)
generations. Ctrl-C/BREAK delivers a durable cancellation request independently
of Read and selected Input. TYPE/DIR poll between bounded steps; console and
filesystem waits retire their exact outstanding request before returning.
Cancellation restores selectors, closes command resources and retires valid
typeahead before renewing the prompt scope. A canceled CD releases its candidate
without replacing the selected directory. The fresh prompt acknowledges status
10 / ERROR_BREAK without a diagnostic; late events cannot cancel its generation.
Cancellation is cooperative and does not forcibly remove a Task.

The first shell owns the interactive line but does not isolate other writers to
the shared console. Unsolicited output can disrupt the displayed edit row; no
atomic prompt restoration across Tasks or independent-window behavior is claimed.
The existing [stream timing result](dos-console-streams-implementation.md#slice-7-integrated-concurrency-and-timing-qualification)
also shows up to 1.7 seconds of visible-echo delay behind FIFO scrolling. Measure
the new editor; do not claim that a shell fixes rendering latency.

## Redirection and cleanup

Support one `<source` and one `>destination` per command, with a preceding word
boundary and optional space after the operator; quoted targets are allowed.
Recognize operators only outside quotes. Their placement among command arguments
does not affect the selected streams. Remove them from the built-in's arguments.
An unquoted operator attached to the preceding word is a syntax error.
The shape follows [AmigaDOS redirection](https://wiki.amigaos.net/wiki/AmigaOS_Manual:_AmigaDOS_Working_With_AmigaDOS#Redirection),
while supported destinations retain Exec816's current backend restrictions.

For example, `TYPE <D1:TEXT.TXT >NIL:` reads and discards converted text, and
`DIR >NIL:` exercises enumeration without display. Open input with MODE_OLDFILE
and output with MODE_NEWFILE. RAW:/CON:/NIL: remain valid DOS destinations; attempting
filesystem output fails with ERROR_DISK_WRITE_PROTECTED. CONSOLE: retains
its explicit unsupported error. Redirection does not read a command script.

Parse and validate the complete command first. Save borrowed Input/Output, open
all requested targets, then select them. If any open/selection fails, restore
changed selections and close temporary handles without invoking the command.
All target paths resolve against the directory before the command starts, even
for a CD command. Once dispatched, a successful CD persists independently of
temporary stream restoration.

Capture the command result/error before cleanup. Restore both borrowed defaults
before closing any temporary handles; unwind in reverse acquisition order on
success and failure. Report errors through the shell's retained console handle,
even with `>NIL:`; there is no public ErrorOutput stream yet. Commands never
close borrowed defaults or call ReleaseContext. Cleanup failures preserve the
first cause; inability to restore valid defaults stops further command dispatch.

EXIT uses the same restoration path, then clears/unlocks the directory, closes
the shell's owned CON: handle and releases its DOS context. Normal resident return
lets the existing coordinated service shutdown restore OS ownership. The unsafe
SIO `$FF93` path still parks before ordinary console/heap teardown; it is never
reported as successful shell cleanup.

## Memory and implementation boundaries

Follow the [bank-zero budget](../reference/platform.md#bank-zero-memory-budget).
Target zero added fixed/per-Task bank-zero reservation, keeping the complete
eight-slot 57,232/61,536-byte loading/runtime baseline including OS. Use the
existing root stack/DP; do not enlarge stacks, reduce task capacity or consume
the protected interrupt reserves. Bulk shell state and path storage use upper RAM.

These are design budgets, not measured layouts:

| Resource | Proposed bound and lifetime |
| --- | --- |
| DOS client current-directory field | One 3-byte pointer; existing 80-byte context is expected to round to 88 bytes, +8 per allocated client. No DosSlot or public Task change. |
| FileLock canonical name | A lock-specific trailer with a length and at most 256 name bytes, in the same upper-RAM allocation; at most 376 rounded bytes including the current 112-byte object. Ordinary FileHandles stay 112 bytes. |
| Resolver name workspace | At most 256 additional upper-RAM bytes shared by the serialized filesystem worker; no recursive path frames or per-component allocations. |
| Shell command line | 256 bytes including NUL. |
| Arguments, handles, counters and saved results | At most 128 bytes, including sixteen 24-bit word pointers. |
| Editor redraw | 128 bytes. |
| Name display / FileInfoBlock scratch | One 264-byte rounded buffer reused between commands. |
| TYPE transfer/conversion buffer | 512 bytes, transformed in place only after a successful Read. |

Shell-private reusable payload is therefore at most 1,288 bytes, before existing
DOS/console resources, locks and temporary redirection objects. Measure allocator
rounding, metadata and peak concurrent allocations, including both CD locks during
exchange. Free variable-sized locks using their actual allocation size; never
use the old fixed Object size for every kind. Roll back name-storage allocation
failure before publishing a lock or retaining an extra mount reference.

Keep the existing one reusable DOS packet/reply port per client and caller-side
RAW transfer path. Return from path preparation helpers before blocking where
possible. The current filesystem already serializes operations; adding paths
must not add another queue or hold Forbid across disk I/O, parsing, allocation,
console rendering or Wait. No IRQ/NMI changes or POKEY involvement are required
for a directory selection.

## Deliberate differences from AmigaDOS

| Difference | Reason / later boundary |
| --- | --- |
| Native pointers, no BPTR/BSTR encoding | Existing 65816 ABI and generated DOS contract. |
| Current directory belongs to a Task's DOS context | No Process abstraction yet; preserves separate state without growing public Task or bank-zero records. |
| Null directory is unset; no SYS: or implicit boot root | No DOS boot-volume selection exists; explicit startup paths avoid binding to the wrong disk. |
| Same-Task locks and guarded UnLock of selected directory | Existing owner/lifetime enforcement; shared/inherited locks need a separate contract. |
| Names start with configured aliases and remain at most 255 bytes | Current MyDOS namespace and bounded native resolver. |
| Restricted parent/quote/parser forms; no implicit CD or patterns | A bounded first shell, without claiming full Shell/ReadArgs language compatibility. |
| Resident built-ins, synchronous DOS calls and cooperative foreground cancellation | Uses the current Task and private request ownership; o65 loading and Process inheritance remain separate work. |
| CON: editor, private diagnostic handle, EXIT and MEM commands | Cooked input is shared library behavior; no public stderr or claim of exact classic command option compatibility. |
| File output remains rejected | The filesystem is qualified read-only; redirection cannot grant write support. |

## Acceptance and delivery order

The [implementation plan](../plans/shell-implementation-plan.md) begins with CurrentDir,
lock naming and DOS path resolution, then adds the resident editor/dispatcher,
built-ins, redirection and integrated lifetime/timing qualification. Keep each
major slice executable and commit it independently. No implementation is included
with this design note.

Required evidence:

1. Raw/optimized native API/layout tests: null versus failed exchange, wrong-kind
   and foreign locks, same-pointer selection, selected-lock UnLock rejection,
   NameFromLock capacity/extent/generation checks, unchanged state on failure and
   allocation-free clearing of an absent context.
2. Relative Open/Lock outside the shell, two Tasks with different directories,
   old handles unaffected by CD, explicit/relative/root/parent forms, cross-mount
   changes, exact/folded name matches, depth/cycle/length boundaries and headless
   operation. Reconstruct canonical names from real entries and verify parent
   metadata, not only strings. Keep RAW:/NIL: classification independent of CD.
3. Inject failure during candidate locking, canonical-name allocation, mount
   acquisition and redirect opening/selection. Verify unchanged current directory,
   balanced references, restored defaults, preserved causal errors, refused live
   context release/removal, safe shutdown and clean Task-slot reuse.
4. Physical-key shell sessions exercise CD, DIR, TYPE, HELP, ECHO, MEM and EXIT;
   relative operands, both redirections, malformed syntax, invalid/truncated
   input, long-line tail editing, Backspace at tail boundaries, prompt Ctrl-C
   and input-loss resynchronization. Assert both retained and physical display
   state; direct FIFO injection supplements faults, not keyboard qualification.
5. Both 128/256-byte MyDOS media, raw/optimized code and kernel banks 1/3. TYPE a
   complete 70,003-byte file through bounded buffers to NIL, verifying actual
   converted bytes independently before each Write; NIL success alone does not
   establish correct content. Use a smaller bounded RAW fixture for exact text,
   cursor and scrolling checks. Retain a separate single large DOS Read
   stack/throughput regression through a relative path.
6. Keep eight Tasks live in a focused coexistence run, with shell calls alongside
   independent memory/message/signal and disk work. Preserve FASTEST125 byte
   deadlines, zero RX/TX misses/gaps and existing alarm/phase limits; retain TX
   coverage and affected recovery cases. Timing runs replay identical images and
   physical-key schedules without passive observers. Set completion bounds before
   execution and investigate editor/scroll latency changes.
7. Compare complete bank-zero maps and actual upper allocations. Observe root,
   console, filesystem, SIO and kernel stacks through blocking calls and cleanup,
   including 256-byte interrupt reserves, guards, register restoration and OS
   coexistence. Compiler-only and host-parser tests do not qualify the shell.
