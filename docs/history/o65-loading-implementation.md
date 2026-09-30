# Native o65 implementation record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/README.md) and [history index](README.md).

The L1–L4 entries below record the original detailed profile. The current
compact format and validation boundary are specified in
[program-loading-design.md](../reference/program-loading.md); the new implementation
is recorded in [compact-o65-implementation.md](compact-o65-implementation.md).

## L1: bounded native validation

The loader reads serialized `actionc.o65.experimental.v1` bytes in ordinary
Action! task context. Its [public contract](../reference/program-loading.md) and
[machine-readable limits](../../abi/program.json) are separate from the validator
implementation. Placement, provider binding and Process publication belong to L2.

The focused native fixture tests an actual compiler-produced file, every
truncated prefix, independently located corrupt fields, and failure at every
metadata allocation. Successful and failed validation both recover the original
heap balance; source bytes remain unchanged. The Rust reference inspector checks
the same fixture and mutations. The host's zero-NMI-allowance rejection is recorded
separately from malformed-format rejection.

The first optimized build exposed an actionc predicate-threading defect: bypassing
a pure test block could remove a selector load used by later `CASE` arms. The fix
is in actionc commit `47cd55b2dac510922949832332b7a2c3220885be`, based on the
previous `32af3e2` pin. It rejects threading candidates whose definitions escape
the block. A regression covers all three targets. The focused regression, NIR
snapshots, NIR fixture sweep and full default `cargo test` passed, as required by
actionc's contributor instructions for shared NIR changes. General hosted compiler
qualification remains deferred. The local compiler commit has not been pushed;
its [patch](../../toolchain/patches/actionc-case-selector.patch) is retained here.

The initial native runs explicitly used the previous pin plus this exact source
change; their provenance retains that override rather than rewriting history.
The repository pin now names the committed fix. No Exec routine-specific compiler
workaround was introduced.

Development evidence is recorded in [o65-l1.json](../development/o65-l1.json).
Reserved bank-zero delta: **0 fixed bytes and 0 per Task**. Validation metadata
and the complete staging copy use the existing upper heap; all context/interrupt
reservations remain unchanged. These checks do not qualify disk loading,
providers, loaded-code execution or their transport/timing matrix.

## L2: placement, providers and retained execution

The upper heap supplies aligned text backings and private data/BSS. All targets
are checked against immutable input before private copying/patching. The actual
checked kernel build supplies a generated manifest with full native contracts
and provider extents. Process ABI v3 retains an Image pointer in previously
reserved row bytes and dispatches loaded entry points through resident code.
Collection releases that reference only after kernel-acknowledged retirement.

The execution fixture compares copied native text/data/BSS with the compiler's
Rust reference relocator at two placements. It runs two concurrent instances
with independent initialized/BSS state, direct and indirect calls, arguments and
results; drops caller ownership while children are alive; rejects an incompatible
provider contract; injects all eight allocation failures; and unloads/reloads.
Independent routine records check both sides of the final code-bank byte and
admission at the next bank. Both raw/kernel-bank-3 and optimized/kernel-bank-1
pass 71 assertions, native guards, ownership and OS restoration.

Integration exposed decimal `65535` being interpreted as signed -1 by Action!.
Unsigned `$FFFF` now appears in the alignment and routine containment checks.
Placement also independently checks that the aligned section is contained in its
actual allocation. This corrects L1's untested large-routine boundary comparisons;
the new independent boundary cases execute in both modes. Unused alignment
capacity is retained/accounted but is not needlessly cleared.

See [o65-l2.json](../development/o65-l2.json) for exact inputs and placements.
Bank-zero reservation delta remains **0 fixed / 0 per Task**. The manifest uses
1,250 bytes of an existing upper arena gap, and each Image requests 42 heap bytes
(48 rounded), in addition to its complete section backings. Multi-bank command
execution, disk/shell integration, transport/concurrency matrices and loaded
fault paths were deferred to L3/L4 and are recorded below; these L2 development
checks are not those qualification claims.

## L3: MyDOS files and external shell commands

`PROGRAMFILE.Load` stages an exact DOS path in reads of at most 512 bytes, closes
its file before validation/admission, and frees staging before returning. The
shell keeps built-ins first, passes a copied quoted argument tail without its
redirections, loans foreground ownership and waits for retirement. Application
status 20 remains a command result; infrastructure failure still stops the shell.
The existing shell transfer buffer supplies parser scratch, so its allocation
stays 1,288 bytes.

