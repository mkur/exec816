# Application menu bars: implementation plan

[Design](application-menu-bar-design.md) · [Plans](../README.md) ·
[Current AES contract](../../reference/aes.md) ·
[Desktop menu baseline](../../history/desktop-menu-window-switching.md)

Status: AM1–AM4 implemented; AM5–AM6 pending. See the
[implementation record](../../history/application-menu-bars.md).

Implement the design in six executable slices, with a commit after each passing
slice. Start from `7492958` and the existing desktop development evidence; record
the actual source revision when implementation starts. There is no baseline-only
slice and no prerequisite to close HY4/PI4. This plan adds application menu bars,
not another latency optimization project.

The design is authoritative for ownership and public behavior. Retain one
application-owned OBJECT tree per AES client, use the existing presenter for
screen-wide menus, and deliver selections through the existing GUI record and
receiving port. Files is the first production consumer. Preserve the shell,
Counter, Control Panel, calculator and window-scoped popup behavior.

## Sequence and completion gates

| Slice | Deliverable | Completion gate |
| --- | --- | --- |
| AM1 | Menu registration, mutation and withdrawal | An upper-memory tree can be installed, replaced and retired without a surviving borrowed reference or lock deadlock. |
| AM2 | Durable menu commands | One accepted selection is delivered once to its original owner; retired selections cannot escape either message storage path. |
| AM3 | Presenter drawing and focus | Two applications' bars/dropdowns compose correctly with the existing six-layer desktop and focus restoration. |
| AM4 | Public bindings and physical interaction | Named/AESPB calls, pointer gestures and keyboard navigation work end to end. |
| AM5 | Files application menu | Open, Refresh, Stop and Quit use ordinary GEM menu calls and the existing command/lifetime paths. |
| AM6 | Integrated evidence and OF816 ZIP | The exact packaged desktop passes the selected coexistence, ownership, stack and pixel checks. |

Each slice depends on the preceding one. AM1–AM3 use focused fixtures to exercise
the private foundation. Publish `menu_bar` and connect production input only
when AM4 can honor the complete public operation. Do not introduce a temporary
public API, selectable compatibility profile or production test switch.

## Rules for all slices

- Follow the [platform contract](../../reference/platform.md),
  [Action! style](../../contributing/style.md) and
  [development-tier testing policy](../../contributing/testing.md). Use the
  compiler pin and record the actual C compiler, ROM, emulator configuration and
  any local override. GEM4XE remains read-only; add donor comparisons to the
  existing binding-reference inputs without silently replacing the renderer.
- Trust valid caller pointers, object links and indices. Establish supported
  shape/capacity and screen fit at installation. Preserve synchronization,
  generation and operational-failure checks; do not add repeated tree audits
  to painting, hit testing, setters or message delivery.
- Generate wire layouts and shared constants from ABI inputs. Rebuild bindings,
  service and affected APPs together. Keep the six-word request argument area
  where sufficient, with explicit full-pointer packing; do not grow the
  112-byte request merely to add a menu-specific packet.
- Keep four AES registrations, four application-window slots, six Layers and
  the existing sixteen ordinary message records per registration. Add no Task,
  signal, timer, kernel operation, priorities or event-wait mechanism.
- Target **0 additional fixed bank-zero bytes, 0 per public Task and 0 private
  idle**, including guards, alignment and unused reserved capacity. Report this
  for every slice. Record upper live/reserved data, heap rounding, code banks,
  manifest extents and measured stack use separately. Put persistent geometry,
  draw continuation and application menu arrays in upper memory.
- Use focused optimized emitted-code tests. Use small raw/optimized probes when
  wire layouts, C/native calls or pointer packing change; do not run the whole
  desktop twice. Test the affected ownership/preemption boundaries explicitly.
  Do not repeat passing checks without changed inputs or a concrete concern.
- Update current reference pages only for completed behavior. Record slice
  results in `docs/history/application-menu-bars.md` and compact evidence in
  `docs/development/application-menu-bars-amN.json`, linking the history index
  when those files are created. Keep traces, binaries and screenshots in `build/`.

Cartridge size is informational following the user’s implementation-time
direction; compression is separate future work. Preserve executable loading and
manifest limits.

