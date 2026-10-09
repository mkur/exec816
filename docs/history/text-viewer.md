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

## TV2 Loadable viewer

`TEXT.APP` provides Open, one optional quoted startup path, line/page/thumb
scrolling, resizing, Cancel Load and cooperative close. It owns the document,
menu and workstation. Idle waits block; pending work alternates bounded reads
and painting, with at most four text rows per UPDATE. Slider values are sent
only when changed, and padded text replaces rows without clearing the page.

The initial optimized standalone walkthrough passed selector acceptance,
Cancel/failed replacement, policy interruption, scroll/resize/exposure, quoted
startup, peer shell/counter progress, read cancellation, Stop, invalid arguments,
warmed heap return, guards and OS restoration. It retained **158 ordinary-stack
bytes** above the interrupt floor. That run preceded the final slider-state cache;
the final-package focused test covers the subsequent resize/scroll changes. The
complete workflow was repeated against the final package for TV4.

Dragging a small scrollbar thumb exposed an existing backend restriction:
XOR outlines required 32×32 pixels. The adapter now admits 8×8 outlines, covering
the 15-pixel-wide track and minimum thumb. The emitted drawing fixture passes
**122 checks**, including odd packed edges, moving narrow outlines, screen edges
and exact background restoration. Its admission counter was updated to observe
the current `DisplayOwnerEnter` boundary. The extracted final-package diagnostic
passes physical minimum resize and thumb-to-bottom dragging, pixel comparison,
heap return and EXIT, retaining **340 ordinary-stack bytes** above the floor.
This diagnostic uses the combined ABI 11 package prepared for TV3/TV4.

The model occupies **1,678 upper bytes**, included in a **67,777-byte image span**.
`TEXT.APP` is **16,542 bytes** on disk: 12,531 code bytes, 563 constants and 1,678
zero-fill bytes, plus packing/import/relocation records. The loader reserves
**133,312 upper bytes** including its existing bank-alignment allowance. A private
workstation reserves 288 bytes; AES context, registration and window-view storage
reserve 344, 1,152 and 808 bytes respectively. The existing selector's state,
snapshot and form session add **32,240 bytes** while active, before those shared
lifetime records. Document and replacement allocations are additional.

The checked raw/optimized model layouts agree. The host suite remains **423 tests,
four historical skips**. Reserved bank-zero delta is **0 fixed, 0 per public Task
and 0 private idle**, including guards and unused capacity; VRAM delta is **0**.
No stack pools were enlarged. These are development checks.

The final exact-ZIP standalone viewer run also passes all 13 pixel scenes,
Open/Cancel/error preservation, selector interruption, read cancellation, Stop,
invalid startup arguments, peer activity, warmed heap return and EXIT. Its minimum
ordinary-stack headroom is **149 bytes**, above the 128-byte target.

## TV3 Launcher and Files association

The C launcher now forwards a pointer and counted length to the existing native
Process argument-copy path. There is one signature and one argument-admission
boundary. C component ABI advances from 10 to **11**; GEMSYS and all APPs must
be rebuilt together. The import count remains **77**. Files gives `.TXT` entries
one quoted path and retains its existing one-child/Stop/collection policy;
directories navigate and other files use empty-argument program launching.

Small emitted C/native probes pass **22 checks each in raw and optimized mode**:
empty, one-byte and 255-byte tails, caller-buffer overwrite/free before the child
reads, invalid length, embedded NUL, unavailable program and exact warmed memory
return. Argument storage rounds to 8 bytes for an empty tail and 256 for the
maximum tail; a maximum quoted viewer path reserves 136 bytes. The shared
component grows **58 bytes**, to **196,520**; no import ordinal is added.
`FILES.APP` grows by 506 bytes on disk to 21,619; its model stays 3,074 bytes.
Its loaded span is 69,557 bytes and rounded image backing is 135,096 bytes,
32 more than before the association.

The first Files-owned child initializes its existing **112-byte timer resources**.
The first `.TXT` association additionally initializes DOS's **256-byte assign-path
buffer**, because Files now uses `C:TEXT.APP`. The observed block contains the
expanded physical path `D1:C/TEXT.APP`. DOS retains this buffer until the parent's
`ReleaseContext`; it is separate from the copied argument tail. The walkthrough
uses warmed child baselines and requires the original pre-Files baseline after
parent retirement. Initial cold-baseline assertions, and then an assertion using
the logical `SYS:` spelling, correctly failed as harness assumptions; no runtime
allocation workaround was introduced.

The final exact-ZIP Files workflow passes text launch, quoted copied paths,
caller-scratch reuse during navigation, one-child refusal, selector Stop,
read-time Stop, native HELLO and GEM calculator launches, collection and relaunch.
Closing Files with its child selector active removes both windows, restores focus
to a survivor and returns the original pre-Files heap/ownership baseline. Panel
keyboard activation, pixel checks, guards and EXIT also pass. Ordinary-stack
headroom is at least **152 bytes** in this run.

Reserved bank-zero delta is **0 fixed, 0 per public Task and 0 private idle**,
including guards, alignment and unused reservation. VRAM delta is **0**.
TV4 packaging documentation remains in progress.
