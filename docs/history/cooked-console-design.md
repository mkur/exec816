# Cooked console contract

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/cooked-console.md) and [history index](README.md).

Status: C1 terminal state, C2 DOS binding and C3 shell migration are implemented
and qualified. Foreground delivery is implemented through B5; instance binding
and multiwindow echo have W1–W3 development coverage. See the [implementation record](console-interaction-implementation.md).

CON: is a synchronous line-oriented stream above console.device. RAW: remains
unbuffered. Bare `CON:` binds the default instance; `CON:XXXXXXXX` selects an
eight-digit hexadecimal [instance identity](../reference/console-windows.md).
CONSOLE: and geometry/name suffixes remain unsupported. CON: is interactive, supports console Write and
rejects Seek. The caller owns its handle; a reference-counted upper-memory
session owns retained input, never a caller's buffer.

## Line acquisition and reads

Printable ASCII appends, Tab inserts one space, and Backspace deletes the last
character. Return seals up to 255 edited characters followed by LF. Read returns
bytes without NUL termination; small reads drain the retained line before new
input is acquired. Zero-length Read consumes nothing and never waits.

Ctrl-D on an empty line produces one zero-byte result. On a partial line it
seals the bytes without LF; one EOF follows after those bytes drain. Later reads
may acquire fresh input. Ctrl-C/BREAK cancels a valid partial line with
`ERROR_BREAK` (304). Foreground delivery while no Read is pending belongs to the
separate cancellation slices.

The 256th edited character invalidates the entire line with ERROR_LINE_TOO_LONG.
Input loss invalidates it with ERROR_BUFFER_OVERFLOW, including any undrained
remainder or pending EOF. Discard through Return, then report failure; Ctrl-D or
Ctrl-C cannot make a suffix executable. The adapter acknowledges that error
before acquiring a fresh line. Output/transport errors do not become EOF.

## Editing and ownership

Tail redraw preserves the prompt already written by the caller. It displays at
most 36 characters with a leading space or `<` when earlier text is hidden.
The adapter reduces that width to fit the current row, retaining one unused
final column; if no space remains it starts a new row. Echo uses the edited
console even when command Output is redirected. One input lease spans line
acquisition and echo, and the client's existing request is reused only after its
previous reply is collected. No public DOS call recurses while client.busy is set.

Keys arriving without a Read use the existing bounded translated FIFO; input
loss remains explicit. Other clients may write between echo quanta and move the
shared cursor. Editing does not reserve a screen row against those writers;
independent windows address presentation isolation in their own slices.

The private session layout is generated from `abi/dos.json`: 400 payload bytes,
including 256 line bytes and 128 redraw bytes. Redraw emits at most 110 bytes;
the session retains only state and its own buffers. Create initializes one
reference; Destroy rejects shared ownership. Duplication is a later Process
operation. C1 adds no worker, stack, DP or fixed reservation. Reserved bank-zero
delta is zero fixed bytes and zero bytes per Task, including guards, alignment
and unused capacity.

History, completion, cursor movement, key repeat and terminal escape sequences
are outside this contract.
