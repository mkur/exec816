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

## D2: mount failure lifetime

The private DOS registry grows from 108 to 114 reserved upper-memory bytes.
Its new six bytes retain the failed configured slot, admission phase and error
after worker cleanup. A successful retry of that slot clears the failure.
The worker carries its current mount phase; the block adapter records the
existing geometry check's specific rejection rather than repeating it.
Published mount snapshots also copy their existing offline error.
Fixed/per-Task/idle bank-zero delta remains **0/0/0 bytes**.

`tools/test_ide_diagnostics_mount.py` passed seven native development scenarios:
normal mount plus failed/successful remount, incorrect sector count, protected
writable mount, empty APT slot, bad SDFS header, missing controller and missing
disk. Checks preserve IoErr, inspect failures after teardown, reject partially
published startup state and restore heap ownership without modifying media.
Evidence: `build/ide-diagnostics/mount/`.
