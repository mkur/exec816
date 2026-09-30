# Native console implementation

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/console.md) and [history index](README.md).

This record follows the [implementation plan](../plans/console-io-implementation-plan.md)
and [design](../reference/console.md). The first milestone has eight slices;
independent text windows remain a separate required follow-up.
The later [scrolling optimization](console-scrolling.md) records idle throughput,
the worker's empty-work checks and focused native regressions separately.

## Slice 1: keyboard and SIO coexistence

Status: complete, 2026-09-21. No ordinary `console.device` is published.
The [qualification record](../qualification/console-coexistence.json) retains
passing cases, failed baselines, image/input hashes and timing results.

The fixture runs a client and the existing SIO worker in the eight-slot memory
profile. A private 64-slot upper-RAM ring captures POKEY keyboard/BREAK events
and directly signals the client through an independent binding. Serial and
keyboard posts share the existing pending-wake algorithm. The fixture includes
native IRQ routing and bank-zero callbacks for ROM emulation-mode dispatch.
It performs no translation, rendering, public port call or allocation in IRQ.

The existing bridge's cooked `KEY` command bypasses scanning. The
[console backend pin](../../toolchain/altirra-console.json) adds explicit
`KEY name down|up` matrix input, including Shift, Control and BREAK. `KEY ALL up`
initializes physical scanning. The tracked patch includes the previously pinned
serial observer and disk instrumentation; it does not change CPU or POKEY
emulation semantics. The same binary runs observation and replay, with trace
environment variables disabled for replay.

The initial experiment reproduced held-key duplicates during SIO transactions.
Writing `SKCTL = 0` at every transaction restarts keyboard scanning/debounce.
Safe retired transactions already leave the serial engine idle, so `sio_start`
now retains the scanner and uses the existing STIMER initialization. It still
sets the serial mode, captures shared error evidence in the fixture before
SKREST, and preserves the existing serial error/recovery policy. There is no
new successful-transfer sleep. The production changes are this reset removal
and selecting the binding in the shared direct-post helper; keyboard ownership
and dispatch remain explicitly test-only.

Aligning presses with actual payloads exposed a second failure: a byte arriving
during keyboard delivery could be overwritten after DMA delayed the subsequent
IRQ entry. The fixture's shared route now gives serial RX **one bounded second
service opportunity** after keyboard service. It does not loop until the bus is
quiet. The serial-byte oracle retains its original deadline and checks exact
payloads; a successful average transfer rate cannot hide an overwritten byte.

The script covers a long held key, press/release, Shift, Control, BREAK, Return
and Escape. Both ownership orders restore IRQ shadows and vectors. Mode 0 is
idle serial ownership; mode 1 continuously reads verified sectors; mode 2
forces an actual emulation callback; mode 3 makes an out-of-range sector fail
and then resumes valid reads while input continues. Later presses are aligned
to payload entry, with the actual capture phase recorded separately. Scripts
have finite breakpoint and completion limits. Trace replay uses the same XEX
and input schedule and compares runtime state, events and transfer counts.

Ten raw/optimized cases pass: idle and emulation entry, both sector sizes with
continuous FASTEST125 traffic, and error/recovery with continued input. Five
keys per traced case are captured in payload phase 11. Maximum receive service
is 67.11 microseconds and command TX refill 64.29 microseconds, below the
78.95-microsecond byte interval. The existing 100-microsecond alarm bound also
passes (maximum watchdog service 96.92 microseconds). Whole-run masked maxima
include idle/WAI and ROM intervals; the per-byte oracle separately checks every
actual receive and transmitted frame. All observed runs replay identically.
Both 22-case recovery suites, eight-task 128-byte optimized and 256-byte raw
serial timing, and a STOCK810 regression pass. No threshold was relaxed.

Bank-zero reservation change: **0 fixed bytes and 0 bytes per task**, including
guards, padding and unused capacity. The eight-slot totals stay 57,232 bytes
during loading and 61,536 bytes at runtime, including OS reservations. The probe
uses the existing client and SIO worker, with no additional task. Its 36-byte
emulation callback fits in the existing 512-byte STUBS reservation. The private
288-byte ring/binding/counter area is at Task-arena offset `$C00`, after the
maximum DOS descriptor extent `$A60` and before native code at `$1000`.
It consumes already reserved upper RAM. Native code remains within its existing
8 KiB reservation. Stack watermarks are sampled before the banked-memory test
helper can reuse retired stack space; they are observed lower bounds, with
native frame/domain and interrupt-headroom guards checked independently.

Reproduction uses the pinned compiler in `build/actionc`, the console bridge
in `build/console-bridge`, and the pinned ROM in `build/firmware`:

```sh
python3 tools/test_console_coexistence.py --case raw --mode 1 --sector-size 128 --trace --output build/console-slice1/bounded-128-raw
python3 tools/test_console_coexistence.py --case opt --mode 1 --order 1 --sector-size 256 --trace --output build/console-slice1/bounded-256-opt
```

Use `--mode 0`, `--mode 2` and `--mode 3` for idle, emulation and recovery cases.
Run `tools/test_sio_recovery.py` in both raw/optimized modes and the existing
eight-task `tools/test_sio_concurrent.py --trace` regression for the production
reset/direct-post changes. Qualification is limited to the recorded emulated
configuration; it does not establish console-device lifetime, full-capacity
console operation or physical hardware behavior.

