# Small shell editor and command history

[Implementation plans](README.md) · [Shell guide](../guides/shell.md) ·
[Current cooked input](../reference/cooked-console.md)

Status: implemented; this note preserves the accepted design. See the
[implementation plan](shell-editing-implementation-plan.md) and
[development record](../history/shell-editing.md).

Add insertion and cursor movement to the existing line editor, plus the last
ten submitted commands. Keep the 255-character limit, one visible edit row and
fixed storage. This should make correcting a filename and repeating a command
comfortable without building a general terminal editor.

## Keys

| Key | Proposed behavior |
| --- | --- |
| Printable ASCII / Tab | Insert at the cursor; Tab inserts one space. |
| Backspace / Ctrl-H | Delete the character before the cursor. |
| Ctrl-A / Ctrl-E | Move to the beginning / end of the line. |
| Ctrl-B / Ctrl-F | Move one character left / right. |
| Atari Left / Right (Ctrl-+ / Ctrl-*) | Same movement as Ctrl-B / Ctrl-F. |
| Ctrl-U | Clear the whole line. |
| Ctrl-K | Delete from the cursor to the end. |
| Ctrl-W | Delete spaces immediately before the cursor, then the preceding word. Words are separated by spaces; no shell parsing. |
| Ctrl-P / Ctrl-N | Recall the previous / next command. |
| Atari Up / Down (Ctrl-- / Ctrl-=) | Same history navigation as Ctrl-P / Ctrl-N. |
| Return | Submit the complete line, wherever the cursor is. |
| Ctrl-C / BREAK | Cancel the line using the existing foreground cancellation path. |
| Ctrl-D | Keep the existing EOF behavior: exit an empty prompt, or submit a partial final command and then exit. |

Movement and deletion at a boundary do nothing. Insertion shifts at most 255
bytes. There is no overwrite mode. Keep the current overflow rule: a 256th
character invalidates the line through Return. Editing and history keys cannot
escape that discard state or recover a suffix after input loss.

Include the Atari cursor keys in the first version. Control letters already
reach cooked input as ASCII control bytes; the current console decoder drops
these four Ctrl-punctuation combinations. Add four translations in
[CONSOLEINPUT.Decode](../../lib/console/consoleinput.act):

| Atari cursor chord | Keyboard scan byte | Translate to |
| --- | --- | --- |
| Ctrl with `+` (Left) | `$86` | Ctrl-B (`$02`) |
| Ctrl with `*` (Right) | `$87` | Ctrl-F (`$06`) |
| Ctrl with `-` (Up) | `$8E` | Ctrl-P (`$10`) |
| Ctrl with `=` (Down) | `$8F` | Ctrl-N (`$0E`) |

These are aliases for existing editor actions, requiring no additional state
or escape-sequence parser. RAW: reports the same translated control bytes;
CON: interprets them while editing. Up/Down do nothing when history is disabled.
Do not turn them into ATASCII screen-control output. Ordinary `+`, `*`, `-` and
`=` remain printable. Host arrow keys work when the emulator maps them to these
Atari chords; test the actual pinned configuration instead of assuming its mapping.
Home/End and a forward-delete binding remain deferred; retain Ctrl-D's EOF meaning.

## Ten remembered commands

Use a ten-slot ring of 256-byte, NUL-terminated strings. Keep the original text,
without its terminating LF; quoted text, spacing, redirection and pipes remain
literal. No tokenization or expansion is involved.

- Remember valid, nonblank lines submitted with Return while at the shell
  prompt, including commands that later fail. Skip only an exact duplicate of
  the newest entry. The eleventh entry replaces the oldest.
- Do not remember an unfinished, canceled or invalidated edit. Return must not
  store a line being discarded after overflow or input loss. Ctrl-D is EOF,
  not a history submission.
- First Ctrl-P saves the current draft and its cursor, then recalls the newest
  command with the cursor at its end. Further Ctrl-P moves toward older entries.
- Ctrl-N moves toward newer entries. Moving past the newest restores the draft
  and its saved cursor. At either boundary, further movement does nothing.
- Recall copies into the ordinary edit buffer. Editing that copy does not alter
  a history slot. Browsing away discards edits to the recalled copy; the saved
  draft remains available. Running it records the edited text normally.
- Return or cancellation resets browsing. History lasts for this shell's
  console session and is released when its last handle closes.

Recalling a command never runs it automatically. There is no history file,
search, numbered listing, `!` expansion, deduplication across the ring or
configurable history length.

## Fit the current console design

