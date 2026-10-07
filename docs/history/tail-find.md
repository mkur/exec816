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

## FIND — implemented

`FIND [DIR] [PATTERN pattern]` walks descendants in filesystem order, matching
entry names with LIST's existing case-insensitive `*`/`?` matcher. It prints paths
using the supplied directory prefix and appends `/` to directories. The start
directory is omitted. Filtering affects output only, so a matching file can be
found beneath an unmatched directory. Empty results return WARN with IoErr zero.
GREP continues to search file contents.

Eight iterative frames retain each directory lock, its path-prefix length and
the complete public FileInfoBlock. Descending cannot overwrite the parent's
enumeration key or reserved cookie. The path buffer holds 255 bytes plus NUL.
The ninth frame or an oversized path reports an error rather than skipping a
subtree or truncating a name. All exits release retained locks while preserving
the first enumeration, write, BREAK or cleanup error. Lookup follows existing
DOS path rules; this command adds no path normalization or filesystem snapshot.

The optimized command has 7,851 text bytes and 2,722 upper-RAM BSS bytes,
including the aligned 2,128-byte frame array. Reserved bank-zero growth remains
**0 fixed bytes and 0 per public Task**, including guards, alignment and unused
capacity. Kernel APIs, Task pools and stack reservations are unchanged.

Development checks pass: 24 emitted command cases, 13 existing LIST cases after
updating the controlled enumeration progress counter, the host suite and a
physical-key session. The latter checks depth-first parent resumption, matching
beneath unmatched directories, case folding, relative paths, directory markers,
no-match/empty WARN, file/missing/invalid roots, maximum depth, recovery after a
depth error, help, a FIND-to-WC pipeline and native MyDOS/SDFS subdirectories.
The fixture failures cover path overflow, partial/failed writes, enumeration and
Close errors, causal-error preservation and BREAK before and after enumeration.
Native filesystem images remain byte-identical after ejection. Guards, complete
shell retirement, allocation balance and OS console restoration pass. The pins
and scope match the TAIL development checks; no full release matrix was run.

The demo builder includes both commands in SYS:C. STORY.TXT introduces them;
the earlier preview archives remain the previously built versions.
