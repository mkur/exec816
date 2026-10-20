GEM4XE v0.12 + QED -- writable two-disk Altirra setup
===================================================

START ON THIS MAC

1. Install Python 3 and AltirraSDL, then double-click launch-gem4xe.command.
   The launcher uses your local AltirraSDL.
2. Allow about a minute for MyDOS and GEM to finish starting.
3. Capture/release the mouse with F12 (Fn+F12 on some Macs), or
   Input > Capture Mouse.
4. D2 opens automatically. Double-click QED.PRG. QED.RSC is beside it.
5. Choose File > New (Ctrl+N), or File > Open (Ctrl+O) to load a document.
   SAMPLE.TXT is also provided; change the D2 file mask to *.* to see all files.

DRIVES AND SAVED WORK

D1: MyDOS 4.50 boot disk, with GEM system files supplied by GEM4XE.car.
D2: A separate 720 KiB MyDOS disk containing QED and its resource/notices.
    QED.PRG and QED.RSC are the exact upstream release files. QED.CFG supplies
    window geometry and selects the internal clipboard.

On first launch the launcher copies mydos-boot.atr and qed.atr into:
  runtime/disks/mydos-boot.atr
  runtime/disks/qed.atr
It mounts these copies read/write and preserves them on later launches.
Your saved work lives in runtime/disks/qed.atr. Keep that file when moving
or upgrading this setup. The top-level ATRs are clean disk templates.
Use D2: (B: in GEM's path notation) for documents; do not save into the ROM.

Only GEM's system and an initial desktop layout are in GEM4XE.car.
QED is loaded from D2; it is not included in the cartridge.
Your normal emulator settings remain separate. Generated setup settings live
in runtime/config and are refreshed on every launch.

SETUP NOTES

Bundled clock, calculator and control-panel accessories are disabled in this
QED profile: their .ACC aliases are named .ACX. The runtime has only three
virtual graphics slots, and QED/CFLIB need two. The previous setup exhausted
these slots, leaving QED with graphics handle 0 and zero font dimensions.
This caused the tiny window and invisible edits. The original release files
remain in original-media/ and the executable/resource payloads are unchanged.

The dedicated 65C816 ROM also keeps the keyboard table clear of GEM's native
interrupt vectors. Use the pinned ROM and the supplied launcher settings.

VERIFICATION

Development checks on the local AltirraSDL GUI build cover New, typing,
Select All, Copy/Cut/Paste, Undo toggle, Save, close and reopen. The test
saved CHECK.TXT to D2 and independently read back exactly "hello world".
The distributed ATR is a clean template and contains no test documents.
profile.json records the exact media and tested emulator hashes. Other
emulator builds have not been covered by that walkthrough.

MANUAL ALTIRRA SETTINGS

Cartridge: GEM4XE.car
Drive 1: mydos-boot.atr, read/write
Drive 2: qed.atr, read/write
OS: firmware/altirraos-816.rom (AltirraOS 3.44 for 65C816)
Hardware: Atari 800XL, PAL, BASIC off
CPU: plain 65C816, multiplier 8, shadow ROM enabled
Native high memory: 63 high banks (4 MiB total)
Atari extended memory: 1088K
VBXE: FX 1.26, primary D6xx page, private memory
Ultimate 1MB: off; Rapidus: absent
Mouse: ST Mouse on port 1; disable joystick keyboard maps
SIO patch: on; fast boot: off

The automatic launcher targets AltirraSDL on macOS. To choose an emulator:
  python3 launch.py --altirra /path/to/AltirraSDL.app
or set ALTIRRA to its executable/app path. Windows Altirra users can apply
these settings manually and mount the supplied cartridge and both ATRs.

ORIGINAL MEDIA AND NOTICES

original-media/ contains the unchanged GEM4XE v0.12 release media.
Those upstream ATRs use SDFS and require a compatible DOS; the new top-level
qed.atr uses MyDOS and is intended for this two-disk setup.
The old read-only QED cartridge is superseded by GEM4XE.car plus qed.atr.

See SOURCES.txt and licenses/ for source and redistribution notices.
QED's supplied notice permits giving it away and forbids selling it.
SHA256SUMS describes the packaged files; runtime/ is generated locally.
