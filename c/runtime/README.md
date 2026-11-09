# Common hosted C runtime

[Design](../../docs/plans/c-runtime-design.md) ·
[Implementation plan](../../docs/plans/c-runtime-implementation-plan.md)

The generated `exec816/c-runtime.h` and lifecycle component start CR0. Production
APP entry remains unchanged until the coordinated CR3 cutover. The component
probe calls the same synchronous phase implementation under the current loader;
its injected initialization failure is fixture-only.

## Dependency disposition

| Input | Disposition and execution reset |
| --- | --- |
| QED allocation.c | Common allocation, size bookkeeping and owner chain; align the prefix to 16 bytes. Reset the ownership head and statistics for each execution. Keep Malloc/Mfree in a thin compatibility adapter. |
| QED entry.c | Common bounded argument storage and cleanup; keep the editor's single-document validation in QED. |
| QED files.c | Common descriptors, native error map and vendor stdio hooks. Keep editor metadata queries and GEMDOS error translation in the port. |
| QED library.c | Common empty environment and unavailable UTC-clock behavior. Replace board exit/assert parking with the qualified RUN termination boundary. |
| Calypsi errno.c | One linked errno global per Image; clear at INIT. |
| Calypsi streamlist.c | Private FILE globals and standard stream state; reset the complete standard FILE objects and dynamic list at INIT, with no live predecessor execution. |
| Calypsi lib_strtok.c | Contains a retained static cursor. Use an execution-resettable common wrapper over the pinned reentrant helper when selected. |
| Calypsi rand.c / rand48 | Contains mutable generator state. Reset to the selected documented initial seed at INIT when selected. |
| Calypsi setjmp.s / setjmp.h | Pinned C-only termination candidate. The huge-data implementation saves S, virtual frame pointer and return address/bank. D/DBR/mode and interrupt assumptions require emitted native-context checks before exposing exit. |
| Calypsi FILE initialization | Keep the explicit checked source correction from toolchain/calypsi-runtime.json. Audit partial-read error and partial-flush handling before accepting the common stdio path. |
| Default heap initialization / board CRT | Excluded: backing is public AllocMem/FreeMem and native Process lifetime. No separate vendor heap or board exit may be selected. |
| Arithmetic, string/memory, integer formatter | Select the actual pinned helper closure; record source/options and independent relocation evidence. Stateful helpers stay image-private. |

All adapters extracted from QED's native files retain their MIT notices.
Compiler library sources retain their original notices and explicit pins.
Correct API use and pointer lifetimes remain caller responsibilities; this is
an ownership/runtime layer, not memory protection.
