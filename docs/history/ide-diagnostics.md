# IDE diagnostics development record

Follow the [implementation plan](../plans/ide-diagnostics-implementation-plan.md)
and [device contract](../reference/ideplus-device.md).

## D1: retained controller observations

Generated IDE interface revision 2 adds copied controller and APT-slot records.
The controller record uses bytes 704–727 of the existing 1024-byte upper arena;
slot reasons reuse existing partition padding. No reservation or heap allocation
is added. Fixed/per-Task/idle bank-zero delta: **0/0/0 bytes**.

Development checks use the pinned compiler and IDE Plus revision-E/PBI-ID-0
emulator with BIOS 2.1 and AltirraOS816. Native APT fixtures cover direct,
low-byte, MBR and chained tables, revision/cycle/overlap/bounds/offset failures,
unsupported 128/256-byte slots and absent controller/media. Snapshot assertions
cover unattempted state, admission reasons, capacity, access and retention after
stop. Raw and optimized native layout probes cover all three generated records.
Evidence stays in `build/ide-diagnostics/` and the layout development directory.
These are development checks, not a physical-hardware qualification.
