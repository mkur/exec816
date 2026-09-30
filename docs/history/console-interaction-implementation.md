# Console interaction implementation record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/console.md) and [history index](README.md).

The [console plan](../plans/console-interaction-implementation-plan.md) is implemented
through W3. Window development checks pass; full release qualification remains
pending.
S0, C1–C3 and B1–B5 are complete; window development and release qualification
are tracked separately under the [testing policy](../contributing/testing.md). Historical results are recorded in
[console-interaction.json](../qualification/console-interaction.json).

## S0: historical qualification validation

The historical sector record now validates against
[explicit Git provenance](../qualification/sio-sectors-provenance.json), preserving
all measured hashes. Each of its 17 source inputs matches its recorded SHA-256
and a named commit/blob. These inputs span multiple revisions; this does not
assert they formed one checkout. Validation requires the referenced Git objects;
shallow checkouts must fetch that history.

Fresh sector suites capture all publication inputs before execution and check
them again afterward. The collector requires both execution snapshots to match
current sources, validates the build hashes and checks once more before writing.
Old run artifacts without execution snapshots cannot be republished as fresh.

Validation: `python3 -m unittest discover -s tests -p 'test_*.py'` passes all
160 tests, including preserved timing/coverage/replay negative controls, changed
historical provenance, stale execution sources and missing snapshots. No guest
execution or new transport qualification was run for this maintenance slice.

Reserved bank-zero change: **0 fixed bytes; 0 bytes per Task**, both during
loading and runtime, including guards, alignment and unused capacity. No target
memory layout or production transport code changed.

## C1: cooked terminal state

`COOKEDLINE` implements the [cooked input contract](../reference/cooked-console.md):
255 edited characters plus LF, partial reads, one-shot EOF, break, discard
through Return after overflow/loss, and tail redraw that preserves the prompt.
Its 400-byte session layout and signed private pending result are generated from
`abi/dos.json`. C2 publishes CON: Open using this state.

`tools/test_cooked_line.py` executes 192 operations against an independent byte
and terminal model in raw/optimized kernel-bank-1 builds and optimized bank 3.
It checks session/output guards, independent sessions, allocation exhaustion and
full memory recovery. Existing stack/domain guards, protected interrupt reserves,
OS restoration and bank ownership checks pass. The host suite passes 160 tests;
generated DOS definitions pass their freshness check.

Commands: `python3 tools/test_cooked_line.py --case raw --output
build/console-interaction/c1/raw`, the corresponding `--case opt` run, and
`--case opt --bank 3 --output build/console-interaction/c1/bank3-opt`.
These test the terminal state, not physical CON: editing or foreground delivery.

Memory: 400 upper payload bytes per session (already divisible by the allocator's
eight-byte alignment), with line and echo capacity included. No new shared or
per-Task reservation. Reserved bank-zero delta: **0 fixed bytes; 0 per Task**,
including guards, alignment and unused reserved capacity.

## C2: physical CON: backend

Bare CON: now opens an owned cooked session; CONSOLE: and suffixes remain
unsupported. RAW: and CON: share the physical endpoint and retain one reader
lease through each cooked line, including echo. Writes, selected streams and
close use the existing endpoint lifecycle. Input and echo reuse one request,
collecting each exact completion before reuse. Echo follows the edited console
when selected Output is NIL:. No filesystem worker waits for keyboard input.

`tools/test_dos_cooked.py` passes raw/optimized bank 1 and optimized bank 3 on
the pinned paced AltirraOS emulator with FASTEST125, accurate disk timing and
SIO patching disabled. Physical tests cover editing, small and zero-length reads,
partial/empty Ctrl-D, BREAK, long-line discard, input loss, failed echo and
resynchronization. A second Task completes a MyDOS read while CON: waits and
receives the expected competing-reader error. Session/handle/endpoint/request
allocation failures recover all memory; close/reopen, selected-handle retirement,
request collection, screen/cursor restoration and stack guards pass.

