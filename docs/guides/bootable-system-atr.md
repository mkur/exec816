# Boot Exec816 from one ATR

[Guides](README.md) · [OF816](boot-monitor.md) ·
[Boot contract](../reference/boot-loading.md#bootable-system-atr)

The default standalone SIO profile (`--bootable-atr`) packages `exec816.atr` with the disk reader,
OF816/kernel XEX, system files and writable workspace. Mount it writable in
FujiNet's D1 slot, then cold-boot. D2 and D8 are not required. Keep a backup of
the ATR because it also contains your saved programs and desktop preferences.

Use the included pinned AltirraOS 65816 ROM and the current 4 MiB AltirraSDL
configuration. Boot transport disables BASIC and reopens the ROM text screen
when its allocation would overlap the high-RAM Task pools. Remove external
cartridges unless booting the supplied Atarimax image. Graphical builds retain
their VBXE/ST mouse requirements. Disable SIO Patch, D: burst I/O and fast boot;
select Generic + 57600 baud disk emulation for direct emulator disk boot.
The [demo guide](demo.md) describes the rest of the machine setup.

Leave the keyboard alone during the five-second OF816 countdown. To use Forth,
press a key and enter `EXEC816` when ready. Keep the disk attached while in
Forth: the reader still needs the rest of EXEC816.XEX. No system-drive override
is needed for this D1 boot.

SYS: and D1: identify one writable filesystem. C: and S: retain their normal
assignments; WORK: is an ordinary assignment to SYS:WORK. MOUNT lists D1 once;
ASSIGN lists WORK. For example:

```text
ECHO saved >WORK:NOTE.TXT
CAT WORK:NOTE.TXT
```

Cold-boot the same ATR to keep using saved files. RAM: remains volatile. In a
FastBasic build, `FB WORK:HELLO.BAS` runs source and `RUN C:BASIC.APP` opens the
workbench. Desktop Save Settings writes WORK:DESKTOP.CFG on this same disk.

BOOT.LDR and EXEC816.XEX are write/delete protected. Updating the system means
creating a new image and copying user files into its WORK directory; replacing
BOOT.LDR independently would invalidate the first-stage sector locator. Normal
last-shell EXIT restores the OS display and parks. Cold-reset to start again.
A failed disk boot also requires cold reset. The first-stage error is compact;
second-stage errors include hexadecimal error, phase, sector and file offset.

Build a standard shell/prime disk, or the graphical FastBasic variant:

```sh
python3 tools/build_demo.py --bootable-atr --output build/demo-disk
python3 tools/build_demo.py --bootable-atr --basic-workbench --release-compiler \
  --output build/demo-basic-disk
build/demo-basic-disk/launch-altirra.command
```

The local launcher maintains a writable copy in the build's altirra directory.
It reuses that copy across launches and keeps package inputs intact. A changed
distribution image receives a new copy. The user ZIP contains the system ATR, matching XEX and Atarimax CAR/BIN,
pinned ROM, guide, notices and checksums. Add `--qed` to a GEM desktop build
for a separate optional `qed.atr` in D2. `launch-xex.command` and the two
`launch-cart-*.command` scripts retain the same writable system ATR as the
default ATR launcher. MD5, ARC, EDX, manuals and overlays live in SYS:C,
with sample files in WORK. No separate utility disk is required.

To update the reader and disk packaging around an unchanged, verified
native/OF816 executable:

```sh
python3 tools/build_demo.py --refresh-boot-sio --boot-sio auto --output build/demo-basic-disk
```

The shared reader negotiates FujiNet HSIO index 8 (nominal 57,600 baud) after
the initial ROM load. Use `--boot-sio standard` for a standard-speed bulk
comparison/recovery build; native storage still needs index 8. Forth receives a
confirmed standard-speed bus and returns to fast loading through `EXEC816`.
See the [shared boot reader](../reference/boot-loading.md#boot-only-sio-reader)
for failure codes and the [fast-boot record](../history/boot-only-fast-sio.md)
for measurements. `--refresh-boot-disk` only rebuilds ATR packaging/readers;
`--refresh-boot-sio` also updates the external recovery XEX prefix.

`--refresh-monitor` deliberately recomposes OF816 as well. The build pins OF816's informational
`.VERSION` timestamp for repeatable bytes. Freeze the final XEX before persistence
tests or copying a matching distribution to FujiNet.

Development checks distinguish direct ROM/ATR boot, real FujiNet-PC through the
documented raw-SIO/NetSIO test relay, and physical hardware. The relay exercises
actual firmware/file operations but pauses emulation during host responses;
it does not qualify physical serial timing. See the
[implementation record](../history/bootable-system-atr.md) for executed scope.
