# FastBasic editor incremental refresh

[Current contract](../reference/fastbasic-workbench.md) ·
[Design](../plans/fastbasic-editor-refresh-design.md) ·
[ER0–ER4 plan](../plans/fastbasic-editor-refresh-implementation-plan.md) ·
[Machine-readable evidence](../development/fastbasic-editor-refresh.json)

The native `BASIC.APP` painter now retains character and attribute cells,
compares nominated rows and draws changed spans using opaque text. Caret and
selection marks participate in comparison; the status strip has independent
damage. Repeated status messages and settled idle need no drawing. A normal
fully visible edit completes in one UPDATE, without a preceding empty update.

Deferred or covered changes publish once before waiting. Forced exposure repair
bypasses cache equality, and pending spans survive newer input. Each turn composes
at most four rows, reconstructs at most 96 glyph cells across fragments and fills
at most eight margin fragments. The painter uses public AES/VDI visibility and
completion interfaces and releases UPDATE between quanta and paint-journal
rollovers. No console internals or new kernel services are required.

Caret-only changes reuse cached source text and syntax colours. Source edits
invalidate nominated base rows; full-view nominations also handle fold-map
changes. Procedure indexing clears fold bits and resets its active count rather
than clearing every unused entry after each keystroke. Entries initialize their
bounds and terminated names before publication. Single-line deletion nominates
its affected row; replacement spanning several rows retains the complete old
range even when its newline count stays unchanged. Base-row recomposition
preserves the previous appearance for comparison; it does not force pixel damage.

## Memory and execution scope

The retained reservation is **5,120 upper-RAM bytes per application**, including
unused capacity. The emitted private structure occupies 5,112 bytes; the editor
model grows from 1,664 to 6,784 bytes. The loadable image span grows from 91,133
to 96,253 bytes, or 91,136 to 96,256 after eight-byte allocator rounding. Code
uses previously reserved image space below its existing data-bank boundary.
The declared C stack minimum remains 1,312 bytes.

Additional reserved bank-zero bytes are **0 fixed, 0 root/kernel, 0 per each of
the twelve public Tasks, and 0 idle**, counting guards, alignment and spare
capacity. No new Task, timer or signal is introduced. Interpreter sessions,
file transactions and Check/Run/Stop/Build retain their current contracts.

## Development checks

This is development evidence, not release or physical-hardware qualification.
The evidence record identifies actual emitted sources, application/package
hashes, machine settings and observer hashes. Build and test output stays under
`build/fastbasic-refresh/` and outside the demo ZIP.

The optimized painter probe compares real editor output with an independently
reconstructed pixel model. It covers append/delete, tabs, keyword
recolouring, selection, Undo/Redo, horizontal pan, resize during pending work,
folding, status tails and saved markers, identical/partial exposure, ten visible
fragments, newer edits during repair, hidden publication/idle, drawing and
UPDATE/visibility failures, bounded completion and ownership. The assistance
probe adds a reused-entry regression after a full procedure table.

Measurements use the pinned AltirraOS 3.44 65816 ROM, 800XL/PAL, 8× clock,
63 high banks, shadow ROM and VBXE. Each sample starts with a physical key offer
and ends at the first independently matching completed scanout. PAL-frame
polling makes these upper-bound observations, not application-only CPU timings.
The original and updated packages use byte-identical native kernel, OF816 core
and wrapped boot XEX. A verified pre-native boot snapshot avoids repeatedly
loading those same bytes; it does not substitute a different application.

Twelve samples per operation use the same observer and key sequence for the
frozen baseline and final application:

| Operation | Baseline median / p95 | Updated median / p95 |
| --- | ---: | ---: |
| Append | 160.4 / 160.4 ms | 80.2 / 100.3 ms |
| Vertical caret movement | 120.3 / 140.4 ms | 100.3 / 100.3 ms |

After the initial saved-state marker change, append and caret samples each
reconstruct two cells, draw no status glyphs and need no empty publication.
The scripted pointer-motion/settling case remains 441.2 ms in both packages;
it includes travel and three settling frames and is not a busy-pointer latency
percentile. Settled idle produces no paint turns during the 20-frame observation.

The maximum-document stress case caught a conservative Backspace nomination:
a one-line deletion marked the entire viewport. It reconstructed 1,120 cells
and took 140 PAL frames in that fixture, exceeding its unchanged 120-frame
bound. The correction narrows affected source rows, and the emitted probe now
checks both single-line deletion and multi-row replacement with an unchanged
line count. The physical fixture also waits for consumed mouse button edges,
matching the other desktop fixtures, before offering the next edge.

The corrected maximum-gap edit completes in **33 PAL frames (660 ms)** with
63 peer advances, below the unchanged 120-frame ceiling. The physical fixture
passes 28 native assertions and 11 independent scanout cases, including mouse
selection/replacement, Undo/Redo, keyboard menus, focus/cover/exposure, horizontal
panning, partial-row/minimum resize, relaunch and maximum-size restoration.
The emitted painter passes 66 checks, logical editing 30, file control 103 and
assistance 512. All 643 host checks pass.

The exact final ZIP also passes the loaded twelve-Task session: two shells and
BASIC coexist with a ten-Task pipeline peak; floating-point Run/Stop uses nine.
The same interpreter Process retains variables, arrays and strings across edits,
parse errors and Stop. Restart clears state, mode change replaces the engine,
output close cancels input, Check preserves the idle interpreter, and canceled
Quit preserves state before final Discard/cleanup. Guards and ownership checks
pass. Across the loaded desktop cases, the smallest observed public Task stack
headroom above its floor is 191 bytes; the eight-Task physical fixture leaves
362 bytes in its smallest pool. These are observed cases, not worst-case proofs.

## Delivery

`build/fastbasic-refresh/demo-final/exec816-demo.zip` is the refreshed package;
its local launcher is `build/fastbasic-refresh/demo-final/launch-altirra.command`.
The repository-root ZIP and FujiNet SD installation receive those exact bytes.
The installer compares writable media with the previous template before replacing
it and preserves changed media by choosing a fresh installation directory.

The independent package audit checks all ZIP checksums and CRCs, 25 notices under
`licenses/`, the 78 extracted system files, the updated `C/BASIC.APP`, MD5/ARC/EDX
and ARC overlays, and exact ATASCII `WORK:SINE.BAS`. The native kernel, core and
wrapped OF816 XEX, and separate QED ATR remain byte-identical. OF816's five-second
autoboot is retained. Matching FastBasic working-source and QED source/relink
companions remain outside the small boot ZIP, with their own checksums.

This scope does not rerun the release placement/concurrency/fault matrices or
qualify physical FujiNet hardware, ROM variants or fonts other than the pinned
8×8 face.
