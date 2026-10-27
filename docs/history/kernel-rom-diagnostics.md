# Early kernel identity and ROM diagnostics

[Implementation plan](../plans/kernel-identity-rom-diagnostics-plan.md) ·
[Firmware contract](../reference/sdx-firmware.md) ·
[Development evidence](../development/kernel-rom-diagnostics.json)

KD0–KD3 are implemented. Admitted kernel initialization prints the same captured
version/source identity as `VER`, before memory adoption and Task/heap setup.
The generated assembler and Action! inputs share one identity record, including
clean tags or the actual commit/dirty state. Identity remains enabled in quiet
mode, and long identities wrap into bounded OS text lines.

After `KERNEL READY`, startup reports the captured CPU-visible CRC-32, selected
ROM profile and SDX installation result. Exact catalog identities retain their
version labels. Following the platform decision that the two native firmware
families are AltirraOS and XLOS, other CRC/vector combinations continue as
`XLOS (assumed)`, using the actual captured interrupt destinations. They print
original NMI/IRQ vectors and separate C000, math-pack and high-ROM CRCs even in
quiet mode. The former unknown-ROM `$0002` rejection is removed.

Mapping and repeated-install failures retain causes `$0001` and `$0003`, print
their meaning and mark this attempt's checksum/profile unavailable. Mapping
failure also prints PBCTL/PORTB. Direct screen writes call no firmware and keep
NMI excluded throughout the block. Terminal reporting preserves the first cause
if shutdown subsequently requires a reset.

## Development checks

All **659 host tests** passed. Eleven optimized emitted startup cases cover the
three pinned ROMs, quiet startup, unknown CRC and mismatched-vector fallback,
quiet fallback, bottom-row scrolling with nondefault margins, mapping/state
failures and a pre-console fatal fault. Register/context, IOCB0, margins,
first-cause reporting and the existing domain guards pass. Four small emitted
binding cases cover raw and optimized builds, including a full-width `$C219`
argument and the direct worker-output path.

Five firmware component phases on each of AltirraOS 3.44/816, stock XLOS816F
2.48 and stock XLOS816F 2.49 pass: real VBI/POKEY IRQ activity, fallback
classification and install/remove, repeated installation, original-vector
chaining, RAM-under-ROM restoration and ownership checks. The ROMs were checked
against their original extracted archives; the older `-DSKINV` experimental
images are not these inputs.

The final extracted ZIP passed four boot/tool walks: combined ATR on stock
XLOS 2.49, new Atarimax CAR on stock XLOS 2.48, XEX on AltirraOS, and CAR on
stock XLOS 2.49 with only the private comparison catalog deliberately mismatched.
All check the early identity/checksum/profile against the captured build and
physical `VER`, run MD5, ARC without arguments and archive listing, write/read
WORK and exit with intact guards and released ownership. A further fallback
walk holds the next startup instruction for three ANTIC frames, then restores
it and completes the same tool checks; this is explicitly test-only.

Startup text assertions read the current OS screen RAM; a paused PNG may show
an earlier or incomplete scanout frame. The three terminal failure fixtures
also hold at their final breakpoint for three ANTIC frames, restore the original
code and verify unchanged context/text. Their complete physical scanout images
show the early identity, installation detail and original terminal cause.

The combined ATR cold boot uses actual ROM SIO with SIO/FP/burst/fast-boot
patches disabled. OF816's countdown takes 249 PAL frames, the reader consumes
658,395 kernel stream bytes in 2,596 sector reads and returns through 772
callbacks. All 1,762,799 initialized/zero-fill native bytes match the build;
reader guards and firmware context survive handoff. These are development
checks on the recorded 800XL / PAL / 8× 65816 / 63-high-bank / VBXE emulator
profile, not a full release matrix or physical-hardware qualification.

## Memory and delivery

Reserved bank-zero growth is **0 fixed/root/kernel bytes, 0 bytes for each of
twelve public Tasks and 0 idle bytes**, including guards, alignment and spare
capacity. The private formatting buffer grows from 24 to 40 transient stack
bytes; existing stack reservations remain unchanged and guarded.

Compared with the tagged 0.2.2 demo, emitted upper code/data changes are
BLITTER 1,688→1,562, NATIVE 6,584→7,367, SIGNAL 11,224→11,223 and SDX
4,324→4,649 bytes: 981 more bytes in total, all within existing capacities.
Resident hosted storage remains 4,096 bytes. No ROM snapshot or bridge
reservation grows. Exact sizes, capacities, source hashes and check records
are in the linked evidence.

`build/rom-diagnostics/demo/exec816-demo.zip` contains OF816, the combined
writable system/work ATR, matching XEX/Atarimax images, AltirraOS and notices.
FastBasic and MD5/ARC/EDX remain on the system disk. All 29 archive entries pass
checksums; XLOS ROMs, QED, development manifests and test output remain outside
the ZIP. The final guide refresh changes only the guide, checksum list and its
copy inside the ATR; executable transport bytes remain identical.

The local development banner truthfully reads
`Exec816 0.2.2 (306cab6-dirty)`. This delivery neither replaces the published
`v0.2.2` tag/assets nor claims a new release. A release build requires its own
clean source identity.

## Local ATR launcher correction

The GUI launcher previously passed the ATR to `--run`. AltirraSDL explicitly
selects its Program decoder for that switch, so disk bytes were executed before
OF816 or the kernel could start, producing garbage and sound. Combined-ATR
launch now uses `--bootrw --disk`; XEX and cartridge launch retain their own
media loaders. The same correction applies to the local XLOS ATR shortcuts.

The failure was reproduced with the installed GUI binary, both with and without
the inherited NetSIO device. The corrected command reaches the normal desktop
under stock AltirraOS, retaining the inherited devices. Fifteen launcher tests
pass, including the selected media type, persistent writable disk and original
settings preservation. This host-side change adds **0 fixed/root/kernel,
0 per-Task and 0 idle bank-zero bytes**; kernel and distribution bytes are
unchanged. See the [launcher execution record](../development/kernel-rom-diagnostics-launcher.json).
