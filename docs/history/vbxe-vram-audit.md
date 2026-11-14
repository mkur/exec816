# VBXE VRAM audit

[History index](README.md) · [Display contract](../reference/display.md) ·
[Authoritative map](../../platform/altirraos/vbxe-vram.json) ·
[Audit record](../development/vbxe-vram-audit.json)

Source audit on 2026-11-14, against `6a1a599e`. The map has no overlapping or
out-of-range reservations. Of 512 KiB, **462.5 KiB is reserved and 49.5 KiB is
unassigned**. The largest free interval is 20 KiB. A new 16 KiB workspace fits
at `$4C000–$4FFFF` without moving any allocation.

The retired Shell backing retains another 40 KiB. Current GUI painting does
not use it, but its private drawing entries, packet operations and executable
tests remain. Treat it as a retirement candidate, not currently free memory.
This audit changes descriptions only; every address, size and interface stays
as it was. It makes no new hardware or performance qualification claim.

## Complete reservation map

Ranges below include both endpoints. Reservations count padding and unused
capacity. Payload figures describe a layout, not permission to reuse its slack.

| Range | Bytes | Reservation | Current use and lifetime |
| --- | ---: | --- | --- |
| `$00000–$12BFF` | 76,800 | `screen` | 640 × 240 packed 4-bpp scanout, pitch 320. |
| `$12C00–$13FFF` | 5,120 | `widget_strip` | 640 × 16 repaint strip, or narrow frame-side staging; unfinished contents survive physical handoffs. |
| `$14000–$26BFF` | 76,800 | `menu_under` | Compact save-under image; retained scene/cache identity and pending DMA protect its contents. |
| `$27000–$2AFFF` | 16,384 | `popup_0` | First retained popup image, with cache validity and pinning. |
| `$2B000–$2EFFF` | 16,384 | `popup_1` | Second retained popup image, with cache validity and pinning. |
| `$30000–$300FF` | 256 | `xdl` | 12-byte display list read by scanout while enabled. |
| `$31000–$35FFF` | 20,480 | `font_masks` | GEM even/odd-X atlases: 8,192 + 10,240 glyph bytes. Staging writes whole 4 KiB pages. |
| `$36000–$36FFF` | 4,096 | `glyph_scratch` | Shared monochrome raster expansion, uncached icons and copy-edge staging; fenced under physical access. |
| `$37000–$374FF` | 1,280 | `cursor` | 256-byte saved background plus four 256-byte AND/OR masks for both X parities. Background survives until pointer erase. |
| `$38000–$38FFF` | 4,096 | `bcb` | Shared blitter command arena; pending DMA pins it. 195 whole 21-byte records fit (4,095 bytes). |
| `$39000–$39FFF` | 4,096 | `frame_gadgets` | Seven fixed images in both X phases, 2,688 bytes uploaded per display session. |
| `$3A000–$3EFFF` | 20,480 | `terminal_font_masks` | ATASCII even/odd-X atlases, 18,432 glyph bytes, including graphics and inverse glyphs. |
| `$41000–$4AFFF` | 40,960 | `shell_backing` | Retained 512 × 160 surface, pitch 256; obsolete GUI owner, callable drawing path remains. |
| `$50000–$62BFF` | 76,800 | `snapshot_0` | First retained compact window image, with cache validity and DMA pinning. |
| `$62C00–$757FF` | 76,800 | `snapshot_1` | Second retained compact window image, with cache validity and DMA pinning. |
| `$78000–$7FFFF` | 32,768 | `icon_cache` | Sixteen 2,048-byte slots. Each has four 408-byte planes (AND/OR, both parities); cache contents survive calls. |
| **Total** | **473,600** | | **462.5 KiB reserved.** |

The menu, popup, window and icon caches together reserve 295,936 bytes
(289 KiB). Their usefulness can be evaluated separately, but empty or invalid
cache contents do not release their fixed reservations.
These are fixed adapter slots, with no dynamic VRAM allocator. Raw hardware
operations check complete VRAM extents and command-arena exclusion where
applicable; the display owner remains responsible for respecting the layout.

## Unassigned intervals

| Range | Bytes | KiB |
| --- | ---: | ---: |
| `$26C00–$26FFF` | 1,024 | 1 |
| `$2F000–$2FFFF` | 4,096 | 4 |
| `$30100–$30FFF` | 3,840 | 3.75 |
| `$37500–$37FFF` | 2,816 | 2.75 |
| `$3F000–$40FFF` | 8,192 | 8 |
| `$4B000–$4FFFF` | 20,480 | 20 |
| `$75800–$77FFF` | 10,240 | 10 |
| **Total** | **50,688** | **49.5** |

The cross-page diagnostic borrows `$3FFF0–$4000F` (32 bytes) from the 8 KiB
interval. Excluding that diagnostic leaves 50,656 bytes; it does not affect
the proposed `$4C000–$4FFFF` workspace. Tests own their graphics session;
diagnostic borrowing is not an additional production allocation.

## Source and ownership checks

- [Driver and public hardware constants](../../platform/altirraos/vbxe.c)
  ([header](../../c/include/hardware/vbxe.h)): scanout uses `$00000`, XDL
  `$30000` and command upload `$38000`. Public raster extents exclude the
  complete command arena. Generic lists remain bounded to 64 records and
  8,192 work units; text has a separate maximum of 86 records / 1,806 bytes.
  Physical capacity is not a larger permitted submission size.
- [Drawing adapter](../../ports/gem4xe/adapter/gem-vbxe.c): widget strip
  `$12C00`, transient scratch `$36000/$36800`, cursor `$37000–$374FF`,
  ATASCII atlas `$3A000/$3C000`, generated gadgets `$39000`, and generated
  icon-cache bases agree with the map. Uncached icon planes each fit the
  2,048-byte half-page under the admitted object-strip limits. Copy edges
  require at most 480 bytes and save them in upper CPU RAM between grants.
