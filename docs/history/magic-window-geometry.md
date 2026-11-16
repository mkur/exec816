# MagiC window geometry execution

[Plan](../plans/gem4xe/magic-window-geometry-plan.md) ·
[Design](../plans/gem4xe/magic-window-geometry-design.md) ·
[Inputs and evidence](../development/magic-window-geometry.json)

The user authorized WG0–WG6 on 2026-11-16. MGVIEW alone is the application
acceptance target. This is development testing, without hosted qualification.

WG0 establishes one generated definition of OBJECT, TEDINFO and GRECT, with
MagiC's sixteen frame IDs, the chosen 8×8 character/16×11 box metrics, the
inline frame record and the stable drawing descriptor. Menus use the same
OBJECT as frames and the public C bindings. New geometry helpers cannot become
Task admission entries. The viewer loader and scroll observer require only
MGVIEW; the former Counter APP and process dependency is removed.

The initial gross upper allocation budget is 798 bytes per created window
(306 existing + 492 frame), before removing retired scalar fields. The pointer
table reduces the service from 11,102 to 9,284 bytes. These are record sizes,
not allocator charges. The tree and two TEDINFOs account for 440 of the frame's
492 bytes. No new bank-zero reservation, Task, signal or VRAM reservation is
introduced; fixed, root, kernel, idle and per-public-Task deltas are all zero.

WG0 validation uses `tools/test_gem_geometry.py`: a tiny C/native layout and
argument probe in raw and optimized modes, with stack guards checked by the
existing native harness. This does not build a desktop, application catalog,
QED, Counter, release image or demo.

WG1 allocates each window at a stable upper address, with an inline frame and
text specifications. Six native pointer slots replace the inline windows; slot
scans admit a non-null pointer before access. Close retains storage. Delete
withdraws both lookup entries after existing synchronous physical work and route
retirement, then frees the allocation. Queued manager targets remain identity/
epoch/endpoint records, with no Window pointer or manager-drain wait under UPDATE.

The optimized storage fixture passed 77 checks: hidden/current-empty defaults,
kind links, owned strings, one/two live allocations, allocation failure after
consuming 58 free heap extents, and complete reclamation. The 798-byte window
charges **800 bytes** after allocator rounding; two charge **1,600 bytes**. The
service is **9,284 bytes**. Guards passed. Reserved bank-zero growth is zero
for fixed, root, kernel, idle and each public Task. Rendering and query consumers
still use temporary legacy projections until their planned cutover.

WG2 ports `_wbm_calc`, `_wind_calc` and `_wbm_ssize`. Current, previous, full,
work and shadow geometry live in the window. Layers and query rectangles are
projections. Equal-size moves update the root origin and retain all 360 child
bytes. Admission no longer rounds x/width to even pixels; clipped shadow moves
can use redraw instead of an incompatible copy projection. Full layout uses
the kind minimum and shared borders; the public character/box metrics are
8×8/16×11. The title/both-bar work insets are 1/11/16/11, with info top 21.

The optimized pure-layout fixture passed 4,477 checks, including signed work/
border round trips for all 4,096 supported kind combinations, stored arrow/
track positions, both minimum thumbs, an origin-only move and clipped overall
projection. Guards passed. No reservations changed from WG1. During the cutover,
legacy render/input consumers receive scalar projections from the tree; WG4/WG5
remove them. WG2 also completes the menu object-size constant rename from WG0.

WG3 makes the frame's per-mille values authoritative. Setters clamp to
[-1,1000], return immediately for an equal value, update only the chosen stored
thumb and publish scalar query values without advancing the visibility revision.
`__sslid` preserves MagiC's signed DIVS/ASR behavior, including negative values.
The other axis stays byte-for-byte intact. Slider setters no longer call the
broad geometry publication path or request a manager turn. A small guarded
copied-thumb projection temporarily serves capture until WG5 removes it.

The optimized arithmetic/axis fixture passed 115 checks. A second focused,
headless policy fixture passed 22 checks through real CreateHidden/Frame/Delete
handlers under native UPDATE: empty-current/full defaults, value clamping,
unchanged-setter return, stable visibility revision, pointer-table withdrawal
and complete heap recovery. It reuses the current C provider and the established
12 KiB upper GUI data arena; it starts no application or display session. Guards
passed, with zero implementation bank-zero reservation growth. Physical subtree
and FIRST/NEXT application checks follow with WG4's renderer cutover.

