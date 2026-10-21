# Native Exec QED in Altirra

[Guides](README.md) · [QED saving evidence](../history/qed-saving.md)

This setup runs the native Exec QED on the normal GEM desktop. It includes the
production APP, its matching English resource, OF816 and the pinned 65C816 ROM.
The separate [GEM4XE reference](gem4xe-qed-reference.md) remains available for
donor comparisons.

## Launch

From the repository root:

```sh
build/qed-exec-altirra/launch-qed.command
```

Allow the five-second OF816 countdown and desktop startup to complete. Capture
the mouse with F12 (possibly Fn+F12), or Input → Capture Mouse. Click Shell and
enter `RUN C:QED.APP`. Alternatively, open C: on the desktop and double-click
QED.APP. Keep other GUI applications closed while trying this preview.

QED opens an empty document. Ctrl+O selects a file; open WORK:SAMPLE.TXT to try
editing. Ctrl+S saves; Ctrl+M opens Save As. Use WORK: for saved documents.
Replacement of D and an older B have separate Cancel-default consents. Ctrl+Q
quits QED; `EXIT` in the shell closes the desktop. The packaged README includes
keyboard controls, limits, notices and manual emulator settings.

The launcher finds local AltirraSDL or accepts an explicit app/executable:

```sh
build/qed-exec-altirra/launch-qed.command --altirra /path/to/AltirraSDL.app
build/qed-exec-altirra/launch-qed.command --prepare-only
```

It generates private settings from a dedicated seed, using a 65C816 at 8x,
63 high banks, VBXE and ST Mouse on port 1. It does not edit ordinary emulator
settings. SYS: in D1 is read-only. WORK: in D8 uses a persistent writable copy
under `build/qed-exec-altirra/altirra/`; keep that directory with your saved work.
Repeated launches and setup refreshes preserve that copy. Close the emulator
before opening another instance against the same writable disk.

## Rebuild and verify

```sh
python3 tools/prepare_qed_exec.py
python3 tools/test_qed_exec_setup.py --bundle build/qed-exec-altirra
```

The preparer reuses the verified QW1 GEM desktop and current QW6 production APP
after checking their inputs, current ABI, provider identity and artifact hashes.
QW7/QW8 did not change that production APP. `--demo-from`, `--qed-from` and
`--output` select reproduced builds or a separate destination. Changes to native
desktop inputs require rebuilding the desktop first; fixture APPs are rejected.
The normal `tools/build_demo.py --refresh-monitor` path refreshes matching media,
OF816, ROM/notices and `exec816-demo.zip`. The ZIP contains only boot files,
guide, notices and checksums; local launchers and reports remain beside it.

The development walkthrough cold-boots the exact extracted ZIP, launches QED
through `RUN`, edits/saves/reopens on WORK:, rotates its backup and checks normal
ownership return and EXIT. It independently audits persisted document/backup
bytes and allocation. Host checks cover notice retention and private launcher
settings with saved-disk preservation. Results remain in the build directory.

This user-requested local preview makes QED available before the broader
strategy steps 6/7. It does not close their practical coexistence, supported
delivery or release qualification work. Reserved bank-zero growth is **0 fixed,
0 per-public-Task and 0 private idle bytes**, including guards, alignment and
unused capacity; the native desktop XEX is unchanged. Before future release
publication, add matching old/new Atarimax CAR and raw BIN images through the
normal demo builder.
