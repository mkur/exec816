# Resident SDX/FastBasic stack

[Current contract](../reference/sdx-runtime.md) ·
[Design](../plans/sdx-resident-stack-design.md) ·
[RS0–RS7 plan](../plans/sdx-resident-stack-implementation-plan.md) ·
[Stack bound record](sdx-resident-stack-bounds.json) ·
[Delivery and measurement record](sdx-resident-stack.json)

The runtime retains one physical page-one guest stack through native services,
preemption and waits. It removes the previous 1,024-byte copy round trip. Two
Images still retain separate banks and direct pages. Invocation admission is
exclusive, with normal result 20/202 for another active guest. Native scheduling
continues. Persistent BASIC retires its invocation before replying, keeping its
Process and data while MD5, ARC, EDX or Check/Build use page one. Busy Run, Restart
and Quit cannot overwrite the current owner's frame.

RS0–RS5 and the RS6 dispatch changes are implemented. Selected development
checks pass. The **100 ms p95 interaction target remains open**, so the complete
plan's acceptance gate is not closed. Full hosted qualification is separate.

## Stack derivation and transitions

The scoped instruction/control-flow audit in
[audit_sdx_stack.py](../../tools/audit_sdx_stack.py) walks the pinned admitted
MD5, EDX, ARC main/overlays and four FastBasic binaries. Unknown transfers fail
closed. Reviewed dynamic tables, writable operands, counted loops and recursive
composition are explicit assumptions in the machine-readable record. This is a
source/binary bound under those assumptions, not a claim about arbitrary guests.

| Admitted guest | Conservative minimum complete S |
| --- | ---: |
| MD5 | `$01CE` |
| EDX | `$01C2` |
| ARC, including rejected compressor descent | `$019C` |
| FastBasic | `$0190` |

ROM borrowing checks `S - 128 >= $0110` before selecting the physical stack.
The reviewed envelope is 122 bytes: CIO wrapper/COP/editor body 33, one direct
emulation VBI 22, owned or ROM IRQ 48, acknowledge-only NMI 13, and a retiring
VBI tail 6. Deeper/transitional NMIs acknowledge and defer. The tail bound assumes
the pinned PAL interval and selected interrupt load. Ordinary native SIO still
excludes ROM serial services. Other ROMs/interrupt chains need another audit.

The lease, CPU owner, complete anchor, ROM depth and transition gate have separate
roles. NMI cannot interpret a partial frame as complete. Already nested ROM work
preserves its current S. The small nested VBI is admitted only while S is in page
one; restoring a native Task's S cannot accidentally enable it. Trap/overlay
unwinds move a bounded 13-byte frame. All 32 DP guard bytes and foreground BREAK
remain checked at every service boundary. Hidden B and complete native context
remain preserved.

ARC's recursive compressor now checks each real entry before deeper descent.
Failure returns SDX 158 and takes ordinary mutation cleanup. A forced failure
with a 16 KiB input preserved the original archive and removed temporary files.
The pinned binary and overlays remain identified before patching.

The BASIC parser initially reached its proposed CPU cutoff on an ordinary
`DIM V(2) WORD:PRINT S$:PRINT "ARRAY";V(1)` line. Its grammar records now use
256 private-bank bytes plus three bookkeeping bytes, bounded to 63 states.
CPU state checks and early error unwind preserve ROM headroom. Both integer and
FP engines accept that line and reject a 64-parenthesis expression with result
306 (`too long`). No whole-page copy fallback was introduced.

## Interaction measurements

The reusable [observer](../../tools/measure_sdx_editor.py) sends physical keys,
holds each for three PAL frames and samples once per frame. It waits separately
for the retained model/input-ready condition and independently decoded client
scanout. Loading is excluded. Each cohort has 20 samples on the same 64×20
desktop and pinned 8× CPU configuration. Horizontal movement alternates Home/End;
vertical movement uses the physical control-arrow keys. Values are frame-quantized
upper bounds, including the input method's timing floor.

| Stage | Insertion p95 ready / visible | Horizontal p95 ready / visible | Vertical p95 ready / visible |
| --- | ---: | ---: | ---: |
| Original copy bridge | 320.9 / 341.0 ms | 140.4 / 160.4 ms | 200.6 / 200.6 ms |
| Resident stack only | 200.6 / 200.6 ms | 140.4 / 140.4 ms | 180.5 / 180.5 ms |
| Changed-column spans | 200.6 / 200.6 ms | 120.3 / 140.4 ms | 160.4 / 180.5 ms |
| Bounded cell dispatch | 140.4 / 140.4 ms | 120.3 / 120.3 ms | 160.4 / 160.4 ms |

