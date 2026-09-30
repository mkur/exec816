# Resident shell

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/shell.md) and [history index](README.md).

The shell runs built-ins in the root Task through DOS streams. The current
implementation provides HELP, ECHO, CD, DIR, TYPE, MEM, TASKS, VER, MOUNT, DEVICES
and EXIT, with per-command
Input/Output redirection. See the [implementation plan](../plans/shell-implementation-plan.md).
See the [implementation record](shell-implementation.md) for qualification status.
Exact-path external commands and two-stage external pipelines are implemented.
Background shell syntax remains outside the current interface.

The resident entry and its shared source files live in
[examples/shell](../../examples/shell).

Build the resident entry with the pinned compiler and eight-slot profile:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
python3 tools/native_program.py --compiler-dir build/actionc \
  --source examples/shell/shell.act --tasks --task-capacity 8 --console \
  --dos-mounts config/shell-sdfs.json --output build/shell
python3 tools/make_data_disk.py --output build/shell/sdfs.atr
```

The output is `build/shell/program.xex`. Use the pinned
[AltirraOS console machine](../../toolchain/altirra-shell-console.json), mount
`build/shell/sdfs.atr` as drive 1,
select **Generic + 57600 baud** in Altirra's Disk Drives dialog (`generic56k`
through the bridge), and disable SIO patch/burst I/O. The
[example mount configuration](../../config/shell-sdfs.json) explicitly declares
D1, unit 49, 720 sectors of 128 bytes, SDFS (format 2) and GENERIC57600 (profile 4).
Use [the 256-byte configuration](../../config/shell-sdfs-256.json) together with
`make_data_disk.py --sector-bytes 256` for matching larger sectors.
MyDOS remains available through [its explicit configuration](../../config/shell-mydos.json)
and `make_data_disk.py --format mydos`; omitted format fields still mean MyDOS. See the
[57.6 kbaud qualification](sio-57600.md) for actual PAL clock rates and limits.
For another admitted
volume, supply its own mount JSON with matching geometry and drive profile;
changing this JSON does not change the disk's format.

Before using **File → Boot Image**, disable **Computer → Boot → Unload disks
when booting new image** in Configure System, then mount the ATR in D1. Cold-load
the XEX with the disk still mounted. A wrong drive mode or absent disk produces
startup `Error 1` (SIO timeout); subsequent relative DIR/CD errors follow from
the missing current-directory lock. Correct the settings and cold-load the XEX
again: changing the drive mode after this timeout leaves the driver offline.

The resident entry prints startup progress through its owned CON: stream:

```text
Exec816 (<commit>)

exec: 8 task slots
exec: stack checks enabled
console.device: ready
sio.device: ready, 57.6k profile
D1: mounting...
D1: ready, read-only

