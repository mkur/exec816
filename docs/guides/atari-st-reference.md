# Shared GEM samples on an Atari ST

[Guides index](README.md) · [Comparison record](../history/atari-st-reference.md)

Hatari runs the same object-tree generation and drawing functions used by the
native Exec AES baseline under EmuTOS and MagiC. This development setup targets
an ST with a 68000 at 8 MHz, 4 MiB RAM and a monochrome 640×400 display.

## Two Counter applications

To run two independent copies of the real Counter event loop under MagiC:

```sh
python3 tools/prepare_magic_counters.py --offline --run
build/magic-counters/launch-hatari.command
```

Use the prerequisites below. Omit `--offline` on the first preparation if the
SDK/MagiC reference inputs are not cached yet. The builder can bootstrap those
inputs through `prepare_st_reference.py`. `--output`, `--cache`, `--hatari` and
`--rom` select other local paths.

The launcher fast-forwards boot and switches to normal speed once both counters
are running. Each window updates about once per second, including the inactive
window. Click either title bar to change focus, or its close box to close that
Counter. Cmd+Q quits Hatari on macOS; AltGr+Q elsewhere. F12, possibly Fn+F12,
opens Hatari's settings. Close this demo before starting another instance.

MagiC launches the same `COUNTER.PRG` twice with `shel_write(1,1,100,...)`, its
parallel execution mode. Arguments `1` and `2` choose the titles and positions.
Both programs run the unchanged `examples/gem-counter/counter.c`, including
`evnt_multi`, visible-rectangle clipping and UPDATE handling. The startup wrapper
uses black ink on white paper and the SDK adapter selects an 8×8 font cell.
The MagiC kernel, AES, VDI and drivers are unchanged. A small resource-free
launcher occupies the desktop slot, avoiding MagxDesk's host-folder API issue
described below.

The recorded development run has distinct application IDs 2/3 and window handles
1/2. Both visible counts advance from 14 to 26. Counter 1 remains inactive while
its model and repaint counts advance; 35 digit pixels change in each window
between the two captured frames. The interactive launcher also passes a check
that both counters advance at normal speed after fast-forward boot. See the
[recorded evidence](../development/magic-counters.json).

The wrapper logs progress outside UPDATE, immediately before each event wait.
This is functional observation, without a performance claim. Automated checks
require independent identities, continuing count/paint progress, inactive-window
painting and changed digit pixels in both windows. Captured reports, PNGs and
framebuffers remain in `build/magic-counters/capture/` across interactive launches.
Live reports are written to `drive-c/COUNT1.LOG` and `COUNT2.LOG`. Build identities
and hashes are in `build.json`; interactive speed verification is in
`interactive-check.json`.

The bounded capture does not test dragging, menus, occlusion/exposure or normal
application retirement. It is a MagiC reference demonstration, separate from
the Exec816 boot demo. Native Exec code and fixed/root/kernel/idle/per-Task
bank-zero reservations change by **0 bytes**, including guards, alignment and
unused capacity.

## Original Text Viewer on MagiC

The original `examples/gem-text/text.c` and `document.c` run as an ordinary
MagiC application beside Counter. Both application sources are compiled directly,
without changes. Use the SDK/Hatari prerequisites below, plus mtools:

```sh
brew install mtools
python3 tools/prepare_magic_text.py --offline --run
build/magic-text-viewer/launch-hatari.command
```

Omit `--offline` if the shared reference inputs are not cached. The builder
accepts the same `--cache`, `--output`, `--hatari` and `--rom` overrides as the
Counter setup. `--run` performs a bounded development check and closes Hatari;
the generated launcher opens the interactive example. Boot and initial loading
fast-forward, then normal speed resumes with `STORY.TXT` visible. This setup
retains the pinned ST monochrome machine. Its resident launcher installs the
upstream US primary keyboard tables and keeps their storage live.

Space pages down; Shift-Space pages up; Up/Down scroll one line. `O` opens
MagiC's native file selector on A:. Its **Undo** shortcut cancels; Escape clears
the filename field. On a Mac without Undo, use the selector's Cancel button.
Return accepts a filename. Escape in the viewer cancels a pending replacement
load. `Q` or the closer exits. Counter remains an independent application after
the viewer closes. Hatari quit/settings shortcuts are the same as above.

`documents.st` is a read-only 720 KiB FAT12 floppy in A:. The adapter maps the
viewer's `SYS:` paths to A: and selects A: as its current drive. `STORY.TXT` has
901 lines; `SMALL.TXT` is a two-line replacement; `BIG.TXT` exceeds the viewer's
64 KiB limit. Programs and observations remain on the private host-folder C:.
The native filesystem lets MagiC's selector enumerate its own directory;
Hatari's host-folder interception does not supply all of MagiC's internal file
services. Refreshing the build recreates the example floppy.

The ST adapter maps the loader's allocation and file calls to TOS/libc/GEMDOS,
and UPDATE to real `wind_update`. Exec's presentation journal, preserved-window
request and extended diagnostic channel have no corresponding service here.
The adapter hides/restores the software cursor around UPDATE, selects the
viewer's 8×8 VDI font, fits its menu to MagiC's system menu font, and explicitly
closes its window, menu and workstation before `appl_exit`. These are reference
bindings, not an Exec kernel or a general Exec compatibility layer.

