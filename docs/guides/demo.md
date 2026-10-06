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
contains `Exec-of816.xex`, `system.atr`, `work.atr`, `altirraos-816.rom`, `README.txt`, license
notices and `SHA256SUMS`. Keep these files together and follow the included boot
instructions. Building from source is an [optional alternative](#build-from-source-optional).

Use [AltirraSDL](https://github.com/ilmenit/AltirraSDL); upstream Altirra will not
run this build. Follow the [settings table and ROM import steps](../../README.md#installation)
in the main README. Open **System → Configure System…** to configure the machine;
the UI labels the 8× CPU setting **65C816 (14.28MHz)** and 63 high banks **4032K**.
The tested configuration is recorded in the [platform pin](../../toolchain/altirra-shell-paced.json).

In **System → Configure System… → Computer → Boot**, uncheck **Unload disks
when booting new image**. Open **File → Disk Drives…**, use the **…** button on
the **D1:** row to mount `system.atr`. Mount a disposable copy of `work.atr`
in **D8:** with writes enabled; both disks must be present. Set **Emulation level** to
**Generic + 57600 baud**. In the settings window's **Computer → Acceleration**
page, **SIO Patch** and **D: burst I/O** must both be unchecked.
Choose **File → Boot Image…** and select `Exec-of816.xex`.
Leave the keyboard alone to enter the shell after five seconds, or press a key
to enter Forth and type `EXEC816` when ready. The ATR is a data disk; boot the
XEX. A missing disk or wrong drive profile can leave the SIO driver offline
after a timeout; correct the settings and cold-boot again.

The supplied SDFS 2.1 system disk has 2,880 sectors of 256 bytes (720 KiB
nominal capacity), equivalent to 80 tracks, two sides and 18 sectors per track. The
disposable WORK: disk also has 2,880 sectors of 256 bytes (720 KiB nominal capacity).
SYS: is read-only; WORK: is explicitly writable. Try:

```text
ECHO saved >WORK:OUT.TXT
CAT WORK:OUT.TXT
COPY SYS:STORY.TXT WORK:COPY.TXT
CMP SYS:STORY.TXT WORK:COPY.TXT
```

CMP succeeds silently. Redirection immediately creates or truncates its target;
a later command failure does not restore old contents. Use disposable copies of
WORK: and see [filesystem writes](../reference/filesystem-writes.md) for limits.

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
HELP ECHO CLS CD DIR TYPE MEM TASKS VER MOUNT DEVICES PATH ALIAS UNALIAS
RUN JOBS BREAK EXIT
```

The prompt supports insertion, Backspace and Ctrl-A/E for beginning/end.
Ctrl-B/F moves left/right, Ctrl-U clears the line, Ctrl-K deletes to the end,
and Ctrl-W deletes the preceding word. Ctrl-P/N browses the last ten commands.
Atari cursor chords work too: Ctrl-+/Ctrl-* moves left/right and Ctrl--/Ctrl-=
browses history. Moving past the newest command restores your draft. See the
[shell guide](shell.md#editing-and-break) for the complete editing rules.

`HELLO | WC` prints `1 3 17`. `CAT STORY.TXT | WC` prints `108 518 3171`.
The [command toolbox](toolbox.md) also supplies CMP, CKSUM, HEXDUMP, HEAD, GREP,
LIST and MORE. Try `HEAD STORY.TXT LINES 5`, `LIST NAMES`, or `MORE LONG.TXT`.
In MORE, Space advances a page, Return a displayed row, and Q quits.

The shell can keep eight command aliases for its session. Try `ALIAS LS "DIR
SYS:"`, then `LS`; `ALIAS` lists the definition and `UNALIAS LS` removes it.

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
SIO and loaded command Tasks. The optional demo starts C:PRIMES through RUN;
the bitmap shell starts full-screen until you enter RUN PRIMES yourself.
A pipeline adds two temporary Tasks, using seven of the
eight reserved slots. The prime search checks candidates up to 10,000 and then
starts a new numbered pass; its latest prime eventually reaches 9,973.

JOBS shows the background Process identity. `BREAK identity` requests stop;
pane closure restores the full shell, including its edited line.
`PRIMES PASSES 1` runs one foreground pass and returns; with PASSES omitted
or zero, it continues until BREAK. `RUN PRIMES PASSES 1` completes without
waiting for another shell command. The display updates only changed numbers.

`EXIT` stops and collects the prime Process, closes its pane and restores the
OS display and input state.

## Scope

There is one foreground pipeline of exactly two external commands. Resident
commands such as TYPE, DIR and ECHO cannot be pipeline stages. Quoted `|` is
literal text. Input redirection belongs on the left and output redirection on
the right. RUN supports one loadable background command with NIL default streams,
PATH/aliases and file redirection. Background pipelines, longer pipelines and scripts
are outside this demo. A failed stage reports the first failure in command order.

This is a development play image, with focused raw/optimized slice checks and
an optimized integration walkthrough. General compiler qualification and the
full release matrices remain separate. The [console refactor record](../history/console-refactor-implementation.md)
describes the implemented scrolling work and its focused checks.

## Commands for the work disk

The [toolbox](toolbox.md) includes COPY, TEE, DELETE, RENAME and MAKEDIR:

```text
MAKEDIR WORK:NOTES
COPY SYS:STORY.TXT WORK:NOTES/ONE.TXT
RENAME WORK:NOTES/ONE.TXT WORK:NOTES/TWO.TXT
CMP SYS:STORY.TXT WORK:NOTES/TWO.TXT
CAT SYS:STORY.TXT SYS:STORY.TXT | WC
COPY SYS:STORY.TXT WORK:NOTES/THREE.TXT
LIST WORK:NOTES/*.TXT NAMES
HELLO | TEE WORK:LOG.TXT
HELLO | TEE WORK:LOG.TXT APPEND
DELETE WORK:NOTES/TWO.TXT WORK:NOTES/THREE.TXT
DELETE WORK:NOTES
```

COPY and TEE create or truncate their destination; APPEND preserves it and adds
bytes at EOF. COPY needs an exact filename; CAT concatenates up to eight exact
files. LIST matches `*` and `?` only in its final path component. DELETE accepts
one to eight exact files or empty directories, and RENAME stays within one
directory. Each accepts a sole unquoted `?` for help.

You can give the writable directory a short logical name:

```text
MAKEDIR WORK:DATA
ASSIGN DATA: WORK:DATA
COPY SYS:STORY.TXT DATA:STORY.TXT
CAT DATA:STORY.TXT
ASSIGN
DELETE DATA:STORY.TXT
ASSIGN DATA:
DELETE WORK:DATA
```

`ASSIGN` lists up to four system-wide directory mappings. It stores a validated
physical path without keeping a lock on the disk; see the
[ASSIGN contract](../reference/assigns.md).

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
names search CurrentDir and then C: through the default [PATH](shell.md#path).
The supplied commands live in SYS:C; startup assigns C: there using one of four
assignment slots. `C:HELLO` and `SYS:C/HELLO` are explicit command paths.
`PATH RESET` restores the C: search entry without changing its assignment.
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
`exec816-demo/` folder with the boot XEX, system and work disks, ROM, a short boot guide,
license notices and `SHA256SUMS`. Build intermediates and test output stay
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
- `of816/system.atr`: matching system disk to mount with the OF816 image.
- `of816/work.atr`: disposable writable WORK: disk for D8:.
- `of816/altirraos-816.rom`: pinned AltirraOS 3.44 ROM for 65C816.
- `of816/ALTIRRAOS-LICENSE.txt` and `of816/OF816-LICENSE.txt`: upstream notices.
- `of816/of816.json`: monitor build inputs, memory layout, media and ROM hashes.
- `program.xex`: direct native entry used by development fixtures.
- `work.atr`: disposable writable 720 KiB disk, with the same format and 256-byte sectors.
- `system.atr`: 720 KiB read-only SDFS data disk with HELLO, CAT, WC, the command toolbox and sample text.
- `system.verification.json`: independent producer/read-back hashes for every
  file in SDFS builds.
- `demo-manifest.json`: source, toolchain, machine, media and artifact hashes.
- `README.md`: this guide.

The default system disk is 720 KiB in SDFS 2.1 with 256-byte sectors. Pass
`--system-kib 360` for a 360 KiB system disk, or `--sector-bytes 128` for
128-byte system media; the sector count adjusts to preserve the selected capacity.
To retain MyDOS, pass `--format mydos --output build/demo-mydos`. Large MyDOS
images use an extended VTOC and 16-bit file links. The mount descriptor always
matches the chosen disk geometry.
Both filesystem options use the filename `system.atr`; the format and geometry
are recorded in the build manifests. WORK: uses the same format and always has
2,880 sectors of 256 bytes (720 KiB), regardless of the SYS: geometry.
Keep SYS: on D1–D7; D8 is reserved for WORK:.

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
