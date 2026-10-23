# Native Exec QED in Altirra

[Guides](README.md) · [QED coexistence evidence](../history/qed-coexistence.md)

This setup runs the native Exec QED on the normal GEM desktop. It includes the
production APP, its matching English resource, OF816 and the pinned 65C816 ROM.
The separate [GEM4XE reference](gem4xe-qed-reference.md) remains available for
donor comparisons.

## Launch

From the repository root:

```sh
build/qed-delivery/normal/launch-qed.command
```

Allow the five-second OF816 countdown and desktop startup to complete. Capture
the mouse with F12 (possibly Fn+F12), or Input → Capture Mouse. Click Shell and
enter `RUN C:QED.APP`. Alternatively, open C: on the desktop and double-click
QED.APP. One additional Counter application is covered by the coexistence
checks. Close it before starting a foreground checksum command; this setup
has eight public Task slots.

QED opens an empty document. Ctrl+O selects a file; open WORK:SAMPLE.TXT to try
editing. Ctrl+S saves; Ctrl+M opens Save As. Use WORK: for saved documents.
Replacement of D and an older B have separate Cancel-default consents. Ctrl+Q
quits QED; `EXIT` in the shell closes the desktop. The packaged README includes
keyboard controls, limits, notices and manual emulator settings.

The launcher finds local AltirraSDL or accepts an explicit app/executable:

```sh
build/qed-delivery/normal/launch-qed.command --altirra /path/to/AltirraSDL.app
build/qed-delivery/normal/launch-qed.command --prepare-only
```

It generates private settings from a dedicated seed, using a 65C816 at 8x,
63 high banks, VBXE and ST Mouse on port 1. It does not edit ordinary emulator
settings. SYS: in D1 is read-only. WORK: in D8 uses a persistent writable copy
selected in `build/qed-delivery/normal/altirra/workspace.json`. A new workspace
creates `altirra/work.atr`; keep that directory with saved work. The selection
survives replacement of the clean template and setup refreshes. To select an
existing private disk explicitly, pass `--work /path/to/saved.atr`. Local
selections move with the workspace; explicitly external disks retain their path.
A broken selection fails without creating a blank replacement. Old hash-named
disks need an explicit selection or a recorded prior private mount. Close the emulator
before opening another instance against the same writable disk.

The refresh retains the idle-cursor fix and adds bounded edit/scroll painting
and correct window cycling while a client waits for messages or timers. Close
the running emulator and restart to load the new system and APP. The previous local setup remains untouched. Both original
local launch directories, `build/qed-exec-altirra/` and
`build/qed-exec-altirra-fixed/`, forward to the earlier caption-preview launcher.

In the earlier caption-preview setup, the WORK path links to
`build/qed-exec-altirra/altirra/work-cecdf2d9dbc4ceb8.atr`, preserving saved
documents without copying or modifying the disk. Keep that original directory
as well. A freshly prepared setup creates its own writable copy on first launch.

## Rebuild and verify

The ordinary builder prepares the provider, pinned QED/cflib sources, ordered
patches, resource and conditional source-frame ledger before packaging:

```sh
python3 tools/build_demo.py --output build/qed-delivery/normal \
  --gem-desktop --qed --format sdfs --sector-bytes 256 --system-kib 720 \
  --mouse-profile mild --release-compiler
python3 tools/test_qed_exec_setup.py --bundle build/qed-delivery/normal
```

Install the pinned actionc, Calypsi 5.18, Altirra bridge/ROM and OF816 build
prerequisites first. Source preparation uses verified downloads/cache; no prior
QED research or preview output is needed. The convenience entry point
`tools/prepare_qed_exec.py --output <directory>` calls the same builder.
The APP, source/patch/resource, ABI and provider checks reject fixtures and stale
inputs. `tools/build_demo.py --output <directory> --refresh-monitor` refreshes
OF816 and the package around unchanged checked runtime inputs.

The ZIP contains boot files, clean media, guide, notices and checksums. Local
launchers, settings, manifests and reports stay outside. Extracted ZIP users
follow README.txt's manual setup. The current
[delivery record](../history/qed-delivery.md) distinguishes new package checks
from [step 6 coexistence evidence](../development/qed-coexistence-qc4.json).
Full release qualification and matching old/new Atarimax CAR/raw BIN delivery
remain separate from these development checks.