The existing optimized RAW regression also passes its 70,003-byte Write,
first-opener exit and shared endpoint lifetime checks. The NIL regression passes
its verified headless no-console-access scope. The host suite passes 160 tests.
These are functional native checks, not a new serial deadline qualification.
Exact run inputs, compiler/ROM/configuration and artifact hashes are recorded in
[the qualification record](../qualification/console-interaction.json).

Memory: each CON: handle adds a 400-byte upper session and a 20-byte handle
rounded to 24 bytes (RAW uses 16). Existing shared endpoint, request and client
allocations retain their extents. No worker or shared reservation is added.
Reserved bank-zero delta: **0 fixed bytes; 0 per Task**, including guards,
alignment and unused reserved capacity. The eight-slot totals remain 57,232
loading bytes and 61,536 runtime bytes including the OS reservation.

## C3: shell migration

The shell now opens CON:, prints its prompt and accumulates completed input in
chunks of at most 64 bytes. It replaces the final LF with NUL before parsing;
its duplicate per-key editor is removed. An empty EOF exits normally, and a
partial EOF dispatches the last unterminated command before cleanup. Break
redraws the prompt. Overflow and loss report failure after cooked resynchronization,
so no accepted prefix or surviving suffix becomes a command.

Parsing, diagnostics, built-ins and temporary file/NIL redirection remain in the
shell. Echo remains with the edited console, including when command Output is
redirected. Startup, selector restoration, close failures, Task removal guards,
serial failures and full ownership recovery use the existing lifecycle paths.

All 75 required matrix entries pass, including the shipped shell, full command,
redirection and lifetime suites in raw/optimized code, seven eight-Task workloads
and five observation/replay pairs. Both sector sizes and the complete 70,003-byte
file pass; every measured serial deadline passes. Guards remain intact, no
protected interrupt reserve is touched, and the host suite passes all 160 tests.
The physical observer records actual cooked transfers; command dispatch and echo
are separate measurement boundaries. Test fixtures formerly treating CON: as unsupported now use the
unsupported CONSOLE: alias, and positive CON: redirection is covered. The physical
redirection runner uses the shipped entry's matching generated disk. Bank-3
capture buffers were moved above the enlarged emitted image; these buffers are
test-only and never become production reservations.

Idle scrolling remains 88 raw / 78 optimized ticks for 16 lines (110 / 97.5 ms
per line), below the 112-tick gate. With no competing writer, physical-key to
checked screen/cursor bounds are 120–140 ms, including key-release delays and
one frame of measurement rounding. Under eight-Task flooding, capture to exact
input collection is at most 63.1 ms; capture to retained cooked echo completion
is at most 1,289.4 ms raw / 575.7 ms optimized across these cases. Echo completion
does not measure physical scanout. These observations do not qualify B5's
cancellation targets or W3's per-window fairness limits.

Replay now anchors exact keyboard frame intervals to the eight-Task admission
checkpoint. The previous absolute-frame harness exposed a three-tick difference
in native-program boot time; the same saved image passed with matching boot
time. An independent control then passed with an eight-frame admission offset
using relative intervals. The final 256-byte optimized case passes fresh
observation/replay under this protocol, preserving its serial IRQ rendezvous,
exact frame intervals, emitted image, output and physical screen checks. Earlier
passing pairs retain their stricter absolute-frame schedules in the record.

Commands: `python3 tools/test_shell_core.py --case raw --eof empty --output
build/console-interaction/c3/core-raw-final` and the optimized `--eof partial`
case; `test_shell_commands_suite.py`, `test_shell_redirection_suite.py` and
`test_shell_lifetime_suite.py` in both modes; `test_shell_entry.py --paced` in
both modes; `test_shell_concurrent_suite.py` for its seven configurations; and
`test_console_scroll.py` in both modes. Tests use their pinned machines and
bounded guest/host limits. No physical-hardware qualification is claimed.

Memory: the shell's 1,288-byte upper allocation is unchanged, including the
unused editor-field capacity and shared number-formatting scratch. Its existing
stream allocation changes from a 16-byte RAW handle to a 24-byte allocated CON:
handle plus the 400-byte cooked session. No worker or fixed reservation is added.
Reserved bank-zero delta: **0 fixed bytes; 0 per Task**, including guards,
alignment and unused capacity. Eight-slot loading/runtime totals are unchanged.

