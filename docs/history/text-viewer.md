# GEM text viewer development record

[Design](../plans/gem4xe/text-viewer-design.md) ·
[Plan](../plans/gem4xe/text-viewer-implementation-plan.md) ·
[Evidence](../development/text-viewer.json)

## TV1 Document storage and loading

The application-owned loader reads at most 1 KiB per step, indexes counted bytes
once, and commits a replacement only after successful Close. Cancellation and
operational failures preserve the previous document. Row formatting reads the
index and raw memory without disk access, expands tabs and clips hidden text.

The optimized controlled fixture passes **139 checks**; the real SDFS fixture
passes **119 checks**. They cover mixed delimiters, a split CRLF, embedded NUL,
exact byte/line bounds and overflow, allocation/I/O failures, cancellation,
old-document preservation, canaries and exact warmed allocation return. The
real input disk is unchanged. The host suite passes **423 tests**, with four
historical skips. These are development checks, not hardware qualification.

The initial real-disk harness used a timer-1 IRQ stimulus that occupied a POKEY
resource required by SIO. Removing that unrelated stimulus and using the pinned
56k disk profile made the fixture pass; no production I/O workaround was added.
The fixture uses an 8 KiB native upper data arena to fit DOS state.

A document allocates 65,536 raw bytes and 16,388 index bytes: **81,928 rounded
upper bytes**, or **163,856** while replacing a full document. Model and loaded
image costs are recorded with the application slice. Fixture ELF hashes and
initialized/zero-fill sizes are in the evidence record. Guards pass; the real
fixture's root stack retains 863 bytes above its interrupt floor.

Reserved bank-zero delta is **0 fixed, 0 per public Task and 0 private idle**,
including guards, alignment and unused reservation. There is no VRAM change.

TV2–TV4 are still in progress.
