# Application menu bars

[History](README.md) · [Design](../plans/gem4xe/application-menu-bar-design.md) ·
[Implementation plan](../plans/gem4xe/application-menu-bar-implementation-plan.md)

## AM1 — Registration and withdrawal

Implemented on the `7492958` baseline. AES wire version 10 keeps the 112-byte
request and sixteen ordinary records. The GUI record grows from 36 to 40 bytes;
the private C context grows from 288 to 308 bytes. Registration retains a caller's
OBJECT tree through the existing Task lease and allocates a 336-byte association
record per installed menu in upper memory. No tree or strings are copied.

Install/replace admits supported shape and geometry once. Failed replacement
preserves the previous registration. Mutations and withdrawal wait for the
existing native paint boundary, including under the caller's UPDATE/MCTRL.
Closing a window keeps installation; application exit withdraws before releasing
caller storage. Private transport is present; public `menu_bar` awaits AM4.

Development checks: 137 optimized menu assertions, two simultaneous owners,
pre-open installation, owner locks, replacement/geometry failures, hide/reopen,
generation exhaustion, poisoned retired storage and heap return. Both raw and
optimized context/layout probes passed, including bank-crossing request access,
register/DP restoration and opposite bridge stack parities. Host suite: 417 tests,
four historical skips. [Evidence](../development/application-menu-bars-am1.json).
The menu fixture's presenter stack peak was 700 bytes, leaving 1604 bytes above
the interrupt reserve. No complete desktop/package or hardware claim yet.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 private idle**. This
includes guards, alignment and spare reservation. Further integrated code/data,
manifest and cartridge accounting belongs to AM3/AM6.

## AM2 — Durable commands

The existing GUI record carries `MN_SELECTED` and a separate menu generation.
One accepted command remains reserved until consumption and title normalization,
in either order. The sixteen ordinary records remain available. Window notices
and menu selections share the existing bounded pending-kind order. Queue edits
and record reservation/population are short Task-side guarded transitions;
publication still transfers immutable storage through the receiving port.

Trusted GUI and popup-deferred messages are filtered by window/menu lifetime.
Ordinary messages with identical public words remain opaque. The event decision
keeps its selected queue head across timer retirement; stale withdrawal triggers
a fresh decision at the same deadline. Retired records cannot acknowledge a new
menu command.

Development evidence: 229 menu, 101 existing GUI and 371 event/timer assertions;
417 host tests with four historical skips. Tests include both acknowledgment
orders, delayed/duplicate selections, interleaved redraw, full ordinary pools,
replacement, stale recycling, deferred selection and close/reopen. Selection
injection is generated only into the fixture's presenter module.
[Evidence](../development/application-menu-bars-am2.json).

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 private idle**. The
fifth pending GUI kind adds 8 upper bytes per client (32 per AES Service).
Wire/context sizes remain as recorded in AM1. Physical interaction and the
packaged coexistence walkthrough remain AM3–AM6 work.

## AM3 — Presenter drawing

Application-owned menu trees now supply the active bar and variable-sized popup.
The native presenter binding reuses the extracted object renderer with its own
GSX scratch, full-address string specs, 16-scanline strips, at most one visible
object and eight examined objects per quantum, and 96-pixel text fragments.
Scratch strips publish only when complete. State/text updates invalidate source
object bounds; focus/install changes redraw the bar. The existing popup layer
is recreated in its freed slot when dimensions change. Windows gains Next/Close
when an application menu occupies the left side.

`wind_get(0,WF_WXYWH)` reports `(0,16,640,224)`. Window dimensions and application
object clipping retain their existing behavior. The window gesture fixture now
clicks the exposed title below the persistent menu bar, instead of its covered
part.

Development checks: 244 menu assertions and seven independent pixel phases,
including a compiled menu, a differently sized RSC menu in another Task, focus
switch/restoration, disabled/text patches, withdrawal, poisoned storage and RSC
free. Raw/optimized probes verify context offsets, native geometry-array layout,
and bridge context. Also passed 176 window, 41 object and 328 native desktop
checks, plus the host suite (417 tests; four historical skips).
[Evidence](../development/application-menu-bars-am3.json).

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 private idle**. The
optional menu record is 340 bytes, rounded to 344; desktop global reservation
grows by 256 upper bytes to 5120 (4910 used in the early composed build).
The early OF816 package builds with 64/64 manifest extents and a 1,018,192-byte
XEX. Its 13,999-byte uncompressed cartridge headroom is informational: the user
has explicitly removed cartridge size as a gate and plans compression separately.
The loading/manifest limits still apply. Full packaged runtime testing remains
AM6 work.
