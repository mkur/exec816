# Original MagiC viewer scrolling reference

[Build and launch](../guides/atari-st-reference.md#compare-scrolling-with-original-mgview) ·
[Development evidence](../development/magic-scroll-comparison.json)

The comparison uses the original 10,052-byte `MGVIEW.APP` already supplied by the
pinned MagiC release. Its bytes are copied unchanged onto a native FAT12 floppy
and independently extracted with mtools for hash verification. It runs as an
ordinary MagiC process with `A:\STORY.TXT` on its command line. Its application,
window and rendering code are neither rebuilt nor instrumented.

The second session uses the existing shared Text Viewer port. Each session has
its own private host C: and read-only native A: image; both use the same MagiC,
EmuTOS, Hatari, 8 MHz 68000 and 4 MiB monochrome configuration. Both read exactly
the same 56,746-byte/901-line text fixture. The resident launcher retains the US
primary keyboard tables. Counter is disabled in both comparison sessions, and
fast-forward ends after document startup. The original viewer readiness check
uses public AES window ownership/work-area queries.
The port's existing diagnostic wrapper is compiled to stop logging once its
first document is fully painted. The pixel check also requires its log to remain
unchanged across scrolling; the original MGVIEW has no injected observer.

MGVIEW's default 8×16 cells and 488×336 work area are retained. The shared viewer
keeps 8×8 cells and its 460×172 work area, including padding/status. These
differences prevent treating this visual setup as a normalized timing benchmark.
No numerical speedup, latency or throughput claim is made.

## Development checks

`tools/prepare_magic_scroll.py --offline --run` launches each actual binary,
requires the MagX cookie and a viewer-only session, changes to normal speed,
and injects Down followed by Up. Raw monochrome framebuffer checks establish
that a one-line scroll copies the old second row's pixels to the first row and
that scrolling back restores the first row. Both applications visibly change
glyph pixels; state changes alone are insufficient. Captured frames, launch logs,
machine commands and hashes are retained under `build/magic-scroll-comparison/`.

The existing viewer/Counter workflow is also rerun because the shared desktop
launcher gains conditional comparison modes. Its default still launches Counter
and the ported viewer with the prior arguments. Focused host checks cover the
existing reference parsing and Counter observation code. This is development
execution evidence, not qualification of physical ST hardware or Exec.

The upstream
[MGVIEW README](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/APPS/MGVIEW/README.TXT)
identifies the program as MagiCDesk's text-viewer helper. Its
[window routines](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/APPS/MGVIEW/SRC/WINDOWS.C)
are available for subsequent analysis of scrolling boundaries. This slice adds
the working reference without changing either application's scrolling algorithm.

No Exec runtime, ABI, pool or drawing policy changes, and the OF816 demo is not
rebuilt. Fixed, root/kernel, private idle and per-public-Task reserved bank-zero
deltas are all **0 bytes**, including guards, alignment and unused capacity.
Exec VRAM reservation delta is **0 bytes**. The existing 384-byte resident MagiC
keyboard-table allocation remains the same in both comparison sessions.
