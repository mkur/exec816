# Shell

[Guides](README.md) · [Demo and boot setup](demo.md)

The shell executes built-ins in its own Task and loads external commands into
child Processes. It supports per-command stream redirection and one foreground
pipeline of two external commands, plus one separately owned background job.
`RUN PRIMES` opens a lower console pane; the optional [demo](demo.md) starts
that same disk command automatically. The shell also works as a resident entry.
Source lives in [examples/shell](../../examples/shell/).

## Built-in commands

| Command | Behavior |
| --- | --- |
| `HELP` | List implemented commands. |
| `ECHO [words...]` | Print words separated by spaces, then LF. |
| `CLS` | Clear the output console and move its cursor to the top left; writes FF when redirected. |
| `CD [directory]` | Change directory, or print its canonical path. |
| `DIR [directory]` | List entries in disk order, with directory markers and exact file sizes. |
| `TYPE [file]` | Print a text view of a file, or borrow noninteractive Input when no file is given. |
| `MEM` | Report ordinary/linear available totals and largest eligible blocks; the totals overlap. |
| `TASKS` | Snapshot live public Tasks, including workers; omit unused slots and private idle. |
| `VER` | Print abbreviated Exec816 and compiler-pin revisions. |
| `MOUNT` | List published runtime mounts, handler, access and mounted/offline state. |
| `DEVICES` | List resident drivers and runtime state, including `timer.device`. |
| `PATH [ADD directory / SET directory / CLEAR / RESET]` | Inspect or change the shell's command search directories. |
| `ALIAS [name ["command arguments"]]` | List, inspect, set or replace a session-local command alias. |
| `UNALIAS name` | Remove a command alias. |
| `RUN command [arguments...]` | Start one loadable background command; default streams are NIL. |
| `JOBS` | Show the running/stopping job or latest collected result. |
| `BREAK identity` | Request cooperative cancellation of that job. |
| `EXIT` | Stop and collect the job, then release shell resources. |

Command names ignore case. MOUNT only lists; it does not mount/unmount media or
probe a drive. A mount's handler is MyDOS or SDFS according to its configuration,
not automatic format discovery. A failed mount leaves a usable prompt; an offline
SIO bus can require a cold boot after correcting the disk/profile setup.

The resident `timer.device` appears as `ready` even with no open requests.
It has no worker Task, so it does not appear under `TASKS`.

TYPE maps ATASCII end-of-line to LF, drops CR, preserves printable ASCII/tab/LF
and displays other bytes as dots. CAT is the external command for unchanged byte
copying. TYPE rejects interactive Input when no file is supplied.

## One background job

`RUN HELLO` returns the prompt immediately. RUN uses the same PATH, aliases,
quoting and copied argument tail as ordinary commands. Built-ins and background
pipelines are unsupported. A second running/stopping job reports error 202.

Input and Output default to NIL. Explicit file/NIL redirection works normally,
for example `RUN CAT <WORK:INPUT.TXT >WORK:OUTPUT.TXT`. Interactive redirection
is rejected before launch. A background command has its own cancellation scope;
keyboard BREAK applies to the shell's current foreground interaction. Commands
requiring OpenConsole must run in the foreground. A graphical command can open
its own output pane through OpenPane.

JOBS shows the Process identity. `BREAK 7` requests stop for job 7 and returns
the prompt; the command must cooperate and settle its I/O. Result collection
and diagnostics happen at complete-command boundaries, preserving a typed draft
and the foreground result. While idle, one completed Process/Image can remain
retained until the next command. Owned panes close during child cleanup, so
layout restoration is immediate. EXIT waits for cancellation and collection;
uncooperative commands can delay it. There is no forced termination, promotion
or job lifetime beyond the shell.

## Paths and directories

DOS uses bounded 8.3 names on both supported filesystems. Examples:

