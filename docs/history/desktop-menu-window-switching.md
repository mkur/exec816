# Desktop menu and window switching

[History](README.md) · [Plan](../plans/gem4xe/desktop-menu-window-switching-plan.md) ·
[Current contract](../reference/desktop.md#desktop-menus-and-window-switching) ·
[Development evidence](../development/desktop-menu-window-switching.json)

DW1–DW3 are implemented. They add a presenter-owned active-window menu, a Windows list and keyboard
switching. Four application windows remain available. Covered windows are
reachable without moving another window. Closing or hiding the focused window
restores the frontmost remaining routable owner; closing a background window
preserves focus. AES windows use their existing top/close messages and ordinary
application event loops. Native windows retain their existing event protocol.

Ctrl+Tab and Ctrl+Shift+Tab cycle stable window slots. Ctrl+Escape opens Windows;
Tab/arrows and Return select, while Escape, BREAK or outside clicking cancels.
The shell's Close entry is disabled. Held application/title gestures retain
ownership. Menu labels and window IDs are copied, and scene changes cancel stale
menus. Visible menu state changes only after the current paint token retires.
Application-defined GEM `menu_bar`/`MN_SELECTED`, accessories and cascading
menus remain unsupported; this slice adds desktop controls, not that GEM API.

Two opaque Layers hold the 16-pixel bar and four-row popup. Layers capacity grows
from four to six; its unchanged 96-rectangle capacity covers the conservative
91-piece region bound. Normal damage repairs exposed application content.
The copied-move path still admits a fully visible window below disjoint chrome;
it rejects a source or destination occluded by a higher layer. Thus the permanent
bar does not force every title drag into repaint-only movement.

## Development checks

Focused emitted-code checks pass: 330 optimized desktop assertions including
focus restoration, 56,694 optimized Layers assertions, and 89 small layout/move
assertions in each raw and optimized build. The latter cover new record layouts,
disjoint chrome, covered destinations, hidden popups and occluded sources.
The host suite passes 417 tests with four historical-source skips.

The pixel observer now resolves private application models through the published
AES window view and owning Process Task. It previously used the caller's
`wind_get` output buffer, which is temporarily cleared during an ordinary query.
A host regression checks two live Counter models with cleared work buffers and
rejects a hidden view. Pixel comparison remains an independent full-scene render.

The extracted OF816 ZIP passes physical pointer/keyboard menu actions, eight
forward/reverse switches, covered-window selection, five independent menu pixel
checkpoints, popup cancellation, disabled shell Close, and window-slot reuse.
Counter continues while the menu is open. Held application and menu gestures
cancel without leaking actions, and demo title drags stay below the bar.
The existing settings, six settings pixel checkpoints, Files launch/Stop/reload,
shell commands/pipeline, idle heap collection and EXIT with a live child/popup
also pass. Guards, ownership and OS restoration pass; no public Tasks remain.

The smallest observed public-Task stack margin is **33 bytes above the 256-byte
interrupt reserve**. Presenter stack peak is 739 bytes, with 1,565 bytes above
that reserve remaining. These are observed high-water marks, not a guarantee
for arbitrary application depth.

Six frame-granular Defaults press-to-matching-scanout samples give an initial
Panel median of 100.29 ms (maximum 120.50 ms), and a reloaded Panel median of
110.27 ms (maximum 120.25 ms). These are smoke observations, not a p95 benchmark
or a latency/flicker closure claim.

These checks are development coverage, not full hosted qualification.
Physical hardware and the existing HY4/PI4 latency/flicker gates remain outside
this work.

## Memory and packaging

Every slice changes reserved bank-zero bytes by **0 fixed, 0 per public Task,
and 0 private idle**, counting guards, alignment and unused capacity. No Task,
signal, timer, direct-page or stack reservation is added.

Compared with the prior Control Panel settings build:

| Upper-memory item | Before | After | Increase |
| --- | ---: | ---: | ---: |
| Fixed image-data reservation | 4,608 | 4,864 | 256 bytes |
| Occupied image-data bytes | 4,564 | 4,796 | 232 bytes |
| Desktop service, rounded heap allocation | 12,480 | 14,192 | 1,712 bytes |
| Populated image banks | 20 | 21 | One 64 KiB bank, $1E |

The service record itself grows from 12,480 to 14,186 bytes. The boot manifest
uses 63 of its existing 64 extent slots; no manifest capacity increase is needed.
The OF816 XEX is 998,433 bytes, leaving 33,758 bytes of Atarimax capacity.
The compiler revision remains pinned and has no local source override. The
standard no-option five-second shell/prime bundle still builds with its original
4,096-byte image-data arena; the executed walkthrough uses the GEM desktop.

The distributable is
[`exec816-demo.zip`](../../build/desktop-menu/final-distribution/exec816-demo.zip),
with its hash and platform pins in the evidence. It contains boot files, matching
disks, pinned ROM, guide, license notices and checksums. Build inputs, manifests
and test output remain outside the archive.
The ZIP's SHA-256 is
`b7ea956b8b04fc349786281f1f79166d4b484fbac03ddbbba71baa43bfae856d`.
