# Exec816 text-console demo

An interactive shell occupies the upper 18 rows of the 40×24 screen. The lower
six rows show an independent prime search. Commands load from disk; two external
commands can exchange bytes through an anonymous pipe.

<img src="../images/demo-boot.png" alt="Exec816 boot messages and TASKS listing, with the prime task running below" width="672" style="image-rendering: pixelated;">

The first screenshot is taken after `TASKS`, before other commands scroll the
boot messages out of view.

## Install and boot

Download `exec816-demo.zip` from [Releases](https://github.com/mkur/exec816/releases)
and extract it. The `exec816-demo/` folder
contains `Exec-of816.xex`, `system.atr`, `altirraos-816.rom`, `README.txt`, license
notices and `SHA256SUMS`. Keep these files together and follow the included boot
instructions. Building from source is an [optional alternative](#build-from-source-optional).

Use [AltirraSDL](https://github.com/ilmenit/AltirraSDL); upstream Altirra will not
run this build. Follow the [settings table and ROM import steps](../../README.md#installation)
in the main README. Open **System → Configure System…** to configure the machine;
the UI labels the 8× CPU setting **65C816 (14.28MHz)** and 63 high banks **4032K**.
The tested configuration is recorded in the [platform pin](../../toolchain/altirra-shell-paced.json).

In **System → Configure System… → Computer → Boot**, uncheck **Unload disks
when booting new image**. Open **File → Disk Drives…**, use the **…** button on
the **D1:** row to mount `system.atr`, and set **Emulation level** to
**Generic + 57600 baud**. In the settings window's **Computer → Acceleration**
page, **SIO Patch** and **D: burst I/O** must both be unchecked.
Choose **File → Boot Image…** and select `Exec-of816.xex`.
Leave the keyboard alone to enter the shell after five seconds, or press a key
to enter Forth and type `EXEC816` when ready. The ATR is a data disk; boot the
XEX. A missing disk or wrong drive profile can leave the SIO driver offline
after a timeout; correct the settings and cold-boot again.

The supplied system disk uses SDFS 2.1 with 128-byte sectors. Filesystem writes
remain unsupported.

The default sector cache keeps 64 KiB of recently read disk data in upper RAM,
shared across files and commands. Repeated commands can avoid SIO while still
loading and relocating normally. Tags/control add about 6.2 KiB; bank-zero
reservations are unchanged. Keep mounted media unchanged until unmount/reset.
The included [OF816 monitor](boot-monitor.md) can change capacity before boot, for example
`decimal 0 CACHE-BLOCKS! EXEC816` to keep only the original scratch sector.
If allocation fails, the shell reports the fallback and remains usable.

## A short walkthrough

Wait for `SYS: -> D1: ready, read-only` and the `>` prompt. The lower tile should advance
without typing. Run these commands in order, starting with `TASKS` to reproduce
the first screenshot:

```text
TASKS
MOUNT
CD SYS:
DIR
HELLO
TYPE README.TXT
MEM
HELLO | WC
CAT STORY.TXT | WC
```

The second screenshot is taken after the last command above:

<img src="../demo.png" alt="Demo walkthrough showing memory information and HELLO and CAT pipelines while the prime task continues" width="672" style="image-rendering: pixelated;">

Type `HELP` to list the shell's built-in commands:

```text
HELP ECHO CD DIR TYPE MEM TASKS VER MOUNT DEVICES PATH EXIT
```

`HELLO | WC` prints `1 3 17`. `CAT STORY.TXT | WC` prints `24 133 746`.
The [command toolbox](toolbox.md) also supplies CMP, CKSUM, HEXDUMP, HEAD, GREP,
LIST and MORE. Try `HEAD STORY.TXT LINES 5`, `LIST NAMES`, or `MORE LONG.TXT`.
In MORE, Space advances a page, Return a displayed row, and Q quits.

The columns are lines, words and bytes. Now run `CAT LONG.TXT | WC` and press
**BREAK** while LONG.TXT is being read. Both pipeline stages retire before the
prompt returns, while the prime search continues. Then run `HELLO | WC` again.

Input can come from a file and final output can be discarded:

```text
CAT <STORY.TXT | WC
CAT STORY.TXT | WC >NIL:
```

Run `MEM`, repeat a few pipelines, and run `MEM` again to observe reclaimed
command memory. `TASKS` at the prompt shows the shell, console, filesystem,
SIO and prime Tasks. A pipeline adds two temporary Tasks, using seven of the
eight reserved slots. The prime search checks candidates up to 10,000 and then
starts a new numbered pass; its latest prime eventually reaches 9,973.

`EXIT` stops and collects the prime Process, closes both tiles and restores the
OS display and input state.

## Scope

There is one foreground pipeline of exactly two external commands. Resident
commands such as TYPE, DIR and ECHO cannot be pipeline stages. Quoted `|` is
literal text. Input redirection belongs on the left and output redirection on
the right. File writes, longer pipelines, scripts and background shell syntax
are outside this demo. A failed stage reports the first failure in command order.

This is a development play image, with focused raw/optimized slice checks and
an optimized integration walkthrough. General compiler qualification and the
full release matrices remain separate. The [console refactor record](../history/console-refactor-implementation.md)
describes the implemented scrolling work and its focused checks.

## Stable system paths

SYS names the system volume even when OF816 selects another drive. The shell
starts with a real directory lock on SYS. Physical names remain canonical in
`CD` output and `MOUNT` lists each real volume once.

```text
CD SYS:WORK
HELLO
HEAD SYS:STORY.TXT LINES 3
HEAD MISSING
HEAD ?
CAT SYS:STORY.TXT | WC
CD SYS:
```

The commands above work while the current directory is WORK. Bare command
names search CurrentDir and then SYS: through the default [PATH](shell.md#path).
If the system disk failed to mount,
the console stays usable; insert the matching disk and use `CD SYS:` to retry.
To choose D2 before startup, see the [OF816 guide](boot-monitor.md).

## Build from source (optional)

From the repository root, with the [build prerequisites](../contributing/building.md)
installed:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
python3 tools/build_demo.py
```

The file to share is `build/demo/exec816-demo.zip`. It contains one
`exec816-demo/` folder with the boot XEX, system disk, ROM, a short boot guide,
two license notices and `SHA256SUMS`. Build intermediates and test output stay
in the development directory. The [distribution guide](../demo-distribution.txt)
has self-contained boot instructions; its disk and drive names are filled in
when packaging.

To refresh the ZIP from an existing OF816 build without recompiling:

```sh
python3 tools/package_demo.py
```

For a custom build directory, pass `--bundle <build>/of816 --output <build>/exec816-demo.zip`.

Development artifacts remain in `build/demo`:

- `of816/Exec-of816.xex`: demo with the OF816 boot monitor and five-second autoboot.
- `of816/system.atr`: matching disk to mount with the OF816 image.
- `of816/altirraos-816.rom`: pinned AltirraOS 3.44 ROM for 65C816.
- `of816/ALTIRRAOS-LICENSE.txt` and `of816/OF816-LICENSE.txt`: upstream notices.
- `of816/of816.json`: monitor build inputs, memory layout, media and ROM hashes.
- `program.xex`: direct native entry used by development fixtures.
- `system.atr`: read-only SDFS data disk with HELLO, CAT, WC, the command toolbox and sample text.
- `system.verification.json`: independent producer/read-back hashes for every
  file in SDFS builds.
- `demo-manifest.json`: source, toolchain, machine, media and artifact hashes.
- `README.md`: this guide.

The default uses SDFS 2.1 with 128-byte sectors. To build 256-byte media for
a capable peripheral, pass `--sector-bytes 256`; the mount descriptor changes
with the disk geometry. To retain MyDOS, pass `--format mydos --output build/demo-mydos`.
Both filesystem options use the filename `system.atr`; the format and geometry
are recorded in the build manifests. Filesystem writes remain unsupported.

Pass `--bitmap-console` for the optional [80×30 bitmap console preview](bitmap-console.md).
The ZIP then also contains `bitmap-console/Exec-bitmap-console.xex`, its matching
`system.atr` and GEM/font notices. Select that XEX explicitly with VBXE FX 1.26
enabled. The normal OF816 boot remains the default; responsiveness acceptance
for the bitmap preview remains open.

To recapture both screenshots from an existing bundle, run:

```sh
python3 tools/test_demo.py --screenshots
```

This boots the packaged OF816 image, types the commands above through physical
keyboard input, saves `build/demo/boot-tasks.png` and `build/demo/walkthrough.png`,
then exits. `build/demo/screenshots-results.json` records the command sequence,
screen text, image hashes and focused execution checks.
The [published capture record](../development/demo-screenshots.json) identifies
the exact image and command sequence shown here.