| Path | Meaning |
| --- | --- |
| `D1:TOOLS/SUB` | Absolute path on the physical volume. |
| `SYS:WORK` | Path on the selected system volume. |
| `DATA:NOTES.TXT` | Path through a validated [ASSIGN](../reference/assigns.md). |
| `/` | Parent of the current directory, clamped at root. |
| `:` | Current volume's root. |
| `/TOOLS` | TOOLS relative to the parent directory. |

`CD ..` is a shell shortcut for `CD /`, including clamping at the volume root.
Other paths do not support `.` or `..` components; embedded/trailing empty
components are unsupported. Relative paths need a selected current directory.
A failed CD preserves the previous selection. SYS starts at the configured system volume;
canonical names still use its physical mount name. See [SYS:](../reference/sys-volume.md)
for selection through the boot monitor.

## External commands

Built-ins take precedence. A bare command such as `HELLO` is searched in the
current directory, then the shell's PATH, initially `C:`. Standard shell startup
assigns `C:` to the existing `SYS:C` directory, where the demo keeps its external
commands. This uses one of the four system-wide assignment slots and follows
the selected system drive. A token containing
`:` or `/`, such as `C:HELLO`, `SYS:C/HELLO` or `/TOOLS/HELLO`, names an exact DOS path.
There is no extension guessing. The file must use the supported
[o65 command profile](../reference/program-loading.md). The child inherits
selected streams and the current directory. Its copied argument tail retains
quotes/escapes and omits shell redirection syntax.

The demo includes HELLO, CAT, WC and the [command toolbox](toolbox.md). CAT
concatenates up to eight exact files, or copies Input to Output when none is
named; WC counts Input. See [writing commands](commands.md).
A child returns a primary status and secondary error; the shell collects both
before showing the next prompt.

### PATH

Each shell stores at most four search directories. The current directory always
comes first and does not consume an entry. `PATH` displays this order without
accessing media. `PATH ADD directory` appends one directory; `PATH SET directory`
replaces the explicit list. `PATH CLEAR` leaves current-directory lookup only,
and `PATH RESET` restores `C:`. Subcommands ignore case.

ADD/SET validate the directory and store its absolute name, so a later CD does
not change its meaning. Duplicate names ignoring case are successful no-ops.
Invalid directories, a fifth entry, BREAK or cleanup failure preserve the old
list. Entries hold names, not locks; PATH does not pin media. Default/reset C:
is resolved through its current assignment. RESET changes the search list only;
it does not recreate or replace C:. Physical names use
the canonical mount spelling; assigned prefixes retain their logical spelling,
so replacing an assignment redirects later command search. PATH never changes
the child's directory.

Only missing files/directories allow the next search attempt. A missing current
directory skips that first attempt; invalid executables, unavailable volumes,
resource errors and BREAK stop lookup. A broken local command therefore reports
its own error. Joined paths are limited to 255 bytes and are never truncated.
Serial commands and both pipeline stages use the same search rules.

The shell still starts in `SYS:`. PATH applies only to executable lookup; file
arguments remain relative to the current directory. If startup cannot establish
C:, the console remains usable. After correcting media, use `CD SYS:` and
`SYS:C/ASSIGN C: SYS:C` to restore the command assignment. Explicit command
paths also work when C: has been removed or redirected.

### Command aliases

`ALIAS` lists the shell's aliases in slot order. `ALIAS name` shows one entry;
`ALIAS name "command arguments"` sets or replaces it, and `UNALIAS name`
removes it. Quote a replacement containing spaces. For example:

```text
ALIAS LS "DIR SYS:"
LS
ALIAS GREET "ECHO hello"
GREET friend
UNALIAS GREET
```

Each new shell starts with `MKDIR -> MAKEDIR`, `LS -> LIST` and `CP -> COPY`.
They accept the target command's arguments, including `LS *.TXT`, and are
ordinary aliases that can be replaced or removed. They consume three of the
eight slots, leaving five for additional aliases.

