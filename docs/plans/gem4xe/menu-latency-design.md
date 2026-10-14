# Dropdown menu latency

Make application and system menus respond promptly by reducing presenter work
per visible change. Keep the existing GEM API, application-owned trees,
input ownership and scene transaction boundaries. This is a renderer and damage
policy change, not a new AES protocol or scheduler priority scheme.

## Current costs

The presenter already draws installed menus directly; each entry does not make
an application RPC. However, `menu-render.c` draws at most one intersecting
object per callback and splits text into 96-pixel fragments. Every callback
fences drawing. Each 16-row strip starts another walk through the menu tree.
Native popup rows also split their maximum 24-character label into two calls.

Application highlighting already damages the old and new items. Native
highlighting instead marks the entire bar and popup dirty. Opening and closing
also repaint more bar content than the changed heading requires. Ordinary
round-robin layer selection can postpone ready menu damage behind other layers.
The worker already continues ready painting without a voluntary yield per
strip; removing such a yield is not an available optimization.

GEM4XE 0.12 (`fe5704f`, `src/aes/menu.c:menu_sr/menu_down/menu_select`)
draws its menu directly, changes individual highlighted objects, and uses
`bb_save`/`bb_restore` to restore covered pixels. Its VBXE save form lives in
VRAM. The reusable ideas are complete labels, small highlight damage and fast
opaque painting. Blindly restoring saved pixels would be incorrect when an
Exec application changes content while its menu is open.

## Rendering

Keep the existing 16-row offscreen strip and publish it only when complete.
Remove horizontal label fragmentation. A callback visits at most the admitted
32 objects, draws at most four intersecting objects, and budgets at most 80
visible text cells. A label is never split: stop before the next object if it
would exceed the remaining budget. Admission already limits strings to 63
characters and dropdown width to 640 pixels, so one label always fits. Count
the clipped width conservatively; do not scan strings again for budgeting.

Native popup rows draw their entire bounded 24-character label in one call.
Start at the row intersecting the strip instead of stepping through preceding
rows; stop when the strip ends. Retain edge clipping, checked/disabled states,
the one-pixel outline and existing cursor preparation/fences. No caller-tree
revalidation is added to drawing.

## Damage and precedence

Publish selected state with its damage only after the live paint token retires.
For native highlight changes, invalidate the old and new rows only. Opening or
changing popup contents damages the popup; changed caption/Windows selection
damages only that bar segment. GEM title selection uses existing object damage.
A new menu owner or changed caption still repaints the affected bar content.

At the start of a new paint transaction, prefer a dirty popup, then the bar.
After at most two consecutive preferred menu transactions, allow one ordinary
round-robin selection if ordinary work is ready. This prevents continuous
menu input from starving other windows. Never interrupt a live paint token,
borrowed source, application update lock or outstanding blit. Input continues
to be serviced between bounded steps; kernel priorities remain unchanged.

## Dismissal and memory

Closing continues to expose underlying layers through normal damage, including
`WM_REDRAW` for application-owned content. Measure dismissal separately from
opening and highlighting. Save-under is a follow-up only if restoration remains
the dominant cost: it would need covered-content invalidation, clipping and
z-order/lifetime rules before a VRAM copy could safely replace redraw.
The follow-up [AES and Layers VRAM design](aes-layers-vram-design.md) specifies
that cooperation, menu save-under and wider use of fixed VRAM image slots.

No new VRAM region, Task, message, signal, timer or public ABI is needed.
Additional scalar state and the native label buffer live in upper-memory image
data. Reserved bank-zero change is **0 fixed, 0 per public Task and 0 idle**,
including stack/DP guards, alignment and unused capacity.

## Evidence

Use the same physical menu interactions before and after, on the pinned
emulator/ROM and compiler. Record open, highlight, heading switch and dismissal
separately, with median/p95 and the measurement's frame granularity. Check exact
pixels against the independent menu model, including long labels, odd/clipped
edges, disabled/checked entries and native menus. Existing lifetime and input
tests must still cover replacement, removal, held-button cancellation,
different owners and durable `MN_SELECTED` delivery.

The complete OF816 demo must also boot and exercise menus while another
application updates. This is development evidence, not hardware or release
qualification. See the [implementation plan](menu-latency-plan.md).