WG4 replaces scalar frame packets with the canonical tree, start object, depth
and clip. Both native exposure and caller setters use the same producer; the
owner and borrower C wrappers select the same GEM4XE traversal/prepared-object
renderer. Trusted frame glyphs retain the platform atlas. The draw request is
20 upper bytes and the shared bitmap packet shrinks from 82 to 78 bytes. The
C renderer adds one 170-byte prepared object and a four-byte bound pointer,
protected by the existing display grant. No ordinary Task packet grows.

Both raw/optimized layout/argument probes pass, including the changed bitmap
packet. The current AES/C application ABI versions are 27/47. Only MGVIEW was
rebuilt as an application. The focused emitted frame fixture passes 33 binding
checks and **293,020 exact pixels** across five checkpoints: full frame and
client preservation, vertical/horizontal subtrees, one obscuring rectangle,
title/info, plus close/reopen/delete. FIRST/NEXT remains valid across nested
slider changes. Passive callback observations are exactly `[9,10,9,10]` for two
vertical setters and `[13,14,13,14]` for two horizontal setters; no generic
frame walk supplies these draws.

The obscured track exposed an existing stipple adapter assumption: screen pitch
was used inside compact scratch. It could overwrite one frame pixel. Stipple
now uses the actual scratch origin and doubled scratch pitch; the same focused
pixel case passes. The native worker stack audit also needed instruction-aware
decoding instead of byte scanning (`b8105e17`); its bound stays 750/1,024 bytes.
No guard or limit was relaxed.

The frame fixture discovers its AES client and retains the original internal
console client. Its three C test bridges reuse compiled provider objects and
the ordinary `__simple_call LONG(ULONG)` boundary. All guards pass; the minimum
observed ordinary floor margin is 231 bytes. Generated bank-zero budgets and
Task pools match WG2 exactly: zero fixed, root, kernel, idle and per-public-Task
reserved-byte changes. These are development checks, not hosted qualification.

WG5 queues generic frame points with the existing retained identity/epoch/
endpoint protocol. Input delivery follows no frame objects and takes no UPDATE.
SCRENMGR resolves the current window under UPDATE, then uses the ported GEM4XE
`ob_find` flow, matching MagiC `_wbm_obfind`. Gadget IDs, thumb and track objects
drive arrow/page/drag interpretation; shared-border hits follow painter order.
The separate capture-side title/gadget calculation and copied thumbs are gone.
Native drag/resize uses canonical bounds and kind minima, without even-pixel
normalization.

The optimized hit fixture passes 25 checks. The focused frame/input fixture
retains all 33 binding checks and 293,020 exact pixels. A retained frame click
puts SCRENMGR in UPDATE's FIFO; while it sleeps, a physical A key advances the
application inbox tail from 0 to 1. Closing the queued target converts it to an
ordered loss/cancellation and releases its endpoint reference before the caller
releases UPDATE or frees/reuses window storage. Guards pass; the minimum floor
margin is 227 bytes. Passive observation counts **zero routing constructions**
for either pair of slider setters.

The window record drops from 798 to 790 bytes (an eight-byte reduction in its
rounded allocation). Each compiled routing publication drops from 662 to 532
upper bytes, saving 260 bytes across the prepared/published pair. The service
pointer table and all bank-zero/Task reservations stay unchanged. No additional
Task, signal, VRAM area or platform service is introduced.

WG6 removes the remaining generic geometry freshness fields, track wrappers,
unused drawing helpers and old inset/gadget constants. `visibilityEpoch` now
describes only the required Layers/query projection. Canonical current geometry
also supplies iconified current queries; the existing private normal-bounds
restore record remains separate. Supported partial kinds no longer require
NAME|CLOSER|MOVER. The native record is **786 bytes**, rounding to **792 bytes**
under Exec's eight-byte allocator; the desktop service remains 9,284 bytes.
The small raw/optimized layout probe now checks every native Window offset as
well as the shared C/native records and drawing arguments.

