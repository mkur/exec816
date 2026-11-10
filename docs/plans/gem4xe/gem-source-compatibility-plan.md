# GEM source compatibility

[GEM plans](README.md) · [Application guide](../../guides/aes-applications.md) ·
[AES contract](../../reference/aes.md) · [VDI contract](../../reference/gem-vdi.md)

Status: GC0 is implemented at the development tier. The
[execution record](../../development/gem-source-compatibility-gc0.json) records
ten native pixel/event scenarios, loaded application lifetimes, raw/optimized
layout constants and compilation against pinned GEM4XE headers. The
[Hatari two-Counter demo](../../guides/atari-st-reference.md#two-counter-applications)
now executes the unchanged Counter body in two independent MagiC processes.
The complete GC1 three-target comparison, latency comparisons and broader
qualification remain open.

Make ordinary GEM application source usable on Exec816 with fewer platform
edits. The application should express its windows, events, resources and drawing
through conventional AES/VDI calls. Exec supplies preemptive Processes, native
storage and the platform binding beneath those calls.

This work concerns rebuilt source. Existing Atari ST binaries and standalone
GEM4XE containers are separate loading contracts. A function name alone does
not establish compatible argument, event, lifetime or redraw semantics.

## Application boundary

- Keep endpoint attachment, private parameter blocks, Task direct pages,
  startup and retirement in the runtime. Ordinary application bodies should
  not need Exec service pointers or Task coordination for GEM operations.
- Keep conventional `wind_update`, visible-rectangle iteration, VDI clipping
  and `WM_REDRAW` sufficient for correct drawing. Retain the documented native
  repaint and preservation extensions for applications that choose them.
- Preserve conservative redraw behavior for callers that omit completion
  reports. Ending UPDATE or finishing a rectangle walk does not prove that an
  application reconstructed its pixels. Hidden model changes cannot be inferred
  from visible drawing.
- Extend shared application services when a real port needs them. Keep native
  filesystem, Process and ownership policy below a reusable GEMDOS/C adapter;
  do not add application-specific kernel services.
- State unsupported calls and bounded resources explicitly. Advertise only
  demonstrated behavior; unsupported operations must not silently succeed.

## Executable slices

| Slice | Work | Acceptance |
| --- | --- | --- |
| GC0: conventional Counter | Remove native repaint/preservation calls from the production Counter body, walk every visible rectangle, use common C integer types and retain the native startup wrapper. | Compile against the native and independently pinned GEM4XE declarations. Execute native timers, overlapping windows, exposure, physical move/top/close and repeated lifetime checks. Report any extra repaint cost. |
| GC1: shared-source reference builds | Select and pin an Atari ST toolchain, GEM headers and emulator/ROM; add a separately linked GEM4XE target using its application kit. Share the Counter body, select or measure its font, and keep startup/build differences outside it. | Execute the same Counter source on all three systems. Header compilation alone does not close this slice; the initial fixed 8x8 layout does not establish support for an ST's taller default font. |
| GC2: events and windows | Compare `evnt_multi` masks, button predicates, click timing, message payloads, window geometry and update nesting against the reference systems. Choose small changes from actual port failures. | Independent event traces and pixel checks, including simultaneous timer/message readiness, covered windows and two concurrent native clients. Document intentional departures. |
| GC3: resources and drawing | Prioritize missing object/resource, font-metric, clipping, raster and menu behavior required by shared applications. Use measured bounds for trees, workstations and menus. | Run small conventional GEM examples and the affected QED paths with matching inputs. Preserve redraw correctness, ownership and resource-exhaustion behavior. |
| GC4: reusable application SDK | Consolidate suitable QED compatibility hooks into shared headers/runtime services for files, paths, allocation and C library use. Keep compiler corrections separately identified. | A second independent application uses those services without copying QED's private adapters; saved bytes and failure/cleanup behavior are checked. |
| GC5: port with a small patch set | Revisit an existing GEM port, classify its remaining platform edits and remove those covered by the shared interfaces. | Record the actual retained patch set and run application behavior beside another native Process. Keep supported scope and remaining limits explicit. |

GC0 is the initial implemented slice. The later rows are ordered follow-ups,
not a claim that their interfaces or reference builds are already delivered.
The existing [GEM4XE/QED reference](../../guides/gem4xe-qed-reference.md) remains
a useful separately pinned behavioral comparison; it is not a shared-source
Counter build.

## Validation and costs

Use the development tier: host checks, focused optimized emitted-code scenarios
and small raw/optimized probes only for changed compiler-facing contracts.
Compare reference systems on observable results, not implementation details.
Keep capability gaps, intentional semantic differences and compiler defects in
separate records so a source rewrite is not mistaken for compatibility.

The GC0 source changes introduce no Task, stack, direct-page pool or other
bank-zero reservation: **0 fixed/root/kernel bytes, 0 bytes per public Task and
0 idle bytes**, including guards, alignment and unused reserved capacity.
Measure emitted code and observed stack use independently. Later slices must
report their own costs before enlarging any reservation.

Keep the current compiler pins. Compiler migration is a separate activity and
is not a dependency of this work. Rebuild applications together when a shared ABI changes.
If a demo is refreshed, use `tools/build_demo.py` with OF816 and retain its
five-second autoboot. Development evidence does not qualify the hosted system,
physical hardware or an unexecuted reference target.
