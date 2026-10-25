# RAWCON cells and console vectors

[Plan](../plans/rawcon-latency-implementation-plan.md) ·
[SDX contract](../reference/sdx-runtime.md#rawcon-cells-and-damage-delivery) ·
[Console contract](../reference/console.md) ·
[Execution record](rawcon-latency.json)

The resident bridge now completes successful EDX get/put calls without returning
through the Action! service loop. Flush sends all changed rows through one public
`CONCMD_WRITE_CELL_SPANS` request. EDX's original editing/call sequence is unchanged.
The combined graphical distribution was rebuilt with matching kernel, system disk,
tools, OF816, cartridges, ROM, notices and checksums.

RC0–RC4 are implemented and the development delivery checks pass. RC5's input
readiness gate passes; **the complete-scanout goal remains open**. This record
does not qualify the hosted system or close the plan's performance acceptance.

## Matched interaction measurements

The three builds use the same 8× 65816 PAL desktop, 64×20 console, port-2 ST
mouse, ROM/emulator pins and twenty samples per operation. Physical keys stay
held for three frames. Loading is excluded. The observer compares the complete
client with independently generated ROM-font pixels, including captures before
readiness. The cell-only and combined builds have byte-identical resident bridge
images; the cell-only build retains the previous per-row Flush.

| Operation | Baseline ready / scanout p95 | Cell-only ready / scanout p95 | Combined ready / scanout p95 |
| --- | ---: | ---: | ---: |
| Insertion | 140.391 / 140.391 ms | 120.335 / 120.335 ms | 80.223 / 120.335 ms |
| Horizontal caret | 120.336 / 120.336 ms | 120.336 / 120.336 ms | 80.223 / 120.335 ms |
| Vertical caret | 160.447 / 160.447 ms | 160.447 / 160.447 ms | 80.223 / 120.335 ms |

Use the exact values, medians and maxima in the execution record. The target
remains p95 ≤100 ms for **both** readiness and complete target scanout. Five PAL
frames are about 100.28 ms and do not pass by rounding. Model readiness and the
first visible glyph are separate observations.

One insertion still makes 74 cell calls: two gets and 72 puts. It now makes one
ordinary guest service return and one vector write, compared with 75 service
returns and two row writes. The measured Flush interval falls from about 56 ms
to 19.6 ms. Inclusive routine intervals include preemption and overlap; their
totals are not exclusive CPU costs.

The remaining interval is in presentation after source acceptance. A separate
one-sample trace observes backing writes around 43–44 and 61–62 ms, scene paint
beginning around 74 ms, two backing-to-screen launches around 77–79 and 99–101 ms,
paint retirement around 113 ms and complete target pixels at 120 ms. Input is
already ready around 80 ms. No scanout fence, priority increase, wider dirty
rectangle or relaxed observer was introduced to hide this interval. Further
presenter work needs to preserve the existing fragment/input/control bounds.

## Safety, lifetime and memory

Binding prepares screen/damage/BREAK operands and thirty row offsets while the
guest lease is held, publishing the owner last. Owner-specific unbinding precedes
buffer release; parked BASIC cannot invalidate another Image's binding. Every
cell checks its complete stack domain, all 32 DP guard bytes and BREAK before
mutation. Invalid coordinates and cancellation detach normally. Successful cells
retire their event once and use the common restore, including pending-work drain.

The leaf borrows/restores four native Task DP bytes below the physical frame.
Its temporary DBR setup retires before that borrow. The emitted instruction walk
bounds successful uninterrupted paths at 170 instructions and four temporary
bytes. The scoped source bound adds a thirteen-byte acknowledge-only NMI: minimum
transient S is `$014F` for the generic `$0160` complete-frame floor. Scratch is
restored before ROM borrowing, whose reviewed 122-byte envelope remains within
the existing 128-byte reserve. These envelopes are not additive across a retired
transition.

Real generic-56k trace/replay exercises 65,536 cells. Uninterrupted transitions
peak at 48.423 µs; receive service peaks at 124.052 µs against the unchanged
169.162 µs byte deadline. Pointer sampling gaps peak at 533.636 µs, below 1 ms.
Interrupt/scheduling-extended call intervals are reported separately, including
ordinary VBI dispatch; they are not represented as continuously masked CPU time.
Stock-810 trace/replay also passes with exact sector contents and native peers.

| Reservation/allocation | Change |
| --- | --- |
| Fixed, root/kernel, each of twelve public Tasks, idle bank-zero | 0 bytes each, including guards/alignment/spare |
| Guest DP pool / bridge bank | 544 / 65,536 bytes unchanged |
| Upper binding | 96 bytes within that existing bridge bank |
| Console Instance | 202→206 payload bytes; rounded allocation stays 208 |
| Fixed console metadata | 896 bytes unchanged; four spare bytes consumed |
| SDX Session | 2,320→2,324 payload; rounded allocation 2,320→2,328 |
| Embedded BASIC Session | 2,344→2,348 payload; rounded allocation 2,344→2,352 |
| Open EDX span array | 300 payload / 304 allocated upper bytes |

## Executed development scope

The execution record identifies exact inputs and result hashes. Checks include:

- Raw/optimized binding, record layout, frame access, hidden B and register/status
  preservation; optimized all-byte and maximum-geometry cell behavior.
- All 32 guard-byte corruptions, insufficient physical-frame headroom, preserved
  native DP scratch, owner-specific cleanup and allocation rollback.
- Real forced NMI during binding publication, complete-frame capture, scratch
  borrow, cell commit, scratch restoration and common-restore handoff; selected
  existing partial-pop and minimum-anchor/nested-ROM paths.
- Ordinary native callers of the new vector operation, all 256 values, maximum
  descriptor count, overlaps, rejection before mutation, FIFO mode ordering,
  cancellation, hidden views, resize refusal, Stop and exact replies.
- Negative hidden-prefix errors, positive BREAK prefixes, full-count late errors,
  conservative retry, and real quiesced/reset-required bitmap faults during
  partially accepted vectors. Unsafe DMA retains caller storage for reset.
- Text and bitmap EDX edit/save/reopen, Caps/inverse qualifiers and physical BREAK;
  retained integer/float BASIC state, busy Run, reset/quit ownership, MD5 and ARC
  help/overlay regressions, with guards and resource retirement checked.
- The extracted final ZIP through combined-ATR cold boot/save and matching XEX;
  both supported cartridge variants through OF816 autoboot, editing and return;
  packaged BASIC → tools/EDX → BASIC workflows using a separately identified
  native checkpoint. Checkpoint replay is not counted as cold boot.

The distribution keeps the five-second OF816 countdown, writable SYS/WORK on
combined D1, MD5/ARC/EDX, separate QED ATR and port-2 mouse. No user-written
FujiNet disk was overwritten. The distributable ZIP contains boot files, a short
guide, notices and checksums; build/test output remains outside it.
