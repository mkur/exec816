# Shell focus without full redraw

[Desktop contract](../reference/desktop.md#presentation) ·
[Development evidence](../development/shell-focus.json)

Shell focus used to invalidate the whole console layer, and presentation sync
treated a focus change as a placement change, dirtying every retained cell.
Title activation also raised an already-front application past the two menu
layers, then restored those layers, damaging an unchanged window.

Focus now damages the title and restores the outgoing caret before changing
its route. Presentation sync preserves the text model and gathered output on
focus-only changes. A private presenter raise helper recognizes the first
application below menu chrome; native and AES raises share it. A move to the
current origin returns before caret removal or copy admission.

Real changes to stacking or geometry still repair exposure. This does not add
a console framebuffer cache or change input routing, scheduling or the public
ABI. The normal title-drag outline remains visible while the button is held.

## Development checks

- Host suite: 459 tests, four existing skips.
- Optimized cache/focus fixture: 18 complete pixel-oracle scenes and 71 native
  checks. Losing and regaining Shell focus each leave exactly one caret cell
  for retained repair. A real raise repairs the covered client; a repeated
  raise/focus performs no client painting.
- Three physical clicks on the front Shell (body, title, repeated title):
  zero retained-client paint steps, with exact pixels after each release.
- Optimized presentation fixture: 19 scenes, 117 checks, including aligned
  and overlapping moves, clipped exposure, scrolling and partial cancellation.
- Exact OF816 ZIP walkthrough: Files, Panel pointer/keyboard activation,
  Counter progress, Text scrolling/document hash, selector cancellation,
  closing/focus restoration, HELLO and clean EXIT. Autoboot took 249 PAL frames.
- Stack floors, guards, ownership cleanup and OS return are checked by the
  emitted fixtures. These are development checks, not release qualification.

The repaint observer is inserted only into the fixture copy of `DESKPAINT`;
the demo has no new counters. No new production data, buffers or Tasks are
reserved. Bank-zero delta is **0 fixed / 0 per public Task / 0 idle bytes**,
including guards, alignment and unused capacity. The packaged build's bank-zero
budget, Task pools and runtime/loading reservations match the menu-switch demo.

## Demo

The refreshed OF816 package keeps its matching system/work media, pinned ROM,
license notices and five-second autoboot. Launch it with:

```sh
/Users/michalkurcewicz/action/exec816-public/build/shell-focus/demo/launch-altirra.command
```

The compiler pin is unchanged. Exact source and artifact hashes are recorded
in the evidence above. No latency percentile claim is made from these checks.
