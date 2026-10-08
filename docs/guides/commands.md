# Write a disk command

[Guides](README.md) · [Build prerequisites](../contributing/building.md)

Disk commands use the small `COMMAND` interface and a `LONGINT FUNC Main()` entry.
Return a named command status; set IoErr when there is a secondary cause to report.
There is no separate SetResult call.

## Start with HELLO

The complete example is [hello.act](../../examples/commands/hello.act):

```action
MODULE HELLO

USE COMMAND
USE CSTRING AS STR

; Write one greeting through the command's selected output stream.
LONGINT FUNC Main()

  LET parsed=COMMAND.ReadArgsOrHelp(c"",NULL,0,NULL,0)
  IF parsed<>COMMAND.ARGS_PARSED THEN
    RETURN(IF parsed=COMMAND.ARGS_HELP THEN COMMAND.RETURN_OK
        ELSE COMMAND.RETURN_ERROR FI)
  FI

  LET greeting=c"Hello from disk!\n"
  LET length=STR.strlen(greeting)

  LET count=COMMAND.Write(COMMAND.Output(),BYTE POINTER(greeting),length)

RETURN(IF count=length THEN COMMAND.RETURN_OK ELSE COMMAND.RETURN_ERROR FI)

ENDMODULE
```

Output is selected by the parent: the same code works on the console, NIL or a
pipe. Write is counted binary I/O; strlen excludes the C-string terminator. The
[CSTRING library](../reference/cstrings.md) is resident, so each command imports
its used routines rather than carrying another library implementation.

Build it from the repository root:

```sh
python3 tools/build_command.py examples/commands/hello.act -o build/commands/HELLO
```

This produces the o65 command and companion reports, not a new disk image.
The [demo builder](../contributing/building.md#build-the-demo) compiles and bundles
all sixteen supplied commands with the matching resident providers. Rebuild the resident image
and commands together when their ABI changes.

## Arguments, input and errors

`COMMAND.GetArgStr()` borrows the Process's NUL-terminated argument string.
Use [ReadArgsOrHelp](../reference/command-arguments.md#optional-command-help)
for shared template parsing and `?` help. Only ARGS_PARSED runs command work;
ARGS_HELP returns OK and ARGS_ERROR returns ERROR. Result slots and decoding
storage belong to the caller. ReadArgs remains available for parsing without
console UI. Neither API reads data Input.

Use Input/Output for selected streams and explicit Open/Close for owned files.
Honor byte counts, EOF and partial-transfer errors. Report failure through
`COMMAND.RETURN_ERROR` and the named errors in COMMAND; preserve a causal IoErr
across cleanup. Long CPU loops can inspect `COMMAND.BreakPending()` so foreground
BREAK does not depend on entering a blocking read.

[CAT](../../examples/commands/cat.act) demonstrates file/stream copying and
[WC](../../examples/commands/wc.act) demonstrates arguments, bounded buffers,
BREAK checks and numeric output. Follow the [style guide](../contributing/style.md).

## Scope

COMMAND is a bounded set of checked resident imports, not the complete resident
Exec API. See the [loading contract](../reference/program-loading.md) for supported
imports and the [Process contract](../reference/process.md) for lifetime, inherited
handles and result collection. For broader Exec experiments, start with the
[standalone message example](messages.md).

## Shared toolbox services

The [toolbox](toolbox.md) uses these resident COMMAND imports:

- `Fault` and `PrintFault` provide bounded [fault text](../reference/dos.md#fault-text)
  using caller scratch and preserving IoErr. Ordinary commands return errors;
  the shell prints their final explanation on its own console.
- `WriteAll(handle, buffer, length)` returns DOS true after the entire counted
  write, or false with IoErr. It handles short writes and BREAK, preserving a
  committed-prefix error. Zero length is a no-op; negative lengths fail.
- `ReaderInit(reader, handle)` initializes a caller-owned `COMMAND.Reader` and
  borrows the handle. Pass the record address as BYTE POINTER. It allocates
  nothing and never closes the handle.
- `ReadByte(reader)` returns 0..255, -1 for EOF or -2 for error. Committed bytes
  precede a saved read error. `reader.error` retains that pending cause; an early
  consumer must check it before claiming success.
- `ReadLine(reader, buffer, capacity)` returns a counted payload excluding its
  delimiter, -2 for EOF or -1 for error. Empty lines return zero.
  `reader.terminated` indicates a present delimiter. It handles CRLF across reads,
  CR, LF and ATASCII EOL. Payloads are binary-safe and not NUL-terminated.
  Capacity exhaustion is an error, never a truncated successful line.
- Lock/UnLock/Examine/ExNext publish existing DOS directory operations using
  opaque BYTE POINTER identities and the generated `COMMAND.FileInfoBlock`.
- IsInteractive/OpenConsole/ConsoleInfo expose the
  [foreground console contract](../reference/dos.md#foreground-console-access).

DOS transfer buffers and reader storage must be in caller-owned upper RAM.
Use command globals (private to the loaded image) for I/O scratch; local arrays
on the native bank-zero stack cannot be passed to DOS Read/Write. Do not modify its cursor fields after
initialization, share it between Tasks, or mix buffered and direct reads from its
handle. Prefetching advances the underlying cursor beyond consumed bytes.
Arguments and buffers must remain valid for each synchronous call; these helpers
do not provide memory isolation for arbitrary machine code.

The examples' `command-files.inc` shares owned-handle cleanup and optional input
opening. `command-common.inc` adds text presentation; `command-write.inc` checks
names and BREAK; `command-transfer.inc` implements COPY/TEE's counted transfer
policy. Keeping those helpers separate avoids loading text formatting into
filesystem mutation commands. `command-pattern.inc` shares LIST-style matching;
`command-selection.inc` collects up to eight COPY/DELETE names before mutation,
borrowing argument prefixes and copying only 8.3 leaf names. It releases all
enumeration locks before opening outputs or deleting entries, avoiding the
mount-wide ExNext invalidation caused by these operations.
Open modes and `OFFSET_BEGINNING`, `OFFSET_CURRENT`
and `OFFSET_END` come from the generated COMMAND constants. CreateDir, DeleteFile
and Rename use the existing filesystem imports. The argument parser, buffered I/O and numeric formatting themselves remain
single resident implementations. New interfaces are generated from
`abi/program.json`; rebuild the resident system and all commands together.

The [PRIMES command](../../examples/commands/primes.act) demonstrates an owned
lower pane. `OpenPane(rows)` returns an output handle; ordinary Close restores
the default console's height. `WriteAt(handle,column,row,buffer,length)` writes
one printable horizontal span and preserves the stream cursor. Check both its
committed count and IoErr before saving displayed values. `Delay(ticks)` waits
in VBI ticks and settles its timer request before returning on BREAK. These
operations reuse the resident console and timer services. Keep write buffers
in command globals and close the pane before Main returns.
