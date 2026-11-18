# MGEDIT migration record

[Migration plan](../plans/gem4xe/mgedit-migration-plan.md) ·
[Port audit](mgedit-port-audit.md) ·
[Native edit-object contract](../reference/aes.md#multiline-edit-objects)

## ME0 — Source selection

Verified 26 pinned Atari MagiC files and the upstream GPLv3 licence. The host
preparation keeps the original resource bytes and writes normalized copies of
Pure C sources, project files and the 68000 line-scan reference. The edit
object operation map is recorded with the source selection.
[Port source](../../ports/magic/mgedit/README.md)

## ME1 — One loaded multiline object

The C816 AES provider owns `XEDITINFO` records through each caller's
registration. A native object tree holds the `G_EDIT` state pointer and the APP
retains its writable buffer. AES draws the object in the existing clipped
window-and-display path. No 68000 library startup or dynamic binding is needed.

The optimized development fixture loads `EDITOBJ.APP` twice on pinned Altirra.
It checks an unterminated buffer refusal, fixed-face text with tabs and mixed
line separators, clipping by an overlapping window, close/reopen, and
automatic retirement of an outstanding editor. Twelve native checks and six
pixel comparisons passed with intact guards and equal free memory after both
collections. The 12,567-byte APP uses ABI 49. The fixture's C provider has
218,496 initialized bytes and 18,871 zero-fill bytes.

Editor state uses 24 upper bytes plus eight per visible text row. The AES
context grows from 442 to 446 live bytes and still rounds to 448 reserved
bytes. The 2,560-byte APP pool had at least 1,199 bytes above its measured
watermark and interrupt floor. Fixed, root, kernel, idle and per-public-Task
reserved bank-zero deltas were zero.

Run `python3 tools/test_mgedit_object.py --output build/mgedit/me1` for the
focused fixture at ME1's revision.

## ME2 — Keyboard editing, caret and selection

The editor consumes key records under caller-owned UPDATE. It keeps the
MagiC CRLF insertion convention and treats each parsed line separator as a
unit for movement and deletion. The capacity check precedes an overlapping
suffix move, so a refused insertion preserves the prior edit state. Visible
text is painted before applying caret or selection XOR through the existing
display-owned fill path. Caret-only movement repaints its affected rows.

Two optimized loaded lifetimes passed typing, split/join, Delete, dirty
state, capacity refusal and nested caret hide/show. Ten pixel comparisons
covered both caret X parities, selection behind an overlapping window,
exposure repair and reopening. The fixture supplies synthetic GEM key
records to isolate the editor. Twelve native lifecycle checks passed with
intact guards. Raw and optimized layout probes agreed on a 64-byte event,
with the key at offset 10 and the message array at offset 32.

ABI 50 builds the fixture at 14,067 bytes. The fixture's provider contains
225,578 initialized bytes and 18,871 zero-fill bytes. Editor state uses
54 live upper bytes, rounded to 56, plus 12 bytes per visible row before
rounding. AES registration storage stays at its ME1 size. The APP pool kept
at least 1,175 bytes above the measured watermark and interrupt floor.
Fixed, root, kernel, idle and per-public-Task reserved bank-zero deltas were
zero.

Run `python3 tools/test_mgedit_object.py --output build/mgedit/me2` for the
current focused check. It builds the matching provider and test APP.