## B1: foreground identity and delivery

The [foreground contract](../reference/foreground-break.md) now exposes
BeginForeground, EndForeground, BreakPending and ClearBreak. An owned CON:
handle binds its retained DOS context and Task to one allocated signal and a
nonrepeating generation. Renewing a scope retires old breaks; ending it clears
every retained route's target before freeing the scope. Close, context release
and Task removal cannot bypass that ownership. Query and acknowledgement preserve
IoErr. The shell starts using scopes in B5; DOS wait interruption starts in B2.

The IRQ captures four-byte route tags without following Task pointers. The
worker resolves them through 16 retained records and publishes durable pending
state before signalling. A separate mailbox preserves a bound break when the
raw ring is full or translated input has been lost. Bound and retired breaks
never become a second input byte. Binding also retires old unbound break bytes
without discarding ordinary translated typeahead. Unbound RAW still reads $03.

Raw/optimized native fixtures pass real Ctrl-C during a no-yield compute loop,
BREAK during a signal wait, redirected Input, repeated/coalesced events, stale
signals, old-route handoff, table/epoch exhaustion, allocation/signal failure,
Task removal/reuse, both input-loss paths and full cleanup. Bank 3 passes too.
Separate raw/optimized images deliberately hold publication between its two
word stores: at least two real NMIs run, IRQ stays deferred, and the resulting
physical BREAK reaches only the fully published generation. These stalled
images are functional controls, not latency evidence.

Passive ordinary-image capture-to-durable-store bounds are 18.814 ms raw and
15.304 ms optimized for the compute/wait cases. The loss controls include a
deliberate worker hold and remain below 63 ms. These have two live Tasks during
delivery; B5 still owns the eight-Task cancellation/prompt limits. The updated
native DOS ABI passes every call in both modes. Headless NIL, selected streams,
client reuse and concurrent file tests pass. Native keyboard/SIO coexistence and
both eight-Task 128-byte shell observation/replay cases pass with zero serial
deadline misses. Scrolling remains 110 / 97.5 ms per line. All 160 host tests pass,
including unchanged historical ABI evidence with its original required call set.

Memory: the scope uses 22 upper payload bytes, rounded to 24, plus one allocated
signal. ClientContext grows from 84 to 86 bytes inside its existing 88-byte
allocation. The 264-byte route table reserves 272 upper bytes, increasing console
metadata from 256 to 528 bytes. Capture grows from 288 to 560 active bytes:
256 bytes of tags plus 16 header bytes. Capture, boot descriptor, glyphs and
keymap end at Task-arena offset $F40 inside the existing $1000 reservation.
No worker, stack or DP is added. Reserved bank-zero delta is **0 fixed bytes;
0 per Task**, including guards, alignment and unused capacity; eight-slot
loading/runtime totals remain 57,232 / 61,536 bytes including OS reservation.

## B2: interruptible console waits

RAW and CON now wait on the exact request reply and the foreground signal.
Durable completion wins when already present; otherwise pending break requests
AbortIO once and still collects that request's terminal reply. A stale signal
cannot complete a transfer. Break before submission leaves the request unsent.
A canceled RAW Read/Write returns its committed positive prefix with IoErr 304,
or failure with 304 when no bytes committed. Earlier device errors retain their
cause. The request, caller buffer, busy flag and input lease remain owned until
collection, then become reusable.

Cooked cancellation retires valid partial input and queued typeahead, emits a
cleanup newline and returns the break error. Echo progress is never returned as
input. A line already invalidated by loss/overflow keeps its discard-through-Return
state and original resynchronization error. Cleanup ignores sticky break.

`tools/test_console_cancel.py` passes 602 native checks in raw/optimized bank 1
and optimized bank 3. Real BREAK cancels empty reads, a queued Write behind a
continuing peer, and an active scrolling Write. Controlled scheduling checks a
64-byte Read prefix, exact collection, break before SendIO, stale notification,
completion winning and break after collection. The canceled scrolling prefix
matches independent retained and physical-screen/cursor oracles. Reusing and
overwriting caller buffers after return causes no subsequent worker access.
All resources, stack/domain guards and the OS console recover.