## Slice 2: instance state and terminal core

Status: complete, 2026-09-21. The
[core qualification](../qualification/console-core.json) records raw and optimized
execution with kernel banks 1 and 3. Each run passes 1,269 checks, independent
cell snapshots, stack/domain guards and allocation ownership restoration.
This remains a private fixture; no console worker or device is published.

[console.json](../../abi/console.json) generates shared records and constants:
130-byte service, 56-byte instance, 26-byte presentation, 12-byte binding and
four-byte raw event. The capture area has 64 slots in 288 bytes. The forthcoming
producer uses monotonically advancing byte indices, addresses slots with
`index & 63`, and detects full with an unsigned head-minus-tail distance of 64;
publication follows the complete slot write. Slice 3 implements that protocol.
Input FIFO capacity is 128 bytes and `CONERR_INPUTOVERFLOW` is 1. The public
42-byte IOStdReq is unchanged. Generated layout checks reject overlap and
bank overflow; emitted address probes check the actual compiler layout.

[consolecore.act](../../lib/console/consolecore.act) owns only retained cells, cursor and
dirty ranges. It supports BS, HT, LF, FF, CR, printable ASCII, ignored remaining
controls/DEL and `?` for high-bit bytes. An instance has dimensions from 1×1
through 40×24; the initial display instance will be 40×24. Writes consume at
most 64 source bytes. Clear and scroll continue in quanta of at most 40 cells,
and a pending edit consumes no further source bytes. A future worker must finish
the edit before completing or cancelling its active write. No core path touches
POKEY, screen RAM, an I/O request or retained caller data.

The fixture interleaves 8×3 and 5×2 instances, checks backspace clamping, tabs,
ignored controls and high-bit substitution, then scrolls and clears one while
checking the other. A separate 40×24 instance verifies the 64-byte limit and
24-quantum full-screen scroll/clear. Independent host expectations compare
every retained byte and surrounding guards. Invalid dimensions, truncated
buffers, bank-zero cells, address overflow and record/cell overlap are rejected
without modifying admitted state.