The viewer retains four-row paint bands, 1 KiB loading steps and its original
640×240 window-sizing assumptions. Full-height ST resize/drag behavior is
outside this first port. The automated check covers actual keyboard paging,
line-scroll pixel correspondence, native selector Open/Cancel, missing and
oversize replacements, read cancellation, inactive Counter pixels and viewer
cleanup. It does not measure repaint speed or disk throughput. MagiC's modal
selector holds UPDATE, so another application's redraw can wait until it closes.

Build identities, screenshots, raw framebuffers and observations stay under
`build/magic-text-viewer/`; see the [development record](../history/magic-text-viewer.md).
This is separate from the OF816/Exec boot demo. Exec fixed, root/kernel, idle and
per-Task reserved bank-zero changes are all **0 bytes**, including guards,
alignment and unused capacity. The native viewer/loader sources are unchanged.

## Prepare and launch the object-tree sample

On the tested Apple Silicon Mac, install the prerequisites with Homebrew:

```sh
brew install hatari m68k-elf-gcc gcc
python3 tools/prepare_st_reference.py --run both
build/atari-st-reference/launch-magic.command
```

The tested versions are Hatari 2.6.1, m68k-elf GCC 16.2.0 and host GCC 16.2.0
(`gcc-16`). The builder requires that host compiler: Clang does not implement
the scalar storage order used by the SDK's host linker. It installs the pinned
[TOS/libc SDK](https://github.com/frno7/toslibc) locally under the output
directory. Exec's Action! and Calypsi compiler inputs stay unchanged.

The [machine-readable pins](../../toolchain/atari-st-reference.json) select
Hatari 2.6.1, its bundled EmuTOS 1.4 ROM, the author's 4 November 2026 MagiC
release, MagiC object-drawing source and the SDK revision. ROM and downloaded
file hashes are checked before use. An existing Hatari installation can be
selected with `--hatari PATH`; use `--rom PATH` if the exact ROM is elsewhere.
The initial SDK clone and missing downloads require network access. Subsequent
preparations can use `--offline`. `--output PATH` selects a private development
directory; Hatari debugger paths currently require no whitespace.

Use `launch-emutos.command` for the other OS. The sample draws three trees,
writes `C:\REPORT.TXT` and leaves the final tree visible. Hatari's F12 opens its
setup GUI; Cmd+Q quits on macOS (AltGr+Q elsewhere). macOS keyboards may require
Fn for F12. The launchers pass a private configuration and drive, leaving the user's
saved Hatari configuration alone.

`--run both` executes bounded captures and quits automatically; `--run magic`
or `--run emutos` selects one. Host execution speed in fast-forward mode is
irrelevant to the guest clock measurements.

## Outputs and shared source

All generated inputs and outputs stay under `build/atari-st-reference/`:

- `launch-magic.command` and `launch-emutos.command`: interactive launches.
- `installation.json`: resolved binaries, hashes, versions, source inputs and
  exact machine commands.
- `shared-sample/SAMPLE.PRG`: one optimized 68000 binary used on both OSes.
  `workload.inc` contains verbatim native `work`, `draw_objects` and `object_tree`.
- `runtime/reference-{magic,emutos}/`: private drive C, `hatari.log`, final PNG
  and raw monochrome framebuffer from automated runs.
- `results.json`: all observations and elapsed medians, discarding two warmups
  from each ten-call cohort. The guest clock has 5 ms resolution.
- Original MagiC ZIP, `MagiC-LICENSE.txt`, `magic-source/AESOBJ.S` and the SDK
  checkout: original inputs, source and upstream notices.

The builder reads the existing native fixture
[`magic_aes_baseline.c`](../../tests/programs/magic_aes_baseline.c) without
modifying it. The separate [ST adapter](../../tests/reference/atari-st/main.c)
supplies startup and observation; its bindings translate the existing GEM
declarations to TOS/libc AES/VDI traps. This is the sample's API subset. It does
not establish complete GEM application compatibility. The object-tree sample
does not run Counter's event loop; the separate two-Counter demo above does.
The object trees contain `G_BOX` objects, with 5, 33 and 9 nodes.

## Supported scope

MagiC boots through its original `MAGXBOOT` loader over EmuTOS. Hatari's host
folder GEMDOS drive lacks the extended file API used by MagxDesk, as documented
in the release's `INSTALL.TXT`. The private runtime replaces
`GEMSYS/GEMDESK/MAGXDESK.APP` with the resource-free sample, so it starts as the
desktop (application ID zero). The original release archive, MagiC kernel,
AES, VDI and drivers remain intact. Each capture checks the `MagX` cookie so a
failed MagiC boot cannot silently become EmuTOS evidence.

The reference exercises a single unobscured window, UPDATE entry/exit,
visible-rectangle enumeration, clipping and object drawing. It retains
screenshots and framebuffers. The recorded run's final 320×128 nested-tree
canvas matches exactly between the two ST systems after aligning work origins.
The runner does not assert pixel equivalence for every case or against Exec.
Normal application retirement, multiple GUI clients, event-loop behavior and
physical ST hardware remain outside the object-tree check. The separate demo
above establishes focused two-client Counter behavior. MagiC's attempted extended
640×240 colour mode produced incorrect rendering and is excluded. Use the
working monochrome configuration for this reference.

Primary upstream documentation:
[Hatari manual](https://www.hatari-emu.org/doc/manual.html),
[Hatari debugger](https://www.hatari-emu.org/doc/debugger.html),
[MagiC source and releases](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources).