Both current cooked-console regressions and eight-Task 128-byte shell
observation/replay cases pass. The latter preserve image, keyboard intervals,
output and serial deadlines. The host suite passes all 160 checks. These are
console cancellation and coexistence checks; filesystem cancellation and the
B5 prompt deadline are still pending. Test-only rendezvous hooks are identified
in the qualification record and are not latency evidence.

No persistent allocation, signal or Task is added beyond B1. Reserved bank-zero
delta is **0 fixed bytes; 0 per Task**, including guards, alignment and unused
capacity. Eight-slot loading/runtime totals remain 57,232 / 61,536 bytes including
the OS reservation; the existing interrupt reserves remain untouched.

## B3: queued filesystem cancellation

Each participating foreground scope now carries a private operation sequence,
command generation, packet/handler identity and prepared/queued/active/replied/
collected state. Cancellation is an independent durable flag and queue link,
never a second use of the busy client's packet. Scope/context lifetime and
identity validation protect every queued reference. Sequence exhaustion rejects
submission. Cleanup calls remain noninterruptible.

A dynamically allocated filesystem-worker signal wakes a bounded queue of at
most eight cancellation records. Worker dequeue and cancellation serialize their
claim with Forbid; only the winner removes/replies to a queued packet. Reply
retires any cancellation link before publishing the message, and the caller
collects that exact packet before releasing its buffer, mount reference or busy
flag. Late and repeated requests cannot cancel a replied or reused operation.
Active requests retain their cancellation flag for B4 but still complete normally
in this slice.

BLOCKWIRE now sends its serial request and waits on reply/control signals. It
can cancel another client's queued packet while preserving sole ownership of its
current adapter/request. It neither starts another sector nor releases the
borrowed serial buffer before exact collection. Public DOS remains synchronous.

Raw/optimized and bank-3 native fixtures pass queued Read/Open/Lock cancellation
while a peer completes and verifies all 70,003 file bytes. Another client retains
its request order and succeeds. Controlled scheduling covers cancellation versus
dequeue and reply, stale requests and sequence exhaustion. Observed physical BREAK injection to the next caller checkpoint is at most
120 ms, including frame rounding and next-scope setup, in the six-live-Task
queued fixture. B5 still owns the eight-Task break/prompt gate. Separate raw/optimized
fixtures reuse the same Task, DOS-context and scope addresses: the retired route
does not cancel the new client, and a fresh physical BREAK does. Allocation,
mount references, signals, ports, stack/domain guards and OS state recover.

Ordinary concurrent files, DOS ABI calls, early replies, 260 client lifetimes,
foreground delivery and startup rollback also pass. The historical lifecycle
schema retains its original startup matrix; fresh schema 2 requires the added
control-signal failure case. All 162 host checks pass and reject a fresh record
missing that case. Native keyboard/SIO coexistence and both-mode checksum,
device-error, short-response, first-cause, framing and protocol recovery regressions
retain their existing safe-return or unsafe-bus fail-stop outcomes.

The first raw eight-Task trace exposed a 101.427 µs fine-alarm service time,
exceeding the unchanged 100 µs limit. The timer asserted during keyboard IRQ
capture after the main timer scan; the console service path checked RX and the
watchdog but deferred the fine alarm to another IRQ entry. It now services at
most one RX byte, watchdog, fine alarm and TX refill per console-service call,
using current enables and preserving watchdog priority. The final raw/optimized
observation/replay matrix passes all serial limits. The raw fine-alarm maximum
is 74.361 µs; watchdog maximum is 83.383 µs. This change adds no storage
and leaves timeout, recovery and unsafe-bus behavior unchanged.

Memory: the scope grows from 22/24 payload/allocated upper bytes to 44/48. The
filesystem registry grows from 90 active bytes to 96 inside its existing 96-byte
reservation. One additional signal belongs to the existing filesystem worker;
there is no per-operation allocation or extra worker. Reserved bank-zero delta
is **0 fixed bytes; 0 per Task**, including guards, alignment and unused capacity.
Eight-slot loading/runtime totals remain 57,232 / 61,536 bytes including the OS.

