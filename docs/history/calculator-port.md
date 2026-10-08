# GEM4XE calculator port

[History](README.md) · [Plan](../plans/gem4xe/calculator-port-implementation-plan.md) ·
[Application guide](../guides/aes-applications.md#gem4xe-calculator) ·
[AES contract](../reference/aes.md)

The port adds a disk-loaded `CALC.APP` and `SYS:CALC.RSC` to the GEM desktop.
It retains the pinned GEM4XE integer arithmetic, keypad IDs and resource layout.
The modal form loop becomes an ordinary movable, closable window with local
form handling and changed-object drawing. Every loaded copy owns its state,
resource and workstation. Files and the shell use the existing Process lifetime.

The independent calculator source pin is
`fbfea9b0b1233a5d659d5ec583c63f863cceadfa`. Extraction, adaptation and generation
occur under `build/`; the donor checkout remains untouched. Existing AES/VDI and
compiler pins are unchanged. The package includes the donor's application
licence and provenance alongside the existing GUI notices.

## Slices

- [CAL1](../development/calculator-cal1.json): packed TEDINFO, noneditable
  G_TEXT/G_BOXTEXT drawing, outward borders, clipping and full upper-memory
  pointers. Small raw/optimized layout/access/measurement probes, 41 object
  checks, three text pixel snapshots and 22 retained-widget stages pass.
- [CAL2](../development/calculator-cal2.json): reproducible flat calculator
  resource, TED fixup and normalized string lengths. Both SDFS and MyDOS pass
  73 resource checks, including sharing, failed replacement and repeated cleanup.
- [CAL3](../development/calculator-cal3.json): windowed APP, physical arithmetic
  and keyboard/mouse handling, range/error transitions, six display snapshots,
  dragging/exposure, repeat lifetimes and heap restoration beside Counter.
- [CAL4](../development/calculator-cal4.json): extracted-ZIP Files launch/Stop/
  reload, shell RUN with idle collection, two independent instances and resources,
  window-capacity failure, missing/bad resources, stop before entry, armed close
  and session exit with a live child/popup. The old cartridge repeats the broader
  desktop regression; the new cartridge checks cold boot, all three initial apps,
  disk HELLO and EXIT. The default OF816 shell/prime smoke also passes.

416 host tests run, with four historical-source skips. Full-scene and button
comparisons use independent rasterization. No additional release matrix ran.

CAL1's height-fit helper uses a comparison instead of division. A focused probe
found that Calypsi 5.18's optimized signed-division truth test branched on stale
flags from `_Div16`; raw emission produced the expected glyph count. Nonnegative
height fitting needs only `height >= cell_height`. The adapter patch removes
that unnecessary division; neither the compiler runtime nor actionc was changed.
The small raw/optimized regression remains part of the recorded checks.

## Memory and cartridge cost

All slices add **zero reserved bank-zero bytes**: fixed 0, each public Task 0,
and private idle 0, including guards, alignment and unused capacity. Calculator
uses existing Task, layer and AES slots. The three startup applications remain
Panel, Counter and Files; close a window before launching Calculator.

| Item | Bytes |
| --- | ---: |
| CALC.APP on disk | 6,691 |
| Private image span, including bank gap/BSS | 65,778 |
| Image backing request (`span + 65535`) | 131,313 |
| Rounded image backing | 131,320 |
| Image metadata, rounded | 48 |
| CALC.RSC on disk | 650 |
| Resource allocation with metadata, rounded | 672 |
| Private calculator window state within the image | 46 |
| Temporary APP loading buffer, rounded | 6,696 |

The existing Process, AES and VDI allocations are additional per-app costs.
The APP verifies relocation at all 62 legal bank bases. CAL3's narrowest measured
public-Task stack margin is 81 bytes above the 256-byte interrupt reserve.
The calculator desktop walkthrough reaches a 51-byte minimum margin; the broader
existing desktop regression reaches 45 bytes. Guards remain enabled.
Calypsi has no Action! per-routine stack check; these observations do not qualify
arbitrary application depth.

The shared GUI grows from 149,030 to 152,221 serialized bytes as it gains text
support. Calculator arithmetic and state are excluded from that component and
the cartridge. The OF816 XEX is 975,801 bytes, leaving 56,390 bytes of Atarimax
capacity, versus LG6's 56,444 bytes: 54 bytes less and above the 32 KiB goal.

Files first opens its existing child-collection timer when it launches an app.
A focused free-list audit identifies all 112 newly held upper bytes: one reply
port and two timer requests. Repeated launch/Stop comparisons use that warmed
baseline; this is Files-owned storage, released by its AES teardown.

On the pinned Generic + 57600 SIO profile, the shell is ready 136.08 seconds
after native entry and all three initial apps at 140.34 seconds. LG6 measured
133.16 and 137.30 seconds respectively. Add the unchanged five-second OF816
countdown. Calculator is not part of startup.

Six physical press-to-matching-button samples span 33.85–140.45 ms, with a
140.33 ms median. These are frame-granular smoke observations with Counter
and Files present, not a p95 comparison or a reopened latency optimization.
Input redraws target the changed key/focus and display; WM_REDRAW repairs the
clipped tree. Settled scene comparisons pass, while transient/subframe flicker
is not excluded by this sampling.

The distributable artifact is
`build/calculator/cartridge-distribution/exec816-demo.zip`. Its 23 members are
boot images, matching disks, the pinned ROM, guides, notices and checksums.
The build directory retains manifests, listings and test output separately.

## Scope

Validation uses the development tier and the pinned emulator/ROM. It is not
hardware or full release qualification. The calculator is integer-only; editable
TEDINFO fields, modal forms, desk accessories and donor binary compatibility are
not added. The pointer-button latency gates remain separate from this port.
