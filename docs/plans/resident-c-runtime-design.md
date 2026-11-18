# Resident C runtime code for Exec816 applications

[Plan index](README.md) · [Hosted C runtime](../reference/c-runtime.md) ·
[C816 loader](../reference/c-program-loading.md)

**Status** — deferred on 2026-11-18 under
[GEM-B3](gem4xe/README.md#gem-b3-resident-c-runtime-code).

Move reusable C runtime code into the existing C816 provider and keep mutable
runtime state with each execution. Start with `ExecCRuntimePhase`. It already
takes the caller's state and callbacks explicitly, and every sampled APP carries
its own 440-byte copy. MGVIEW supplies the functional acceptance case and Counter
supplies a small second consumer.

MagiC's MGVIEW owns its window, document and event loop. It calls system DOS, AES
and VDI services and links its Pure C startup and library routines. Exec already
provides the shared system services through C816 imports. This proposal extends
that code-sharing mechanism to the Exec C runtime while keeping the drawing and
window flow in MGVIEW. [Original MGVIEW project](../../ports/magic/mgview/upstream/MGVIEW.PRJ) ·
[MagiC architecture](../architecture/magic.md)

## Measured duplication

The following figures sum the linked `farcode` and `switch` fragments of the
named objects. The C runtime column includes the typed main adapter and excludes
separately linked Calypsi archive objects. The phase dispatcher is included in
the C runtime column. The current MGVIEW is APP ABI 48. The peer link maps are
from the archived ABI 45 desktop build with the same Calypsi compiler and
`lifecycle.c` input. They establish which code is repeated across consumers.

| APP | File bytes | Common C runtime bytes | Phase dispatcher bytes | GEM rectangle bytes | GEMDOS adapter bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| MGVIEW | 29,120 | 6,608 | 440 | 1,042 | 773 |
| Counter | 14,754 | 5,675 | 440 | 0 | 0 |
| Text | 27,390 | 5,675 | 440 | 0 | 0 |
| GemARC | 49,898 | 6,445 | 440 | 0 | 0 |
| QED | 137,552 | 6,601 | 440 | 1,042 | 488 |

Panel, Files, BASIC and Widget also carry the 440-byte dispatcher. The link
maps are in `build/mgview-right-repeat/fixed-app` and
`build/gem-mgview/demo`, under `bitmap-console/apps` or `qed-production`.

Each sampled APP also carries 140 import thunks from one assembly section.
Each import costs four thunk bytes and eight file-record bytes, for 1,680 bytes
per APP. Generate one discardable section per thunk so the linker can drop
unreferenced imports. The packer already emits records from linked symbols and
the loader resolves each record by ordinal. This is a separate file-size
slice ahead of the rectangle and GEMDOS exports so each APP pays for its own
imports. Validate references in code and in function-pointer tables before
counting the savings.
[Import generation and packing](../../tools/c_program.py) · [Loader validation](../../lib/dos/cprogram.act)

## First resident move

Compile the existing `c/runtime/lifecycle.c` into the resident C provider and
bind `ExecCRuntimePhase` through a generated C816 import. Build the APP entry
against that import and remove its local copy of the implementation. The ABI
cutover rebuilds the provider and APPs together. The callback table,
`ExecCRuntimeState`, typed main adapter and nonlocal termination boundary
belong to the APP.

The resident runner still invokes INIT, RUN, FINISH and RELEASE on the
application Task. The dispatcher receives the existing APP state, call record
and callback table. Each callback runs synchronously on the existing Task
stack and direct page. The runner retains the Image until completion and
keeps the existing order of GUI detachment and heap release. The dispatcher
uses the ordinary C816 tail jump, with a target fixed at load time.
[Phase dispatcher](../../c/runtime/lifecycle.c) · [Resident runner](../../c/calypsi/program.c) ·
[APP scope and callbacks](../../c/runtime/scope.c)

The first estimate is roughly **428 bytes saved per APP** from replacing 440
bytes with one 12-byte import. The provider takes one copy of the implementation
plus its binding. Fresh links determine the actual text and fixup deltas. In an
MGVIEW-only bundle the APP download can get smaller while the combined boot
payload grows. A multi-APP installation amortizes the resident copy.

## Further resident candidates

- **GEM rectangle helpers.** MGVIEW and QED link the same six helpers, including
  `rc_intersect` and the `wind_*_grect` wrappers. Move those existing routines
  behind ordinary C816 imports. They act on caller-owned rectangles and use the
  existing caller-context AES entry points. The estimate is 970 bytes per
  consumer from the measured 1,042 bytes less six imports. Check emitted costs
  and pixels on MGVIEW's copy and exposed-strip path, where `rc_intersect` runs
  per rectangle. [Shared rectangle source](../../c/compat/gem/rect.c)
- **GEMDOS, allocation, arguments and file operations.** The GEMDOS adapters
  reach the runtime's descriptor, error and heap state. Share larger operations
  when they can take an explicit execution-state pointer into the APP's existing
  upper-memory scope. A small APP-side binding can preserve the standard
  `Fopen`, `Malloc` or C library signature and supply the pointer. Move code
  and its state access together so a descriptor retains one owner, including
  pending errors and consumed-close semantics. Keep the lifecycle in the
  existing runner and reuse Exec allocator and DOS operations.
  [GEMDOS design](gemdos-compatibility-design.md) · [C runtime state](../reference/c-runtime.md)
- **Stdio and compiler helpers.** Require a dependency and ownership audit
  before assigning resident entry points. Each execution owns its `errno`,
  descriptor table, FILE list, `stdin`/stdout wrappers, exit handlers and
  termination state. The selected vendor objects also have private state and
  compiler calling conventions. Scope the first larger extraction to an
  operation with a bounded state interface and measured reuse. Keep MGVIEW's
  document parsing, line index, tab expansion and repaint in the viewer.
  [Runtime source selection](../../tools/c_runtime_build.py) ·
  [Pinned Calypsi runtime](../../toolchain/calypsi-runtime.json)

An implicit Task lookup could supply the scope to a resident function with the
original C signature. It would add a lookup to ordinary allocation and file
calls and would need a defined lifetime for that lookup. The explicit pointer
uses ownership already established at APP entry. General shared-library
loading would introduce library discovery and unload coordination. C816 already
supplies the fixed binding required here.

## Memory and acceptance

The first slice targets **zero added reserved bank-zero bytes**, including
fixed, root/kernel, idle and per-Task reservations. Check the provider's actual
upper code-bank extents. The frozen MGVIEW provider reaches 14,469 bytes into
bank `$10`, with 51,067 bytes between that extent and the bank end. Confirm
the linked placement and report the provider byte increase alongside the APP
text, import and fixup savings.
Report boot XEX bytes and ATR occupancy separately for MGVIEW-only and a sample
multi-APP bundle. Measure per-Image heap charge as well as serialized size.
Shrinking text in relative bank zero can leave the allocation charge flat
because the fixed relative placement of writable data determines the span.
[Bank-zero budget](../reference/platform.md#bank-zero-memory-budget) ·
[Provider budget](../../tools/calypsi_provider_budget.py) ·
[C816 storage and entry bridge](../reference/c-program-loading.md#storage-and-entry-bridge)

Verify provider ownership and the APP map, including relocated call sites and
function pointers across the legal bank placements. Exercise the phase boundary
with focused raw and optimized C runtime checks. Cover normal return, failed
INIT, early stop, and retention when GUI retirement fails. Then run optimized
MGVIEW open, scroll and exit and a small Counter coexistence check. Check a
second invocation of a retained Image and verify ordinary stack guards, results
and cleanup. QED's archived map provides evidence for the rectangle candidate.
A focused QED run belongs to a later slice that actually moves its GEM or
GEMDOS routines. [Runtime probes](../../tools/test_c_runtime.py) ·
[Retirement probe](../../tools/test_c_runtime_retirement.py) ·
[MGVIEW checks](../../tools/measure_mgview_horizontal.py)