## B4: active filesystem and transport cancellation

Filesystem cancellation now runs between bounded path, directory, sector and
copy steps, including a check immediately before starting another sector. A
canceled Read returns its committed prefix with ERROR_BREAK and advances the
cursor by that exact count; zero progress returns failure. Seek preserves its
starting position. Unreturned Open/Lock objects are freed before reply. Object
publication and directory-result publication are explicit completion-wins
regions, so cancellation cannot leave an inaccessible object or partially replace
an enumeration cookie. Reply clears retained parser and caller pointers.

The filesystem worker remains the sole adapter owner. Its private conditional
SIO operation uses the existing AbortIO engine while queued/preparing, then
collects the exact reply. An already-started healthy frame finishes under its
existing finite deadline; cancellation stops the filesystem before subsequent
copying or another transfer. Public on-wire AbortIO is unchanged. Existing
checksum, device, timeout, framing and protocol errors retain precedence, with
unsafe bus state still requiring the existing offline/fail-stop path. Cleanup
Close/UnLock and collection complete despite pending or repeated break.

The native matrix passes 135 healthy checkpoint cases: raw/optimized code,
128/256-byte sectors, FASTEST125/GENERIC57600 and a bank-3 placement. It covers
first/middle/final Read sectors, pre-submission, copying, Seek, object allocation
and publication, directory scanning/publication, serial preparation, wire
activity and terminal completion. Tests verify exact bytes and cursor, untouched
suffix/guards, post-return buffer reuse, one terminal collection, retry and full
heap/port/signal ownership recovery. These deterministic tests inject through
the real task-side foreground delivery function; they are not physical-key
latency measurements.

Another 48 native cases combine real peripheral faults with break during wire
activity or after terminal error, in both compiler modes and sector sizes.
Fast protocol rejection can finish before the injecting Task runs again; that
case records a terminal race rather than claiming wire-time injection. Recoverable
faults permit another successful request. Unsafe cases verify the original cause,
cleared serial buffer pointers and complete command/filesystem cleanup before the expected
$FF93 reset-required stop; they do not claim OS restoration. Forty original
public SIO abort/recovery cases also retain their expected outcomes.

Both queued-cancellation regressions and eight-Task physical keyboard/SIO
observation/replay runs pass. Replay preserves the image, input intervals,
output bytes and physical screen; all existing serial deadlines remain enforced.
The raw fixture grew into bank $0C, exposing its arbitrary fixed-bank scratch
reservation as a limit on its 70,003-byte allocation. Its 8,192-byte observer now
uses ordinary upper heap storage, its Task records use declared writable image
storage, and the host captures output before that allocation is freed. The
workload, read size, live Task count and timing gates are unchanged.

All 162 host checks pass. No persistent allocation, signal or worker is added.
Reserved bank-zero delta is **0 fixed bytes; 0 per Task**, including guards,
alignment and unused capacity. Eight-slot loading/runtime totals remain
57,232 / 61,536 bytes including the OS; protected interrupt reserves stay intact.
B5 still owns command-scope integration and the 100/250/500 ms acceptance gates.

## B5: shell cancellation and prompt recovery

All 25 physical-input cases with replay and 32 native regression runs pass on
the pinned platform. All 168 host tests pass, including negative controls for
missing matrix coverage, invalid timing and delayed/incomplete peer sector chains.
Measured maxima are **42.479 ms** capture-to-durable, **41.751 ms** queued
publication-to-exact-collection and **402.343 ms** capture-to-usable-visible-prompt,
below the unchanged 100/250/500 ms limits. The peer's maximum next-sector gap is
164.058 ms, below its existing 200 ms gate.

The shell renews its foreground generation between prompt editing and each
built-in. TYPE/DIR poll between bounded steps, and their console/filesystem waits
use B2–B4 cancellation. CD checks its acquired candidate before exchanging the
selected directory. Command retirement restores Input/Output, closes temporary
resources, clears valid typeahead and renews the prompt scope. ERROR_BREAK is a
recoverable status 10; the fresh prompt acknowledges it without an error
diagnostic. Earlier errors retain precedence. Scope admission failure unwinds
startup; late captured events and stale signals do not cancel the next command.

