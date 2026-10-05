# Shell editing and history implementation plan

[Plans](README.md) · [Design](shell-editing-design.md) ·
[Current cooked input](../reference/cooked-console.md)

Status: implemented; [development record](../history/shell-editing.md) and
[machine-readable evidence](../development/shell-editing.json). The design's fixed ten-entry history,
255-character line, control-key editing and Atari cursor aliases are in place. No completion,
search, escape parser, new worker or persistent history.

## E1: line editing and cursor aliases

Extend COOKEDLINE's generated session with a logical cursor, viewport start,
displayed cursor and optional history pointer. Keep the drain position separate.
Insertion and Backspace shift bounded suffixes; Ctrl-A/E/B/F/U/K/W implement the
specified moves/deletions. Preserve Return, EOF, BREAK, overflow and loss rules.
Use the existing 128-byte echo buffer for bounded redraw; retain cheap appends.
Reset cursor/viewport state at line retirement and cancellation. Translate Atari
Ctrl-+/Ctrl-*/Ctrl--/Ctrl-= to Ctrl-B/F/P/N in CONSOLEINPUT, preserving punctuation.

Extend the emitted cooked fixture and its independent text/screen oracle:
start/middle/end edits, no-ops, narrow/36/37/255-byte views, shrinking suffixes,
width changes, cursor-independent submission, EOF, quarantine and echo bounds.
Run raw and optimized variants; validate the four scan aliases independently.

## E2: optional history and shell integration

Generate the 2,824-byte history record: ten 256-byte slots, a 256-byte draft and
eight control bytes. Allocate once on first enable, retain across disable, free
on final cooked-session release. Keep browsing copies independent of slots;
restore the draft and cursor after the newest entry. Save valid Return submissions
once, skip blank and consecutive duplicate entries, and never save a discarded
line. Reset browsing on Return, EOF, loss and cancellation.

Add checked native `DOS.SetConsoleHistory(handle, enabled)` using existing
caller-owned handle validation and the cooked session's busy lease. Reject
non-CON and stale handles, preserve pending line/drain/EOF/discard state, and
release the lease on allocation failure. Record the native DOS ABI addition;
no new kernel selector or loaded COMMAND provider is required.

Use reserved ShellState storage for history availability. Enable once per prompt,
keep enabled through partial reads, disable before any parse/dispatch and on
read errors/EOF. On initial allocation failure retain editing and disable history
for that shell session. Preserve primary/secondary command results around prompt
configuration and cleanup.

Cover ring wrap, duplicate/blank submissions, draft restoration, edits to recall,
small drains, enabled/disabled recording, two sessions, shared reference cleanup,
busy rejection and allocation failure through emitted code. Exercise the public
operation on real handles, including inherited CON input with history disabled.

## E3: integrated shell, docs and demo

Update HELP, shell/cooked/RAW contracts and demo instructions. Extend the physical
shell/demo editing checks with control letters and actual Atari cursor chords,
recalled pipelines, long lines, draft restoration, BREAK and EOF. Check both
logical cells and physical caret, ownership/heap recovery and OS restoration.
Run the host suite and changed generators. Rebuild with the pinned compiler,
ROM and paced emulator through `tools/build_demo.py`, retaining OF816's five-second
standard shell/prime autoboot, all commands and both disks. Verify the final ZIP
contains only distributables and its checksums match.

Record source/artifact hashes, selected test scope, stack observations and actual
code/data costs in a development record. Update the plan/index status and commit
the completed changes. Development checks do not qualify a release or hardware.

## Budget and validation discipline

Target zero additional fixed or per-Task bank-zero reservations, including
guards, alignment and unused capacity. Keep stack/DP pools and provider capacity.
The proposed cooked payload grows 402 → 410 bytes (408 → 416 rounded); optional
history costs 2,824 upper-RAM bytes. One enabled shell therefore adds 2,832 bytes.
Measure actual layouts and resident code size against the writable-command demo.

Use focused development checks, not a release matrix. Reuse an unchanged build
only when its relevant inputs match. The first two slices use raw/optimized
emitted tests; the physical session uses the pinned optimized system and the
packaged demo. Keep all intermediates and results in `build/shell-editing/`.
