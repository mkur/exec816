# Window preservation development record

[History index](README.md) · [Implementation plan](../plans/gem4xe/window-preservation-plan.md) ·
[AES contract](../reference/aes.md#opt-in-window-preservation)

2026-10-14. Development scope; no hosted-system or hardware qualification claim.

## Implementation

WP1 separates title, client and remaining frame fragments before strip limiting.
An aligned visible client rectangle uses one asynchronous cache/backing copy;
frame composition stays within its sixteen-row scratch capacity. The presenter
prefers focused-window work after menu precedence, with round-robin background
repair and idle cache maintenance. IRQ/NMI and Task scheduling are unchanged.

WP2 adds `AES_WF_EXEC_PRESERVE` ($6001), set once before opening a window.
Successful restoration creates no new exposure obligation for participating
owners. Conventional owners still receive `WM_REDRAW`; misses and invalid images
retain the existing fallback. Prior pending content work is never cleared by
this policy. Menu save completion already retires exact manager damage; the
deferred bounding-union notification now applies only to conventional owners.
It is not used as proof of restored coverage.

WP3 opts in Files/Desktop, Counter, Control Panel, Calculator and Text. Scoped
updates avoid invalidating sibling folders. Counter gives VDI the whole logical
digit rectangle before visibility clipping. Text publishes a model-only update
once per newly queued damage batch before its multi-turn renderer; this uses an
additional existing BEGIN/END pair, without introducing another API or RPC
operation. Shared forms use a scoped update and invalidate borrowed pixels at
dismissal before the existing owner-repair notification. VDI/object bindings
accept a live UPDATE with no visible rectangles, including iconified clients:
they record logical changes without drawing into the tile.

## Focused checks

- Optimized desktop presentation: 117 emitted assertions and independent scene
  pixels; the same image's quiesced-failure replay passed 111 assertions.
- Optimized AES cache fixture: 178 C assertions and four native assertions;
  conventional and opted-in exposure, complete and
  partial updates, fully hidden model-only invalidation, scoped sibling updates,
  actual two-slot eviction, resizing, copied moves and mixed-policy menu
  restoration. The final case exercises VDI and object drawing on a closed
  zero-visible view (the same binding admission as an iconified view), checks
  that no paint completion is journalled, then reopens and checks exact pixels.
  Normal EXIT and guards remained intact.
- Packaged application walkthrough: covered Counter progress and revealed
  pixels; Panel pointer/keyboard input after moving; Calculator result 42;
  loaded Text bytes, scrolling and a shared selector's cancelled dismissal;
  application cleanup and HELLO/EXIT. This used the first package
  (`8096c712020235a3700d5b6a9aeeb1cb62939813dea9129015675f71385e6112`),
  before the final no-visible-rectangle binding adjustment. The final package
  separately passed the focus/menu observer and clean EXIT below.
- Generated AES definitions and focused host checks: desktop contract (5),
  calculator resource (1), demo packaging (12), desktop packaging (3).

Local evidence is under `build/window-preservation/`, outside the ZIP. The
fixture's old work-height expectation was updated to the already implemented
compact frame dimensions. An initial build using the debug host compiler hit
the 600-second compile timeout; the pinned release executable completed the
same development build. No compiler sources or pin changed. Demo tooling now
accepts `--release-compiler` for `--gem-desktop` and records that build profile.

## Matched focus and menu observations

`tools/measure_window_preservation.py --count 2` ran against the existing
`build/ram-desktop/demo` baseline (with `--conventional`) and the exact extracted
`build/window-preservation/demo-final` ZIP. Neither guest was patched. Both used
PAL, 65816 ×8, 4 MiB RAM, VBXE FX 1.26 at $D600 with private 512 KiB VRAM and the
ST mouse. The AltirraOS ROM SHA-256 was
`85a6e927038f401f05f0056fd41a062986cbf7e104c1ac135c248764c132c9a7`;
the bridge executable SHA-256 was
`a7defb3b8a471711b4f1fd679f3b8f8364a415494ae68f59be6628334713ca59`.
Compiler revision stayed `05c01f39ff3beef97af0e65b0a16666f5a1bd805`, with
Calypsi 5.18 for C clients. The manifests retain full inputs/configuration.

Client pixels and the whole window are checked separately against warm images;
the independent scene oracle checks the settled scene. Shell's blinking caret
cell is excluded. Time starts at physical input scheduling, including the
two-frame title-button hold, and is sampled once per PAL frame. These are two
observations per action, **not a p95 distribution or hardware measurements**.

| Focus action | Baseline median | Preserved median | Preserved maximum |
| --- | ---: | ---: | ---: |
| Shell client and whole window | 701.8 ms | 280.8 ms | 280.9 ms |
| SYS: client pixels | 1,002.9 ms | 641.9 ms | 641.9 ms |
| SYS: whole window | 1,263.6 ms | 1,163.3 ms | 1,163.3 ms |

Both samples used one Shell backing copy, versus eleven before. SYS: used one
38,106-byte client restore, versus twelve before, with **zero Files repaints,
zero cache captures and zero patches**. Previously each SYS: raise caused one
Files repaint and a 38,106-byte patch. The passive `COPYSTART` trace counted two
total copies during each SYS: interval, including the surrounding scene work,
versus fourteen before. Clicking the already active SYS: title changed none of
the counters.

| Keyboard menu action | Baseline samples | Preserved samples |
| --- | --- | --- |
| Open File | 400.9, 200.6 ms | 361.2, 200.3 ms |
| Switch File → View | 741.9, 220.5 ms | 361.0, 220.5 ms |
| Dismiss | 380.9, 140.5 ms | 260.7, 140.5 ms |

The first menu cycle fell back from the composite save to client snapshots;
the second reused the menu save. Neither preserved cycle repainted Files or
maintained its client snapshot. Warm composite-save latency is essentially
unchanged. The improvement is larger when the old path would have repainted
the application. Popup construction/input admission were not changed.

Client completion improves substantially, while SYS:'s remaining frame work
still takes roughly another half-second in this arrangement. This plan does
not make that full-window completion instant. Keep frame-work reduction as a
separate measured follow-up; do not increase the sixteen-row frame scratch limit.

Reports: `demo-final/window-preservation-results.json`, the baseline's report
of the same name, `walkthrough/cache-desktop-results.json`,
`aes-cache/results.json`, `presentation/presentation-success.json` and
`presentation/presentation-results.json` (failure replay), under the local build
directories. Both focus runs finished with runtime status zero and intact guards.

## Memory

All slices add **0 fixed bank-zero bytes, 0 per public Task and 0 idle Task
bytes**, counting guards, alignment and reserved capacity. VRAM reservations
are unchanged. Upper-RAM state adds six one-byte AES window policies, one painter
partition index and two bytes in each Text application instance. There are no
new per-window bitmaps, region arrays, queues, Tasks or signals.
The baseline and final `memory.json` budgets match exactly: fixed runtime 10,528,
public Tasks `[1824,1600,1600,1600,1600,1600,2848,2848]`, idle 800 and total
runtime 26,848 bytes excluding the OS, 58,080 including it.

## Packaged demo

Built through:

```sh
python3 tools/build_demo.py --gem-desktop --release-compiler \
  --output build/window-preservation/demo-final
```

The 630,765-byte `exec816-demo.zip` contains OF816, five-second autoboot, matching
system/work disks, the pinned AltirraOS ROM and notices. Build inputs, manifests,
screenshots and test output remain outside it. ZIP SHA-256:
`a3d93292f287574ab6f42863063e8b929f5a9276ce2e63dfd5ab59d2dd476536`.

```sh
open /Users/michalkurcewicz/action/exec816-public/build/window-preservation/demo-final/launch-altirra.command
```