The [known native compiler limits](compiler-issues.md#backend-limitations-that-shaped-the-implementation)
remain in force. The terminal keeps a row offset instead of multiplying on each
character; admission sums at most 24 rows with a checked bound and uses widened
address/length arithmetic. Geometry and extent checks and ABI probes use small
procedures under the 254-byte frame limit. No compiler defect or pin change is
introduced. Observed root stack use is 538 bytes raw and 438 optimized; the
largest kernel watermark is 1,166 bytes of its 1,536-byte stack. The protected
256-byte interrupt reserve remains untouched.

Bank-zero reservation change: **0 fixed bytes and 0 bytes per task**, including
guards and padding. Loading/runtime totals remain 57,232/61,536 bytes including
OS. Explicit console fixtures reserve 256 upper-RAM bytes in the selected kernel
bank for service, instance and presentation, including 44 bytes of alignment
and unused space. The capture area fits the already reserved Task arena.
Headless builds add neither reservation nor Task. The fixture's six guarded
heap allocations consume 1,360 rounded payload bytes and are released; its
separate upper-RAM snapshot is test evidence, not a production screen buffer.

```sh
python3 tools/generate_console.py --check
python3 -m unittest discover -s tests -p 'test_console_layout.py'
python3 tools/test_console_core.py --case raw --bank 1 --output build/console-slice2/raw-bank1
python3 tools/test_console_core.py --case opt --bank 3 --output build/console-slice2/opt-bank3
```

Repeat the two emitted cases with the other mode/bank pair for the recorded
four-case matrix. The independent instances prove terminal-state isolation;
they do not implement a public multiwindow service.


## Slice 3: native input delivery

Status: complete, 2026-09-21. The [input qualification](../qualification/console-input.json)
records 13 passing input cases and the relevant recovery/core regressions.
The native producer now uses its own protected
binding and the shared direct-post/pending-wake path. Its IRQ handler performs
no Task scan, allocation, public port operation or rendering. A three-task
fixture separates the waiting keyboard consumer from the SIO client and worker.
The console remains unavailable in ordinary builds until slice 6.

The 64-slot ring uses monotonic byte counters: an unsigned head-minus-tail of
64 is full, and `index & 63` selects a slot. The producer publishes the head
only after key, kind and the coherent 16-bit native tick are stored. The consumer
copies both words before advancing the tail. Full rings drop new events and
latch loss. Keyboard hardware overruns are captured before shared SKREST;
reset is allowed with no live serial frame, including an idle SIO owner. An
active frame retains its serial error latches until the existing safe reset.
Binding precedes IRQ enablement. Release disables its sources, restores vectors
and only its mask bits, drains pending wakes and clears the binding before
consumer removal. Invalid signal claims and duplicate claims leave ownership
unchanged. Private binding packets are checked against the caller's stack.

[consoleinput.act](../../lib/console/consoleinput.act) translates captured scan codes with
the fixed Atari US key-position map. It supports Shift, Ctrl letters/space,
Caps Lock, Return as LF, BS, Tab, Escape and BREAK as byte 3. Identical key/kind
captures within one native tick are debounced; POKEY scanning supplies held-key
suppression. There is no software repeat or ROM CH/stage-two dependency.
Unsupported special keys are ignored. FIFO overflow discards the ambiguous
stream and latches one loss report; a nonempty read reports it without copying
bytes. Zero-length reads leave that report pending. Clearing input preserves
Caps state and retained output. Closed instances discard captured input.

The instance grows from 56 to 62 bytes for captured key/tick debounce state.
The same 256-byte upper-RAM metadata reservation has 38 bytes of padding/unused
space. Capture remains 288 bytes in the existing Task arena. Bank-zero change
is **0 fixed bytes and 0 bytes per task**, including all guards and padding;
loading/runtime totals remain 57,232/61,536 bytes including OS. Native helpers
occupy 7,407 of the reserved 8,192 upper-RAM bytes; keyboard callbacks use 36
bytes within the existing 512-byte STUBS reservation. No new stack or DP is
reserved. The fixture admits two additional Tasks in existing slots. Its five
heap allocations occupy 536 rounded payload bytes: instance 64, FIFO 128,
reply port 32, SIO request 56 and serial buffer 256. The fixture's consumer
Task record occupies 62 loaded bytes in its separate upper-RAM test bank.
All heap bank ownership returns to the manifest baseline. Observed maximum
root/kernel stack use is 816/1,173 bytes of their 1,536-byte reservations;
the serial worker reaches 656 of 1,024 bytes. All interrupt reserves and
stack/domain guards remain intact.

The new concurrent consumer exposed a 102.55 µs watchdog delay against the
unchanged 100 µs gate. RX now samples SKSTAT once (retaining overrun-before-framing
error precedence) and checks its common data phase first. This removes an extra
slow peripheral read before an already pending watchdog. There is no added
successful-transfer sleep or timing-threshold change. The failed baseline is
retained separately from passing evidence. The keyboard/recovery combination
then exposed a byte arriving after the serial-first check and waiting through
the keyboard wake post. Capture now gives RX one bounded opportunity after
publishing the raw slot and before posting its signal, as well as the route's
existing pre-return opportunity. There is no retry loop. The failing recovery
workload and all four size/compiler timing cases pass with unchanged-image
replay. Maximum RX service is 76.69 µs, TX refill 64.29 µs (78.94 µs deadline),
and watchdog lateness 87.90 µs (100 µs limit). Both 22-case SIO recovery suites
pass. These remain observed emulator results, with little worst-case RX margin;
eight simultaneous Tasks and display traffic are still unqualified.

A claim-path assembly width annotation
was also corrected after the hardware-state restore check detected it; neither
issue requires a compiler workaround or pin change.

The emitted fixture checks translation, Caps/Shift interaction, tick wrap,
identical-tick debounce, all 128 FIFO positions and wrap, one-shot overflow,
zero reads, clear and closed input. Controlled ring fixtures exercise all 64
slots, byte-counter wrap and atomic loss discard. Separate physical-key runs
withhold the consumer until 70 scanned presses fill/drop from the ring, and
hold CPU IRQs while two real scanned keys cause a POKEY overrun. That deliberate
starvation runs with SIO idle and is not a serial latency test. Keys after
release must leave capture/binding state unchanged. Native/emulation callbacks
wake a consumer already in TS_WAIT; NMI-injection runs interrupt signal-mask
and wake-link publications while checking context and guards.

```sh
python3 tools/test_console_input.py --case raw --mode 1 --sector-size 128 --trace --output build/console-slice3/raw-128
python3 tools/test_console_input.py --case opt --mode 1 --sector-size 256 --trace --output build/console-slice3/opt-256
python3 tools/test_console_input.py --case raw --mode 2 --order 1 --output build/console-slice3/wait-emu-raw
python3 tools/test_console_input.py --case opt --mode 4 --order 1 --output build/console-slice3/overflow-opt
python3 tools/test_console_input.py --case raw --mode 5 --order 1 --output build/console-slice3/wait-overrun-raw
python3 tools/test_console_input.py --case opt --mode 0 --nmi --output build/console-slice3/post-nmi-opt
```

Modes 0/1/2/3 select idle, continuous SIO, emulation callback and recovery;
4/5 select raw-ring overflow and physical keyboard overrun. Only mode 5 patches
a fixture routine with the checked, deliberately masked test assembly. Ordinary
capture and all key injection still use POKEY's actual scan path. The 12-frame
NMI publication probe uses longer held/release intervals and makes no byte-rate
claim. SIO recovery regressions run in both raw/optimized modes, including
256-byte sectors, because the shared RX path changed.

## Slice 4: queued requests and shared worker

Status: complete, 2026-09-21. The [device qualification](../qualification/console-device.json)
records raw and optimized public-call tests, each with 90 assertions, three
simultaneously live Tasks during physical input, intact guards and restored
hardware/heap ownership. Ordinary builds still do not publish the console.

The fixture explicitly admits one worker through a checked private control
service. A 16-byte immutable boot descriptor identifies its entry. OpenDevice
only binds the exclusive default instance; it never allocates or starts the
worker. READ, WRITE and CLEAR use unchanged IOStdReq and generic completion,
reply and collection semantics. The policy reserves a pending read immediately,
then hands arrivals to the worker under scheduling exclusion. Writes have a
separate FIFO and an active request. Queued cancellation unlinks directly;
active cancellation finishes a logical scroll before reporting the committed
prefix. Completion clears service ownership before replying. CLEAR resets
input/loss while leaving retained cells and an empty waiting read alone.

The worker processes at most 64 source/input bytes or 40 edit cells per quantum,
with input between output steps and IRQs enabled. Full-width buffer validation
precedes transfer. A 65,560-byte linear write verifies crossing a bank and the
64 KiB length boundary. The fixture frees that source, performs another write
and checks the retained result. Another Task completes output while the reader
waits for physical A, Return and BREAK keys. Controlled FIFO fixtures verify
loss reporting and CLEAR ordering independently of the hardware capture tests.
A CLEAR-order test waits for the worker to enter TS_WAIT before introducing loss;
merely observing its read-validation flag does not establish that ordering.

Close checks for queued/active work; callers must collect every borrowed request
before close, as required by the generic device contract. There is no separate
allocation/collection ledger. Successful deferred requests receive one reply;
zero-length and immediate errors use quick completion only when requested.
Offset must be zero, full-width unit/flags are checked, and the `$FFFFFFFF`
write sentinel is rejected. The public overflow constant is generated alongside
the existing Exec I/O constants.

The dependency-free CONSOLECAPTURE module supplies the two native ring operations
to both protected policy and the worker, avoiding an Exec import cycle. Private
policy records are generated from the same layout as worker records. Generic
I/O dispatch was split into small entry/settled/test-device procedures so raw
compiler frames and cumulative kernel stack use remain within existing budgets.
No compiler change or pin override is needed.

Bank-zero reservation change is **0 fixed bytes and 0 per Task**, including guards
and padding. Loading/runtime reservations remain 57,232/61,536 bytes including
OS. Metadata remains 256 upper-RAM bytes: service 136, instance 62, presentation
26 and 32 padding/unused. The 288-byte capture and new 16-byte boot descriptor
fit the existing Task arena. The worker occupies one already reserved 1,568-byte
slot and allocates 960 retained cells plus 128 FIFO bytes; its Task and arrival
port are embedded in service metadata. Snapshot allocation belongs to slice 5.
Maximum observed raw root/worker/kernel stack use is 492/698/1,200 bytes; all
256-byte interrupt reserves remain untouched. Optimized values are 428/552/1,105.

```sh
python3 tools/test_console_device.py --case raw --output build/console-slice4/ordered-raw
python3 tools/test_console_device.py --case opt --output build/console-slice4/ordered-opt
PYTHONPATH=tools python3 - <<'PYTEST'
import json, sys, native_program, test_io_services
from pathlib import Path
pin = json.loads(Path('toolchain/altirra-console.json').read_text())
native_program.PLATFORM_PIN = test_io_services.PIN = pin
sys.argv = ['test_io_services.py', '--compiler-dir', 'build/actionc',
            '--bridge-dir', 'build/console-bridge',
            '--suite', 'queues,handoff,queued_handoff,gap',
            '--output', 'build/console-slice4/io-queues-fast']
test_io_services.main()
PYTEST
```

Generic I/O lifetime, queued SIO and core regressions also pass. The native input
256-byte continuous-SIO regression passes with timing observation and an
unchanged-image replay after the shared dispatch/module changes. This is still
the smaller input workload; integrated display/eight-task timing remains pending.

## Slice 5: borrowed-screen presentation

Status: complete, 2026-09-21. The [display qualification](../qualification/console-display.json)
records raw/optimized checks in kernel banks 1 and 3. A final 30-line fixture
receives a real physical key during an active hidden write, completes that
write, frees its source and later redraws solely from retained cells. Independent
host expectations compare all 960 retained and screen bytes at each checkpoint.
The [glyph capture](../qualification/images/console-glyphs.png) and
[scroll capture](../qualification/images/console-scroll.png) show the pinned output.

[consoledisplay.act](../../lib/console/consoledisplay.act) validates GRAPHICS 0 geometry,
40-column DMA, ROM font, character/priority shadows, normal attract state,
editor cursor extent and the complete 32-byte display list. Screen and list
must be disjoint within OS-high RAM below `$C000`; neither address is hardcoded.
The qualified ROM supplies screen `$BC40` and list `$BC20`. Unsupported mode
startup fails and rolls back allocations without claiming the display. Ten
additional invalid-state checks cover unsafe addresses, font, mode and shadows.
Hardware display registers are write-only to the CPU: runtime validation uses
the pinned ROM's software state, while bridge ANTIC/GTIA readback checks the
physical startup/restoration baseline. This is not a general graphics-mode
adapter or hardware readback API.

The service allocates a separate 960-byte OS screen snapshot, including the
old visible cursor, before removing that cursor. Only presentation writes
physical screen RAM. The generated glyph table maps ASCII `$20–$5F` to codes
`$00–$3F`, lowercase to `$61–$7A`, and `|` to `$7C`. Backtick, braces and tilde
have no matching font glyph and display `?`. The nonblinking cursor saves and
inverts a displayed glyph without changing retained text. One redraw processes
at most 38 source cells plus two cursor stores, bounded by 40 screen writes.
Copies, scrolling and restoration allow IRQs and task preemption throughout.
A private 5×2 clipped-view fixture checks every unrelated cell and guard; it
is not a public window implementation.

Retained ROM stage-one VBI runs even when stage two is suppressed. A bounded
8-byte addition to the existing VBI hook clears ATRACT while display ownership
is active, before the ROM computes colors. No rendering or translation runs
there. The fixture forces the clock/attract wrap while the worker sleeps.
Normal release restores the exact screen snapshot, cursor inhibit and saved
attract state; editor coordinates, display list, font and display/color shadows
remain intact. The smaller keyboard/SIO timing regression and identical-image
replay pass after this hook change: RX maximum 69.36 µs, TX refill 64.85 µs
against 78.94 µs, watchdog 85.64 µs against 100 µs. Display/SIO concurrency is
still reserved for slice 8.

Longer diagnostic scroll workloads are **not passing evidence**: 250 lines
exceeded the 240-second host checkpoint limit; 50 lines exceeded a tighter
60-second limit. The latter had made observable progress (raw Actual 1,961 of
2,001; optimized had completed that write and was finishing the following
scroll), and had already consumed the injected input. The final 30-line case
passes the same 60-second bound. These host-timeout observations establish no
console throughput guarantee; retain them when assessing larger workloads.

The keyboard maps and glyph table are generated from the private ABI into a
256-byte read-only payload at `$F0D30–$F0E2F`, immediately after the worker boot
descriptor, in the existing upper-RAM Task arena. They use explicit 24-bit local
pointers; bare mapped arrays retain the compiler's documented 16-bit address
limit. This removes the former keyboard tables and their pointer cells (134
bytes) from near data and avoids adding a 128-byte bank-zero glyph table.
Packaging and recorded image hashes include the generated table payload.

Bank-zero reservation change remains **0 fixed and 0 per Task**, including
all guards and padding. Loading/runtime totals are 57,232/61,536 bytes including
OS. Presentation grows to 30 bytes inside the same 256-byte metadata reservation,
leaving 28 bytes padding/unused. Resident heap payload is now 2,048 bytes:
960 cells, 960 snapshot and 128 FIFO. The existing worker slot remains 1,568
reserved bytes. The raw display fixture reaches 722 of its 1,024 stack bytes;
the 256-byte interrupt reserve remains untouched, leaving 46 bytes above it.
No compiler pin change is needed; a large fixture oracle was split to respect
the documented stack-relative displacement limit.

```sh
python3 tools/test_console_display.py --case raw --output build/console-slice5/upper-raw
python3 tools/test_console_display.py --case opt --bank 3 --output build/console-slice5/upper-opt-bank3
python3 tools/test_console_input.py --case opt --mode 1 --sector-size 256 --trace --output build/console-slice5/upper-input
python3 -m unittest discover -s tests -p 'test_console_layout.py'
```

The public device regression also passes with presentation enabled. Normal
fixture shutdown is qualified here; coordinated resident and terminal-fault
cleanup and ordinary publication remain slice 6.

## Slice 6: service lifetime and publication

Status: complete, 2026-09-21. The [lifetime qualification](../qualification/console-lifetime.json)
records 32 lifecycle/service cases plus eight public-startup and headless
regressions in raw and optimized code. Configured startup, rollback, client
exit and coordinated retirement pass.

`--console` (or `console: true` in the kernel configuration) starts the worker
in the root Task after memory/Task initialization, before Main. Child Tasks do
not repeat startup. `--no-console` overrides the configuration; the repository
default remains false. The build records the resolved option and validated
worker/start entry addresses. OpenDevice only binds the ready default instance.
Startup failure removes the failed worker and finishes with `$FF95` without
entering Main. Normal stop and failed initialization wait for actual worker
removal, including its intermediate retiring state.

The three resident services now use their known worker/context pointers to
count remaining service Tasks. Removing the last application initiates console
and filesystem retirement; filesystem cleanup releases SIO references so the
serial worker can retire. Root-before-child exit remains legal. An attempted
removal of a bound worker or the last client with an open/busy console fails;
clients still have to abort/collect requests and close the instance themselves.
Closing discards closed-state input but retains the worker and permits reopening.
There is no general service registry or additional Task scan.

ROM console/foreign COP entry is blocked during native console ownership even
without SIO. After safe explicit Stop, the fixture compares the original screen
and keyboard state and successfully calls EXECOS.Write. Terminal faults first
check the existing SIO fail-stop condition. On a safe bus, terminal cleanup
selects the kernel stack/domain, retires keyboard delivery and restores the
saved screen/cursor/attract state before releasing heap claims. Normal worker
release remains preemptible; the terminal copy runs with interrupts disabled
only after safe serial shutdown. Early initialization clears the ownership flags
so fault cleanup cannot interpret uninitialized data as a claimed display.

The unsafe test addresses an absent D8 through real native SIO. It reaches an
independent caller-cleanup checkpoint, then parks at `$FF93` with serial,
keyboard, display and heap ownership retained. Caller buffers have already been
retired from the hardware descriptor. It does not restore ROM state or free the
console snapshot on that path.

The allocation fixture separately exhausts cells, FIFO and snapshot storage;
other cases cover both worker signal claims, a competing native binding, all
remaining execution slots, and invalid screen mode. All roll back and allow a
subsequent valid start. Signal collisions use controlled private fixture setup;
physical close/reopen tests use actual matrix keys. A failed diagnostic initially
put public Task records in heap memory, which admission correctly rejected.
The final capacity fixture uses registered writable upper-RAM image records;
no production admission rule was changed to accommodate it.

Bank-zero reservation change remains **0 fixed and 0 per Task**, including
all guards and padding: loading/runtime totals remain 57,232/61,536 bytes
including OS. The existing 1,568-byte worker slot and 2,048-byte heap payload
are unchanged. Native helpers grow by 104 bytes to 7,526 of their existing
8,192-byte upper-RAM reservation. Bank-zero adapter use grows inside existing
reservations: ROM console +14, exit +4, gateway +8, stubs +27 and boot +22 bytes.
Raw console-only root/worker/kernel stack maxima are 446/679/1,200 bytes; the
combined DOS fixture reaches root 862, console 679, filesystem 724 and SIO 656.
All 256-byte interrupt reserves and domain guards remain intact. No compiler
revision change was required.

```sh
python3 tools/test_console_lifetime.py --case raw --mode 6 --output build/console-slice6/allocation-raw
python3 tools/test_console_lifetime.py --case opt --mode 9 --output build/console-slice6/reopen-opt
python3 tools/test_console_services.py --case raw --mode 4 --output build/console-slice6/pinned-services4-raw
python3 tools/test_console_services.py --case opt --mode 5 --output build/console-slice6/unsafe-final-opt
```

Lifetime modes 0–9 cover ordinary exit, worker removal, open-client exit,
root-before-child exit, ROM return, initial mode failure, allocation, capacity,
signal/binding claims and close/reopen. Service modes 0–3 cover both claim and
release orders, 4 covers automatic console/DOS/SIO retirement after a verified
777-byte MyDOS read, and 5 covers unsafe serial timeout. All modes run in raw
and optimized code. Headless DOS lifetime and queued-SIO regressions also run
in both modes. Package/layout checks pass; display/SIO timing and the complete
eight-task workload remain slice 8.

## Slice 7: resident console and DOS example

Status: complete, 2026-09-21. The [example instructions](../guides/console-example.md)
and [qualification](../qualification/console-dos.json) cover raw/optimized runs on
both original MyDOS sector sizes. The full 70,003-byte file is present only on
the 256-byte fixture; the 128-byte fixture returns and verifies 777 bytes from
the same single 70,003-byte Read request. No write or host-generated replacement
filesystem is used. Both media files remain unchanged.

[console.act](../../examples/console.act) shares its device client, bounded line
editor and persistent reader with the emitted test. It has separate READ/WRITE
requests over one exclusive open and checks durable completion state before
Wait, since output collection can consume their shared port signal while an
input reply is already queued. A separate application reader Task performs
one DOS.Read while the console client continues receiving and echoing keys.
The `t` command previews bytes with explicit ATASCII `$9B` to LF conversion;
other nonprinting bytes become dots. This conversion lives above DOS and the
device. The `e` command demonstrates an ordinary missing-file error. Quit waits
for the reader, collects all requests and closes the console before returning.

Each final run consumes 56 real matrix keypresses, including five during the
active file read. Tests exercise BS at an empty prompt, `ab` → BS → `ac`, 38
presses clamped to a 36-character line, BS within that line, two text opens,
an error and quit. The line's four guard bytes survive, the cursor stays short
of wrapping, every file byte is verified, and the host compares all 259 preview
bytes with an independent conversion expectation. The
[echo](../qualification/images/console-dos-echo.png) and
[file/error preview](../qualification/images/console-dos-files.png) screenshots
were visually checked. The fixture named TEXT.TXT contains a byte-test pattern.

There are three public Tasks after console/reader admission and five after the
first DOS open adds filesystem and SIO workers. Repeated opens, errors and
screen operations leave the count unchanged. The reader is admitted once and
waits on a signal between operations. All five retire cleanly; final screen,
keyboard mask/cursor, heap ownership and stack/domain guards match the baseline.

Two implementation limits were caught by executable checks. An initial reader
routine exceeded its checked raw stack budget during DOS client allocation,
before transfer. Splitting open/transfer/close into natural steps fixed it;
there is no compiler workaround or stack enlargement. Grouping the example's
small globals and text constants also keeps it within the existing 64-extent
manifest capacity. Ordinary helper procedures take a byte argument so only
actual zero-argument entries occupy the bounded Task-entry table.

Bank-zero reservation change is **0 fixed and 0 per Task**. Loading/runtime
totals remain 57,232/61,536 bytes including OS; five existing slots are used.
The example occupies 293 bytes of the existing near-data arena, including its
one static public Task record, and allocates 70,303 bytes of client buffers in
upper RAM, plus its port/requests. Console heap payload remains 2,048 bytes.
Raw observed stack maxima are root 1,250, console 730, reader 760, filesystem
724, SIO 664 and kernel 1,205 bytes. All 256-byte interrupt reserves survive;
the raw reader has only 8 bytes above that reserve in this workload. Further
call depth needs fresh measurement. No platform or compiler pin changed.

```sh
python3 tools/test_console_dos.py --case raw --sector-size 128 --output build/console-slice7/final128-raw
python3 tools/test_console_dos.py --case opt --sector-size 128 --output build/console-slice7/final128-opt
python3 tools/test_console_dos.py --case raw --sector-size 256 --output build/console-slice7/final256-raw
python3 tools/test_console_dos.py --case opt --sector-size 256 --output build/console-slice7/final256-opt
```

These are five-task functional runs with observation disabled. Serial deadline,
eight-task, alternate-kernel-bank and input/display latency qualification remain
slice 8. This example does not implement a complete shell, DOS console handler,
application loader or multiple windows.

## Slice 8: eight-task and serial timing qualification

Status: complete, 2026-09-21. The
[concurrency qualification](../qualification/console-concurrency.json) completes
the initial full-screen console milestone on the pinned emulator. It records
seven workload configurations, including five observed/unobserved replay pairs,
two TX/replay pairs and twelve real serial-fault recovery cases. Raw/optimized
emitted code passes with kernel banks 1 and 3; timing is qualified in bank 1.
STOCK810 coverage is the optimized 128-byte case. No compiler pin changed.

Eight public Tasks are simultaneously admitted and remain live during the file
read: console client, console worker, read client, filesystem worker, SIO worker,
allocator/message producer, signal peer and message receiver. Private idle is
additional. The three work clients perform checked allocation/clear/fill/free,
message ownership/reply and signal handshakes. Their work progresses during the
single DOS.Read. Thirty 40-byte console writes force wrapping and scrolling;
eight physical matrix keypresses produce exactly eight collected reads and
visible glyphs. The first key is aligned with actual serial payload reception.
All returned file bytes are checked, as are every wire byte and all 960 retained
cells mapped to the physical screen, including the cursor overlay. A
[screen capture](../qualification/images/console-concurrent.png) shows the resulting
scroll/echo state. Safe exit restores the screen, keyboard state, heap ownership
and serial pointers.

FASTEST125 uses the existing 78.9423-microsecond byte deadline. Maximum receive
service is **73.87 microseconds**, TX refill **64.85 microseconds**, and watchdog
service **95.79 microseconds** against its unchanged 100-microsecond limit.
There are zero observed RX deadline misses, TX refill misses or TX gaps.
Command setup/hold, post-to-worker, reply collection, subsequent sector start,
CRITIC, Forbid and write-turnaround checks retain their existing limits.
The write/readback fixture injects a real key during payload TX while the
console consumes output; turnaround is 1,237.70–1,248.42 microseconds within
1,000–1,800. Normal transfers still have no mandatory ROM-service sleep.

Each traced workload replays the identical image and guest key schedule with
observation disabled, reproducing the final screen and verified file payload.
This slice only exports two existing native labels; it adds no guest trace
instructions. Timing markers identify existing call/return instructions and
routine entries. Two earlier probes lack the subsequently added BLOCKWIRE
return marker: their reply-collection time is conservatively bounded by the
next serialized request or a known post-collection milestone. The record
explicitly distinguishes those bounds from directly observed collection.
Negative controls remove a captured key or move a SERIN observation past its
physical byte deadline; both fail the expected oracle. These are deliberately
corrupted traces, not additional guest/hardware fault executions.

Keyboard reply and visibility latency are separate from serial timing. The
worker's finish-read call precedes publication; the client's specific WaitIO
return bounds completed reply delivery. Visibility is measured when the client
first observes its unique glyph in screen RAM, so it includes polling and
scheduling. Eight samples per case give these upper bounds:

| Profile | Capture to collected reply, maximum | Capture to observed echo, median / maximum |
| --- | ---: | ---: |
| FASTEST125, 128-byte raw | 61.24 ms | 179.91 / 832.16 ms |
| FASTEST125, 128-byte optimized | 53.74 ms | 158.11 / 734.03 ms |
| FASTEST125, 256-byte raw | 57.78 ms | 259.08 / 984.49 ms |
| FASTEST125, 256-byte optimized | 71.65 ms | 224.44 / 742.32 ms |
| STOCK810, 128-byte optimized | 52.09 ms | 163.08 / 221.26 ms |

Heavy scrolling can therefore delay visible echo by about a second. Input is
retained and clients complete, but this is a usability limitation, not a new
hard real-time keyboard guarantee. The JSON record includes all samples and
min/mean/median/p95/p99/max distributions; with eight samples p95/p99 select the
maximum. Faster presentation remains a measured follow-up rather than a hidden
acceptance assumption.

The longest Forbid interval is 9.05 ms. Masked maxima include the existing
idle task's `SEI`/`WAI` interval: WAI wakes on a pending maskable IRQ even with
I set, then executes CLI before delivery. Whole-residency and transaction-envelope
maxima are reported separately with their entry PCs; they must not be described
as CPU work blocking every serial byte. The unchanged per-byte oracle checks
actual arrival/refill latency independently.

The full 70,003-byte Read takes 49.37 seconds raw and 48.94 seconds optimized,
or **1,418/1,430 bytes per second**, with accurate floppy mechanics enabled.
The original 128-byte fixture contains only 777 bytes and returns a short read
from the same 70,003-byte request: 584/692 bytes per second at FASTEST125 and
332 at STOCK810. These are single-call filesystem measurements with concurrent
work, excluding Open, verification and cleanup. They are not wire bandwidth
or a new throughput optimization.

Checks have preset 180-second/9,000-frame interaction limits and
1,800-second/30,000-frame large-read/completion limits. TX has separate
120-second checkpoint and 240-second completion limits. Six existing D8 fault
cases run in each compiler mode with the configured console resident; first
error, offline state, post counts, cleared request pointers and independent
cleanup checkpoints retain their existing assertions. Input during recovery
and unsafe console/heap retention are covered by the earlier coexistence and
lifetime records. Relevant generic-I/O, signal/Wait, DOS lifetime and ROM adapter
regressions are linked rather than represented as newly rerun suites. This
slice also passes 68 package tests, five console layout/admission tests,
generated-layout checks, Python compilation, document links and diff checks.

Bank-zero reservation change is **0 fixed and 0 per Task**, including padding
and guards. Loading/runtime totals remain 57,232/61,536 bytes including OS.
The console occupies one existing 1,568-byte worker slot. Its upper-RAM costs
are 256 bytes of metadata (136-byte service containing Task and port, 62-byte
instance, 30-byte presentation and 28 bytes of spacing), 288 bytes of capture
state including binding/ring, 16 boot bytes and 256 glyph/keymap bytes in the
existing Task arena. Three AllocMem payloads consume exactly 960 + 128 + 960 =
2,048 bytes; all are eight-byte multiples, with no live allocation header or
rounding waste. Existing global heap metadata remains shared. Native helpers
remain 7,526 of 8,192 reserved bytes; no adapter instructions grow in this slice.
The fixture admits three additional public Task records in a registered
192-byte upper-RAM image extent. Stack/domain guards and all 256-byte interrupt
reserves survive. The raw reader still reaches 760 of 1,024 bytes, leaving only
8 bytes above its interrupt reserve; deeper call chains need fresh checks.

```sh
python3 tools/test_console_concurrent.py --case raw --sector-size 128 --trace --output build/console-slice8/target128-raw
python3 tools/test_console_concurrent.py --case opt --sector-size 256 --trace --output build/console-slice8/target256-opt
python3 tools/test_console_concurrent.py --case opt --sector-size 128 --speed 1 --trace --output build/console-slice8/stock128-opt
python3 tools/test_console_concurrent.py --case raw --bank 3 --output build/console-slice8/bank3-raw
python3 tools/test_console_tx.py --case raw --output build/console-slice8/tx-raw
python3 tools/test_console_recovery.py --case opt --output build/console-slice8/recovery-opt
python3 tools/test_console_trace.py --probe build/console-slice8/target128-opt --output build/console-slice8/trace-controls
```

Run both compiler modes for the FASTEST125 sector sizes, alternate-bank
functional workload, TX and recovery. The bridge, ROM, media and compiler
hashes are in the qualification record. Large-read runs can take tens of host
minutes with passive observation and debugger checkpoints; the bounds above
remain enforced.

## Initial milestone completion

All eight initial-console slices are complete and committed separately:

| Slice | Evidence | Commit |
| --- | --- | --- |
| 1. Keyboard/SIO gate | [Coexistence](../qualification/console-coexistence.json) | [`7768a38`](https://github.com/mkur/exec816/commit/7768a38) |
| 2. Terminal core | [Core](../qualification/console-core.json) | [`5ef412f`](https://github.com/mkur/exec816/commit/5ef412f) |
| 3. Input delivery | [Input](../qualification/console-input.json) | [`9d12b8d`](https://github.com/mkur/exec816/commit/9d12b8d) |
| 4. Device requests | [Device](../qualification/console-device.json) | [`2fbbd79`](https://github.com/mkur/exec816/commit/2fbbd79) |
| 5. Presentation | [Display](../qualification/console-display.json) | [`0a1c615`](https://github.com/mkur/exec816/commit/0a1c615) |
| 6. Service lifetime | [Lifetime](../qualification/console-lifetime.json) | [`5871102`](https://github.com/mkur/exec816/commit/5871102) |
| 7. DOS example | [Example](../qualification/console-dos.json) | [`2b386d1`](https://github.com/mkur/exec816/commit/2b386d1) |
| 8. Integrated qualification | [Concurrency](../qualification/console-concurrency.json) | This commit: `Qualify console I/O under concurrent SIO and DOS` |

Use `--console` to enable configured startup and follow the
[example instructions](../guides/console-example.md). Independent text windows, focus
and multi-instance fairness remain the required
[follow-up stages](../plans/console-io-implementation-plan.md#required-multiwindow-follow-up).
This milestone does not implement a complete shell, DOS `CON:` handler,
application loader/format, 12–16-task capacity or physical-hardware qualification.
