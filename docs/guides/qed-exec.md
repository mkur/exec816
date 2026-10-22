# Native Exec QED in Altirra

[Guides](README.md) · [QED coexistence evidence](../history/qed-coexistence.md)

This setup runs the native Exec QED on the normal GEM desktop. It includes the
production APP, its matching English resource, OF816 and the pinned 65C816 ROM.
The separate [GEM4XE reference](gem4xe-qed-reference.md) remains available for
donor comparisons.

## Launch

From the repository root:

```sh
build/qed-coexist/caption-preview/launch-qed.command
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
build/qed-coexist/caption-preview/launch-qed.command --altirra /path/to/AltirraSDL.app
build/qed-coexist/caption-preview/launch-qed.command --prepare-only
```

It generates private settings from a dedicated seed, using a 65C816 at 8x,
63 high banks, VBXE and ST Mouse on port 1. It does not edit ordinary emulator
settings. SYS: in D1 is read-only. WORK: in D8 uses a persistent writable copy
under `build/qed-coexist/caption-preview/altirra/`; keep that directory with
your saved work.
Repeated launches and setup refreshes preserve that copy. Close the emulator
before opening another instance against the same writable disk.

The refresh retains the idle-cursor fix and adds bounded edit/scroll painting
and correct window cycling while a client waits for messages or timers. Close
the running emulator and restart to load the new system and APP. Both original
local launch directories, `build/qed-exec-altirra/` and
`build/qed-exec-altirra-fixed/`, forward to the current launcher.

In this existing local setup, the new WORK path links to
`build/qed-exec-altirra/altirra/work-cecdf2d9dbc4ceb8.atr`, preserving saved
documents without copying or modifying the disk. Keep that original directory
as well. A freshly prepared setup creates its own writable copy on first launch.

## Rebuild and verify

```sh
python3 tools/prepare_qed_exec.py
python3 tools/test_qed_coexist.py --output build/qed-coexist/baseline-reproduced
```

The preparer uses the refreshed native desktop in
`build/qed-coexist/native-window-focus` and the production APP in
`build/qed-coexist/caption-production`. It checks
their inputs, current ordered patches, ABI, provider identity and artifact hashes.
Rebuild the APP with `tools/build_qed.py --executable` when its patches change.
`--demo-from`, `--qed-from` and
`--output` select reproduced builds or a separate destination. Changes to native
desktop inputs require rebuilding the desktop first; fixture APPs are rejected.
The normal `tools/build_demo.py --refresh-monitor` path refreshes matching media,
OF816, ROM/notices and `exec816-demo.zip`. The ZIP contains only boot files,
guide, notices and checksums; local launchers and reports remain beside it.

The development gate cold-boots the exact extracted ZIP in three disposable
workflows: QED alone, with Counter, and beside a foreground 512 KiB checksum.
It checks physical input to completed text/form pixels, peer progress, saves,
backup/reopen, Stop/Cancel, normal collection, heap return and EXIT. Independent
checks audit persisted bytes and allocation. Separate emitted fixtures cover
repeated lifetimes, actual allocation refusals, idle blinking and cache
invalidation. The [step 6 record](../development/qed-coexistence-qc4.json) binds
the measured package, pins, response limits, memory, stack scope and results.

Step 6 passes its selected development gate. Supported delivery, final scope
reconciliation and release qualification/publication remain step 7. Reserved
bank-zero growth is **0 fixed, 0 per-public-Task and 0 private idle bytes**,
including guards, alignment and unused capacity. The native desktop was rebuilt;
its reservation budget and C provider identity are unchanged. Before release
publication, add matching old/new Atarimax CAR and raw BIN images through the
normal demo builder.
