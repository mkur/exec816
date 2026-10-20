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

## QS3 Actual executable startup

Executable mode packs the complete retained graph as an ordinary C APP,
without an analysis marker or trap. The default analysis artifact still rejects
packing. Every legal-base relink passes; minimum-stack metadata remains 2,560
bytes. Required resource pointers and free strings are checked before publishing
the menu. Startup uses the supported native window flags and marks a window
open only after successful admission. CFLIB owns one workstation; QED borrows it.

The donor poller's negated-double-click/both-button request was outside the
native contract. All retained main-loop polls now request supported double
left-down events. Native normalized Ctrl letters reach menu shortcuts before
ordinary text insertion; shortcut captions retain the donor parser's required
trailing position. Termination breaks immediately after the final event rather
than entering another idle wait after deleting the last window. A focused
emitted poller regression complements the physical event checks.

The loaded complete QED opens its actual Untitled document, installs the
30-object menu, selects the built-in 8×8 font and paints its native work area.
The pixel assertion checks the empty document's background, excluding the
dynamic caret and presenter pointer. Physical Close, Ctrl+Q and another Close
each return normally through collection and unload. Later cycles restore exact
upper-memory availability. Snapshots include the actual resource/window pointers
and private heap totals; they are observations, not a replacement editor.

The [QS3 development record](../development/qed-startup-qs3.json) identifies
artifacts, costs, pixel counts and emitted drawing entries. The passive observer
selects the third launch's physical pool and Process lifetime through retirement.
Native IRQ/NMI, direct-page ownership, guards and normal OS return are checked.
These are startup development checks; failure/Stop closure and the current full
source-frame ledger follow in QS4. Editing, dialogs and Save remain later gates.

Reserved bank-zero delta: **0 fixed, 0 per-public-Task, 0 private idle bytes**,
including guards, alignment and unused reserved capacity. Pool and region maps
exactly match QS2. Resource owner and form/popup storage retain QS1 costs.

The QS3 APP occupies 138,608 code, 1,300 initialized and 26,648 BSS bytes;
its 155,084-byte container spans 269,680 image bytes and requests up to
335,216 alignment-backing bytes. The observed private heap owns four blocks,
53,303 payload / 53,351 backing bytes. The selected launch retains 1,691
ordinary-sample and 1,708 after-reservation bytes above the interrupt floor
(asynchronous minimum 1,609). The source-frame bound remains conditional
until QS4 reconciles the changed graph.

## QS4 Failure, Stop and stack closure

Startup alerts are deferred until the first document is ready. An acquisition
failure returns primary 20 and preserves its native cause through retirement;
private backing allocation failure records ERROR_NO_FREE_STORE. Failed window-open
rollback preserves the cause before deleting its partial document. Deferred
closing-position history publication is removed, avoiding an allocation and
default-directory query during retirement. This also
avoids entering a modal alert while window/document acquisition is incomplete.

The development failure APP forwards successful public requests and refuses
one selected application acquisition boundary. It covers QED's AES init call,
workstation, resource, menu and native window create/open calls, plus actual
missing/malformed resource loads and persistent refusal from each of the first
four private allocations. Its first/final normal launches use public RequestStop.
The AES-init case follows the native Process provider's registration; it tests
QED's unwind, with lower provider setup failure owned by existing native tests.
No production test mode or kernel protocol is introduced.

The failure cohort copies the unchanged APP from SYS: to RAM: with public
DOS Read/Write, then uses ordinary RAM-file load/start/wait/unload for each
case. Resource reads remain on SYS:. The separate production cohort repeats
actual disk APP loads. After retirement, fixture
observations require no private heap blocks, resource/menu/window owners or
resident AES context. The supervisor requires idle native service, released
image execution ownership, the expected primary/secondary result and exact
memory recovery. A separate unchanged-production-body cohort exercises physical
Close, Ctrl+Q, repeated Close and cooperative Stop.

The passive observer captures each failure/Stop lifetime with physical stack
pool, Process identity and direct-page attribution. The emitted source ledger
accepts the current executable as well as the independent analysis image.
Its typed callback catalog and finite action contexts still reject new indirect
sites and unbounded cycles. The [QS4 record](../development/qed-startup-qs4.json)
separates the conservative source bound, observed full chains and conditional
continuation allowance. Future editing, dialog and file workflows must establish
their own continuation evidence. Native IRQ/NMI, guards and OS return remain
part of the executed development checks.

Reserved bank-zero delta: **0 fixed, 0 per-public-Task, 0 private idle bytes**,
including guards, alignment and unused capacity. The startup flag adds two
initialized private-image bytes; resident storage is unchanged. Fixture control
words and failure wrappers are absent from the production APP.

QS4 completes four production disk-launch cycles and fourteen failure/reuse
cycles. Minimum ordinary headroom is 1,691 production / 1,687 failure-fixture
bytes above the interrupt floor; full observed ordinary chains use 613 / 617
bytes. The 1,165-byte conservative source bound plus the separate 768-byte
continuation cap, 256-byte interrupt reserve and 128-byte headroom leaves
243 bytes in the declared pool. All fourteen failure-fixture lifetimes retain
identity/DP attribution. These observations do not qualify future editing or
Save chains. Host checks pass 529 tests with four expected skips.