The final MGVIEW run exposed a creation/display distinction: its full border
starts at x=-1. Following MagiC, create now retains the signed FULLXYWH as
metadata while reserving a hidden layer; physical open/set admission remains
on screen. No Layers policy was broadened. Rechecking AESWIN `ws_curr`,
`wind_open` and `wind_close` also fixes previous/current roles: accepted equal
current requests remember the old current, open initializes previous to the
accepted rectangle, and close clears current/work while preserving previous/full
and the allocated tree. The expanded frame fixture passes **46 binding checks**,
including close/reopen/current/previous/full queries, with the same **293,020
exact frame pixels**, independent key delivery/cancellation and zero slider-only
routing constructions. The hidden policy fixture passes 24 checks, including
the signed creation rectangle and a partial kind.

MGVIEW passes **20 loader/lifetime checks**, three completed Processes and ten
exact viewport comparisons (**916,800 pixels**): document and empty file,
vertical down/up, horizontal right/left, resize, move and both thumb drags.
The viewport starts at `(1,22,616,200)`. Resize accepts `(0,11,505,174)` from
`(0,11,633,222)`; vertical/horizontal drags move the model by six/three cells.
Retirement restores heap baselines and ownership. Coarse held-pointer stimuli
caused a loss/cancellation during the exploratory walkthrough; the observer now
uses isolated, paced physical phases during drags and checks settled coordinates.
The input cancellation policy is unchanged. No other APP is needed.

The first stack observation correctly rejected MGVIEW's former 1,312-byte
declaration: startup touched 1,292 bytes in a small pool, entering its reserved
interrupt headroom. Its APP declaration now requests an **existing 2,560-byte
pool**. This changes admission, not platform reservations. The final walkthrough
observes 1,301 touched bytes for MGVIEW and **1,003 bytes above its ordinary
floor**. All stack/domain guards pass. The frame fixture's minimum ordinary
floor margin is 225 bytes; the unchanged private idle margin is 188 bytes.
The generated bank-zero budget and every Task pool match WG2: **zero additional
fixed, root, kernel, idle or per-public-Task reserved bytes**, including guards,
alignment and unused capacity. No reservation, Task, signal, VRAM region or
specialized platform service was added.

One passive down/up capture uses the current MGVIEW alone, with no builds during
measurement. Each scroll makes two standard slider calls, one selected-axis
calculation, one semantic viewport copy and one exposed text-row draw. The
selected scrollbar rendering and scalar publication are separate from arithmetic.
Inclusive spans below must not be added together.

| Observed cost | Down | Up |
| --- | ---: | ---: |
| Selected-axis calculation, Task CPU | 0.945 ms | 0.929 ms |
| Scalar window-view publication, Task CPU | 0.139 ms | 0.145 ms |
| Selected subtree painting (`AESFRAME.Paint`), inclusive Task CPU | 31.484 ms | 31.350 ms |
| `vro_cpyfm`, inclusive Task CPU | 76.674 ms | 77.276 ms |
| Whole `set_shift`, Task CPU | 162.589 ms | 164.171 ms |
| Whole `set_shift`, off Task | 16.182 ms | 18.754 ms |
| Whole `set_shift`, native interrupts | 35.586 ms | 35.756 ms |
| Whole `set_shift`, elapsed | 214.357 ms | 218.682 ms |
| Complete viewport, PAL polling bracket | 202.230–223.586 ms | 221.362–240.731 ms |

All three native UPDATE attempts per sample succeed without a blocking Obtain.
The input publication helper is entered four times. The focused frame fixture
observes zero routing constructions for slider updates and checks the actual
selected-object visits. At the new odd work edge the semantic copy uses
15 successful `VbxeOwnerCopyRect` completions and 16 balanced display entries/
leaves per scroll; these small units finish without an observed completion IRQ.
The old single-hardware-unit assertion is removed. Exact pixels and physical
completion remain checked. This changed viewport/parity workload and two
frame-polled samples do not establish an overall speedup against earlier captures.
END_UPDATE/cache policy and device drawing limits remain outside this change.

The host suite passes 722 tests with five skips. Generated definitions and local
documentation links pass checks. Only the shared provider, native fixtures and
MGVIEW were built; no Counter, QED, catalog, demo or release matrix ran. These
are development checks, not hosted qualification. Current public geometry
contracts are in [AES reference](../reference/aes.md); captures, hashes and the
per-slice input/stack records are in the linked evidence JSON.