An alias replaces one command word, then the shell appends that invocation's
arguments. It works at the start of a command or in either pipeline stage;
the ordinary parser then applies redirection and pipeline rules. Expansion
happens once per stage, so aliases do not chain or recurse. Built-in names
keep precedence and cannot be assigned. Names contain 1–15 ASCII letters,
digits, `_` or `-`, starting with a letter; comparison ignores case. Alias
replacements are at most 127 printable bytes and may contain fixed arguments,
but no quotes or shell operators (`|`, `<`, `>`, `;`). A resulting line over
255 bytes fails before opening files. The table holds eight aliases and its
1,152-byte payload is allocated in upper RAM at session startup. It lasts for
this shell session. Other shell sessions and loaded programs have their own
command lookup rules.

```text
CD SYS:WORK
HEAD SYS:STORY.TXT LINES 3
PATH ADD SYS:TOOLS
PATH RESET
```

### Help and errors

All supplied commands accept a sole unquoted `?`, for example `HEAD ?` or
`WC ?`. They print `Arguments: <template>` on the foreground console and return
OK without reading Input or writing data Output. Quoted `"?"` remains data.
Help still works with redirection and pipes; headless help fails explicitly.

The shell reports errors once on its retained console, for example
`HEAD: Object not found (205)`. Pipeline errors name the stage supplying the
combined result. Syntax and redirection errors use `Shell`; a failing status
without a secondary code gets `Command returned n`. WARN with secondary zero,
BREAK and an expected producer broken pipe remain quiet. Reporting never replaces
the original primary/secondary result. See [fault services](../reference/dos.md#fault-text).

## Quoting and redirection

A line holds at most 255 bytes and sixteen words including command names and
redirection targets. Double quotes surround a whole word and permit spaces or
an empty word. Inside quotes, `**` means `*` and `*"` means `"`; other escapes
and attached quoted fragments are errors. Outside quotes, asterisk is literal.
There is no variable or wildcard shell expansion, script syntax or command list. LIST interprets
`*` and `?` in the final component of its own path argument; other commands
receive the characters literally.

Use at most one `<source` and one output redirection, either `>destination` to
replace a file or `>>destination` to append. Operators start at word boundaries;
space after the operator is optional and the target may be quoted:

```text
TYPE <SYS:STORY.TXT >NIL:
DIR WORK >NIL:
HELLO >RAW:
ECHO message >>WORK:LOG.TXT
HELLO | WC >>WORK:COUNTS.TXT
```

Duplicate input or output redirections, `>>>`, attached operators and missing
targets fail before execution. Targets resolve against the directory selected
before the command. The shell restores borrowed streams before closing temporary handles;
a successful redirected CD still changes directory. Input redirection does not
run a script. File output requires an explicitly writable mount. `>` creates or
truncates the target during Open; `>>` preserves existing bytes or creates a
missing file, then seeks to its end before executing the command. Append
requires a seekable file; targets such as NIL:, CON: and RAW: fail with a seek
error and the command does not run. Terminal Close errors make an
otherwise successful command fail while restoring the prompt and streams.
See [filesystem writes](../reference/filesystem-writes.md).
Diagnostics use the shell's retained console.

## Pipes

Exactly two external commands can run concurrently:

```text
HELLO | WC
CAT STORY.TXT | WC
CAT <STORY.TXT | WC >NIL:
```

An unquoted `|` can touch adjacent words. Quoted pipes are literal text. Empty
stages, a second pipe, built-ins as stages, output redirection on the left and
input redirection on the right are rejected before opening files or loading code.
Line/word limits apply to the whole pipeline.

The prompt returns after both children retire. The first ERROR/FAIL in command
order supplies the result; otherwise the first nonzero status is returned (WARN
is 5). A left-stage ERROR with ERROR_BROKEN_PIPE is ignored for the combined
result when the right stage returns OK or WARN with no secondary error. This
lets HEAD and MORE/Q finish early. Both individual results remain recorded;
other producer errors and consumer failures are never hidden. BREAK
cancels both stages and collects their outstanding I/O; unrelated Processes keep
running. See [pipes](../reference/pipes.md) and [Process groups](../reference/process.md#two-member-foreground-groups).

## Editing and BREAK

The prompt is `> `. Typing inserts at the cursor; Backspace deletes before it,
Tab inserts one space and Return submits the whole line. A single row follows
the cursor, with `<` when text to the left is hidden.

| Keys | Action |
| --- | --- |
| Ctrl-A / Ctrl-E | Beginning / end of line. |
| Ctrl-B / Ctrl-F | One character left / right. |
| Ctrl-L | Clear the screen and redraw the prompt and current input, retaining its cursor. |
| Ctrl-U | Clear the whole line. |
| Ctrl-K | Delete from the cursor to the end. |
| Ctrl-W | Delete spaces and the preceding word. |
| Ctrl-P / Ctrl-N | Older / newer command. |
| Atari Ctrl-+ / Ctrl-* | Cursor left / right. |
| Atari Ctrl-- / Ctrl-= | Older / newer command (up / down). |

History keeps ten nonblank commands, skips consecutive exact duplicates and
lasts for this shell session. Moving forward past the newest entry restores your
unfinished draft and cursor. Editing a recalled command does not alter its saved
entry; browsing away loses those edits. Program input is excluded. History needs
about 2.8 KiB of upper RAM; if unavailable, editing still works. There is no
completion, search or history file. Ctrl-D exits an empty prompt; after partial
input it submits that final command and then exits normally.

Ctrl-C/BREAK clears the prompt or cancels the foreground command, including with
redirected streams. Cleanup and outstanding I/O retirement precede the next
prompt. Long CPU-bound commands must cooperate by polling BreakPending. A new
route generation prevents old BREAK input from canceling the next command.

A 256th character or input loss invalidates the whole line through Return, so a
truncated suffix cannot execute. Other writers to the same instance can disturb
the edit row; [separate console instances](../reference/console-windows.md) provide
independent presentation. See [cooked input](../reference/cooked-console.md) and
[foreground cancellation](../reference/foreground-break.md) for precise rules.

## Standalone resident build

With the [build prerequisites](../contributing/building.md) installed:

```sh
mkdir -p build/shell
python3 - <<'PYCONFIG'
import json
from pathlib import Path
profile = json.loads(Path('platform/altirraos/memory-4m.json').read_text())
profile['image_data_bytes'] = 4096
Path('build/shell/memory.json').write_text(json.dumps(profile))
PYCONFIG
python3 tools/native_program.py --compiler-dir build/actionc --source examples/shell/shell.act --tasks --task-capacity 8 --console --dos-mounts config/shell-sdfs.json --memory-profile build/shell/memory.json --output build/shell
python3 tools/make_data_disk.py --output build/shell/system.atr
```

The 4 KiB upper-RAM data area accommodates shell globals and help/fault strings,
matching the demo; it does not enlarge bank-zero reservations.
This is a development XEX and sample data disk. Use the [demo builder](demo.md)
for the OF816 distribution including external commands and the matching ROM.
The sample disk includes a C directory for the boot assignment, with a short
readme in place of executable commands.
The [earlier shell guide](../history/shell-guide.md) and
[implementation record](../history/shell-implementation.md) preserve historical
startup transcripts and measurements.

## WC


[WC](../../examples/commands/wc.act) counts its selected input stream:

```text
WC <README.TXT
WC <NIL:
```

It prints three decimal counts in `lines words bytes` order, followed by a
newline. LF, standalone CR and ATASCII `$9B` terminate lines; CRLF counts once,
including across reads. A final word without a line ending counts as a word but
does not add a line. Words are separated by ASCII space, tab, LF, vertical tab,
form feed, CR or `$9B`. The byte count includes every input byte unchanged.

WC uses a 512-byte buffer and unsigned 32-bit counters. A BREAK or read error
while counting stops the command without printing totals. Counts beyond
4,294,967,295 bytes fail with error 207 instead of wrapping. It borrows the selected streams and leaves
them open. Filenames and options are not accepted as arguments; use redirection.

Build the serialized command with the pinned compiler, then place `WC` on the
command disk as a binary file:

```sh
python3 tools/build_command.py examples/commands/wc.act -o build/WC
```
