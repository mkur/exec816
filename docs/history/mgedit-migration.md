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
ME2 fixture at its revision.

## ME3a — Scroll and resize

The edit object now reports its scroll metrics, retains the first visible
line and applies absolute line and pixel offsets. It clips each copy to source
and destination pixels in one visible rectangle. The existing GEM raster copy
handles aligned and odd pixel displacements. The newly exposed strip is drawn
through the object dispatch. Page-sized shifts redraw their viewport. Resize
allocates replacement visible-row storage before releasing the old storage.

The first development build exposed an incorrect Calypsi stack read when
constructing the points array from earlier array entries. The corrected
construction derives all eight points from the rectangle. The emitted listing
and independent pixel comparison verified the correction.

The optimized loaded fixture passed 20 pixel comparisons and 12 lifecycle
checks across two loads. It covered line and page movement, repeated
horizontal movement in both directions including odd offsets, and resize.
The fixture's APP is 16,129 bytes at ABI 51. The provider is 230,941
initialized bytes plus 18,871 zero-fill bytes. The 70-byte editor state
rounds to 72 upper bytes, with 12 bytes per visible row before rounding.
Reserved bank-zero bytes stayed unchanged, guards were intact, and the APP
pool retained 1,167 bytes above its observed watermark and interrupt floor.

## ME3b — Pointer selection and drag autoscroll

The caller passes the captured press to `edit_evnt` under UPDATE. The edit
object places the caret or changes the selection, then waits for release,
movement and the autoscroll timer in MagiC's event order. It repaints affected
rows and uses the ME3a copy and exposed-strip path to scroll. Each DISPLAY
borrow ends before the next wait. A lost input record restores the viewport,
caret and selection from drag entry and returns the diagnostic.

The optimized Altirra fixture passed physical drag, autoscroll and release,
then repeated capture in the same boot. The peer timer advanced 20 and 17
ticks during the two drags. After the first release, the fixture held UPDATE
until uncaptured motion queued SCRENMGR on the native semaphore. A physical
key arrived in the editor inbox during that wait. A second run injected
button input loss during a physical drag. The viewport and selection returned
to their entry state, with 20 peer ticks observed during the hold. Each run
passed 20 pixel comparisons and 16 native lifecycle checks with intact guards.

The editor fixture APP is 17,064 bytes and the peer is 11,069 bytes. The
provider has 234,967 initialized bytes and 18,871 zero-fill bytes. The editor
stack retained at least 1,097 bytes above the measured watermark and
interrupt floor.

The production editor state and AES registration keep their ME3a sizes and
APP ABI 51. Reserved bank-zero growth is zero for fixed, root, kernel, idle
and per-public-Task storage. The fixture uses the existing 12-Task profile
for the additional loaded peer. Compared with ME3a's 8-Task fixture this
reserves 7,648 more bank-zero bytes, including direct pages and stack guards
for three 1,600-byte slots and one 2,848-byte slot.

Run `python3 tools/test_mgedit_object.py --output build/mgedit/me3b` to build
and exercise the physical release case, then run the same command with
`--reuse --loss` to inject a dropped button record during the drag.

## ME4 — Named documents

The native patch builds the named-document code from the pinned `MGEDIT.C`
and `MGEDWIND.C`. Startup opens APP arguments through GEMDOS, the editor
maintains each document's `G_EDIT` and window, and the donor's Ctrl+S, Ctrl+U
and Ctrl+Q branches remain available before its menu is ported. Keyboard,
mouse and window messages use their delivered window identities.

The document reserves its file length plus 65,536 bytes through public
`AllocMem` with `MEMF_LINEAR`. The reserve includes the terminator. Load
requires the complete size observed by FSTAT, a successful close and a
document with no embedded NUL. A full write and successful close are both
required to clear the dirty flag. Save retains MagiC's create/truncate
sequence. On a failed write, the live buffer remains available for retry.
Explicit document close, cooperative stop and application return free the
linear allocation. Abrupt Task retirement still has no general raw-allocation
reclamation service.

MagiC holds its recursive UPDATE through its modified-close alert. The
approved Exec mapping keeps the document live and calls `form_alert` outside
UPDATE/MCTRL. Save and teardown then enter UPDATE. The native form borrows the
editor window. The port keeps user-requested sizes at or above 248×104 outer
pixels to leave room for the three-button prompt with the system face.

The optimized loaded scenario opened two editor documents beside MGVIEW.
Physical input cancelled with Escape and exercised Save and Discard choices.
Reopening found the saved edit in memory. Independent ATR decoding matched
all 70,001 edited bytes and the untouched second file, including mixed line
endings and high bytes. A second run verified 312 exposure pixels after
switching from MGVIEW and injected a one-byte short write. The document
stayed dirty and open, and the next Save and reopen matched the expected
bytes. Each run passed 16 native lifecycle checks with intact guards and
equal free memory after both editor lifetimes. The C816
provider and APP ABI 51 are unchanged. `program.app` is 22,302 bytes with
the existing 2,560-byte minimum stack pool. That pool kept at least 837 bytes
above its measured watermark and interrupt floor in the coexistence fixture.

Each document adds a 267-byte window record with the 16-byte C runtime prefix
rounded to 288 bytes. The linear allocation rounds up to an eight-byte
boundary. The shared editor state retains the ME3 allocation sizes. Fixed,
root, kernel, idle and per-public-Task reserved bank-zero deltas are zero.
The fixture reuses ME3b's 12-Task configuration.

Run `python3 tools/test_mgedit_document.py --output build/mgedit/me4` for the
focused coexistence fixture. Add `--reuse --short-save` to relink the editor
with the test-only short-write injection and exercise the smaller document.
