# TAIL and FIND utilities

Roadmap item 3 is delivered in two command slices. The current user contract is
in the [toolbox guide](../guides/toolbox.md).

## TAIL — implemented

`TAIL [FILE] [LINES n]` retains the last ten lines by default. Zero returns
without reading; one through sixteen uses the same fixed ring. Each slot holds
up to 1,024 bytes, a counted length and the source delimiter flag. Lines use the
existing reader's LF/CR/CRLF/ATASCII recognition. Embedded NUL and an
unterminated final line remain counted payload. No seek or new provider is needed
for pipes. Read errors and BREAK prevent suffix emission; write and Close errors
retain the existing command cleanup policy.

The optimized command uses 17,306 upper-RAM BSS bytes, including the aligned
16,448-byte ring, reader and argument storage. Its reserved bank-zero delta,
counting guards, alignment and unused capacity, is **0 fixed bytes and 0 bytes
per public Task**. It uses the existing command Task and stack reservation.

Development checks pass: 32 emitted command cases, 22 existing HEAD cases after
refreshing the shared fixture's current pane/timer API declarations, the host
suite and a physical-key shell session. Cases cover circular wrap, limits,
mixed delimiters across single-byte reads, NUL, long lines, input over 64 KiB,
partial writes, read/write/Close errors, BREAK, help, file ownership and pipes.
The shell uses the pinned native AltirraOS ROM and paced emulator, profile 4
generic56k with accurate disk timing disabled. Guards, OS restoration and shell
retirement checks pass. These are development checks, not release qualification.
The [evidence record](../development/tail-find.json) pins the actual artifacts.

The demo builder includes TAIL in SYS:C and STORY.TXT introduces it. This slice
does not refresh the previously built preview ZIP.

## FIND — next slice

Use `FIND [DIR] [PATTERN pattern]` for recursive filename matching with the
existing case-insensitive `*`/`?` matcher. Keep directory frames and output paths
bounded, retain each public enumeration record separately and release all
locks on success, errors and BREAK. GREP continues to search file contents.