Canceled console output finishes its already committed scroll before replying.
The worker keeps its 64-byte source, 40-cell edit and 38-cell redraw budgets,
checks input between quanta and remains VBI-preemptible. It omits voluntary yields
while retiring that bounded canceled edit. Final-byte/idle writes now reply in
the same quantum. Cooked cleanup emits a newline only when the cursor is not
already at column zero, avoiding a redundant full-screen scroll.

The physical-input fixture uses eight live Tasks and verifies a subsequent
physical `ECHO OK`, exact selectors and resource ownership, scope renewal, empty
reply queues, full heap recovery, stack/domain guards and OS restoration. Its
25 cases cover raw/optimized compute, Ctrl-C, typeahead retirement, queued/active
TYPE, DIR, CD, redirected TYPE and active scrolling output. Both compiler modes
also cover 256-byte media at GENERIC57600; a bank-3 case checks placement.
The peer performs one complete 70,003-byte Read on 256-byte media or a 777-byte
Read on 128-byte media, verifying every byte. Queued cancellation returns while
that peer remains active. Observation and replay retain the same image and every
relative keyboard/control frame, and match the recovered physical screen.

Capture-to-durable delivery is gated at 100 ms. Queued cancellation is gated at
250 ms using the caller's exact packet collection as a conservative upper bound
on terminal reply publication. The 500 ms prompt gate uses the later of physical
RAM completion and caller readiness after collecting its prompt Write. Separate
keypress-to-observed-frame measurements include hardware scanning and frame
rounding. These are healthy-path measurements; B4 retains the fault/recovery
qualification and unsafe-bus fail-stop behavior.

Serial byte, timer, masked-interval and scheduling limits remain unchanged. A
separate oracle extracts the peer's full file chain from the ATR and checks every
consecutive sector against the existing 200 ms next-start limit. Testing exposed
RX/timer edges arriving after the main serial scan or during keyboard handling.
The IRQ now services serial state before keyboard routing and rechecks RX after
watchdog service and at the end of the bounded console helper. Each helper has
at most three RX checks, one watchdog, one fine alarm and one TX refill, with no
loop or new storage. A trailing byte after terminal completion retains the
existing recovery/offline path.

The regression matrix includes raw/optimized cooked editing, 602 console
cancellation checks, idle scrolling, commands, redirection, the shipped paced
shell, TX and native keyboard/SIO coexistence. Sixteen lifetime runs cover the
existing cleanup failures, new foreground signal/heap exhaustion and a late
command-generation break. Core/command/redirection observers now allocate upper
heap capture storage and snapshot it before FreeMem; their rendezvous hooks are
functional observations, not timing evidence. Idle visible scrolling remains
110 ms raw / 97.5 ms optimized per line, within the unchanged 112-tick gate for
16 scrolls.

Reproduce an individual timing case with `python3 tools/test_shell_break.py
--case raw --scenario queued-type --size 256 --profile 1 --bank 1 --replay
--output build/console-interaction/b5/gate-break/raw-queued-type-256-p1-b1`.
The collector's `MATRIX` specifies all 25 combinations; profile 1 is FASTEST125
and profile 4 is GENERIC57600. `python3 tools/record_console_break.py` checks
complete coverage, current input hashes, pins, replay, timing and memory before
publishing. Execution uses the [paced shell pin](../../toolchain/altirra-shell-paced.json)
and the recorded compiler revision without overrides.

Memory: the shell now participates in the existing 44-byte foreground scope,
allocated as 48 upper bytes, and owns one signal. Its 1,288-byte shell allocation
is unchanged; no shared state or worker is added. Reserved bank-zero delta is
**0 fixed bytes; 0 per Task**, including guards, alignment and unused capacity.
Eight-slot loading/runtime totals remain 57,232 / 61,536 bytes including the OS;
protected interrupt reserves remain intact.


