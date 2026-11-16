# Implement MagiC window geometry for MGVIEW

[Design note](magic-window-geometry-design.md) · [GEM plans](README.md) ·
[Port guidance](../../contributing/README.md#gem-architecture-guidance) ·
[Development testing](../../contributing/testing.md)

Status: implementation authorized, 2026-11-16. Progress and emitted evidence are
recorded in [the execution record](../../history/magic-window-geometry.md).
MGVIEW is the sole application acceptance target. Other applications and their
private bindings may break; they are not regression gates. This plan proposes
adopting the design's frame tree, selected-object drawing and SCRENMGR frame-hit
boundary together. Preparing the plan does not change the runtime contract or
approve an additional architectural departure.

## Outcome and fixed boundaries

Port MagiC's window/frame geometry, using its pinned source routines as the
implementation outline. A slider setter updates one axis from an existing
track; frame drawing and hit-testing consume the same tree. Creation/resize
owns full layout, while an origin-only move retains relative child geometry.
Keep MGVIEW's ordinary size-then-position GEM calls.

Use current Exec allocation, recursive UPDATE, signals, retained input delivery
and display grants. Preserve normal Task preemption and IRQ/NMI protocols.
There is no additional Task, scene gate, private kernel operation or specialized
platform service. A demonstrated missing general service must be reported under
the governing guidance. END_UPDATE cache policy remains separate: this plan
does not claim to remove the measured full-window recapture cost.

Keep one current implementation and ABI. A commit is executable when its
focused emitted-code fixture passes; MGVIEW need not work between every internal
cutover. Update compiled callers together. Do not keep a working legacy GUI as
an alternate profile or return successful placeholders for unported behavior.
Use compiler/ABI inputs from [actionc.json](../../../toolchain/actionc.json)
and record any local override explicitly.

## Concrete choices for adoption

These choices make the design reviewable before implementation. They are
proposals in this plan, not new claims about MagiC or platform necessity.

| Area | Proposed implementation |
| --- | --- |
| Window storage | Follow MagiC's allocation per created window: one upper-heap window record with an inline 16-object tree and two text specifications. Replace the six inline desktop window records with a bounded table of native pointers. Close retains the record; delete retires and frees it. |
| Object format | Promote the existing 24-byte `MenuObject` shape to a shared GEM object definition, used by frames and existing object/menu consumers. Keep 32-bit `ob_spec` values; explicitly bridge native three-byte and C huge four-byte pointers. |
| Authority | The window owns GEM `GRECT` current/previous/full/work/overall values, per-mille values and frame objects. Layers half-open rectangles and application query views are projections. No second layout algorithm writes those projections. |
| Profile metrics | Keep the selected 640×240 mode and 8×8 text font. Propose a 16×11 device frame box, matching the current gadget cell; return character 8×8 and box 16×11 from `graf_handle`. Apply MagiC's formulas to those parameters, with default info-object height 11. |
| Frame input | Input delivery queues retained target identities and coordinates. SCRENMGR, under UPDATE, uses current frame objects to interpret the click. Remove capture-side thumb classification. |
| Rendering | Use frame-visible clips and an actual start object. Reuse GEM4XE object primitives and trusted built-in gadget raster code through the established owner/borrower display paths. |

The metrics choice resolves an existing mismatch: `ExecAESGrafHandle` currently
returns 8 for all four outputs, while frame code uses 16×11 cells. This is an
explicit Exec device-profile proposal, not a derivation of those numbers from
the Atari MagiC driver. If a different profile is selected, change the shared
metric inputs before WG2; do not compensate inside slider or hit-test code.

Use MagiC's one-pixel base frame margins and shared-border formulas, replacing
Exec's independent left/right/bottom padding and fixed eight-pixel thumb
minimum. With the proposed metrics, a titled window with both scrollbars has
work insets left/top/right/bottom **1/11/16/11**; adding the default info object
makes top 21. Minimum thumbs follow the selected axis's box extent, limited by
track length. These examples must be independently checked against the pinned
formulas, not used as a new hardcoded layout.

This creates odd work-area X coordinates. Geometry must not round the work area
back to even pixels to satisfy a copy optimization. Remove even-X/width
normalization from window geometry; use the driver's existing packed-edge path
or normal redraw fallback. The existing on-screen window-admission profile is a
proposed temporary scope limit, not MagiC parity. Pure layout uses signed GEM
coordinates; full off-screen window admission remains outside acceptance unless
MGVIEW requires it. Report that requirement before broadening Layers policy.
Clip the overall/shadow projection to the screen without altering canonical
window geometry; a clipped move can take the redraw fallback.

## Source and module map

Keep the [design's pinned MagiC/GEM4XE sources](magic-window-geometry-design.md#source-baseline).
Use AESWIN `_wbm_create`, `_wbm_skind`, `_wbm_ssize`, `_wbm_calc`, `_wind_calc`,
`__sslid`, `_wbm_sslid`, `ws_slide`, `wind_draw`, `objc_wdraw` and `_wbm_obfind`.
Port their object relationships and signed integer rules, including normalization
to [-1,1000], special size -1 and negative/halfway rounding. Use existing
compiler/runtime wide arithmetic rather than translating 68000 instructions
literally or adding a new arithmetic service.

| Current code | Planned change |
| --- | --- |
| `abi/aes-server.json`, `generate_aes_server.py`, GEM object headers | Shared object/text records and focused C/native layout checks. |
| `abi/desktop.json`, `generate_desktop.py`, `DESKTYPES` | Canonical heap-owned window record and pointer slots; generated shared definitions. |
| `AESWINDOW`, `AESWINDOWSTATE`, `DESKCORE`, `DESKMOVE` | Admit/mutate/retire one window model; narrow query publication. |
| `DESKGEOMETRY` | Replace repeated work/track/thumb calculations with source-mapped frame routines, provisionally in `AESFRAMEGEOMETRY`. |
| `AESFRAME`, `DESKPAINT`, `CONSOLEBITMAP`, `desktop-frame.c` | Tree/start-object frame request and selected-object rendering, with no scalar thumb geometry packet. |
| `aes-objects.c`, extracted GEM4XE object primitives | Separate reusable object work from application-only view/workstation admission; frame clips include borders. |
| `AESSNAPSHOT`, `AESMOUSE`, `DESKDRAG` and manager consumers | Routing facts without thumb geometry; one frame-object hit-test under UPDATE. |
| `aes-windows.c`, `vdi.c`, MGVIEW port adapter | Current query/metric/bridge ABI, rebuilt when required. |

Keep title/info lifetime under its current binding contract while moving their
specifications into the frame record; this geometry plan does not silently
change string ownership. Standard built-in frame callbacks remain trusted linked
code; arbitrary application USERDEF support is not added.

## Slice order

WG0 → WG1 → WG2 → WG3 → WG4 → WG5 → WG6. Commit each passing slice separately.
Use the smallest emitted fixture that exercises the changed boundary. During
cutover, an unmigrated consumer may read a projection of the canonical model;
it must not retain a second geometry calculator. Remove each projection when
its last consumer moves. The final cleanup checks below are mandatory.

### WG0 — freeze inputs, metrics and the focused harness

- Record donor hashes/ranges, actual compiler/ROM/emulator configuration and
  the current viewer/provider inputs. Reuse saved slider captures for the old
  baseline; do not rebuild the application catalog or rerun old frame matrices.
- Put shared object IDs and metric inputs in machine-readable definitions;
  define the proposed window/frame/text record layout and bridge descriptor.
  Confirm 24-byte OBJECT, 28-byte TEDINFO and eight-byte GRECT with both
  language views. Preserve a single shared object definition.
- Classify the new shared geometry/object helpers as library entries in
  `generate_tasks.py`; public helper routines must not become independently
  admissible Task entries.
- Prepare a tiny geometry fixture and an MGVIEW-only loader/observer. Reuse
  the existing DOS/Process and scroll observation helpers; remove Counter as
  a mandatory APP/media/process dependency. Discover Task roles/loaded bases
  rather than assuming the old Counter/viewer pool numbers.

Pass: source/metric checks and a small raw/optimized emitted layout/argument
probe agree. This limited raw probe covers the changed language/ABI boundary;
it is not a raw system build. Record the generated upper-storage budget before
allocating the new runtime records. Product behavior is otherwise unchanged.
Repeat this same small ABI probe if a later slice changes layouts or bridges.

### WG1 — canonical window allocation and frame creation

- Convert window slot users to the bounded pointer table. Allocate one
  address-stable window record through public Exec memory services; initialize
  identity, ownership, geometry values, object types/specifications and links
  before publishing it. Follow MagiC's empty current/previous rectangles at
  creation and full rectangle from create arguments. Use the
  `_wbm_create`/`_wbm_skind` outline, including kind-derived minimum size.
- Keep frame tree and text specifications inline in that allocation. Retain
  existing owned title/info storage. Make kind linking source-driven, including
  the scrollbar/thumb parent-child relationships; hidden objects retain their
  standard IDs. Do not reduce the tree to MGVIEW's current kind.
- Close withdraws the open epoch but retains the window. Delete withdraws the
  record from lookup, completes existing physical borrows, then frees once.
  Queued events hold identity/epoch and endpoint storage, not a window pointer:
  a later lookup rejects the withdrawn identity before dereferencing it. Retire
  routes/endpoints through the existing lifecycle path; never wait for a manager
  event to drain while holding the UPDATE it needs. Creation failure unwinds once.
  Convert internal native window creators to the same model or retire unused
  creators; do not keep inline and allocated window implementations together.

Pass: one hidden window creates, changes kind and deletes with correct
links/ownership. A creation-allocation failure leaves no published slot
or leak. A queued target cannot dereference a deleted or replacement record.
Use a focused fixture, not a full application run. WG2 verifies close/open
retention once full layout is connected.

### WG2 — full layout, work calculation and origin-only moves

- Port `_wbm_calc`/`_wind_calc` and `_wbm_ssize`; use the kind-derived
  minimums instead of independent fixed size/scroll-height admission constants.
  Commit current/work/overall
  geometry from the window; derive Layers visibility and C query views from it.
  Preserve previous/full geometry in their MagiC roles.
- Recompute track/arrow positions when kind or dimensions change. An
  unchanged-size move updates origins and screen projections while leaving
  relative child geometry untouched. Apply the existing copied-move fence and
  failure/commit protocol; a source/destination projection mismatch may redraw.
- Replace `DESKGEOMETRY.Work` and track reconstruction in geometry/query paths.
  FIRST/NEXT derives work intersections from canonical work geometry and live
  visibility under its existing UPDATE contract. Bounds/work changes publish a
  complete query view; a query does not run layout or acquire a second gate.
- Make `graf_handle` and frame metrics agree. Update pixel models to the
  pinned equations, including shadow/clipping and odd work edges.

Pass: emitted create/resize/kind cases match an independently derived donor
model. An origin-only move preserves child-relative coordinates and per-mille
values. Work/border round trips, previous/full queries and one clipped-visible
projection pass. Confirm each generated geometry value has one writer.

### WG3 — selected-axis slider setters

- Port `ws_slide`/`__sslid`/`_wbm_sslid`: normalize, compare, store, calculate
  from the selected stored track, then select its scrollbar for drawing.
  Both position and size use this routine. Equal values with the selected
  smart-redraw behavior produce no calculation or drawing.
- Remove `AESWINDOWSTATE.Geometry` from slider setters. The calculation
  updates no other axis, allocates nothing and invokes no view/cache/routing
  helper. Publish only scalar query facts that actually changed, through the
  existing short commit boundary. Do not advance a visibility-iterator revision
  for a thumb-only change; the visible rectangle list did not change.
- Replace old scalar thumb fields with tree-derived consumer inputs. Any
  temporary raster adapter reads the tree; it does not reconstruct tracks.
  Cache invalidation still required by the current surrounding operation stays
  outside geometry; it is not an excuse to retain a broad layout helper.

Pass: both axes, -1/default, clamp limits, minimum/short track and rounding
boundaries match the donor rules. A changed vertical setter invokes exactly
one selected-axis calculation and leaves horizontal object bytes unchanged,
and vice versa. Layout is not called. Keep MGVIEW's two standard calls.
A FIRST/NEXT walk remains valid across a nested slider-only update.

### WG4 — actual selected-object frame drawing

- Change the shared frame interface to tree/start-object/depth/clip plus
  existing display authority. Update owner and borrower entries together.
  Use UPDATE-owned upper scratch for a stable bridge request if needed;
  do not add a larger automatic packet to an ordinary application stack.
- Extract/reuse object traversal and prepared primitive work from the current
  GEM4XE binding. Do not call the application `ExecAESDraw` wrapper for frames:
  it currently requires an application workstation/view and work-only clips.
  Frame drawing uses the window's full visible region, and only the selected
  subtree is visited. Reuse built-in gadget images below that traversal.
- Preserve current display admission, scratch/list limits, fences and unsafe
  fault retention. All physical completion remains inside the originating
  UPDATE operation. A device-list drain does not publish GUI state or become
  another manager turn. No new row/grant policy is part of this refactor.
- Cut title/info/full-frame exposure over to the same frame tree, then remove
  procedural frame-layout arithmetic, scalar-thumb packet fields and the
  narrow-clip generic-frame substitute. Update machine-readable wire inputs
  and current generated callers when their layouts change.

Pass: exact frame pixels for one window plus one obscuring rectangle, both
scrollbar subtrees and a title/info case. A vertical scrollbar draw visits no
horizontal, arrow, title or sizer object. Check actual selected-object visits,
not only unchanged pixels outside the clip; frame-only setters preserve client
work pixels. Keep caller UPDATE through the
borrow/fence and verify the owner uses the same renderer.

### WG5 — SCRENMGR hit-testing and narrow routing publication

- Replace capture-side gadget interpretation with a retained frame interaction
  event. Input delivery keeps window identity/epoch and endpoint lifetime,
  coordinates/buttons and work-area/MCTRL routing facts. It follows no frame
  pointers and never waits for UPDATE.
- SCRENMGR obtains UPDATE for the interaction, resolves the retained identity,
  and applies `_wbm_obfind`-style object hit-testing to the current tree. Define
  this processing-time interpretation explicitly; do not keep a second
  capture-time thumb geometry path. Reuse the existing copied-event queue,
  cancellation and endpoint retirement services.
- Drag/page/arrow interpretation uses object IDs and stored track/thumb
  rectangles. Remove `DESKGEOMETRY.Gadget`'s procedural frame layout and thumb
  fields in `WindowRoute`. Slider changes no longer invalidate/rebuild the
  complete routing snapshot or wake SCRENMGR solely to interpret new geometry.
  Genuine layout/focus/registration changes still publish required facts.
- Preserve committed `wind_find` reads and independent keyboard delivery.
  Build each changed outside-UPDATE read projection before its short guarded
  publication; no full-layout Forbid and no reader-only synchronization fix.

Pass: point/arrow/page/thumb hits use the same geometry as drawing on both axes.
One focused case delivers a key while SCRENMGR blocks on UPDATE; one closes a
window with a queued frame click and verifies safe retirement. Cover loss or
cancellation in that focused interaction without expanding to an input matrix.
A slider-only change performs zero full routing-snapshot constructions.

### WG6 — remove leftovers and accept MGVIEW

- Remove unused generic layout/freshness helpers, old fields, packet decoders
  and geometry-dependent routing branches. Update imports, generators and
  observers. Search for duplicate track arithmetic as well as old names;
  restoring an alias or compatibility profile does not complete the slice.
- Build the current provider and MGVIEW only where their inputs changed.
  Reuse matching binaries/media. Run MGVIEW alone through open, resize, move,
  both-axis line scrolling, thumb interaction and close/Process retirement.
  Preserve ordinary GEM application logic; adjust only the shared binding or
  existing port adapter required by the current ABI.
- Record exact viewport/frame pixels and all stack/guard observations. Update
  current reference contracts and the execution record; preserve earlier
  measurements as historical evidence, not current qualification.

Pass: one canonical geometry model feeds query, painting and interaction;
changed setters calculate only their axis and complete synchronously. MGVIEW
retirement frees the window/tree allocation and existing provider/process
resources. No other APP is needed to pass this plan.

## Measurement and build discipline

Use development checks: small host/source checks and focused optimized emitted
cases for the affected slice. Repeat only when changes or failures justify it.
Use raw mode only for WG0's focused changed layout/bridge probe or diagnosis.
Do not run QED, Counter acceptance, a catalog, the old 36-phase frame matrix,
demo refresh or release matrices. A requested future demo still uses OF816.

Take one small down/up observation at WG6. Separate selected-axis arithmetic,
query/routing publication, subtree raster, ownership admission, CPU, off-Task,
interrupt and checked physical completion costs. Geometry changes alter work
width and packed-edge behavior: keep isolated arithmetic inputs matched, record
actual viewer viewport geometry, and do not claim an overall speedup from
unmatched pixel workloads or two frame-polled samples. Do not require the old
one-hardware-copy-unit count at newly odd edges; verify one semantic viewport
copy, correct pixels and the actual device units it needs.

## Storage and completion accounting

The current native window record is 306 bytes and the allocated desktop service
is 11,102 bytes. Its six inline windows reserve 1,836 upper bytes. The proposed
six native pointer slots use 18 raw bytes before surrounding alignment; created
window records are separately allocated through the existing public heap.

The tree alone is 384 bytes per created window. Two existing-format TEDINFOs add
56 bytes: **440 bytes for tree plus text specifications**, before window metadata,
canonical rectangles, owned text, alignment and normal allocator overhead.
Remove old fields and projections from the final calculation; do not claim a
net saving from those gross numbers. WG0/WG1 must record generated sizes and
actual upper heap cost for one and two live windows, plus failed creation and
complete retirement. Borrowed frame pointers survive until physical return.

Every slice targets **0 additional fixed, root, kernel, idle and per-public-Task
reserved bank-zero bytes**, counting DP, guards, alignment and unused capacity.
Report actual `bank_zero_budget` and Task-pool differences, and observed stack
floors, including borrowed bridge scratch and callbacks. No new signal, Task,
VRAM region or physical scratch reservation is planned. Bring a required
increase or extra architectural departure to the user with measured costs and
alternatives before implementation. This planning-only change adds zero
reserved bank-zero bytes and makes no executable qualification claim.