Final artifact identities, median/p95 values, routine timing and sample hashes
are in the delivery record. Idle waits produce no damage. Complete rendering,
inverse caret, scroll, short-write/error damage retention, cancellation and
resource ownership have separate emitted checks. Console requests continue
through public synchronous `WRITE_CELLS`. Their measured rendering cost and
remaining service/guest work keep the 100 ms goal open; guards and transport
deadlines were not relaxed.

## Executed development scope

The ROM and emulator identities are pinned in the delivery record. The dedicated
AltirraOS 65816 ROM SHA-256 is
`85a6e927038f401f05f0056fd41a062986cbf7e104c1ac135c248764c132c9a7`.
The toolchain uses `toolchain/actionc.json`, with no compiler override.

- Host suite: 649 checks at the recorded run; generators and changed-file content
  checks. Focused stack-walker regressions cover indirect/unbalanced/unbounded
  transfers and flag refinement.
- Raw and optimized emitted frame/ABI fixtures: 95 checks each, including every
  guard byte, physical frame access, hidden B, trap movement and restoration.
- Minimum-anchor ROM probe and rejection immediately below it; real IOCB0 output,
  fine scrolling/nested VBI, guards and native restoration. Four forced ROM
  transition phases and three lease construction/move/release phases.
- Early emulation entry and all eleven distinct partial-return NMI phases.
  A different native Task enters ROM while the guest is suspended.
- Selected stock-810 and `generic56k` real-sector cases with pointer IRQs, exact
  bytes, native-peer progress and trace/untraced replay. Final generic56k RX
  service maximum 78.94 µs and TX refill maximum 66.54 µs, against the existing
  169.16 µs byte deadline; 3,803 checks. These are selected profiles, not a full
  interrupt/transport qualification matrix.
- MD5 verification/BREAK; ARC no-argument help, extraction, sequential reuse,
  mutation/cancellation rollback and forced recursive bound failure; EDX exact
  editing, save/reopen, inverse caret, traps and BREAK.
- RAWCON max-geometry, unchanged/narrow/separated changes, scroll and partial/error
  writes: 2,628 checks. Integer/FP persistent sessions: 631 checks, including real
  FBCI compilation, retained bindings/channels/modes, busy Run, Stop, Restart,
  Quit under another owner and final collection.

Final package walkthroughs and their result hashes are recorded separately in
the delivery record. A native checkpoint is accepted for the GUI walkthrough
only after independent verification of all emitted native bytes. Cold combined
ATR boot exercises actual loading separately; this distinction is recorded.

## Memory and delivery

Every slice adds **0 reserved bank-zero bytes**, including guards, alignment and
spare capacity: fixed, root/kernel, each of twelve public Tasks and idle. The
delivery's fixed runtime budget is 11,072 bytes; idle remains 800 bytes. The
public Task reservations remain `[1824,1600,1600,1600,1600,1600,2848,2848,1600,
1600,1600,2848]`. The two-DP reservation stays 544 bytes. The upper bridge bank
stays 65,536 bytes reserved despite removal of the host page image and shrinking
each context record from 512 to 16 bytes.

RAWCON Session storage grows 30 bytes, from 2,290 to 2,320; actual eight-byte
allocations grow 24 bytes, from 2,296 to 2,320. Embedded BASIC Session grows from
2,314 to 2,344 bytes, allocations 2,320 to 2,344. The parser adds 259 private-bank
BSS bytes. Emitted heap starts are `$4900` for FBI and `$5600` for FB; available
program storage follows those maps, not old hardcoded capacity expectations.
Per-stage memory-report hashes and code extents are in the delivery record.

The graphical programming distribution is rebuilt through `build_demo.py` with
the current native ABI, OF816 and its five-second autoboot, combined writable D1
SYS/WORK, SDX tools, separate QED ATR, port-2 ST mouse, matching ROM, notices and
checksums. Guest-only parser refresh uses the builder's unchanged-native-input
and artifact checks around that fresh native build. ZIP contents exclude build
intermediates and test output. No writable user FujiNet disk is overwritten.