## W1: independent instance binding and lifetime

Implemented four console slots through one resident worker: the permanent default
and three owner-created instances. Each has independent retained cells, input,
read/write queues, foreground scope and DOS endpoint. `CONSOLE.Create/Destroy`
uses opaque non-reused units; RAW/CON accept an eight-hex-digit unit suffix.
Creation rolls back every allocation, open references prevent destruction, and
Task removal rejects a live owned instance. A permanent registry borrow protects
the worker's final pointer access during retirement. Additional instances remain
hidden until W2 implements presentation and focus.

The worker rotates runnable instances with its existing source/edit/redraw
budgets. A default-only fast path avoids scanning empty slots, and an active
write omits the redundant global idle query. The idle scrolling regression passes
at 115 ms raw / 102.5 ms optimized per line, within the unchanged 112-tick gate
for 16 scrolls. Cooked input recalculates the tail width after advancing a row;
positive reads on windows narrower than three columns fail explicitly.

Development evidence is recorded in [console-windows.json](../development/console-windows.json).
Both raw and optimized builds pass 118 normal lifetime/isolation assertions,
9 assertions before the expected owner-removal fault, and 49 before the expected
active-close fault. Cases cover allocation rollback, slot/identity exhaustion,
stale units, pending reads on two instances, output isolation, endpoint sharing,
foreground binding, narrow cooked input and repeated full-size create/destroy.
Normal completion restores heap/ownership and the OS screen, cursor and keyboard
mask; all scenarios preserve the stack/domain guards. Reproduce either compiler
mode with `python3 tools/test_console_windows.py --case raw --output
build/development/windows/raw` (substitute `opt` for the optimized case).

Focused supporting checks pass for physical device I/O, foreground break,
keyboard/SIO coexistence, shell smoke and idle scrolling. These precede the final
narrow-CON correction, which the final raw/optimized instance fixtures exercise.
All 168 host tests and generated-definition checks pass. This is development
coverage; window presentation/fairness and release qualification remain pending.
The compiler, paced emulator and ROM pins are recorded without local overrides.

Fixed upper reservations grow by **192 bytes**: a 144-byte window registry and
48 bytes for three additional DOS endpoint slots. Each additional instance uses
**224 + round8(width × height)** upper heap bytes. The foreground scope's 48-byte
allocation and endpoint's 104-byte allocation are unchanged despite larger
payloads. Reserved bank-zero delta is **0 fixed bytes; 0 per Task**, including
guards, alignment and unused capacity. Eight-slot loading/runtime totals remain
57,232 / 61,536 bytes including the OS; protected interrupt reserves are intact.


## W2: tiled presentation and captured focus

Implemented owner-controlled Show/Hide/Focus, nonoverlapping full-size tiles,
hidden output and one focused cursor. Hiding or destroying the focused instance
selects the lowest visible slot; closing its I/O binding retains presentation.
A serialized presentation transaction pauses worker borrows, drains an existing
quantum, and erases at most one 40-cell row per yield. Its owner and the shared
screen remain protected against Task removal and service shutdown.

Physical keys keep their captured instance across focus changes. BREAK and loss
use separate 16-bit route mailboxes, so another focused window cannot overwrite
a pending notification. Native clear/open/close acknowledges only the selected
unit's loss and tombstones its captured events. It preserves other input and
bound BREAK. IRQ performs a fixed tag-slot bit lookup without instance/Task
pointers or a window scan; route resolution and bounded retirement run in task
context with IRQ enabled outside short bitmap transactions.

Development checks pass in raw bank-3 and optimized bank-1 builds: 114 native
assertions each, real key/BREAK injection, and eight exact 960-byte screen/cursor
checkpoints. They cover overlap/edge rejection, queued keys and two pending
BREAK routes, overflow in one window while another retains 64 keys, input
retirement across close/reopen, focused/unfocused destruction and hidden redraw.
Both restore the exact OS screen, cursor, keyboard ownership, heap and request
ownership, with untouched interrupt reserves. Run `python3 tools/test_console_focus.py
--case raw --bank 3 --output build/development/windows/focus-raw-b3` or use
`--case opt` with the default bank.

