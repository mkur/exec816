# Minimal GEM/VDI hosting implementation

[History](README.md) · [Current contract](../reference/gem-vdi.md) ·
[Optional artifact](../guides/gem-vdi.md) ·
[Completed plan](../plans/gem4xe/minimal-vdi-implementation-plan.md)

G0–G6 establish one supervised renderer Task, one root-owned client and a VBXE
backend for the selected GEM4XE 0.9.4 VDI routines. Classic Exec message and Task
lease semantics govern requests and retirement. The non-reentrant renderer runs
in its own Task, rather than on each caller's stack; no private GEM kernel gate
was added. Driver completion and display recovery remain in the adapter.

The fixed mode is 640×240, sixteen colors and an 8×8 built-in font. See the
current contract for the exact allowlist and unsupported operations. This work
does not establish AES, a desktop or general application hosting.

| Slice | Development evidence |
| --- | --- |
| G0 | [Inputs and read-only hardware admission](../development/gem-vdi.json) |
| G1 | [Selected C extraction, entry and Task context](../development/gem-vdi-g1.json) |
| G2 | [Service protocol and lifetime rollback](../development/gem-vdi-g2.json) |
| G3 | [Display ownership, mapping and bounded recovery](../development/gem-vdi-g3.json) |
| G4 | [Real primitives, independent/upstream pixels and scanout](../development/gem-vdi-g4.json) |
| G5 | [Drawing, computing peer and physical SDFS](../development/gem-vdi-g5.json) |
| G6 | [Uninstrumented artifact, distribution and OF816 controls](../development/gem-vdi-g6.json) |

G5 passed thirteen cases in each compiler mode: concurrent drawing, accepted
queued/active stop, recoverable/unquiesced device failures, worker/client/stop
allocation failures, large-pool admission and root-signal exhaustion. During the
first physical transaction, real blit progress and peer progress both changed
between active IRQ samples with the same terminal-post count. Every disk byte,
the final scene hash, saved C contexts, unused DP, guards, cleanup and headroom
were checked. An uncollected reply was not used as proof of overlap.

The diagnostic workload is twelve commands and 768 glyphs plus a cold 2 KiB
read. Raw/optimized submit-to-collection durations were 841/828 PAL ticks,
including owner-side screen readback and hashing. Each normal run used six
service round trips (twelve request/reply messages, excluding DOS traffic).
Diagnostic XEX sizes were 447,737/401,187 bytes. G6 separately measures the
artifact without these diagnostic hooks; those timings are not interchangeable.

For the G6 artifact, raw/optimized submit-to-collection durations were 361/346
PAL ticks (7.22/6.92 seconds), followed by the separate 150-tick visible hold.
XEX sizes were 447,261/400,708 bytes. Renderer stack peaks were 472/444 bytes,
leaving 1,832/1,860 bytes above the interrupt-reserve floor. Both visible scanouts
matched the independent pixel/palette model exactly. These are measurements of
this fixed workload, not general rendering throughput.

Maximum observed G5 stack use across both modes was 569 bytes for the renderer,
56 for the peer, 331 for root, 276 for the kernel and 50 for idle. The renderer
retained at least 1,735 bytes above its interrupt-reserve floor. These measurements
bound only executed paths; the C compiler does not insert automatic stack checks.

Every slice's reserved bank-zero delta is zero: fixed, each public Task and
private idle, counting external guards, alignment and unused capacity. The
pre-existing mixed layout supplies both large stacks and the 4 KiB CPU aperture.
Code and data retain two complete upper banks (131,072 reserved bytes); private
VBXE allocations reserve 107,008 bytes. Exact emitted maps and VRAM extents are
in the evidence, separate from CPU memory accounting.

The optional artifact deliberately uses the G5 font workload for a reproducible
concurrency demonstration, followed by a three-second visible hold. The G4 corpus
remains the broader mixed-primitive/pixel test. Packaging goes through
`tools/build_demo.py --gem-vdi`, includes OF816, matching disks, pinned ROM,
notices and checksums, and preserves the standard five-second shell/prime boot.
These are development checks on the recorded emulator configuration, not a full
qualification matrix or a physical-hardware claim.

The G6 standard-shell observer waits for each active console write to finish
before checking its displayed title. Dirty-range and cursor agreement alone can
hold between the clear and title portions of a multi-quantum prime-frame write.
This corrects an intermediate-frame observation; no console target code changed.