The starting packaged build has 63 of 64 manifest extents, 33,758 bytes of OF816
cartridge headroom and a 33-byte minimum observed margin above the interrupt
reserve. Measure growth as code lands, including an integrated build in AM3.
Keep new state in existing upper-memory records or owned allocations where
practical. A larger bank-zero reservation or unrelated loader/compiler redesign
is not an implicit part of this plan.

## AM1 — Register and retire application-owned menu trees

Primary changes: `abi/aes-server.json`, `tools/generate_aes_server.py`,
`lib/aes/aesstate.act`, `aescore.act`, `aeswindow.act`, `aeslocks.act`, a small
`lib/aes/aesmenu.act`, and private C context/marshalling declarations.

1. Define the complete private layout needed for menu registration and delivery:
   tree address, bounded title/dropdown associations, installed-menu generation,
   one command's state and trusted delivery/deferred-message tags. Extend
   generated C/native layout probes; initialize unused menu fields to zero.
   Do not copy whole trees or labels per client.
2. Implement install/replace/withdraw against the existing client Task lease.
   Installation is valid before `wind_open`. Prepare association/geometry data
   before replacing the previous registration. Failed admission keeps the old
   registration usable. Use a non-reused generation, reporting exhaustion rather
   than wrapping into a previous lifetime.
3. Add presenter-side installed-tree mutations for enable, title state and text
   pointer changes. Wait for an active paint reference to retire before touching
   its source tree. Honor the caller's own UPDATE/MCTRL ownership without waiting
   for that caller to unlock; commit the model and defer visible work. Preserve
   the existing local helper implementation for uninstalled trees.
4. Centralize withdrawal: cancel the owned gesture, retire pending menu work,
   withdraw the generation and release every paint reference before replying.
   Window close clears commands for that open lifetime but retains installation
   for reopen. Application exit withdraws before endpoint drain, RSC free and
   Process collection. Explicit resource/string free remains the caller's
   responsibility after successful withdrawal.

Add a small menu fixture to the existing AES runner. Cover two registrations,
upper-bank pointers, inactive/pre-open installation, replacement, hide/reopen,
generation exhaustion, unsupported/capacity failure, and repeated cleanup.
After successful withdrawal, overwrite/free the old fixture tree and prove the
presenter cannot touch it. Exercise setter/withdrawal calls under the owner's
UPDATE/MCTRL and a competing display borrow, with bounded completion. Run the
small context/layout probe in raw and optimized modes and check guards and
register/DP restoration.

Exit: lifetime and mutation work without production menu interaction. Suggested
commit: `Add AES menu registration and withdrawal`.

## AM2 — Deliver selections without loss, duplication or stale references

Primary changes: `lib/aes/aesgui.act`, menu state, `aescore.act`,
`c/calypsi/aes-messages.c`, `aes-events.c`, `aes-menu.c` and private context fields.

1. Add one pending menu-command kind to existing GUI ordering. Reserve it before
   accepting a selection. Build the eight public words specified by the design,
   including original title/item/box indices and full tree address. Never replace
   an accepted command with a later click or consume an `appl_write` pool record.
2. Publish through the existing destination-owned GUI record, publication holds
   and receive-port signal. Keep published records immutable. Rearm only after
   both consumption/recycling and title normalization; either transition can
   happen first. Acknowledgment returns without waiting for the other transition.
   Pending redraw/top/move/close work continues in existing order.
3. Carry both window epoch and menu generation through trusted GUI readiness,
   selection and recycling. Filter stale menu records before returning
   `MU_MESAG`; recycling an old generation must not acknowledge a new menu.
   Preserve ordinary message payloads, including `MN_SELECTED` lookalikes.
4. Preserve trusted origin and generation when `menu_popup` stores a received
   message in its existing deferred slot. Apply the same stale check on that
   slot before the event decision, and keep message/timer commit ordering intact.
   Do not introduce another queue or polling wake.

Extend the menu fixture and existing GUI/event regressions. Inject selections
through a fixture-only entry, not a production API. Test delayed consumers,
duplicate clicks, both acknowledgment/recycle orders, full ordinary-message
pools, interleaved redraw/close, and Process-owner `RequestClose` while a command
is pending. Test focus change after acceptance, close/reopen, replacement/removal
before consumption, stale recycling and a stale deferred-popup selection. An
ordinary message with identical public words must still arrive unchanged.
Test relevant publication/recycle preemption boundaries, pending exit and heap
cleanup. Repeat small raw/optimized probes only for additional boundary changes.

