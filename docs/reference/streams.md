# Console and NIL streams

[Reference index](README.md) · [DOS API](dos.md) · [Stream example](../guides/streams-example.md)

DOS uses the same owned FileHandle interface for disk files, console streams,
NIL and pipes. File I/O and stream selection run in the caller; console hardware
work uses the shared console worker. Opening a stream adds no Task, stack or DP.

## Names and modes

| Name | Behavior |
| --- | --- |
| `CON:` | Cooked, line-oriented input and console output on the default instance. |
| `RAW:` | Unbuffered input and console output on the default instance. |
| `CON:XXXXXXXX` / `RAW:XXXXXXXX` | Select the opaque eight-hex-digit console instance identity. |
| `NIL:` | Reads return EOF; writes discard bytes and return the requested count. |

Names are case-insensitive. Geometry/name suffixes and CONSOLE: are unsupported.
Console selection follows the [instance contract](console-windows.md). Instances
must already exist; Open does not create a window.

MODE_OLDFILE, MODE_NEWFILE and MODE_READWRITE are accepted for these streams;
they do not impose separate read/write access rights. Unknown modes fail.
IsInteractive is true for console handles and false for NIL. These streams reject
Seek with ERROR_SEEK_ERROR. An enabled native console is required for CON/RAW.

## Transfers

Read and Write use counted bytes without NUL termination. A zero length neither
waits nor consumes input. Negative lengths and invalid buffer extents fail before
submission. Successful writes return bytes accepted, not a promise that the whole
screen has finished repainting.

RAW Read waits for available input and returns an available prefix; it does not
wait for Return, fill every requested byte, edit or echo. The device's bounded
copy quantum is not a narrower public length field. RAW has no keyboard EOF
convention; absent a foreground cancellation route, Ctrl-C/BREAK is byte 3.
The common keyboard decoder maps Atari Ctrl-+/Ctrl-*/Ctrl--/Ctrl-= to bytes
2/6/16/14 (Ctrl-B/F/P/N). RAW returns these bytes without performing editing
or history. Ordinary unmodified punctuation is unchanged.

CON adds the [cooked input contract](cooked-console.md): retained edited lines,
LF termination, Ctrl-D EOF and explicit input-loss errors. Its session owns its
buffers, never a caller's transient buffer. Output uses the native console's text
interpretation; neither handle type is a terminal escape-sequence emulator.

A transfer may return a positive committed prefix with a secondary error. Failure
before any bytes returns -1. Output failures do not become EOF. Foreground BREAK
uses the separate [cancellation scope](foreground-break.md), including when no
Read is active. Pipe byte ordering, EOF and broken-writer behavior are described
in the [pipe contract](pipes.md).

## Ownership and standard streams

Use [DOS selection and error calls](dos.md#task-local-state-and-ownership) for
Input, Output, SelectInput and SelectOutput. A selection borrows an owned handle;
changing it does not close the previous handle. Closing clears selections that
refer to that handle. Raw handle pointers cannot be lent to another Task.

The DOS adapter holds one underlying device-open binding per console endpoint;
multiple DOS handles share it through references. Each caller retains its own
request/reply resources. Process inheritance creates distinct owned wrappers,
sharing the endpoint and cooked session where applicable. Concurrent cooked
reads are serialized by the session's input lease.

Close and Process cleanup retire all active request use before releasing endpoint
storage. The final endpoint reference closes the device binding. This permits
multiple programs to use a console without violating the device's exclusive-open
rule. Console-instance destruction remains subject to its live-handle and route
lifetime checks.

The [original stream design](../history/dos-console-streams-design.md) records
implementation stages and earlier storage budgets.
