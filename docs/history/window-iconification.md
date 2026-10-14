# Window iconification

[Design](../plans/gem4xe/window-iconification-design.md) ·
[Plan](../plans/gem4xe/window-iconification-plan.md) ·
[Machine-readable evidence](../development/window-iconification.json)

Shell and ordinary AES/native windows can now be iconified using the title
gadget or Iconify in the native caption/Windows menu. The presenter reuses the
existing layer as a labeled bottom tile. A tile click or its `* ` Windows entry
restores normal geometry and focus. Ctrl+Tab skips tiles. Application tasks,
timers, handles and retained content keep running; application code is unchanged.

AES reports normal outer/work geometry and an empty visible region while
iconified. `WF_TOP` restores; geometry changes update the saved rectangle.
Native SHOW/RAISE/FOCUS restore, while HIDE forgets the tile. Close and process
exit use existing teardown. Shell output changes its retained model while
hidden; restoration repairs the backing before copying text. Tiles cannot
acknowledge console damage or enter the application snapshot cache.

This uses existing presenter ownership, Layers mutations, input capture and
AES lock admission. No new scheduler operation, Task, signal, layer allocation
or drawing engine is introduced. Console view publication now follows input
mutation within the same presenter turn, before output/paint decisions.

## Memory

Relative to the preceding window-backing build, reserved bank zero changes by
**0 fixed / 0 per public Task / 0 idle bytes**, counting guards, alignment and
unused capacity. No stack or direct-page reservation grows. VRAM changes by
**0 bytes**, retaining the 40 KiB Shell backing and existing AES caches.

The private desktop ABI advances from 13 to 14. Each window adds ten bytes
(saved bounds, iconified flag and alignment), so the six-window service grows
by **60 upper-heap bytes**, from 18,656 to 18,716. No application API changes.
All resident consumers are rebuilt together.

Static upper-memory data grows by **112 bytes**: three menu records (96 bytes)
and two Iconify strings (16 bytes). The existing 6,912-byte reservation now has
6,698 occupied bytes and 214 free. The native fixture retains its existing
larger test arena; the packaged production image uses the unchanged reservation.

## Development checks

- Host suite: 459 tests, four existing skips; generated definitions current.
- Raw and optimized layout/access probes: 113 checks each, including adjacent
  window records and their new fields.
- Optimized native desktop: 362 checks, including geometry, focus, content
  updates, hide/show/close, ownership and existing held-removal behavior.
- Optimized AES windows: 280 C checks and four native fixture checks. Physical
  iconification verifies empty visible regions, unchanged normal geometry,
  hidden geometry changes, `WF_TOP` restoration and close/reopen. Existing
  move/full/size/slider/lock checks remain in the same run.
- Exact final ZIP, physical input and independent pixel comparisons: Files
  gadget, tile cancellation, menu/tile restoration, Windows Iconify, Counter
  timer progress while hidden, ongoing Shell output while hidden, restored
  current text, slot reuse, HELLO and clean EXIT.
- Separate final-ZIP recovery run: Files and Shell iconified together,
  Ctrl+Tab skipping tiles and independent Windows-menu restoration.

Both demo runs return with intact guards and zero live Tasks. In the full
walkthrough, the presenter has 1,477 bytes above its stack floor, the tightest
ordinary Task has 243, and idle has 127. Kernel interrupt reserve remains
untouched. These are observed development margins, not static bounds.

Source baseline: `c474aab9cc8d8760bbda3e4766391e1d6b206f18`. The compiler pin
remains `05c01f39ff3beef97af0e65b0a16666f5a1bd805`; a local wrapper selects its
release host binary, without changing target optimization or ABI. No compiler
suite or full qualification matrix was run. The evidence records the pinned
AltirraOS 65816 ROM and exact PAL/VBXE emulator configuration. No hardware or
latency qualification is claimed.

## Demo and limits

The final 624,633-byte ZIP includes OF816, the matching SYS/WORK media, pinned
ROM, licenses, checksums and updated controls guide. Five-second autoboot is
retained. Both walkthroughs use the final archive after its guide/monitor
refresh; intermediates and test output remain outside the distribution.

```sh
/Users/michalkurcewicz/action/exec816-public/build/window-iconification/demo/launch-altirra.command
```

The tiles use fixed slot positions and a generic window glyph, with eight title
characters; Windows provides longer names and recovery when a tile is covered.
Frames below 64 pixels wide use the menu. The borderless desktop is excluded.
This is automatic presenter policy, not negotiated GEM `WM_ICONIFY` /
`WF_ICONIFY`. Movable tiles, custom tile artwork and task suspension remain
outside this implementation. Hidden applications retain their resources.