The console build exposed the L2 manifest overlapping console tables in the
upper Task arena. Packaging rejected that layout. The manifest now occupies
`$4000–$467F` of the already reserved arena bank, after the actual Task service
code; packaging checks both extents. The manifest is still 1,250 bytes within
1,664 reserved bytes. Shell helpers are excluded from the ordinary Task entry
registry; the real root and Process trampolines remain admitted.

The isolated ATR builder preserves binary bytes and normalizes only declared
host text files. Native parser checks cover quoting and redirection removal.
The physical shell fixture exercises compiled HELLO/ECHOARGS, current/qualified
paths, missing/truncated/incompatible files, file/NIL redirection, status 20,
repeated launch and BREAK followed by another successful command. It checks exact
writes, retained and physical text, complete heap recovery, native guards and OS
restoration. The BREAK checkpoint waits for foreground transfer, which occurs
after Task admission. See [o65-l3.json](../development/o65-l3.json) for run inputs.

Bank-zero reservation delta: **0 fixed / 0 per Task**, including guards and
unused capacity. Staging and images use upper memory. No timing qualification
is inferred from these development runs; the integrated transport gates are L4.

## L4: integrated lifetime and transport qualification

Status: passed, 2026-09-25. [o65-l4.json](../qualification/o65-l4.json) contains
16 result bundles covering 42 native sessions. All eight timing cases have zero
RX/TX deadline misses or transmission gaps. The 186 host tests and generated
program/Process ABI checks also pass.

The integrated fixture runs the production shell dispatcher with eight live
Tasks. A loaded reader remains alive while foreground HELLO and READ commands
load from MyDOS, inherit their selected streams, execute and retire. On 256-byte
media the background reader verifies all 70,003 bytes while foreground READ
copies the same file to NIL through EOF. The timing oracle checks every wire byte. The
128-byte and stock-media regressions retain a bounded 777-byte data workload.
Image observations record text/data/BSS and complete aligned backing allocations;
provider records contain actual emitted addresses, extents and native contracts.

| Matrix | Geometry / placement | Coverage in raw and optimized code |
| --- | --- | --- |
| FASTEST125 | 128 and 256-byte sectors, kernel bank 1 | Timing, replay and complete functional workload |
| 57.6 kbaud | 256-byte sectors, kernel bank 1 | Timing, replay and complete functional workload |
| STOCK810 | 128-byte sectors, kernel bank 1 | Timing, replay and complete functional workload |
| Alternate kernel | 128-byte FASTEST125, kernel bank 3 | Complete functional workload |
| Multi-bank text | Two distinct aligned placements | Execution, unload/reload and loaded overflow |
| Disk faults | 128-byte FASTEST125 | Checksum, device error and truncated response during seek and staged read |

The full functional workload injects exhausted Task capacity, staging allocation
failure, every native-loader allocation failure, BREAK after a staging chunk and
BREAK at loaded entry. Repeated successful commands follow those failures.
Caller Image ownership is dropped while the background Process remains alive;
its last reference survives until acknowledged retirement. Every completed
scenario recovers the expected heap, handles, locks and Task ownership, with
native stack/domain guards and OS restoration checked.

Timing cases use the existing byte, alarm, Forbid and reply-collection limits.
Each has an identical-image/input replay without tracing and a separate complete
functional run. Transport variants reuse frozen emitted code and change only the
serialized mount descriptor. The loaded reader performs bounded computation
between cooperative polls; this avoids tracing a tight `Yield` loop throughout
the holding period. An earlier combined trace of all failure/reload cases reached
the host timeout; it is not qualification evidence. Guest serial deadlines were
not changed.

Additional native fixtures run more than 64 KiB of executable text at two
different aligned placements, then check a loaded stack overflow. Overflow takes
the resident fault path and retains the live Image; command-level fault isolation
is unsupported. Peripheral checksum/device errors are injected both before the
length seek and after staging allocation. Cleanup preserves the causal error,
and another command can run after a recoverable error. A truncated peripheral
response instead retains the first mount error and the existing reset-required
offline latch, while releasing software ownership; no bus recovery is claimed.

Bank-zero reservation delta: **0 fixed / 0 per Task**, including alignment,
guards and unused capacity. The eight-slot runtime reservation remains 61,536
bytes including the OS. Probe globals fit inside the existing near-data capacity;
L4 introduces no production allocation, worker or memory reservation.

The runners and two-tier guidance are described in [testing.md](../contributing/testing.md).
This loader matrix does not replace general compiler qualification or the
independent console-window release matrix.
