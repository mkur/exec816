# OF816 boot monitor

`Exec-of816.xex` in the distribution ZIP starts a real OF816 Forth interpreter under the
pinned AltirraOS 65816 ROM. It runs before the main Exec payload loads. After a
five-second countdown it resumes loading the selected image and enters Exec's
existing hosted startup.
Press a key during the countdown to stay in Forth; type `EXEC816` to boot later.

```text
AltirraOS → small bootstrap → OF816 countdown → load Exec816 → shell
                                  ↓ key            ↑
                              OF816 prompt → EXEC816
```

The bundle contains the monitor and kernel in one XEX. It does not read a
separate kernel file from disk. OF816 is used as a boot monitor; its upstream
full Open Firmware layer is not included.

The bootstrap initializes the default settings and loads OF816. An INITAD
callback enters the monitor while the XEX or cartridge reader is paused.
`EXEC816` and countdown expiry restore that reader's context and return with
RTS. The reader loads the remaining native payload; the final RUNAD enters the
validated Exec image. OF816's keyboard and vectors are released before loading
resumes, and its retired interpreter is not restarted after Exec exits.

`Exec816 boot`, `Loading OF816` and `Loading Exec816` show progress on the ROM
text console. Each dot represents 16 KiB of completed copy/zero-fill work;
the final partial block also prints a dot. The monitor appends its banner and
countdown without clearing earlier text. The bitmap console starts later when
the selected Exec application opens it. Remote image loading is not provided.

The sector cache defaults to 64 KiB of upper-RAM data storage. At the Forth
prompt, select a different capacity for this boot:

```forth
decimal
CACHE-BLOCKS@ .       \ current request: 512
128 CACHE-BLOCKS!     \ 16 KiB of payload
0 CACHE-BLOCKS!       \ disable the larger cache
512 CACHE-BLOCKS!     \ restore the 64 KiB default
EXEC816
```

Zero also disables the optional 32-entry SpartaDOS extent cache. With caching
enabled, that table uses 2,304 allocated upper-RAM bytes and falls back to normal
measurement if allocation fails.

Capacity counts 128-byte blocks; a 256-byte sector takes two. Accept zero or a
power of two from 16 through 2048. Invalid values, including negative or wider
Forth cells, throw error -24 and leave the request unchanged. The getter reports
the request, not an allocation: Exec allocates after handoff and keeps the
one-sector buffer if allocation fails. The shell reports that fallback once.
Settings apply only to this boot. Autoboot uses the default without input.
Defaults are initialized once before Forth. Resumed loading preserves the
complete boot record, and kernel startup validates and captures the request
before admitting Tasks; it does not reset valid Forth settings.