Exit: command delivery survives the tested ordering/lifetime cases without
changing ordinary message capacity or timer waits. Suggested commit:
`Deliver generation-tagged GEM menu commands`.

## AM3 — Draw active application menus in the desktop

Primary changes: `lib/desktop/deskmenu.act`, `deskmenupaint.act`, `deskpaint.act`,
AES menu/focus integration, `c/calypsi/aes-windows.c`, and a small presenter menu
drawing binding beside the extracted code in `ports/gem4xe/aes/`.

1. Select the visible menu from the focused shown window's AES owner. Keep
   installation and visibility separate. Switch only at a paint boundary;
   cancel unfinished gestures, preserve accepted commands, and use existing
   focus restoration. No installed active menu means the desktop fallback.
2. Draw titles within x=0..431 and preserve Windows at x=432. Permit standard
   screen-wide root/bar containers, clipping their drawing appropriately. Keep
   original tree coordinates/indices and apply presenter origin offsets.
   Give each dropdown its own on-screen bounds; clamp position, not dimensions.
3. Reuse the two private chrome layers. Hide/delete/recreate the private popup
   at an idle scene boundary when dimensions change, without taking an additional
   layer slot. Add Next window/Close below the Windows list when application
   titles occupy the left side; preserve captured-target and disabled-shell rules.
4. Reuse extracted object/text primitives with presenter-owned scratch and
   bounded paint continuation. Admit G_TITLE through the menu binding rather
   than loosening native widget admission or public work-area clipping. Preserve
   16-scanline strips and existing object/text work limits. Patch only affected
   title/entry damage for state changes; use full menu damage for install/focus
   changes. Never mutate source state halfway through a paint transaction.
5. Return desktop work area `(0,16,640,224)` from `wind_get(0,WF_WXYWH)` in desktop
   mode. Keep window conversion and existing committed window sizes unchanged.

Use a focused desktop fixture with two different compiled menus and a small
RSC tree. Compare independent pixels for bar activation, variable-size dropdowns,
disabled entries, title normalization, focus switch, shell fallback and exposure
repair. Include Counter updates, shell scrolling, a title drag beneath disjoint
chrome and menu withdrawal during a paused paint. Verify four app slots remain
usable, object drawing stays work-area clipped and the desktop query is correct.
Extend `tools/desktop_oracle.py` from source trees and committed public state,
without reading target cached hit/visible geometry as expected output.

Build the composed GEM desktop through `tools/build_demo.py` now to catch resident
code, global arena and manifest limits. This is an early capacity check, not a
request to run the full packaged walkthrough after every slice.

Exit: correct bounded rendering and safe focus/lifetime handoff, including the
full-size build. Suggested commit: `Render application menu bars in the presenter`.

## AM4 — Connect public GEM calls and menu input

Primary changes: `c/calypsi/aes-menu.c`, `aes.c`, public headers, binding reference
inputs, `abi/c-program.json` and its generators, plus desktop menu/input routing.

1. Expose `menu_bar` through its named function and AESPB opcode 30/counts
   1/1/1/0. Route installed-tree `menu_ienable`, `menu_tnormal` and `menu_text`
   through AM1; keep uninstalled trees local. Preserve existing popup behavior.
   Reject unsupported bar modes without partially altering installation.
2. Add the C application import, update the current ABI version and rebuild all
   affected APPs together. Check pointer packing and public/private parameter
   counts through emitted code; do not add old/new ABI compatibility profiles.
3. Wire click-open, drag-release, heading changes and outside cancellation to
   AM2 command admission. Skip disabled/hidden items. Keep press ownership across
   the bar, popup, windows and release; loss/Escape/BREAK never leaks a click.
   Window switching remains available while an application awaits acknowledgment.
4. Preserve Ctrl+Tab/Ctrl+Shift+Tab and Ctrl+Escape. Add Ctrl+Shift+Escape for
   application-menu entry, Left/Right for titles and Up/Down/Tab/Return for item
   navigation. Respect held gestures and existing UPDATE/MCTRL/display gates;
   do not translate or deliver consumed keys a second time.

