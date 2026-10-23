# Upstream GEM4XE/QED reference

[Guides index](README.md)

Use this separate GEM4XE setup to compare the original editor's behavior while
developing the [Exec816 QED port](../plans/gem4xe/qed-port-strategy.md).
It runs the unchanged GEM4XE release's Calypsi QED executable and resource file.
The Exec port is built separately by `tools/build_qed.py`.

## Build and launch

From the repository root:

```sh
python3 tools/prepare_qed_reference.py
build/gem4xe-altirra/launch-gem4xe.command
```

Python 3 is required. The builder downloads missing pinned release files, source
notices and the public-domain MyDOS boot disk into
`build/qed-gem4xe-reference/v0.12/`. It uses the shared pinned ROM under
`build/firmware/`; if absent, it invokes [the ROM builder](../contributing/building.md),
which requires MADS and `7zz` or `7z` on `PATH`. An existing firmware directory
can be selected with `--firmware PATH`; it must contain the exact ROM and
`ALTIRRAOS-LICENSE.txt`. Use `--offline` once all inputs are cached, or select
another input cache with `--cache PATH`.

Outputs are `build/gem4xe-altirra/`, `build/gem4xe-altirra.zip` and the separate
`build/gem4xe-altirra-build.json` development report. `--output PATH` changes
their destination. The ZIP contains static boot/application media, launcher,
guide, provenance, original media, checksums and license notices. Build reports
and local saved disks stay outside the archive. Extracted launchers remain
executable. Repeated builds with identical inputs produce the same archive
using the same Python/zlib version.

The launcher finds a local AltirraSDL, or accepts an explicit location:

```sh
python3 build/gem4xe-altirra/launch.py --altirra /path/to/AltirraSDL.app
```

`ALTIRRA` can also name the executable/app. `--prepare-only` prepares private
settings and disk copies without requiring an emulator installation. Close an
older instance of this setup before launching another against its writable disks.

## Use QED

1. Allow about a minute for MyDOS and GEM to start. D2 opens automatically,
   showing `QED.PRG` through a `*.PRG` mask.
2. Capture/release the mouse with F12 (possibly Fn+F12), or Input → Capture Mouse.
3. Double-click `QED.PRG`. Choose File → New (Ctrl+N), then type.
4. Try Ctrl+A, Ctrl+C, Ctrl+X and Ctrl+V. Undo is available from Edit or the
   emulated F2 key; the host's function-key mapping may need adjustment.
5. Save a document on B: (D2), close it and reopen it. `SAMPLE.TXT` is provided;
   change the file mask to `*.*` to see all files.

D1 boots MyDOS 4.50 and presents GEM's system files from the cartridge. QED and
its resource are on a separate 720 KiB MyDOS disk in D2. On first launch, clean
templates are copied to `runtime/disks/mydos-boot.atr` and `runtime/disks/qed.atr`
inside the setup. Subsequent launches and builder refreshes preserve those
copies. **Keep `runtime/disks/qed.atr` when moving or upgrading saved work.**
The top-level ATRs remain clean templates. Private settings under
`runtime/config/` are regenerated; ordinary Altirra settings are untouched.

## Pinned configuration and corrections

[gem4xe-reference.json](../../toolchain/gem4xe-reference.json) pins GEM4XE v0.12,
its source revision, release assets, notices, generated media and the tested
macOS arm64 AltirraSDL binary. ROM source/build pins come from the shared
[Altirra pin](../../toolchain/altirra.json). The generated `profile.json` carries
the reference pins, and the launcher checks the packaged media before use.
Other emulator binaries can be selected, but the recorded walkthrough applies
only to the recorded binary and configuration.

| Setting | Value |
| --- | --- |
| Hardware | Atari 800XL, PAL, BASIC off |
| ROM | AltirraOS 3.44 for 65C816 |
| CPU | Plain 65C816, multiplier 8, shadow ROM enabled |
| Native RAM | 63 high banks, 4 MiB total |
| Atari extended RAM | 1088K, independent of native high banks |
| VBXE | FX1.26, primary D6xx, private memory |
| Other accelerators | U1MB off, Rapidus absent |
| Mouse | ST Mouse on port 1; keyboard joystick maps disabled |
| Storage | SIO patch on, fast boot off, generic disk emulation |
| Media | `GEM4XE.car`, MyDOS boot D1, QED D2; both disks writable |

The carrier selects `MOUSEPORT=1`, adds a saved desktop opening B: with a
`*.PRG` mask, and renames the CLOCK, CONTROL and CALC `.ACC` directory aliases
to `.ACX`. Startup accessories otherwise exhaust the available VDI virtual
workstations: QED obtains handle zero, zero font dimensions and a tiny blank
document window. QED/CFLIB require two of the three virtual slots. All original
executable and resource payload bytes remain unchanged; the builder checks this.
The dedicated 65C816 ROM also keeps the keyboard table clear of the native
vectors installed by GEM. The older XL/XE ROM and QED-in-ROM carrier were
superseded by this profile.

The original upstream ATRs use SDFS; this setup repackages the exact QED files
onto MyDOS for the selected boot environment. The builder independently audits
allocation and extracted bytes, then checks all generated media against the
working reference hashes. Supplied QED, GEM, MyDOS and AltirraOS notices are
retained in the package; QED's notice prohibits sale.

## Validation scope

The [recorded development walkthrough](../development/gem4xe-qed-reference.json)
covered boot, D2 launch, New, typing, selection, Copy/Cut/Paste, Undo toggle,
Save, close and reopen. Host extraction independently confirmed the saved
`CHECK.TXT` contained exactly the eleven bytes `hello world`. Screenshots and
the original report are identified in that record; the clean disk template
contains no test document. Rebuilding matching media preserves those inputs;
it does not constitute another emulator walkthrough.

Host checks cover relocation, checksum rejection, private settings, saved-disk
retention and archive contents. Run the repository's
[development checks](../contributing/testing.md) after changing the builder or
launcher. This setup changes no Exec implementation or qualification. Reserved
bank-zero change is **0 fixed bytes and 0 bytes per Task**, including guards,
alignment and unused capacity.
