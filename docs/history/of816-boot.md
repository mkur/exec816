# OF816 boot monitor

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/boot-monitor.md) and [history index](README.md).

`build/demo/of816/of816-exec.xex` starts a real OF816 Forth interpreter under the
pinned AltirraOS 65816 ROM. After a five-second countdown it launches the
standard eight-Task shell/prime image through Exec's existing hosted startup.
Press a key during the countdown to stay in Forth; type `EXEC816` to boot later.

```text
AltirraOS → combined XEX → five-second countdown → Exec816 shell
                                  ↓ key
                              OF816 prompt → EXEC816 ↗
```

The bundle contains the monitor and kernel in one XEX. It does not read a
separate kernel file from disk. OF816 is used as a boot monitor; its upstream
full Open Firmware layer is not included.

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

Capacity counts 128-byte blocks; a 256-byte sector takes two. Accept zero or a
power of two from 16 through 2048. Invalid values, including negative or wider
Forth cells, throw error -24 and leave the request unchanged. The getter reports
the request, not an allocation: Exec allocates after handoff and keeps the
one-sector buffer if allocation fails. The shell reports that fallback once.
Settings apply only to this boot. Autoboot uses the default without input.

The [boot record](../reference/platform.md#boot-service-settings) is shared with
the direct XEX loader. Packaging checks its version and location against image
metadata. System-drive words and `SYS:` remain in the separate
[SYS: plan](../plans/sys-volume-implementation-plan.md).

## Try it

Use the existing hosted build prerequisites:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
python3 tools/build_demo.py
```

Every demo build also packages OF816. The builder fetches the small upstream repository into
`build/of816-upstream` when absent. It checks the exact revision in
[toolchain/of816.json](../../toolchain/of816.json), builds the Forth core with ca65,
and wraps the native image built in the same run. The final `of816/` directory
contains the boot XEX, matching system disk and pinned AltirraOS ROM, together
with upstream license notices. The builder verifies the ROM size and hash
before packaging it. Custom `--output` paths use the same directory layout.

To repackage an existing native image without rebuilding it, use
`python3 tools/build_of816.py`; its default output is also `build/demo/of816`.
Then run `python3 tools/package_demo.py` to refresh the distribution ZIP.
Full demo builds produce `build/demo/exec816-demo.zip` automatically. Share
that archive; it contains the boot files, a short guide, license notices and
checksums. Assembly listings, manifests and test output remain in the build
directory.

The resulting files are:

- `build/demo/of816/of816-exec.xex`: monitor plus the standard shell/prime image.
- `build/demo/of816/sdfs.atr`: the matching read-only disk, with HELLO, CAT, WC and
  sample text.
- `build/demo/of816/altirraos-816.rom`: pinned AltirraOS 3.44 ROM for 65C816.
- `build/demo/of816/ALTIRRAOS-LICENSE.txt` and `OF816-LICENSE.txt`: upstream notices.
- `build/demo/of816/of816.json`: build inputs, memory layout, media and ROM hashes.

Open `build/demo/of816/of816-exec.xex` in the
[pinned machine configuration](../../toolchain/altirra-shell-paced.json): 800XL,
AltirraOS 65816, PAL, 8× CPU, shadow ROM, 64 KB base RAM plus 15 native high
banks, BASIC disabled, VBI enabled and DLI disabled. Select the bundled
`altirraos-816.rom` as the OS firmware.

Mount `build/demo/of816/sdfs.atr` in D1 with **Generic + 57600 baud** drive emulation,
SIO patch and burst I/O disabled. Disable **Unload disks when booting new image**,
then boot the XEX while keeping the ATR mounted. The ATR is a data disk.

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
`CAT STORY.TXT | WC`; the latter prints `24 133 746`. See the
[standard image guide](../guides/demo.md) for other commands and pipes.

To place the same companion disk in D2, cancel autoboot and enter:

```forth
decimal
2 SYSTEM-DRIVE!
SYSTEM-DRIVE@ .
EXEC816
```

Use the same Generic + 57600 baud profile. D1 can be empty. Startup reports
`SYS: -> D2: ready, read-only`; try `SYS:HELLO` or
`SYS:CAT SYS:STORY.TXT | SYS:WC`. The old D1 name is not retained.
The setter validates the full cell and rejects zero, values outside 1..8,
missing system selection and conflicts with other mounts. Rejection leaves the
previous request unchanged. The getter reports a request, not mount success.
See [SYS semantics](../reference/sys-volume.md); these settings last for one boot.

`EXIT` stops Exec and restores the saved OS display, which contains the earlier
Forth text. It does not resume the retired interpreter.

`BYE` before launching Exec restores OS vectors, I/O records and MEMLO, then
parks with OS interrupts running. Reset/reload to start another session.

To package another existing native image, use `--exec-build`. For example, the
original standalone C experiment remains available with
`--exec-build build/calypsi/messages/program --output build/of816-c`; it requires
the [C example](../guides/calypsi-c.md) to be built first and has no companion disk.

## Startup and ownership

The upstream core is unmodified at
[`8c923624`](https://github.com/mgcaret/of816/tree/8c923624520fab2196d5c75a97ab94da599d420a).
The local port supplies console callbacks and the `EXEC816`, `CACHE-BLOCKS!`
`CACHE-BLOCKS@`, `SYSTEM-DRIVE!` and `SYSTEM-DRIVE@` dictionary words.
FCode is disabled. The combined artifact includes a copy of the upstream
two-clause BSD license as `OF816-LICENSE.txt`.

The ordinary Exec XEX loader first loads and validates the native image
and ownership manifest. Additional INITAD callbacks copy OF816 into an unused
upper bank, staying in emulation mode on the OS stack. The final RUNAD enters
OF816 instead of entering Exec immediately. The packager rejects payload or
BSS overlap with the borrowed bank-zero arenas and requires two free upper
banks. Both the standard eight-slot profile and the standalone four-slot
profile use the same adapter. Root stack and kernel stack sizes are checked
before packaging.

For the standard image, Forth code occupies bank `$0E`, and dictionary/heap
space uses bank `$0D` between 16-byte guards. These banks are selected from the
embedded image's free-bank manifest. Exec's bank table remains unchanged:
while Forth runs, Exec has not started allocating; after handoff, both banks
are available to Exec and no firmware callbacks remain live.

Bank-zero storage is borrowed from root/kernel reservations already present in that
image:

| Range | Boot use | Later Exec use |
| --- | --- | --- |
| `$21F0–$230F` | Guarded 256-byte Forth direct page; 52 active core bytes | Root Task DP and guards |
| `$41F0–$480F` | 512-byte parameter stack, 16-byte internal guard, 1008-byte return stack, outer guards | Root Task stack and guards |
| `$49F0–$500F` | Adapter/state, internal guard and a separate 256-byte startup stack, outer guards | Kernel stack and guards |

The Forth phase reuses **3,424 reserved bank-zero bytes**. The additional
reservation is **0 fixed bytes and 0 bytes per Task**, including alignment,
guards and unused capacity. Copying also reuses the existing XEX staging
arena. The 1,059-byte adapter fits within its 1,264-byte code/state limit; the
remaining internal guard and startup stack fit within the same reservation.
The Forth core occupies 21,842 upper-RAM bytes in the recorded build.

The startup call frame has its own stack because OF816 switches to a Forth
return stack while retaining the caller's return address. Keeping that frame
on page one would let a subsequent ROM console call overwrite it.

The kernel stack is unused during XEX loading and the monitor phase. The
adapter leaves this arena before native startup initializes it. Using this
reservation also fits the eight-slot image, whose console worker has a smaller
1,024-byte stack.

## Console, interrupts and handoff

OF816 uses the ROM screen editor for output and opens `K:` on IOCB1 for input.
Forth handles line editing and echo. The adapter translates CR/LF, Return and
Backspace at the ASCII/ATASCII boundary. IOCB1 must initially be free; an
occupied channel is left unchanged and the monitor exits without taking it.
The two borrowed IOCB records are restored before their buffer storage is
reused. This is a basic text console port, not a complete terminal emulation.

Native NMI/IRQ wrappers preserve the full register context and run the saved
ROM handler on the OS stack. An interrupt already on page one keeps its live
S. CIO uses the same rule and the ROM's existing `COP #$00` bridge; it restores
the caller's D, DBR, widths and interrupt mask on return. No Exec gateway is
installed until Exec's normal startup runs.

The countdown uses the OS VBI clock: five intervals of 50 ticks on the pinned
PAL profile, independent of the CPU speed multiplier. Clock-byte wrap is
handled with modulo subtraction. It starts after the boot hint is printed;
initial XEX loading and Forth initialization are outside the five seconds.
Cancellation enters the monitor indefinitely, without rearming the timer.
The timeout uses the same handoff as the explicit `EXEC816` word. NTSC timing
is not supported by this first port.

`EXEC816` abandons the Forth activation, closes its keyboard channel, restores
both IOCBs and the original interrupt vectors, establishes the OS stack/mode,
then jumps to the original validated Exec loader entry. All remaining handoff
instructions are in bank zero. Exec can then initialize the borrowed root/kernel
arenas and reuse the upper banks. There is no return edge into Forth.

## Development evidence

```sh
python3 -m unittest discover -s tests -p 'test_of816_package.py'
python3 tools/test_of816.py
```

The [development record](../development/of816-boot.json) pins the upstream source,
embedded Exec image, ROM, emulator, configuration and observer. Checks cover:

- Automatic handoff after approximately five seconds (250 PAL ticks), including
  clock-byte wrap and the visible countdown. Final-second cancellation consumes
  the key and keeps the monitor active beyond the original deadline.
- Real physical keys: Forth arithmetic followed by the `EXEC816` word.
- Forth DP/stack/data guards and the restored vector/IOCB handoff boundary.
- Default autoboot captures and allocates 512 blocks. The manual route tests
  set/get, zero, invalid full-cell values preserving the request, then boots
  with 128 effective blocks. See [cache evidence](../development/sector-cache-of816.json).
- Both boot routes reach the unchanged optimized standard image. Physical keys
  exercise disk HELLO, the CAT/WC pipeline and EXIT, with native Task cleanup,
  stack/domain guards, bank ownership and OS display/input restoration.
- Separate `BYE` and occupied-IOCB exits, including the continuing OS VBI clock.
- Host rejection of overlapping boot storage, insufficient free banks and
  truncated XEX records.

This is focused development evidence for the pinned hosted experiment. The
kernel/compiler output is reused unchanged; this change adds assembly startup
and host packaging, not a new compiler ABI. Full OF816 language conformance,
arbitrary hardware, direct reset boot, disk loading, general terminal controls
and returning from Exec to Forth are outside this experiment.
