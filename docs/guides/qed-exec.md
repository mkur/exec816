# Native Exec QED in Altirra

[Guides](README.md) · [QED coexistence evidence](../history/qed-coexistence.md)

This setup runs the native Exec QED on the normal GEM desktop. It includes the
production APP and English resource on a separate `qed.atr`, plus the main
system, OF816 and the pinned 65C816 ROM. The preferred `exec816.atr` contains
SYS and WORK, with no QED payload.
The separate [GEM4XE reference](gem4xe-qed-reference.md) remains available for
donor comparisons. This profile uses D1 for the combined system and workspace,
and D2 for optional QED. ATR, XEX and Atarimax boot share that system image.

## Launch

From the repository root:

```sh
build/qed-delivery/separate-disk/launch-qed.command
```

Allow the five-second OF816 countdown and desktop startup to complete. Capture
the mouse with F12 (possibly Fn+F12), or Input → Capture Mouse. Click Shell and
enter `MOUNT QED: DRIVE 2 FORMAT SPARTA`, then `RUN QED:QED.APP`.
Alternatively, open QED: on the desktop and double-click
QED.APP. One additional Counter application is covered by the coexistence
checks. Close it before starting a foreground checksum command. Those checks
used eight public Task slots; the current builder reserves twelve. Larger
concurrent workloads need separate qualification.

QED opens an empty document. Ctrl+O selects a file; open WORK:SAMPLE.TXT to try
editing. Ctrl+S saves; Ctrl+M opens Save As. Use WORK: for saved documents.
Replacement of D and an older B have separate Cancel-default consents. Ctrl+Q
quits QED; `EXIT` in the shell closes the desktop. The packaged README includes
keyboard controls, limits, notices and manual emulator settings.

The launcher finds local AltirraSDL or accepts an explicit app/executable:

```sh
build/qed-delivery/separate-disk/launch-qed.command --altirra /path/to/AltirraSDL.app
build/qed-delivery/separate-disk/launch-qed.command --prepare-only
```

It generates private settings from a dedicated seed, using a 65C816 at 8x,
63 high banks, VBXE and ST Mouse on port 2. It does not edit ordinary emulator
settings. The combined system disk in D1 is writable; QED in D2 is read-only.
The main system boots without QED. WORK: names SYS:WORK on the same disk;
there is no required D8 disk. The launcher keeps a private writable copy shared
by ATR, XEX and cartridge launch. Preserve it when updating the distribution,
and copy saved files into the new system image. The explicit `--split-disks`
development profile retains a separate D8 WORK disk and its `--work` selector.
Close the emulator before opening another instance against the same writable disk.

## Rebuild and verify

The ordinary builder prepares the provider, pinned QED/cflib sources, ordered
patches, resource and conditional source-frame ledger before packaging:

```sh
python3 tools/build_demo.py --output build/qed-delivery/separate-disk \
  --gem-desktop --qed --format sdfs --sector-bytes 256 --system-kib 720 \
  --mouse-profile mild --release-compiler
python3 tools/test_qed_exec_setup.py --bundle build/qed-delivery/separate-disk
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
Full release qualification remains separate from these development checks.
The Atarimax reader retires before the twelve-Task pools are initialized.
Other cartridge mappers and physical hardware remain outside these checks.

The merged provider and APPs use C ABI 27 and AES wire ABI 18; rebuild them
together. The console and FastBasic bindings consume 4 KiB of the earlier
provider code growth allowance, leaving 12 KiB for future code, 4 KiB for
tables and 16 KiB for data/BSS within the existing provider banks. These are
build-time bounds, with no additional fixed or per-Task bank-zero reservation.

## Source and relinking

The boot ZIP is accompanied by `exec816-qed-<revision>-source-relink.tar.gz`
and `QED-DELIVERY-SHA256SUMS`. Keep these together for redistribution. The source
archive contains Exec sources, prepared application/library sources, ordered
patches, resources, retained objects and exact tool/runtime identities. Install
Calypsi 5.18 separately; its compiler and SDK archive are not included.

Extract the source archive and follow `qed-source-relink/README.txt` to relink
unchanged objects or replace a retained CF-Lib object from modified source.
An unchanged relink must reproduce QED.APP exactly. A changed-library APP is a
separate diagnostic build. QED redistribution must remain free of charge;
Exec-authored native adapters use the authorized MIT grant, while donor,
generated GEM declarations and compiler/runtime notices retain their own terms.
