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