The focused native keyboard/SIO trace and foreground-break regression pass;
raw/optimized idle scrolling remains 115 / 102.5 ms per line inside the existing
gate. All 168 host tests pass. The [development record](../development/console-windows.json)
retains pinned build inputs and results; W3 and complete release qualification
remain pending. This does not requalify the full SIO/platform matrix.

W2 adds no record allocation or fixed/per-Task bank-zero reservation. It uses
existing padding for focus, presentation ownership and route bitmaps. Native
code grows from 7,933 to 8,300 bytes. Its linker subregion grows from 8,192 to
8,704 bytes, including 404 unused bytes, inside the already reserved upper Task
arena; the outer reservation is unchanged. Eight-slot loading/runtime bank-zero
totals remain 57,232 / 61,536 bytes including the OS and all guards/alignment.


## W3: multiwindow progress under eight-Task SIO

The W1 worker's rotation passes the bounded development workload without further
production changes. It keeps the 64-source-byte, 40-edit-cell and 38-redraw-cell
budgets. Root, console/filesystem/SIO services and four application clients are
simultaneously live. Three tiles run a continuous producer, eight small writes,
two pending readers, focus changes and a computing foreground scope. Small-write
measurement starts after the producer's first actual scroll. Each compiler mode
completes two exact 777-byte DOS reads on 128-byte media at FASTEST125.

Limits were frozen before the first W3 execution. Observed maxima are:

| Observation | Raw | Optimized | Limit |
| --- | ---: | ---: | ---: |
| Eight-byte Write to exact collection | 78.486 ms | 75.196 ms | 250 ms |
| Small Write to observed redraw | 78.549 ms | 97.002 ms | 500 ms |
| Continuous 20-byte Write, including scroll | 510.858 ms | 384.135 ms | 1,000 ms |
| Captured key to another window's collected Read | 48.661 ms | 57.592 ms | 250 ms |
| Captured key to observed RAW echo | 105.904 ms | 91.106 ms | 500 ms |
| Captured key through CON line echo/collection | 248.552 ms | 190.399 ms | 500 ms |
| Captured BREAK to durable notification | 33.405 ms | 9.154 ms | 100 ms |

The cooked observation includes the fixture's physical Return after the first
key; it is a line-completion upper bound. Raw/optimized producers complete
18/21 writes. Both runs reach all eight small writes, preserve exact retained
bytes and the full physical screen/cursor, and use at most six retained route
slots. The native IRQ captures actual Z, A, Return and BREAK presses. Both
pending readers coexist; focus selects the intended one while output continues.

All 35 SIO transactions per run retain existing byte, phase, mask, alarm,
collection and scheduling checks. Maximum next-sector gaps are 96.994 / 109.027
ms, below the unchanged 200 ms limit. The first measured key overlaps an active
DOS.Read. Stack/domain guards, protected interrupt reserves, heap/ownership,
media bytes and exact OS console restoration all pass. Five host tests exercise
negative controls for late, missing, duplicate and reversed observations; all
173 host tests pass. The shipped shell's focused smoke test also passes.

Reproduce with `python3 tools/test_console_fairness.py --case raw --output
build/development/windows/fairness-raw`, substituting `opt` for the other mode.
Pinned inputs, limits, timings and source hashes are retained in the
[development record](../development/console-windows.json). These runs are the
bounded development tier. Full 70,003-byte workloads, profile/placement coverage
and identical-input replay remain release qualification; no full hosted-platform
qualification is claimed for the new window implementation.

W3 adds only fixtures and evidence. Production reservation growth is **0 upper
bytes, 0 fixed bank-zero bytes and 0 bank-zero bytes per Task**, including guards,
alignment and unused capacity. The workload's 20×12, 20×12 and 40×12 instances
use 464, 464 and 704 upper heap bytes respectively, sharing the existing worker.
Eight-slot loading/runtime bank-zero totals remain 57,232 / 61,536 bytes including
the OS. Native retained-cell/physical-scroll acceleration stays on the backlog;
Process lifetime and o65/external commands remain separate implementation plans.