>
```

The build embeds the seven-character hexadecimal Exec816 commit without a `0x`
prefix, preserving any leading zeros and appending `-dirty` when
the source tree has uncommitted changes (`unknown` outside a Git checkout).
The console line follows successful CON: setup; the SIO line follows a successful
OpenDevice/CloseDevice of `sio.device`, starting its resident worker without
disk traffic. Mount readiness follows a successful root lock and current-directory
selection. The task-slot count and nominal baud profile come from the build
configuration. Startup omits configured disk geometry, which is not detected,
and does not probe CPU or RAM. A failed mount prints `D1: mount failed` and
the existing numeric error, then leaves a usable prompt.

[Stack checks](../contributing/stack-checks.md) default to enabled in `config/kernel.json`.
Pass `--no-stack-checks` to the build command for an unchecked benchmark image,
or `--stack-checks` to force them on. Startup reports the resolved setting.
Both modes keep the same reserved stacks, interrupt headroom and canaries.

`ShellBootStart(consoleName)` provides this startup around the shared session code.
Command fixtures use `ShellStart(initial)`, which accepts a null initial path
to leave the default directory unset. The
ordinary empty `config/dos-mounts.json` can build a console-only session; an
unavailable initial directory reports its error and leaves a usable prompt.

| Command | Behavior |
| --- | --- |
| `HELP` | List implemented commands. |
| `ECHO [words...]` | Print words separated by single spaces, then LF. |
| `CD [directory]` | Select an owned directory lock; without an operand, print its canonical name. |
| `DIR [directory]` | List entries in disk order, with `/` for directories and exact byte sizes for files. |
| `TYPE [file]` | Read in 512-byte chunks and print a text view; without a file, borrow noninteractive Input. |
| `MEM` | Report ordinary/linear available totals and largest eligible blocks separately. |
| `TASKS` | Snapshot live public tasks: slot, state and name. |
| `VER` | Print the Exec816 commit and pinned actionc commit as abbreviated hexadecimal strings. |
| `MOUNT` | List published runtime filesystem mounts, with handler, access and mounted/offline state. |
| `DEVICES` | List built-in Exec drivers and their current runtime state. |
| `EXIT` | Restore borrowed defaults, release owned locks/console/context, and return through coordinated service shutdown. |

Commands ignore case. Directory names follow DOS's bounded 8.3 namespace on either filesystem.
For example, `CD D1:TOOLS/SUB`, `CD /`, `CD :`, and `CD /TOOLS` use absolute,
parent, current-volume-root, and parent-relative forms. Leading parents clamp
at root. There are no `.` or `..` aliases; embedded/trailing empty components
remain unsupported. A failed CD preserves the previous directory. Relative
paths require a selected directory, while an explicit mount remains usable
without one.

TASKS includes the shell and service workers; unused slots and the private idle
context are omitted. The configured eight slots include these public tasks.
States are RUNNING, READY, WAITING (signals), or SLEEPING (timed sleep).
The display is a snapshot: the shell is RUNNING when captured, while other
states may change before printing finishes. Names are copied to at most 23
characters, control/non-ASCII bytes become dots, and unnamed tasks display
`(unnamed)`. Scheduling exclusion protects the copy, with IRQs enabled;
it is released before any DOS output. The snapshot uses the existing shell
transfer buffer and retains no pointers into another task's storage.

VER prints, for example, `Exec816 (abcdef0)` and `actionc pin: 47cd55b`.
The latter identifies [toolchain/actionc.json](../../toolchain/actionc.json);
local compiler overrides remain separately recorded in build provenance.
TASKS, VER, MOUNT and DEVICES accept no operands and support ordinary output
redirection, such as `TASKS >NIL:`, `MOUNT >NIL:` or `DEVICES >RAW:`.

MOUNT is currently the listing form only; mounting/unmounting through the shell
is not implemented. It copies published records from the running DOS service:

```text
MOUNT FILESYSTEM ACCESS    STATE
D1:   SDFS       read-only mounted
```

The current handler is read-only MyDOS. Its name identifies the handler serving
the mount, not an automatically detected disk format. Geometry is omitted.
Offline published mounts remain visible as `offline`; unmounted and unpublished
records are omitted. An empty, failed, starting or stopping service prints
`No mounted filesystems`. Listing does not start the service, open a volume,
probe media, or issue SIO traffic. The snapshot copies at most eight aliases
(31 characters plus terminator) before releasing scheduling exclusion.

DEVICES shows the production drivers included in the image:

```text
DEVICE          STATE
console.device  ready
sio.device      ready
```

Driver states are `inactive`, `starting`, `ready`, `stopping`, `stopped` or
`offline` (`unknown` for an unrecognized state). The console row is absent when
console support is omitted. An unused SIO driver remains `inactive`; listing
does not initialize it. These are software drivers, not a scan of attached
physical devices. A DOS mount such as D1: appears under MOUNT instead.

Both commands use the existing 512-byte shell transfer buffer, hold Forbid only
while collecting their snapshot, and leave IRQs enabled. No pointers into mount
storage survive the copy, and all DOS output occurs after Permit. There is no
additional persistent allocation or bank-zero reservation.

The playground ATR is 90 KiB plus its 16-byte header, with four small text files:
`README.TXT`, `HELLO.TXT`, `DOCS/COMMANDS.TXT` and `TOOLS/SUB/NOTE.TXT`.
Its editable source files live in [examples/shell-disk](../../examples/shell-disk).
Try `DIR`, `TYPE README.TXT`, `CD DOCS`, `TYPE COMMANDS.TXT` and `CD :`.
The ATR is a data disk; boot the separate XEX. Large regression files remain
in the test fixtures and are not bundled with the playground image.
DIR still computes exact file sizes by walking their chains, so large disks
can take much longer. Ctrl-C or BREAK cancels a running command and restores
the prompt after its outstanding I/O retires.

TYPE drops CR, maps ATASCII `$9B` to LF, preserves printable ASCII/tab/LF, and displays other bytes as dots. A failed Read prints none of that call's partial data. NIL Input ends immediately; the interactive Input is rejected to keep TYPE from waiting for keyboard lines. Ordinary and linear MEM values overlap and must not be added together.

Enter at most sixteen words, including the command and redirection targets. Double quotes surround a
whole word and allow spaces or an empty word. Inside quotes, `**` means `*` and
`*"` means `"`; other escapes and attached quoted fragments are errors. Outside
quotes, an asterisk is literal. One unquoted `|` separates two external commands,
including without adjacent spaces. Command lists are rejected before dispatch.
A backtick is an ordinary parser byte, but the
current Atari keymap has no physical backtick key. No expansion is performed.

Use one `<source` and one `>destination`, with an operator at a word boundary;
space after the operator is optional, and targets may be quoted. For example,
`TYPE <D1:TEXT.TXT >NIL:`, `DIR TOOLS >NIL:` or `ECHO "<literal>" >RAW:`.
Attached operators, duplicates, append `>>` and missing targets are errors.
Both targets open against the directory selected before the command; the shell
restores both borrowed defaults before closing either temporary handle. A
successful redirected CD persists. Input redirection does not run a script.
Filesystem output fails read-only (214); CONSOLE: remains unsupported.
Diagnostics always use the shell's retained console. A command output error
returns status 10 if diagnostics still work; a restoration or cleanup failure
stops dispatch with status 20 and retains unresolved ownership.

A pipeline contains exactly two disk-loaded commands, for example `HELLO | WC`
or `CAT STORY.TXT|WC`. Quoted pipes remain literal argument bytes. Empty stages,
a second pipe, resident built-ins as stages, output redirection on the left and
input redirection on the right are rejected before any file is opened or command
is loaded. The existing 255-byte line and sixteen-word limits apply to the whole
pipeline, including redirection targets. Each stage gets its own original quoted
argument tail; the separator and redirections are omitted.

Input redirection may appear on the left and output redirection on the right:
`CAT <STORY.TXT | WC >NIL:`. Both Images and stream snapshots are prepared before
launch. Both stages run concurrently, and the prompt returns after both retire.
Success requires both to succeed; otherwise the first failing stage in command
order supplies the status and error. Diagnostics stay on the private shell
console. BREAK during loading cancels the load; during execution it cancels both
stages and collects their outstanding I/O. An unrelated background Process keeps
running. A fresh route prevents stale BREAK from reaching the next prompt.
See the [pipe contract](../reference/pipes.md) and [Process group lifetime](../reference/process.md#two-member-foreground-groups).

The prompt is `> `.  Printable ASCII appends, Backspace deletes the final byte,
Tab inserts a space, and Return submits. A 255-byte logical line displays its
last 36 characters; `<` marks a hidden prefix. Redraw leaves the last physical
column unwritten, so editing never depends on backspacing over a wrapped row.
Editing belongs to the [cooked CON: session](../reference/cooked-console.md); the shell
reads completed lines in chunks of at most 64 bytes before parsing them.
There is no history, completion, cursor navigation or key-repeat synthesis.
Ctrl-D exits at an empty prompt. After partial input it executes that final
unterminated command and then exits through ordinary cleanup.

Ctrl-C and BREAK clear the prompt line or cancel the current built-in, including
when its Input or Output is redirected. Cancellation restores the selected
streams, releases command resources and clears queued typeahead before the
fresh prompt. It records status 10 and ERROR_BREAK (304); the prompt acknowledges
the break without printing an error diagnostic. A canceled CD retains its old
directory. Input typed during a command is bounded console typeahead.
A 256th character invalidates the entire line until Return. An input
loss discards the partial command and resynchronizes through Return; Ctrl-C
cannot make the remaining suffix executable. Another Task's console output
can disturb the edit row; independent windows are not implemented.

Command results retain a status (0 success, 10 command error, 20 fatal failure)
and a signed secondary error. Diagnostics use the shell's owned CON: handle.
Console output failure other than cancellation stops dispatch and proceeds through cleanup. If a
resource cannot safely be released, the shell retains its identity and the
existing DOS/Task lifetime guards prevent successful removal with live ownership.

The [integrated qualification](shell-implementation.md#slice-8-integrated-shell-capacity-and-timing-qualification)
passes with eight live Tasks, a complete 70,003-byte Read, physical keyboard
input, shared output and 125 kbaud SIO in raw and optimized code. The shipped
shell plus console/filesystem/SIO services uses four public slots. Shell state
occupies 1,288 upper-RAM bytes. Its CON: binding adds a 400-byte cooked session
and a 24-byte allocated handle, with no additional bank-zero reservation.
The original qualification above describes the former RAW editor; current
migration results belong to the [console interaction record](console-interaction-implementation.md).

A filesystem command can wait behind another Task's entire filesystem request;
the full-read workload measured 45–46 seconds for a queued CD to complete.
Other Tasks continue running during that wait. Shared scrolling can also delay
the next prompt by seconds. This milestone provides neither asynchronous command
cancellation nor an isolated console window. The qualification records distinguish
RAW collection, completed editor writes and eventual physical display.

## External commands

Built-ins take precedence. Any other command token names an exact file in the
current directory or a qualified DOS path, for example `HELLO` or `D1:TOOLS/HELLO`.
The file must be a checked Exec816 o65 command; see the
[loader contract and build command](../reference/program-loading.md#disk-loading-and-shell-dispatch).
There is no extension or PATH search. The child inherits selected streams and the
current directory. Redirection is removed from its copied argument tail; quotes
and escapes are retained. Diagnostics continue on the shell's private console.

`HELLO >NIL:` discards command output. `READ <TEXT.TXT` (the test reader command)
uses a file as input. MyDOS file output remains unsupported. BREAK/Ctrl-C is
cooperative: a command must use ordinary cancellable DOS calls or poll
`COMMAND.BreakPending()`. Its exit status is collected before the next prompt.

### WC

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
