# Cooked console contract

[Reference index](README.md) · [Console streams](streams.md)

CON: is a synchronous line-oriented stream above console.device. RAW: remains
unbuffered. Bare `CON:` binds the default instance; `CON:XXXXXXXX` selects an
eight-digit hexadecimal [instance identity](console-windows.md).
CONSOLE: and geometry/name suffixes remain unsupported. CON: is interactive, supports console Write and
rejects Seek. The caller owns its handle; a reference-counted upper-memory
session owns retained input, never a caller's buffer.

## Line acquisition and reads

Printable ASCII inserts at the cursor, Tab inserts one space, and Backspace
deletes the character before the cursor. Return seals up to 255 edited characters followed by LF. Read returns
bytes without NUL termination; small reads drain the retained line before new
input is acquired. Zero-length Read consumes nothing and never waits.

Ctrl-D on an empty line produces one zero-byte result. On a partial line it
seals the bytes without LF; one EOF follows after those bytes drain. Later reads
may acquire fresh input. Ctrl-C/BREAK cancels a valid partial line with
`ERROR_BREAK` (304). Foreground delivery also works while no Read is pending; see
[foreground cancellation](foreground-break.md).

The 256th edited character invalidates the entire line with ERROR_LINE_TOO_LONG.
Input loss invalidates it with ERROR_BUFFER_OVERFLOW, including any undrained
remainder or pending EOF. Discard through Return, then report failure; Ctrl-D or
Ctrl-C cannot make a suffix executable. The adapter acknowledges that error
before acquiring a fresh line. Output/transport errors do not become EOF.

## Editing and ownership

Ordinary echo preserves the prompt already written by the caller. It displays
at most 36 characters with a leading space or `<` when earlier text is hidden.
The horizontal viewport follows the logical cursor, including movement back
through a long line. Ctrl-A/E moves to the beginning/end, Ctrl-B/F moves left/right,
Ctrl-U clears the whole line, Ctrl-K deletes through the end, and Ctrl-W deletes
spaces and then the word immediately before the cursor. Boundary moves are no-ops.
Atari Ctrl-+/Ctrl-* are left/right; Ctrl--/Ctrl-= are previous/next history.
Ctrl-L clears the edited console with FF and redraws the current input at the
top of the screen, retaining the logical cursor and history browsing state.
At acquisition, the adapter saves the row prefix before the input cursor, up
to 16 characters, and restores it after FF. This includes the shell's `> `
prompt. Longer prefixes and prefixes on a previous row are not restored.
The first echo draws that prefix and the current text; subsequent appends emit
only the new characters while the whole line fits. Deletion, loss and changes
to the viewport or cursor use a bounded redraw, including clearing stale suffix
characters and placing the physical caret. At width 36 this emits at most
111 bytes into the existing 128-byte echo buffer. The remaining 17 bytes retain
the prefix and its length. A screen clear resets the old caret before painting,
so FF, prefix, text and cursor movement fit in the first 111 bytes as well.
Session size and fixed/per-Task bank-zero reservations are unchanged.
The adapter reduces that width to fit the current row, retaining one unused
final column; if no space remains it starts a new row. Echo uses the edited
console even when command Output is redirected. One input lease spans line
acquisition and echo, and the client's existing request is reused only after its
previous reply is collected. No public DOS call recurses while client.busy is set.

Keys arriving without a Read use the existing bounded translated FIFO; input
loss remains explicit. Other clients may write between echo quanta and move the
shared cursor. Editing does not reserve a screen row against those writers;
[independent windows](console-windows.md) provide separate presentation.

The private session layout is generated from [dos.json](../../abi/dos.json).
It owns its line and redraw buffers in upper RAM. Process inheritance shares the
session through references; one input lease serializes line acquisition and echo.
Final cleanup waits for outstanding use before releasing storage. No additional
worker, stack or DP is allocated per session.

## Optional history

History is disabled on a new session. Native `DOS.SetConsoleHistory(handle, enabled)`
enables recording/browsing or disables both. The shell enables it only while
reading its prompt and disables it before parsing or dispatching a command.
Programs reading inherited CON input therefore do not browse or record shell
history. The setting belongs to the shared cooked session, not a wrapper.

Ctrl-P/N (or Atari up/down) recall older/newer entries. A fixed ring holds ten
nonblank Return submissions, skipping consecutive exact duplicates. Original
text is saved before shell parsing, so failed commands remain recallable. EOF,
cancellation and discarded lines are not recorded. The first move into history
saves the current draft and cursor; moving past the newest entry restores them.
Recall copies into the live line. Editing that copy does not change a saved entry;
browsing away discards those edits. Return, EOF, cancellation, loss and disabling
history reset browsing. Toggling history preserves pending reads, drain position,
EOF and discard state.

The optional block is allocated once on first enable and freed on final session
release. Allocation failure leaves editing usable and history disabled; the shell
then stops trying for its lifetime. The session payload is 410 bytes (416 rounded)
and the optional history block is 2,824 bytes in upper RAM. Compared with the old
402-byte payload (408 rounded), one shell with history adds 2,832 bytes. Fixed
and per-Task reserved bank-zero bytes are unchanged.

Completion, history search/persistence, key repeat and terminal escape sequences
are outside this contract.
