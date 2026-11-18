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
focused check. This fixture builds only the native provider and test APP.
