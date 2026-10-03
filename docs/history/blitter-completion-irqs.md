# Blitter completion IRQs

[Historical records](README.md) · [Implementation plan](../plans/blitter-irq-implementation-plan.md) ·
[Display contract](../reference/display.md) · [Console contract](../reference/console.md)

BI0–BI5 were implemented on 3 October 2026. The bitmap console now waits for a
retained completion signal while its copy/fill list runs. Input and READ service
continue; drawing and retained-model changes remain gated. Completion checking
uses less CPU, but these measurements do **not** establish faster scrolling or
meet the desktop latency targets.

## Implementation and safety

The driver binds public producer `VBXE_BLITTER=4` to its retained display owner
and allocates one signal. The existing controller/recipient and signal lifetime
rules cover this source. A fixed upper-RAM mailbox retains the owner, generation,
operation ID and IDLE/ARMED/DONE/EXPIRED state. IRQ code never follows a C packet
or console instance pointer. `VbxeCompletionMask` and `GemDrawingCompletionMask`
expose the driver's signal without transferring its ownership.

Task context validates and uploads the one copy/fill list. A short IRQ-masked
sequence acknowledges old status, publishes identity/deadline, arms the shared
timer demand, publishes ARMED, enables completion and starts hardware. Native
and emulation IRQ routes acknowledge owned completion, confirm hardware idle,
commit DONE, cancel timeout demand and post the retained signal. They preserve
the full interrupted context and never suspend a live OS activation. The SIO
route still receives service when both sources are pending.

The shared POKEY timer independently checks the original wrapping VBI deadline.
After sixteen ticks it commits EXPIRED once and posts the same signal. It does
not poll BUSY on every edge. Poll/Fence checks the final hardware state and
performs bounded STOP/recovery in Task context. A lost IRQ with completed pixels
can retire normally; hardware that cannot be stopped retains storage and
ownership in reset-required park. Normal close first settles DMA, then disables
the source, releases/drains its binding, frees its signal and restores resources.

The console reserves its request/input/stop bits before opening the display.
Packet version 3 has 60 bytes and returns the completion mask. Collect merges
Wait-consumed bits; the worker queries the driver on notification and retains
adoption work while a registry entry is PRESENTING. Pending WRITEs and controls
alone cannot keep it running. There is no new Task, kernel selector, list queue,
character ring, priority policy or font change. Synchronous drawing stays
bounded and leaves completion IRQs disabled.

Two implementation findings affected the final layout and route. The existing
12 KiB native service segment ran out of room, so the blitter helper occupies a
separate 2 KiB reservation in unused space in the same upper Task bank. Loaded
SIO testing also exposed excessive emulation IRQ overhead when no VBXE interrupt
was armed. An inactive fast path now chains those ordinary POKEY entries without
saving another full native frame; the final SIO watchdog service maximum is
80.56 µs against its unchanged 100 µs limit.

## Development evidence

| Slice | Evidence and scope |
| --- | --- |
| BI0 | [Polling baseline](../development/blitter-irq-bi0.json), passive timing markers and pixel oracle. |
| BI1 | [Producer and IRQ delivery](../development/blitter-irq-bi1.json), native/emulation copy/fill, context restoration and source lifetime. |
| BI2 | [Operation and watchdog](../development/blitter-irq-bi2.json), real C/native launch, missing IRQ, tick wrap, idle and stuck-engine recovery. |
| BI3 | [Sleeping worker](../development/blitter-irq-bi3.json), input/READ while BUSY, cancellation, PRESENTING, faults, control and loaded SIO/ST checks. |
| BI4 | [Races and lifetime](../development/blitter-irq-bi4.json), raw/optimized producer retention and signal protection, completion before Wait under Forbid, coalesced notifications, lost-source wrap, rollback, destruction and stop. |
| BI5 | [Final measurements](../development/blitter-irq-bi5.json), isolated pixels and three loaded input phases with same-image unobserved replays. |

The final host run contains 320 tests, with four skips and no failures. Generated
Task/producer, timer, blitter and bitmap packet definitions match their inputs.
These are development checks plus targeted interrupt/ownership/coexistence
cases, not a full release qualification or real-hardware claim.

The pin is PAL 65C816 ×8, 4 MiB, VBXE FX 1.26 at `$D600`, AltirraOS 3.44 for
65C816, with physical SDFS traffic and ST mouse on port 1 for loaded runs.
Compiler revision is `f1ff4ce0d16b4705e66d69aad00ca4a7be3e1d08`, without
overrides; C uses Calypsi 5.18. The portable evidence records ROM, compiler,
actual mouse-capable emulator and image hashes. All three final loaded phases
use XEX SHA-256
`02a8a818b0bbe73a7a8f9a7f76cf67b884c2b09905a0d1b81702e3654538adbb`.
No emulator timing or guest instruction changes were made for observation.

## CPU cost and isolated latency

The paired baseline reuses the unchanged BI0 image with the same final fixture
stimulus: no synthetic unowned POKEY timer. Original BI0 used that synthetic
timer and reported 30.77/33.19 ms; it is incompatible with the new driver's
timer ownership. Both paired measurements below omit it. The new watchdog must
therefore pay the whole timer activation cost in this isolated case.

| Two isolated full-screen scrolls | Paired polling baseline | IRQ implementation |
| --- | ---: | ---: |
| Edit through final drawing chunk | 29.57 / 30.11 ms | 32.48 / 32.51 ms |
| C completion queries per list | 4 / 4 | 1 / 1 |
| Worker Wait / Yield per list | 0 / 4 | 1 / 0 |
| Worker CPU charge while pending | 11.54 / 11.54 ms | 3.02 / 3.01 ms |
| Native IRQ/NMI bodies while pending | 0.10 / 0.10 ms | 4.26 / 4.22 ms |
| Worker plus native interrupt charge | 11.64 / 11.64 ms | 7.28 / 7.24 ms |
| Watchdog checks | 0 / 0 | 120 / 119 |
| Nested watchdog body time | 0 / 0 ms | 0.299 / 0.296 ms |

