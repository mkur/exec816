# CG2 implementation plan

[Design](colour-files-design.md) · [Roadmap](../../roadmap.md#colour-gem-desktop-roadmap)

Status: implemented; focused development checks pass. This is not release qualification.

1. Extend generated frame/AES constants for INFO, FULLER and WM_FULLED. Add
   copied information text, matching work geometry and release-to-activate
   fuller handling. Add menu_icheck and check-mark rendering.
2. Count paired physical clicks in the existing input route. Expose counts to
   ordinary button/multi waits; preserve single-click callers and loss handling.
3. Add stock icons, grid/list layout, sorting, status totals and full/restore to
   Files. Keep selection redraws confined to their cells and release directory
   locks before mutations. Preserve existing Path/New Folder/Rename behavior.
4. Run focused emitted frame, input, icon/list and resource checks, including
   resize/scroll/exposure, keyboard and mouse opening, Cancel and clean exit.
   Build through tools/build_demo.py with OF816 and exercise the resulting disk.
   Record development results, median/p95 feedback and reserved memory deltas.

[Development evidence](../../development/colour-gem-cg2.json): physical icon/list,
sort, double-click, full/restore, resize, directory dialogs, native launch, shell
and orderly exit checks pass on the OF816 ZIP. The pointer fixture passes 141
checks; raw/optimized context/layout checks pass. Full-screen expectations are
computed independently from application OBJECTs and window state.

Forty icon selection samples measure **180.4 ms median / 200.6 ms p95** from
release submission to matching two-cell scanout, using frame-granular polling.
The first 36-pixel object layout measured 200.6 / 240.7 ms; the final 32-pixel
objects use one widget unit. Panel press feedback in the final run measures
100.3 / 100.3 ms. These are observed distributions, not a new latency guarantee;
icon selection remains an optimization opportunity after the desktop is complete.

Reserved bank-zero changes relative to TX7: **0 fixed, 0 for every public Task,
0 idle**, including guards, alignment and unused reservation. The smallest
observed public-Task margin above its interrupt floor is 260 bytes; idle has
121 bytes. The renderer reuses its existing VRAM scratch. Copied information
strings, icon descriptors and click state use upper RAM.