The [boot record](../reference/platform.md#boot-service-settings) is shared with
the direct XEX loader. Packaging checks its version and location against image
metadata. System-drive selection is described below and in the
[SYS: contract](../reference/sys-volume.md).

## Try it

Download `exec816-demo.zip` from [Releases](https://github.com/mkur/exec816/releases)
and extract it. Current builds include OF816, Exec816, system and work disks,
and the matching ROM. Older release archives have their own enclosed instructions.
See the [installation guide](../../README.md#installation).

Configure [AltirraSDL](https://github.com/ilmenit/AltirraSDL) using the
[installation guide's settings table and ROM import steps](../../README.md#installation).
The [pinned machine configuration](../../toolchain/altirra-shell-paced.json) uses
800XL, AltirraOS 65816, PAL, 8× CPU, shadow ROM, **4 MB of RAM (64 KiB base RAM
plus 4,032 KiB of native high memory, or 63 banks)**, BASIC disabled, VBI enabled
and DLI disabled. Upstream Altirra will not run this build.

In **System → Configure System… → Computer → Boot**, uncheck **Unload disks
when booting new image**. Open **File → Disk Drives…**, use the **…** button on
the **D1:** row to select `system.atr`, and set **Emulation level** to
**Generic + 57600 baud**. Mount a disposable copy of `work.atr` in **D8:** with
writes enabled; both disks must remain present. Under **Computer → Acceleration** in the settings
window, uncheck **SIO Patch** and **D: burst I/O**. Finally, choose
**File → Boot Image…** and select `Exec-of816.xex`. The ATR is a data disk.

Leave the keyboard alone to boot automatically. To use the monitor, press a
normal keyboard key (or BREAK) during the countdown and release it. The cancel
key is consumed, including repeats if held; it is not part of the first Forth
command. Modifier keys alone and the console START/SELECT/OPTION buttons do not
cancel the countdown.

At the Forth input cursor, try:

```forth
decimal 6 7 * .
: square dup * ;
9 square .
exec816
```

The first two calculations print `42` and `81`. The last word starts the shell
in the upper 18 rows and the independent prime search in the lower six rows.
Wait for `SYS: -> D1: ready, read-only` and the `>` prompt. Try `HELLO` and
`CAT STORY.TXT | WC`; the latter prints `108 518 3171`. See the
[standard image guide](demo.md) for other commands and pipes.

To place the same companion disk in D2, cancel autoboot and enter:

```forth
decimal
2 SYSTEM-DRIVE!
SYSTEM-DRIVE@ .
EXEC816
```

Use the same Generic + 57600 baud profile. D1 can be empty. Startup reports
`SYS: -> D2: ready, read-only`; C: points to D2:C. Try `C:HELLO` or
`C:CAT SYS:STORY.TXT | C:WC`. The old D1 name is not retained.
WORK: stays on D8, so select D1–D7 for SYS: in this build.
The setter validates the full cell and rejects zero, values outside 1..8,
missing system selection and conflicts with other mounts. Rejection leaves the
previous request unchanged. The getter reports a request, not mount success.
See [SYS semantics](../reference/sys-volume.md); these settings last for one boot.

`EXIT` stops Exec and restores the saved OS display, which contains the earlier
Forth text. It does not resume the retired interpreter.

`BYE` before launching Exec restores OS vectors, I/O records and MEMLO, then
parks with OS interrupts running. Reset/reload to start another session.

## Handoff and limits

OF816 is a boot monitor, not a resident Exec service. It borrows two free upper
banks selected from the native image's map, plus guarded bootstrap storage. At
return to the reader it retires the interpreter; Exec can later reuse those
banks. Returning
from Exec does not resume Forth. The packager checks the combined image's memory
requirements before producing the XEX.

The upstream full Open Firmware layer and FCode are not included. The core and
license come from the [OF816 pin](../../toolchain/of816.json). Port internals,
original memory measurements and development evidence remain in the
[OF816 integration record](../history/of816-boot.md).

## Build from source (optional)

To build your own monitor image, install the [build prerequisites](../contributing/building.md) and run:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
python3 tools/build_demo.py
```

Every demo build also packages OF816. The builder fetches the small upstream repository into
`build/of816-upstream` when absent. It checks the exact revision in
[toolchain/of816.json](../../toolchain/of816.json), builds the Forth core with ca65,
and wraps the native image built in the same run. The final `of816/` directory
contains the boot XEX, matching system/work disks and pinned AltirraOS ROM, together
with upstream license notices. The builder verifies the ROM size and hash
before packaging it. Custom `--output` paths use the same directory layout.

To refresh a matching demo's monitor and ZIP without recompiling its native
payload, use `python3 tools/build_demo.py --refresh-monitor`. The native build
must already contain the current loader callbacks. Its default output is
`build/demo`.
For monitor-only packaging, use `python3 tools/build_of816.py`; its default
output is `build/demo/of816`.
Then run `python3 tools/package_demo.py` to refresh the distribution ZIP.
Full demo builds produce `build/demo/exec816-demo.zip` automatically. Share
that archive; it contains the boot files, a short guide, license notices and
checksums. Assembly listings, manifests and test output remain in the build
directory.

The resulting files are:

- `build/demo/of816/Exec-of816.xex`: monitor plus the standard shell/prime image.
- `build/demo/of816/system.atr`: the matching read-only disk, with HELLO, CAT, WC and
  sample text.
- `build/demo/of816/work.atr`: disposable writable disk for D8:.
- `build/demo/of816/altirraos-816.rom`: pinned AltirraOS 3.44 ROM for 65C816.
- `build/demo/of816/ALTIRRAOS-LICENSE.txt` and `OF816-LICENSE.txt`: upstream notices.
- `build/demo/of816/of816.json`: build inputs, memory layout, media and ROM hashes.

To package another existing native image, use `--exec-build`. For example, the
original standalone C experiment remains available with
`--exec-build build/calypsi/messages/program --output build/of816-c`; it requires
the [C example](calypsi-c.md) to be built first and has no companion disk.
