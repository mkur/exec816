# MGVIEW drawing and window foundations

[History index](README.md) · [Implementation plan](../plans/gem4xe/mgview-foundation-plan.md) ·
[VDI contract](../reference/gem-vdi.md) · [AES contract](../reference/aes.md)

## MV1: VDI bindings

Adds named/PB alignment, text attributes and solid rectangle fill. The origin
arithmetic is reproducibly extracted from pinned GEM4XE 0.9.4; its state is
explicit and coordinates are widened. Bindings use the existing per-Task
workstation and drawing grant. Baseline remains the default; alignment applies
before streaming. No drawing-unit limits change.

The private workstation grows by four upper-heap bytes. Reserved bank-zero
growth is zero for fixed storage, root, kernel, idle and every public Task,
including guards, alignment and unused capacity. Loaded C ABI 41 adds the
three imports; source clients and resident providers must be rebuilt together.

[Development evidence](../development/mgview-foundations-mv1.json) records the
executed layout/API probes, physical pixel check and host suite. This is
development coverage, not hosted-system release qualification. The original
MGVIEW application and its mouse calls remain separate work.