The shell now reads CON: through `DOS.Read`; editing lives in
[COOKEDLINE](../../lib/dos/cookedline.act), with transport and echo in
[DOSCOOKED](../../lib/dos/doscooked.act). Extend those modules. Keep one editor;
ordinary CON: readers also gain cursor movement and insertion.

History is optional and off by default. Add one small native DOS operation,
provisionally `SetConsoleHistory(handle, enabled)`, for a caller-owned cooked
handle. Enabling allocates history on first use; disabling preserves the entries
but stops recording and ignores Ctrl-P/N. Reject a busy session and non-CON
handles through ordinary DOS errors. Neither toggle changes pending line, EOF
or discard state. No new kernel operation or COMMAND import is needed.

The shell enables history once before acquiring each prompt line and disables
it before parsing or dispatching that line, including built-ins. Keep it enabled
across the small reads that drain that one line. Disable it on prompt errors and
EOF too. Thus a command reading inherited CON: input cannot recall shell commands
or add its data to history. Inherited handles retain the existing shared session;
they do not get another history allocation. Separate shell CON: sessions have
separate rings.

If the initial history allocation fails, continue with editing and leave history
disabled for that shell session. Do not retry allocation on every key or prompt.
Keep storage owned by the existing cooked session and free it at final release.
The input lease and busy state continue to serialize editing; no callbacks,
extra worker or new locking scheme are required.

## Display and storage

Track a logical insertion cursor separately from the existing read/drain
position. Keep a horizontal viewport that follows the cursor, including the
blank insertion cell at the end. Retain the leading `<` for hidden text on the
left; text beyond the right edge is simply clipped. Ctrl-A/E reveal either end.
Use the existing maximum of 36 text columns, reduced for narrow windows, and
keep the final physical column unused to avoid automatic wrapping.

Remember the displayed cursor's offset from the edit area's start. For a redraw,
backspace to that start, write the marker and visible text, blank any old suffix,
then backspace to the insertion cursor. Preserve the caller's prompt. With at
most 37 occupied columns this needs at most 111 output bytes, fitting the current
128-byte echo buffer. Retain the cheap append path when appending at the end
without shifting the viewport; other edits use one bounded redraw. No new cursor
escape protocol or direct screen writes are needed. Writes by another Task to
the same instance retain today's documented interference limitation.

Proposed storage budget, using the existing eight-byte heap rounding:

| Addition | Upper-RAM bytes |
| --- | ---: |
| Cursor and viewport offsets (two CARDs), displayed cursor (BYTE), optional history pointer (three bytes) | 8 per cooked session; current 402-byte payload becomes 410, rounded allocation grows from 408 to 416 |
| Ten 256-byte history slots | 2,560 per enabled session |
| Saved draft | 256 per enabled session |
| Ring next/count, selection and enabled flags; draft length/cursor | 8 per enabled session |
| Total extra for one shell with history | **2,832** |

The optional history block is 2,824 bytes, already eight-byte aligned; use
AllocMem, without an AllocVec prefix. A one-time shell availability flag can use
existing reserved shell storage. No per-entry allocation, length table, second
redraw buffer or whole-screen cache is necessary. Generate private record changes
from [abi/dos.json](../../abi/dos.json).

Target **zero additional fixed or per-Task bank-zero reservations**, counting
guards, alignment and unused capacity. No new Task, stack or DP. Upper-RAM code
size and observed stack use must be measured during implementation; the table
is a proposed data budget, not a measured build result.

## Small implementation slices

1. Extend COOKEDLINE editing and bounded redraw. Check insert/delete/movement,
   cursor-independent Return, 36/37/255-character boundaries, narrow windows,
   EOF, BREAK and discard recovery in raw and optimized emitted code. Check all
   four Atari cursor translations and unchanged unmodified punctuation.
2. Add the optional ring and shell prompt bracketing. Check empty/full/wrapped
   history, duplicates, exact text, draft restoration, editing recalled entries,
   allocation failure, shared-session cleanup and absence of history during
   foreground program input. Small reads must record a submitted line once.
3. Update HELP and the shell guide. Run a focused physical-key shell session,
   including Atari cursor chords, a long command, cancellation and a recalled
   pipeline; verify Left/Right match Ctrl-B/F and Up/Down match Ctrl-P/N. Check actual
   screen/cursor, guards, OS return, heap cleanup and memory costs. Refresh the
   standard OF816 demo through `tools/build_demo.py` and exercise the new keys.

Use the development testing tier. Completion, multi-line commands, undo/yank,
keymaps, persistent history and a reusable readline framework stay out of scope.