Pending CPU intervals run from launch to `BitmapComplete` entry. Worker charge
includes its C/kernel calls, scheduling tails and bus stalls. The separate
native interrupt bucket includes IRQ/NMI bodies on every Task, without double
counting nested interrupts. Watchdog body time is already inside that bucket.
Off-worker CPU is excluded from the sum; emulation/ROM interrupt time has no
separate exclusive bucket. This is not a total-system instruction count.

Worker charge falls about 74%, and worker plus native interrupt charge about
38%. Wall time increases in these paired samples. The 13 exact pixel scenes
and their unobserved replay pass. Repeated scrolls take 40.45–44.60 ms.

Exact BUSY deassertion is unavailable. The owned IRQ observation is an upper
bound on hardware completion, not the physical edge. For the two isolated
scrolls, launch to IRQ observation is 15.15/15.08 ms, IRQ observation to signal
publication about 0.031 ms, publication to observed worker selection
0.91/0.93 ms, and publication to adoption entry 2.99/3.01 ms. The last interval
includes scheduling and Task-side completion work.

## Loaded input phases

Each phase runs the same eight-Task workload with physical disk traffic, mouse,
keyboard and BREAK. Each of its ten lists has one C completion query and at
least one Wait. There is one runnable-work Yield among those lists per phase;
there is no repeated completion Poll/Yield loop. The full console Poll routine
still runs cheaply on ordinary turns to handle retained adoption; the table
measures its inclusive CPU charge, including those no-notification calls.

| Input phase after observed BUSY | Completion routine CPU, baseline → IRQ | Visible raw glyph, baseline → IRQ | Visible cooked glyph/caret, baseline → IRQ | Maximum IRQ-image turn CPU |
| --- | ---: | ---: | ---: | ---: |
| Immediate | 36.55 → 27.87 ms | 94.24 → 127.16 ms | 105.55 → 101.92 ms | 21.36 ms |
| About 2 ms | 35.76 → 29.11 ms | 110.14 → 127.16 ms | 78.81 → 101.92 ms | 20.68 ms |
| About 8 ms | 38.76 → 24.82 ms | 106.07 → 138.99 ms | 90.64 → 97.84 ms | 24.25 ms |

The phase-zero baseline was reobserved on its unchanged image; the other two
baseline phases use the preserved [S3 evidence](console-responsiveness.md).
Completion-routine CPU falls 19–36%. This does not imply a general loaded CPU
gain: at phase zero, mean worker plus native interrupt charge over each entire
pending interval rises from 18.88 to 19.13 ms. Those intervals include input,
READ service and unrelated SIO/ST interrupts, and their durations change with
scheduling. With the mouse clock already running, the nested watchdog bodies
average 0.234–0.236 ms per list.

All final phases pass their unchanged SIO timing limits, input order, pixels,
guards, teardown and unobserved replay. Maximum ST sampling gaps are
269.18–271.01 µs. Maximum IRQ-to-signal publication is about 0.032 ms; maximum
publication-to-worker selection is 12.34 ms, and publication-to-adoption can
reach 52.61 ms. IRQ delivery alone does not bound when the owner finishes work.

Every phase observes an incorrect frame after 40 ms. Raw visible-input samples
regress, and cooked results vary. These finite samples do not establish a
worst-case bound. The 4 ms complete worker turn, 20 ms whole scroll and 40 ms
visible-input targets remain open. The next investigation should separate
ready-queue delay and remaining worker work after wake, while retaining the
peripheral timing limits established here.

## Memory and reproduction

Every slice adds **zero reserved bank-zero bytes**: fixed, root/kernel, each
public Task and private idle, including guards, alignment and unused capacity.
The eight-Task runtime budget remains 25,408 bytes excluding OS reservations
(56,128 including them). Loading remains 21,872/52,592 bytes respectively.

Upper Task metadata grows by 64 bytes. The upper code reservation is 2,048 bytes
at offset `$5000`, with a final 619-byte payload; unused reserved capacity is
included. The timer uses one additional byte inside its existing 32-byte area.
The bitmap packet grows by four bytes, its cached mask adds four bytes, and the
worker frame adds four bytes within its existing pool. No extra bank, stack,
DP or command arena is allocated. BI4/BI5 add no production reservations.
Final isolated/loaded console stack peaks are 444 bytes; loaded kernel peak is
289 bytes and idle peak 54 bytes. Guards remain intact, with no kernel interrupt
reserve bytes touched in these runs. Earlier slice evidence covers raw and
controlled emulation contexts separately.

Representative final commands (the output directories retain build artifacts):

```sh
python3 tools/test_console_bitmap_scroll.py --mode opt --output build/blitter-irq/bi5-scroll --observe --performance
python3 tools/test_console_bitmap_scroll.py --mode opt --output build/blitter-irq/bi5-scroll --replay
python3 tools/measure_async_scroll.py --output build/blitter-irq/bi5-loaded-3547 --profile-turns --phase 3547 --reuse
python3 tools/measure_async_scroll.py --output build/blitter-irq/bi5-loaded-3547 --profile-turns --phase 3547 --replay
python3 -m unittest discover -s tests -p 'test_*.py'
```

Use phases 0, 3547 and 14188; `--reuse` requires an existing matching image and
is omitted for a fresh build. No demo refresh or release package was part of
these slices.
