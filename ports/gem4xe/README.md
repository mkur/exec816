# Hosted GEM4XE port

[Implementation plan](../../docs/plans/gem4xe/minimal-vdi-implementation-plan.md) · [G0 contracts](../../docs/plans/gem4xe/hosting-contracts.md)

The initial executable is a read-only VBXE detection probe. The renderer,
message service and display lease are not implemented yet.

[inputs.json](inputs.json) pins GEM4XE 0.9.4, the Exec baseline, compiler/runtime
hashes and selected source roles. Source files stay under `build/gem-vdi/` until
G1 adds reproducible extraction/patches. Fetch missing inputs and verify all
hashes with:

```sh
python3 tools/gem_vdi_inputs.py --fetch
```

Existing but changed inputs fail verification rather than being overwritten.
The selected notices include COPYING, COPYING.LIB, font provenance and the
upstream licence note; preserve these with imported source and distributions.
Exec's MIT interface grant does not relicense donor code.

Using the pinned local compiler, firmware and `build/shell-paced-bridge`, run:

```sh
python3 tools/test_gem_vdi.py --mode raw
python3 tools/test_gem_vdi.py --mode opt
```

Each build runs with FX 1.26, without VBXE and with unsupported FX 1.24.
The target reads identity bytes, sleeps across VBI and exits through the hosted
restoration path. Tests check detection status, all existing stack/domain guards,
OS display state and the unmapped aperture sentinel. They do not enable graphics.
Results and source/build records stay under `build/gem-vdi/g0-{raw,opt}/`.

The [separate platform pin](../../toolchain/altirra-gem-vdi.json) enables only
VBXE with private 512 KiB VRAM at `$D600`. It also selects physical SIO settings
for the later SDFS workload; G0 does not mount a disk or claim concurrent I/O.
Existing default platform checks continue to require add-ons off.
