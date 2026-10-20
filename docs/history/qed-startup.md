# QED application startup implementation

[Startup design](../plans/gem4xe/qed-startup-design.md) ·
[QS1–QS5 plan](../plans/gem4xe/qed-startup-implementation-plan.md) ·
[Native foundation](qed-native-feasibility.md)

## QS1 Resource ownership

The generator adapts the pinned English RSC to ten trees, 185 objects, 24
TEDINFO records, 44 free strings and a 30-object menu in 10,500 bytes. It
preserves non-menu local indices, generates matching identifiers and removes
discarded menu references. Pointer/3D/image decorations are flattened; deferred
Find controls are disabled. No upstream cache or historical QF record changes.

General resources admit sixteen trees and 64 objects per tree, retaining the
256-object total and independent 33-object menu ceiling. Form and popup saved
state each grow by 64 upper-memory bytes; the resource owner grows 16 → 22
bytes, so QED's loaded resource owner totals 10,522 bytes before allocator
rounding. Traversal remains iterative, depth eight. The separate hosted widget
packet retains its existing 32-object capacity.

R_STRING returns the actual free string; R_FRSTR returns its relocated pointer
slot. Admission checks extents and termination once. Failed replacement keeps
the previous resource. The emitted resource probe checks every tree/string,
both named/AESPB access, writable TED backing, menu installation/withdrawal,
malformed free-table/tree rejection, bounds and repeated ownership cleanup.

The [QS1 development record](../development/qed-startup-qs1.json) identifies
two optimized and two raw loaded Process cycles. Both modes pass the resource
and emitted-layout boundary; the raw cases reuse the unchanged optimized native
provider. Observed minima are recorded separately per mode. The host suite
passes 529 tests with four expected historical-source skips; complete selected
source compilation/link, generator and content/local-link checks also pass.
The provider uses 178,654 code bytes (+598 from QF6), unchanged 40,145 table
bytes and 25,739 data/BSS bytes. The generated resource reproduces the tested
bytes after deriving menu height from the desktop's machine-readable contract.

Reserved bank-zero delta: **0 fixed, 0 per-public-Task, 0 private idle bytes**,
including guards, alignment and unused reserved capacity. The pool and region
maps exactly match QF5; the generic runner's older compaction comparison is not
this slice's immediate reservation delta. These are development checks; actual
QED startup and editor qualification remain later gates.

## QS2 Fixed-font source and input boundary

The retained QED output module uses an 81-byte private visible-cell buffer,
the built-in 8×8 font and explicit baseline conversion. Empty rows and text
use clipped public v_bar/v_gtext calls. Cursor visibility is published before
redrawing its row; scrolling and line shifts redraw from actual text storage.
Proportional/italic/XOR/raster paths and block drag/drop are removed. Flat
resource frame calculations and public menu_popup replace the donor capability
fallback. The native presenter keeps pointer ownership; donor shape/hide
requests do not enter the link.

The ordinary graf_mkstate named/AESPB snapshot is imported by current C APP
ABI 25. Its four-word snapshot needs no persistent reservation. The input
regression checks known coordinates and both interfaces, then proves that
queued key/button records and wait interest survive the query and are consumed
by the subsequent ordinary wait. Small raw/optimized loaded probes exercise
the new import/calling boundary. The emitted renderer probe records calls from
the actual adapted output module and checks tabs, viewport bounds, baseline
conversion, empty text and empty rows. Its callbacks are fixture-only; actual
native QED pixels belong to QS3.

Every former analysis binding has an explicit disposition. The complete
selected-source link contains no analysis trap; the analysis marker still
prevents executable packaging until QS3. Editing/selection rendering, dialogs
and saved-file behavior retain the later strategy gates. Matched application
rebuilds and exact-package smokes complete in QS5.

Reserved bank-zero delta: **0 fixed, 0 per-public-Task, 0 private idle bytes**,
including guards, alignment and unused reserved capacity. The actual costs and
executions are identified in the [QS2 record](../development/qed-startup-qs2.json).