- [Pinned source selection](../../ports/gem4xe/selection.json),
  [patches](../../ports/gem4xe/patches/0003-hosted-window.patch) and
  [extractor](../../tools/extract_gem_vdi.py): the selected renderer uses
  screen `$00000`, GEM fonts `$31000/$33000` and scratch `$36000`.
  Fresh extraction matches the renderer/header audited from the latest demo.
  The copied donor header also declares its own BCB, pointer, second screen
  and save-under addresses. Those declarations do not allocate hosted VRAM:
  the production [drawing build](../../tools/build_bitmap_console.py) excludes
  donor `src/vbxe/vbxe.c` and uses Exec's hardware adapter. Importing more donor
  code must reconcile those addresses before linking it.
- [Desktop generator](../../tools/generate_desktop.py) and
  [generated constants](../../c/include/hardware/vbxe-snapshots.h): both
  Action! and C cache/save/backing constants match the JSON. The
  [gadget generator](../../tools/generate_frame_gadgets.py) derives its base
  from the map and packs 2,688 bytes within its 4 KiB reservation.
- [Window cache](../../lib/desktop/deskcache.act) checks compact image size
  against 76,800 bytes per slot. The
  [menu/popup cache](../../lib/desktop/deskmenucache.act) uses its fixed
  save-under and popup destinations; popup size is bounded to 16,384 bytes.
  These caches retain validity and pins across asynchronous operations.
- [Backing packet dispatcher](../../lib/console/console-bitmap.c),
  [packet ABI](../../abi/console-bitmap.json), drawing adapter and
  `VbxeOwnerBackingText` still route to `$41000`. The
  [drawing fixture](../../tests/programs/gem_drawing.c) fills the full backing,
  draws both font parities and copies it to screen. There is no current
  production Action! caller of `BACKING_TEXT` or `BACKING_FILL`; the
  [GF12 retirement](gem-first-gui.md#gf12-native-graphical-policy-retirement)
  removed the GUI owner rather than these primitives. The latest demo's
  drawing link report confirms both entry points and `VbxeOwnerBackingText`
  remain in the shipped image.

The map is partly generated, not the single source for every renderer address.
Driver constants, adapter literals and selected donor definitions must be
checked together when changing an allocation. The JSON's `g3_used_bytes`,
`g4_used_bytes`, `i5_used_bytes` and `dt3_used_bytes` are historical slice
measurements. For example, `g3_used_bytes: 0` on a cache does not make it free.

## Reuse decisions

1. **Use a new 16 KiB reservation at `$4C000–$4FFFF` for the first copy
   experiment.** It fits wholly in unassigned space and leaves 34,304 bytes
   unassigned (34,272 excluding the diagnostic). A 303 × 96 image with a
   conservative 153-byte staging pitch, including a spare shift byte, uses
   14,688 bytes. This is a capacity calculation, not an implemented allocation
   or evidence of a speedup. Current work/row bounds still apply.
2. **Retire Shell backing separately if more space is needed.** Remove or
   migrate its packet operations, drawing entry points, ATASCII backing
   selector, fixed-destination helper, generated constants and executable fixtures together before
   releasing the reservation. That would yield 89.5 KiB total unassigned and
   merge `$3F000–$4FFFF` into 68 KiB before the diagnostic exclusion. There is
   no need to undertake this retirement to obtain the first 16 KiB workspace.
3. **Keep shared scratch lifetimes explicit.** The widget strip cannot be
   borrowed by a competing owner between continuations. Transient `$36000`
   storage may be reused only after dependent commands fence; copy-edge data
   survives in CPU RAM rather than assuming VRAM survives another owner.
   A new shared copy workspace needs the same physical-grant/fence discipline;
   retaining its contents across handoff would need explicit ownership.
4. **Do not count reserved slack as free.** In particular, the 2 KiB after
   the GEM glyph payload is read and rewritten unchanged by whole-page staging.
   Gadget slack, per-icon slot padding, XDL allowance, ATASCII atlas padding
   and unused BCB capacity also remain reserved. Reusing them requires updating
   reservations and checking producer extents, preservation and ownership;
   payload sizes alone do not establish that sharing is safe.

The CPU aperture `$8000–$8FFF` maps successive 4 KiB VRAM pages; it does not
limit workspace size. The adapter's `page[4096]`, `commands[4096]` and the
workstation's 642-byte raster scratch are upper CPU RAM, separate from these
VRAM reservations. Enlarging VRAM scratch does not itself require enlarging
the CPU aperture. This audit adds **0 fixed, root/kernel, idle or per-public-Task
reserved bank-zero bytes**, including guards, alignment and unused capacity.

## Validation and corrections

Development tier: all sixteen reservation bounds, non-overlap, totals, every
historical used-byte field, cursor subranges and diagnostic separation were
checked. Pinned input verification and fresh extraction passed. Ten existing
host tests passed across `test_display_abi.py`, `test_desktop_contract.py`,
`test_frame_gadget_assets.py` and `test_icon_cache.py`; these cover generated
definitions, interval accounting and independent gadget/icon pixel models.
Documentation links and the audit record were checked separately.

The adapter guide's old 420,352 reserved / 103,936 unassigned totals were
stale. It now agrees with the map and names both font atlases and the icon
cache. The display contract now makes the retained backing entries explicit,
and the map's note distinguishes historical payload fields from allocations.
No target behavior changed, so no new emitted-code run, demo rebuild or full
qualification matrix was required. Earlier execution records remain frozen.
