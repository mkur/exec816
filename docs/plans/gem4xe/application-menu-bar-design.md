# Application menu bars

[GEM integration](README.md) · [Implementation plan](application-menu-bar-implementation-plan.md) ·
[Current AES contract](../../reference/aes.md#resources-and-popup-menus) ·
[Desktop menus](../../reference/desktop.md#desktop-menus-and-window-switching)

Status: implemented through AM6 with development checks.
See the [execution record](../../history/application-menu-bars.md).

Let an ordinary GEM application install an OBJECT menu tree, receive
`MN_SELECTED` through its existing event loop, and acknowledge the selected
title with `menu_tnormal`. Focus determines whose menu is displayed. Keep the
desktop Windows menu available beside it. Use Files as the first application,
with Open, Refresh, Stop and Quit commands.

This extends the hybrid AES model: application content still draws in its own
Task; the existing presenter owns menus outside application windows. It adds no
kernel service, Task, priority, signal, timer or alternate event wait.

## Starting point and scope

The completed [desktop menu slice](../../history/desktop-menu-window-switching.md)
provides a 16-pixel bar, one popup, window cycling and focus restoration. Its two
private Layers leave four application-window slots available. Its labels are
desktop-owned copies, not GEM application menus.

[aes-menu.c](../../../c/calypsi/aes-menu.c) already implements `menu_popup`,
`menu_ienable`, `menu_tnormal` and `menu_text`. The last three currently alter
caller memory without involving the presenter. `menu_bar` and `MN_SELECTED`
are missing. Do not build a second popup event framework or reimplement those
local helpers for uninstalled trees.

Use the existing 24-byte OBJECT format, full C pointers, fixed 8×8 font,
32-object limit, eight-level bound and 63-character labels. Accept the usual
menu shape: root with bar and dropdown-container children; titles beneath the
bar's active container; corresponding dropdown boxes in sibling order. Preserve
original object indices. Support G_BOX/G_IBOX containers, G_TITLE headings,
G_STRING entries, SELECTED/DISABLED and hidden entries. Disabled strings can
serve as separators. No accessory insertion, cascading/scrolling menus,
callbacks, icons, editable objects or general menu layout engine in this slice.

Start Files with a compiled-in menu tree. Its existing RSC-backed browser
content remains unchanged. The same menu API accepts a relocated RSC tree in
the admitted subset; test that path with a small resource fixture. This is
source compatibility for rebuilt applications, not Atari ST binary loading.

## Public calls

The basic signatures and parameter counts follow the
[GEM menu library](https://freemint.github.io/tos.hyp/en/menu.html).

| Call | Behavior in this profile |
| --- | --- |
| `menu_bar(tree, 1)` | Install or replace this application's menu. Reinstalling the same tree republishes its layout. Does not top a background window. |
| `menu_bar(tree, 0)` | Withdraw this application's installed menu; complete withdrawal before returning. |
| `menu_tnormal(tree, title, normal)` | Preserve local behavior for uninstalled trees. For the installed tree, serialize the state change and schedule affected title damage; normalizing the selected title acknowledges its command. |
| `menu_ienable(tree, item, enable)` | Preserve local behavior for uninstalled trees. For the installed tree, serialize DISABLED changes and repaint the affected visible entry. |
| `menu_text(tree, item, text)` | Preserve Exec816's existing pointer-replacement behavior and string-lifetime contract; update the installed menu through the same serialized path. Text must fit its declared bounds. |
| `MN_SELECTED` | Deliver the selected title and entry through `MU_MESAG`, using the existing receiving port. |

Add named and AESPB `menu_bar` bindings: opcode 30, control counts 1/1/1/0.
Retain opcodes/counts for the existing helpers. Initially accept only show/hide
modes 1/0; extended query/install modes remain unsupported. `menu_icheck` and
CHECKED rendering can follow a concrete application need.

Background installation updates that application's registration but leaves
current focus intact. This is the chosen multitasking policy, rather than
single-application GEM's immediate screen takeover. A registration can exist
before its window opens. Only the owner of a focused, shown window supplies the
visible application menu; windowless menu ownership is deferred.

No complete AES-version or extended-menu capability claim follows from this
subset. Extend the existing binding-reference pin and generated ABI/import
definitions during implementation, and rebuild all affected applications.

## Tree ownership and mutation

Keep **one registered application-owned tree per AES client**, referenced by
its full address. The existing client Task lease retains its application image.
The caller keeps the tree and all referenced strings alive until successful
withdrawal or application exit. A tree shared by independently modifying Tasks
is outside this profile.

This deliberately extends the earlier object-call lifetime: normal `objc_*`
calls retain no caller pointer after return, while an installed menu is a
long-lived registration. The presenter may draw it between calls. Do not make
a second copy of every application's tree or text, add per-object handles, or
retain pointers to transient call parameters. The desktop Windows list keeps
its existing copied-label representation.

Menu installation records title/dropdown associations and bounded geometry once.
Trust valid object links, indices and caller-owned pointers. Check supported
shape/capacity and screen fit at installation; do not rewalk a validator during
input, drawing or each helper call. Normal allocation/unsupported-operation
failures leave the previous registration intact.

Installed-tree helpers use a small presenter RPC for the actual shared mutation.
The original tree is changed only at admission, when its current paint has
retired; failure leaves it unchanged. Uninstalled-tree helpers remain local.
Reuse the existing packet and intake budget, with explicit menu operations;
this is AES policy, not a new kernel gateway. Menu updates are infrequent and
must not turn ordinary object changes into presenter calls.

The presenter manages the title's SELECTED state. Item hover/press is private
gesture state, so it need not rewrite every application's object state as the
pointer moves. Direct structural changes to an installed tree require withdrawal
and reinstallation. Use menu helpers for installed state/text changes; changing
memory alone is not an implicit redraw notification.

An owner may call these helpers while holding UPDATE/MCTRL: commit model changes
without waiting for that owner to release its own lock, then defer painting and
interaction until release. Never wait for menu dismissal or application message
consumption inside the mutation RPC. Other owners' display/scene borrows still
protect active drawing. Do not hold Forbid while painting or walking a tree.

## Bar, popup and focus

Keep the 640×16 desktop bar and the Windows heading at x=432. Application title
rectangles must fit the left 432 pixels. Standard screen-wide root/bar containers
are allowed; clip their bar drawing to that application area. Normalize its
screen origin and title baseline in presenter drawing coordinates, preserving
the caller's tree coordinates and object numbering. Dropdowns begin below the
bar, use their resource geometry and may extend across the screen. Clamp their
screen position without modifying the source tree; reject a dropdown too large
to fit the usable screen. No scrolling or silent title truncation.

When an application menu is present it replaces the left desktop title menu.
Keep Next window and Close available beneath the Windows list in that case:
at most four window entries and two actions. Close still targets the captured
window identity and is disabled for the shell. With no installed active menu,
retain the current active-window menu. Files should name its first title Files
so the owner remains apparent.

Reuse the existing two chrome Layers. The popup's bounds must match the opened
dropdown; its current four-row, 208-pixel box is not a GEM layout constraint.
At an idle scene boundary, delete/recreate the hidden private popup layer when
its dimensions change. This reuses its slot and requires no public window-resize
API or increase beyond six Layers/96 region rectangles. Restore exposed pixels
through normal damage, never a saved-under screen buffer.

Use the extracted object/text drawing routines through a small presenter-side
menu binding. The current native widget admission path assumes a work-area
tree and does not admit G_TITLE: do not feed menus through it unchanged or
weaken its unrelated contract. Likewise, public `objc_draw` remains confined
to application work areas. Menu drawing uses the presenter's display ownership,
16-scanline strips and bounded object/text steps, with input boundaries retained.
No application callback runs in the presenter. Menu scratch lives in upper RAM.

Focus changes cancel an unfinished gesture and select the new owner's installed
menu at a paint boundary. Focus restoration after close/hide uses the implemented
frontmost-routable-window policy; no separate previous-menu stack is needed.
Closing an application's window makes its menu inactive but leaves registration
available for reopen. Withdraw on `menu_bar(..., 0)` or `appl_exit`.

Return `(0, 16, 640, 224)` for `wind_get(0, WF_WXYWH)` in desktop mode, excluding
the bar. This corrects the current whole-screen query. Existing window geometry
is not silently resized, and application drawing still clips below chrome.

## Input and command delivery

Retain click-to-open and press-drag-release selection. While a menu is open,
crossing a heading switches dropdowns. Skip disabled/hidden entries; outside
click, Escape, BREAK or input loss cancels without click-through. A held
application or title gesture keeps its original ownership. The menu owns its
input sequence until release, including after cancellation.

Keep Ctrl+Tab/Ctrl+Shift+Tab for window cycling and Ctrl+Escape for Windows.
Use Ctrl+Shift+Escape to open the first enabled application title. Left/Right
switch titles, Up/Down or Tab/Shift+Tab navigate entries, Return selects, and
Escape cancels. Reserve these shortcuts before caller routing only when no
pointer gesture is held. No mnemonic/accelerator parser in this slice.

The selected title remains highlighted until the application calls
`menu_tnormal(tree, title, 1)`. Deliver the following eight words, matching the
inspected [GEM4XE control-manager layout](https://github.com/slaapliedje/gem4xe/blob/fbfea9b0b1233a5d659d5ec583c63f863cceadfa/src/aes/ctrl.c#L286):

| Word | Value |
| --- | --- |
| 0 | `MN_SELECTED` (10) |
| 1–2 | 0: current system sender convention and no additional payload |
| 3 | Original title object index |
| 4 | Original entry object index |
| 5–6 | Original application tree address, high word then low word |
| 7 | Original dropdown-box object index |

The pointer words preserve the full C address. They describe the selected tree,
not a temporary rendering view; their presence does not imply submenu support.

Reuse the destination-owned GUI delivery record and receive port. Extend pending
GUI state with **one menu command**, admitted only while no previous menu command
for that registration awaits delivery/acknowledgment. Do not pass selections
through redraw-style replacement/coalescing. Keep the existing first-pending
ordering and immutable published record. Ordinary `appl_write` retains all
sixteen records, and redraw/close work must still progress.

Rearm application-menu selection only after its command record has been
consumed/recycled and its title normalized. Until then Windows, focus switching
and other applications remain usable. There is no timeout, unbounded queue or
wait inside `menu_tnormal`. A focus change after selection does not redirect or
discard that already accepted command; the original application receives it.

## Withdrawal and stale messages

Window epochs alone are insufficient: an application can replace its menu while
keeping the same window. Give each installed-menu lifetime a non-reused
generation. Replacement/withdrawal cancels its unfinished gesture and pending
command, retires that generation, removes every paint reference, and only then
replies. A returned success is the point at which the old tree may be freed.
Close also cancels commands for the old open-window lifetime and clears any
unacknowledged title, while preserving the installed tree for later reopen.

Add private menu-generation metadata to trusted GUI delivery state, alongside
the existing window epoch. A zero menu generation denotes an ordinary window
notice. The caller filters retired menu deliveries before returning `MU_MESAG`
and recycles them through the current wake protocol. Do not identify a trusted
menu message solely by its public word 0: ordinary application messages with
the same words remain opaque.

The existing `menu_popup` can defer a received GUI message in its one caller-local
slot. Preserve origin/generation metadata there too, or a deferred selection
could escape the queue's stale-message filter after replacement. Do not add a
second mailbox. Messages already returned to application code are its
responsibility; withdrawal cannot retract an application-owned result buffer.

On `appl_exit`, withdraw menu references before the existing endpoint drain,
resource free and Process collection. Explicit `rsrc_free`, successful resource
replacement or freeing a string referenced by the menu requires the caller to
withdraw that menu first. This follows the valid-pointer ownership contract;
do not scan arbitrary object pointers at each resource call. Failed resource
loading continues to preserve the old allocation. In particular, never wait for
the exiting caller to dequeue a selection before replying to its exit RPC.

## First application and validation

Files installs its compiled-in menu after registration and removes it before
freeing source data. Its Files dropdown offers Open, Refresh, Stop and Quit. Reuse
the existing command routines, selection model, child cancellation and collection;
Quit follows the same cooperative path as WM_CLOSED. `MN_SELECTED` dispatches by
object index and normalizes its title after handling the command. Enable Open
only for an available selection/launch slot and Stop only for a live child.
Keep the current window controls; migrating them is not required by this design.

Development checks must cover two independent menu owners (including two copies
of one app), inactive installation, close/reopen, fallback to shell, held-button
cancellation, disabled entries, keyboard navigation and exact message words.
Exercise a delayed consumer, a full ordinary message pool, redraw/close ordering,
replacement before consumption, the deferred popup slot, resource withdrawal and
exit with a menu open. Both compiled and RSC trees must work above bank zero.
Compare settled pixels independently while Counter and shell output continue.

Use optimized emitted-code integration tests, plus small raw/optimized probes
for changed C/native layouts, AESPB counts and pointer-word packing. Check
register restoration, guards, stack margins, heap/ownership cleanup and bounded
completion. Refresh and execute the OF816 ZIP with matching rebuilt apps; retain
the standard five-second shell/prime default. HY4/PI4 and physical-hardware
qualification remain separate.

## Memory and implementation boundary

Reserve **0 additional fixed bank-zero bytes, 0 per public Task and 0 private
idle**, including alignment, guards and unused capacity. Keep four application
slots, six Layers and the existing Task/stack/DP reservations. Small per-client
registration/generation/command state and presenter continuation storage belong
in upper memory; no per-client tree copies or framebuffer backing are required.

Measure exact upper-memory, generated ABI and code growth in the implementation
plan. The current tested build has a 33-byte minimum observed margin above the
interrupt reserve, 63/64 manifest extents and 33,758 bytes of OF816 cartridge
headroom. Keep menu arrays and rendering buffers off public-Task stacks. The
note does not assert that the next image fits those limits without a build.

The implementation plan should order registration/retirement and trusted
delivery before drawing/input, then add Files and the integrated demo proof.
No scheduler changes, generic event framework or wholesale donor control-manager
port are needed. The local GEM4XE checkout at
`fbfea9b0b1233a5d659d5ec583c63f863cceadfa` was inspected read-only; its newer menu
runtime is a reference, not an implicit update of Exec816's pinned renderer.
