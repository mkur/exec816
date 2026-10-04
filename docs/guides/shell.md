# Shell

[Guides](README.md) · [Demo and boot setup](demo.md)

The shell executes built-ins in its own Task and loads external commands into
child Processes. It supports per-command stream redirection and one foreground
pipeline of two external commands. The [demo](demo.md) adds an independent prime
Process in a second console tile; the shell itself also works as a resident entry.
Source lives in [examples/shell](../../examples/shell/).

## Built-in commands

| Command | Behavior |
| --- | --- |
| `HELP` | List implemented commands. |
| `ECHO [words...]` | Print words separated by spaces, then LF. |
| `CD [directory]` | Change directory, or print its canonical path. |
| `DIR [directory]` | List entries in disk order, with directory markers and exact file sizes. |
| `TYPE [file]` | Print a text view of a file, or borrow noninteractive Input when no file is given. |
| `MEM` | Report ordinary/linear available totals and largest eligible blocks; the totals overlap. |
| `TASKS` | Snapshot live public Tasks, including workers; omit unused slots and private idle. |
| `VER` | Print abbreviated Exec816 and compiler-pin revisions. |
| `MOUNT` | List published runtime mounts, handler, access and mounted/offline state. |
| `DEVICES` | List resident drivers and runtime state. |
| `EXIT` | Release shell resources and finish through coordinated shutdown. |

Command names ignore case. MOUNT only lists; it does not mount/unmount media or
probe a drive. A mount's handler is MyDOS or SDFS according to its configuration,
not automatic format discovery. A failed mount leaves a usable prompt; an offline
SIO bus can require a cold boot after correcting the disk/profile setup.

TYPE maps ATASCII end-of-line to LF, drops CR, preserves printable ASCII/tab/LF
and displays other bytes as dots. CAT is the external command for unchanged byte
copying. TYPE rejects interactive Input when no file is supplied.

## Paths and directories

DOS uses bounded 8.3 names on both supported filesystems. Examples:

| Path | Meaning |
| --- | --- |
| `D1:TOOLS/SUB` | Absolute path on the physical volume. |
| `SYS:WORK` | Path on the selected system volume. |
| `/` | Parent of the current directory, clamped at root. |
| `:` | Current volume's root. |
| `/TOOLS` | TOOLS relative to the parent directory. |

There are no `.` or `..` aliases; embedded/trailing empty components are
unsupported. Relative paths need a selected current directory. A failed CD
preserves the previous selection. SYS starts at the configured system volume;
canonical names still use its physical mount name. See [SYS:](../reference/sys-volume.md)
for selection through the boot monitor.

## External commands

Built-ins take precedence. Any other command token names an exact file in the
current directory or a qualified DOS path, such as `HELLO` or `SYS:HELLO`.
There is no extension or PATH search. The file must use the supported
[o65 command profile](../reference/program-loading.md). The child inherits
selected streams and the current directory. Its copied argument tail retains
quotes/escapes and omits shell redirection syntax.

The demo includes HELLO, CAT, WC and the [command toolbox](toolbox.md). CAT accepts an optional file, otherwise
copies Input to Output; WC counts Input. See [writing commands](commands.md).
A child returns a primary status and secondary error; the shell collects both
before showing the next prompt.

## Quoting and redirection

A line holds at most 255 bytes and sixteen words including command names and
redirection targets. Double quotes surround a whole word and permit spaces or
an empty word. Inside quotes, `**` means `*` and `*"` means `"`; other escapes
and attached quoted fragments are errors. Outside quotes, asterisk is literal.
There is no expansion, script syntax or command list.

Use at most one `<source` and one `>destination`, at word boundaries. Space after
the operator is optional and the target may be quoted:

```text
TYPE <SYS:STORY.TXT >NIL:
DIR WORK >NIL:
HELLO >RAW:
```

Duplicate operators, append `>>`, attached operators and missing targets fail
before execution. Targets resolve against the directory selected before the
command. The shell restores borrowed streams before closing temporary handles;
a successful redirected CD still changes directory. Input redirection does not
run a script. Mounted filesystems reject output because they are read-only.
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

The prompt is `> `. Printable ASCII appends, Backspace deletes, Tab inserts a
space and Return submits. The cooked session shows a tail of the line with `<`
when earlier text is hidden. There is no history, completion or cursor navigation.
Ctrl-D exits an empty prompt; after partial input it submits that final command
and then exits normally.

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
python3 tools/native_program.py --compiler-dir build/actionc --source examples/shell/shell.act --tasks --task-capacity 8 --console --dos-mounts config/shell-sdfs.json --output build/shell
python3 tools/make_data_disk.py --output build/shell/system.atr
```

This is a development XEX and sample data disk. Use the [demo builder](demo.md)
for the OF816 distribution including external commands and the matching ROM.
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
