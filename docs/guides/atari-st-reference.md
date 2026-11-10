# Shared GEM sample on an Atari ST

[Guides index](README.md) · [Comparison record](../history/atari-st-reference.md)

Hatari runs the same object-tree generation and drawing functions used by the
native Exec AES baseline under EmuTOS and MagiC. This development setup targets
an ST with a 68000 at 8 MHz, 4 MiB RAM and a monochrome 640×400 display.

## Prepare and launch

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
not establish complete GEM application compatibility or run Counter's event
loop. The object trees contain `G_BOX` objects, with 5, 33 and 9 nodes.

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
physical ST hardware remain outside this check. MagiC's attempted extended
640×240 colour mode produced incorrect rendering and is excluded. Use the
working monochrome configuration for this reference.

Primary upstream documentation:
[Hatari manual](https://www.hatari-emu.org/doc/manual.html),
[Hatari debugger](https://www.hatari-emu.org/doc/debugger.html),
[MagiC source and releases](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources).