Exercise the complete path using two ordinary GEM fixture applications through
public calls, including two instances with equal title text/object indices.
Assert the exact recipient, full message words, once-only command action and
title acknowledgment. Include enable/text changes during an open menu,
all-disabled menus, hidden entries, replacement while a button is held,
background installs and focus restoration after close. Disabling an armed item
must prevent its selection; text patches must preserve declared geometry.
Run small raw/optimized
public binding probes, then optimized physical pointer/keyboard and pixel tests.
Update the AES reference and application guide with the delivered subset and
explicit exclusions. Remove fixture-only selection injection from production
link roots.

Exit: an ordinary GEM event loop can use the menu without Exec-specific menu
calls. Suggested commit: `Expose GEM menu bars and desktop menu interaction`.

## AM5 — Give Files a real application menu

Primary changes: `examples/gem-browser/browser.c`, `browser.h`, its model/layout
probes, application observers and the existing Files integration checks.

1. Add a small compiled-in OBJECT tree to the private Browser model in upper
   memory, with one Files title whose dropdown contains Open, Refresh, Stop
   and Quit. Keep command labels/source storage alive for the registration.
   Install through `menu_bar`; remove before freeing its model/resources.
2. Handle `MN_SELECTED` in the existing event loop, dispatch through the current
   operations and normalize the selected title. Update Open/Stop enabled state
   when selection, launch availability or child lifetime changes. Avoid redundant
   setters when state is unchanged.
3. Keep the resource-backed browser controls and window-scoped popup. Quit uses
   the same deferred close and child-cancel/collection path as WM_CLOSED; no new
   command dispatcher or application framework. Handle installation failure via
   normal application cleanup.
4. Update layout probes and observers together. Do not add tree/event arrays to
   the already constrained C Task stack. Test two Files instances in the smaller
   dedicated fixture; the production panel/counter/shell desktop has limited
   spare Task/window capacity.

Exercise pointer and keyboard Open/Refresh/Stop/Quit; disabled actions; native
HELLO/TICK and GEM APP launch; menu ownership while the child is focused; Stop
and Quit with a live child; window closer; resource cleanup and reload. Prove
independent menu trees for two instances and restoration of the other menu after
close. Keep the calculator and Control Panel launch paths working.

Exit: Files supplies a useful application menu using supported GEM calls.
Suggested commit: `Use an application menu bar in Files`.

## AM6 — Package and record the complete desktop

Extend `tools/desktop_menu_check.py`, `tools/test_gem_files.py` and
`tools/test_gem_desktop_boot.py` to cover the production menu alongside the
existing Control Panel settings, Counter, shell and launcher walkthrough.
Update both the distribution guide and generated disk README.

Run host checks and the remaining affected optimized regressions. Then build and
test the exact OF816 ZIP:

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=2 CARGO_PROFILE_DEV_DEBUG=0 python3 tools/build_demo.py --gem-desktop --output build/application-menu/distribution
python3 tools/test_gem_desktop_boot.py --bundle build/application-menu/distribution
```

The extracted bundle must demonstrate active application/fallback bars, covered
window access, physical menu selection/cancellation, dynamic item state, correct
focus/menu restoration and independent pixel repair while Counter and shell
output continue. Retain the existing settings, native/GEM launch and Stop,
pipeline, idle collection and EXIT-with-live-child checks. Exercise a withdrawn
RSC tree in the focused fixture before recording final lifetime coverage.

Verify guards, public/presenter stack margins, register/OS restoration and heap/
ownership return. Record time-bounded command completion; frame-granular menu
feedback observations may expose a regression but do not claim a p95 improvement
or flicker closure. Investigate new stack-floor violations or clearly visible
usability regressions before calling the slice complete.

Report actual upper memory, bank-zero deltas, owned code banks, manifest extents,
OF816 XEX bytes and cartridge headroom. Preserve the five-second autoboot and
standard no-option shell/prime build. Check cartridge packaging if its code or
layout changes; do not turn this into an automatic full cartridge/platform matrix.
Distribute only `exec816-demo.zip`, containing boot files, matching disks, pinned
ROM, short guide, license notices and checksums. Keep build manifests and test
output outside it.

Finish the history/evidence and indexes, record artifact/source hashes and actual
test scope, and mark AM1–AM6 complete only when their gates pass. This remains
development coverage, with full hosted qualification, hardware and HY4/PI4
separate. Suggested commit: `Verify and package application menu bars`.
