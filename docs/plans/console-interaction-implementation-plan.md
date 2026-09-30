# Console interaction implementation plan

Status: implementation complete through W3, 2026-09-24. S0, C1–C3 and B1–B5
retain their qualification records; W1–W3 pass development checks. Full window
release qualification remains pending. Ordinary changes use the
[development test tier](../contributing/testing.md); full release qualification is separate.
See the [implementation record](../history/console-interaction-implementation.md).
Baseline: `407df9d`, including the [scrolling optimization](../history/console-scrolling.md).

Scope: historical SIO evidence maintenance, cooked CON: input, shell migration,
foreground Ctrl-C/BREAK with safe I/O cancellation, and independent console
windows. Apply the [shared delivery and validation rules](interactive-programs-implementation-plan.md#baseline-ownership-and-delivery-rules).
Publish public contracts separately in the proposed `docs/reference/cooked-console.md`,
`docs/reference/foreground-break.md` and `docs/reference/console-windows.md`.

The [Process lifetime plan](process-lifetime-implementation-plan.md) starts after
B5 and owns inheritance and child retirement. Window slices W1–W3 follow B5
using existing Task/application fixtures. They do not require the Process or
o65 plans: captured routing, isolation and retirement can be tested through the
current Task API. Process foreground handoff is integrated and rechecked in P2.
Finishing B5 enables Process work but does not complete this console plan.

## Sequence and dependencies

| Slice | Executable outcome | Depends on |
| --- | --- | --- |
| S0 | Historical evidence validation and current-source checks have distinct meanings | Baseline |
| C1 | Bounded cooked-line state machine passes native byte/ownership tests | S0 |
| C2 | Real CON: Read/Write/Close works through the existing console worker | C1 |
| C3 | The shell uses CON: and retains editing, redirection and failure behavior | C2 |
| B1 | Ctrl-C/BREAK reaches the current foreground scope without a pending Read | C3 |
| B2 | Console waits can be interrupted and their exact completion collected | B1 |
| B3 | A queued filesystem operation can be canceled while another client continues | B2 |
| B4 | Active filesystem/SIO work retires safely after cancellation | B3 |
| B5 | Running shell commands stop and restore a usable prompt | B4 |
| W1 | Multiple console instances have independent bindings and lifetimes | B5 |
| W2 | Tiled presentation and captured-key routing implement keyboard focus | W1 |
| W3 | Multiple windows remain responsive under flooding and eight-task SIO work | W2 |

The original host baseline was 157/158 passing checks, with the historical SIO
source-hash mismatch described below. S0 now passes all 160 host checks. Idle scrolling is 110 ms raw / 97.5 ms
optimized per line on the pinned machine. The new benchmark gate is at most
112 guest ticks for 16 visible scrolls. These are separate from keyboard and
filesystem latency.

## S0: qualification evidence maintenance

`tests/test_sio_sector_record.py::test_published_gate` currently compares the
historical `docs/qualification/sio-sectors.json` input hashes to today's working
tree. Its validator already checks agreement between recorded inputs and each
recorded build. Separate those two questions:

1. Keep historical schema, coverage, timing, replay, guards and internal input
   consistency checks. Preserve all deliberately corrupted-record controls.
2. Audit the recorded source hashes against the actual historical Git objects
   or preserved run artifacts. Record exact commit/blob provenance separately;
   a record updated in several commits must not be assigned an invented single
   source revision. If evidence is missing, report it as unresolved and recover
   it before claiming provenance verification.
3. Put current-working-tree equality in the collector/check for a freshly run
   qualification, where stale sources must still fail. Historical validation
   must remain usable without treating current production changes as corruption.
   Document any additional Git history/artifact requirement for provenance checks.

**Acceptance:** the host suite passes without changing measured historical
hashes or weakening its negative controls. Mutating a recorded build input,
removing a case, relaxing a deadline, or omitting replay still fails. A fresh
record whose source changes after execution fails publication. This maintenance
slice makes no new SIO execution claim and adds zero reserved memory.

## C: cooked console input

### C1: contract and terminal state

Define CON: as line-oriented input with echo and editing above console.device.
Initially accept bare `CON:`; leave CONSOLE: and geometry/name suffixes explicitly
unsupported until their semantics are separately specified. IsInteractive
recognizes CON:, Seek fails, and Write retains console byte-output behavior.
RAW: never gains implicit echo, EOF interpretation or foreground signal behavior.

Start with these line rules:

- Printable ASCII appends; Backspace removes the last character; Tab adds one
  space. Preserve the shell's bounded tail display and avoid accidental wrap.
  History, completion, cursor navigation and synthesized key repeat are deferred.
- Allow 255 edited characters plus LF. Return seals the line and includes LF
  in Read's bytes. Read does not append NUL. Small caller buffers receive a
  prefix and later reads drain the retained remainder before taking more input.
- Ctrl-D on an empty line completes a positive-length Read with zero bytes.
  On a partial line it seals bytes without LF, followed by one EOF result after
  those bytes drain; the following Read may accept fresh input. A zero-length
  Read neither blocks nor consumes buffered text/EOF.
- Ctrl-C/BREAK cancels a valid partial line and reports a named break error;
  C3 makes the shell redraw its prompt. B1 later adds foreground delivery.
- The 256th character invalidates the entire line. Input loss likewise
  invalidates it. Discard through Return and report the appropriate line-length
  or input-loss error; neither EOF nor Ctrl-C may turn the remaining suffix into
  an executable command. Never report truncated successful input or false EOF.

Use an upper-RAM cooked session behind an owned DOS handle. It owns line bytes,
read position, EOF and resynchronization state; its initial reference count is
one. This permits [P2](process-lifetime-implementation-plan.md#p2-inherited-streams-and-current-directory) to share the same session through explicit duplication.
Store no caller buffer after a synchronous Read returns. Keep parsing and
command dispatch out of the session.

**Acceptance:** emitted raw/optimized tests cover empty/one/36/37/255/256-byte
lines, Return, partial reads down to one byte, Backspace, Ctrl-D, Ctrl-C, loss
at every line state, and two independent sessions. Compare returned bytes,
retained state and guard regions against an independent model. Inject allocation
failure and verify unchanged ownership. C1 can test private state without yet
publishing CON: Open.

### C2: DOS backend and physical input

Add the CON backend to DOS name/object dispatch and the generated DOS contract.
Factor the existing RAW endpoint ownership so RAW and CON share one physical
OpenDevice rather than competing for it. Keep one input lease across a cooked
line's acquisition and echo. Reject a competing RAW/CON reader with the existing
busy error; completed line remainders stay in their session. Serialize access
to a shared session when [P2](process-lifetime-implementation-plan.md#p2-inherited-streams-and-current-directory) introduces duplicate handles.

Run cooked Read in the calling Task, using the existing console worker. Reuse
the client's request sequentially for input and echo after collecting each
completion. Internal helpers must preserve the one-operation `client.busy`
contract; calling public DOS.Write recursively while Read is busy is invalid.
Echo targets the console being edited even when selected command Output is NIL:
or another destination. No filesystem worker handles a keyboard wait.

**Acceptance:** a resident native example opens CON:, reads/echoes lines and
handles EOF while another Task completes real MyDOS reads. Test competing
readers, closing/reopening, first-opener exit, source release after Write,
selected-handle close, input loss, failed echo, and every allocation rollback.
Check physical screen/cursor and exact bytes, request collection, signal/port
ownership, stack reserves and OS restoration in raw/optimized builds.

### C3: shell migration and qualification

Switch the shell's prompt input to CON:. Remove its duplicate editor and update
fixtures together; retain command parsing, diagnostics, redirection and built-in
dispatch in the shell. Handle a line returned through several Read calls,
terminal EOF, break, and resynchronization errors explicitly. File/NIL input
redirection remains ordinary byte input rather than acquiring a cooked editor.

**Acceptance:** run the shipped shell and existing core/command/redirection/
lifetime suites. Repeat eight-task console/SIO observation and replay, including
128-byte media and the complete 70,003-byte file on 256-byte media. Keep the idle
scrolling gate, serial deadlines and protected stack reserves. Publish cooked
editing/echo latency separately from command and physical-display latency.

## B: foreground Ctrl-C and BREAK

### B1: foreground identity and signal delivery

Create an upper-RAM foreground binding for each console session: target Task,
Task lifetime identity, allocated signal, command-scope generation and durable
pending-break state. Before Process exists, the target is the shell Task during
a built-in. [P2](process-lifetime-implementation-plan.md#p2-inherited-streams-and-current-directory) later transfers that binding to the foreground child. Allocate a
signal for participating Tasks; do not silently reserve a new bit in every Task.

Carry an input-route generation with captured events. The IRQ captures the
generation and posts only to the existing console worker; the worker resolves
the event's destination and posts a break signal from task context. Preserve
old-route lifetime until captured events retire. Late events may be retired
with their old scope but must never cancel a new command or a reused Task.
Specify wrap/exhaustion rejection and the atomic publication protocol covering
IRQ, NMI, handoff, close and removal. This route identity is reused by W2.

Break recognition must run even when no console Read is pending, including
while the target computes, waits for a filesystem packet or has redirected
Input. An unbound RAW session continues to return byte $03. A bound foreground
event becomes one durable break request; it must not also become a duplicate
input byte. Provide a documented task-side break query/acknowledgement operation.
Keep delivery cooperative; forced Task removal is not command cancellation.

**Acceptance:** native compute and wait fixtures receive real Ctrl-C/BREAK;
test early/late/repeated input, stale signals, command handoff, signal exhaustion,
Task removal/reuse and input-ring loss. Force asynchronous entry during binding
publication. A target that does not poll or enter an interruptible wait remains
running; document that limit rather than claiming safe forced termination.

### B2: interruptible console waits

Replace only the relevant DOS wait path with reply-or-break waiting. After any
wake, inspect durable completion and break state. If cancellation wins, request
AbortIO and still collect the exact terminal reply before releasing the caller
buffer, request, endpoint lease or busy state. Completion may win the race.

Define partial progress in the public break contract: a canceled transfer with
committed bytes returns that positive count with the break secondary result;
zero progress reports failure with the break error. Retain the foreground break
until acknowledged. Never invent an undo of displayed bytes or rewind a file
cursor silently. Update RAW/CON adapters and callers consistently for this new
explicit cancellation outcome.

**Acceptance:** cancel an empty Read, a queued Write and an active scrolling
Write. Cover break before SendIO, before Wait, simultaneously with completion,
and after completion collection. Verify exactly one reply, accurate committed
prefix, coherent scroll completion, no subsequent buffer access, stale-signal
handling and resource reuse in raw/optimized code.

### B3: queued filesystem cancellation

Add a private operation identity/state to the existing DOS request lifecycle:
prepared, queued, active, cancellation requested, replied and collected. Bind it
to the client and command generation. Cancellation state and wake linkage must
be independent of the packet/message currently owned by the filesystem; a busy
client cannot reuse that packet to send a second ordinary DOS call.

Use a bounded pending-cancellation queue and a control signal for the filesystem
worker. Define a serialized claim between dequeue and cancellation. The winning
path alone removes/replies to a queued packet. Validate authority and generation
before following pointers. Replace the blocking EXEC.DoIO in BLOCKWIRE.Transfer
with SendIO plus reply/control waiting so it can retire another client's queued
cancel while its current serial request continues. It still collects its own
exact serial reply and does not start another transfer on that adapter.

**Acceptance:** cancel a queued Read/Open/Lock while another Task's 70,003-byte
Read continues. The canceled caller must receive its reply before that large
read finishes. Cover cancellation versus dequeue, reply and client-slot reuse;
retain mount references and buffers until their final owner retires. Unrelated
requests keep their order and complete normally. No public asynchronous DOS
packet API is implied by this private protocol.

### B4: active filesystem and transport cancellation

Add cancellation checkpoints to path traversal, directory enumeration, sector
progress and file copying. Treat object allocation/publication as explicit
ownership transitions: canceled Open/Lock cannot leave an unreturned live object.
Honor cancellation while waiting for SIO by using the existing AbortIO and
collection/recovery protocol. The filesystem worker remains the sole owner of
its adapter and active request; the caller never frees or aborts that storage
behind the worker's back.

Return the committed byte count/cursor position specified in B2. Retire parser
state and per-operation references before replying. Preserve timeout/checksum
causes and unsafe-bus offline/fail-stop behavior. Cleanup operations such as
Close/UnLock and exact reply collection must finish despite a pending break;
repeated break input cannot prevent resource retirement.

**Acceptance:** inject break during directory scans, first/middle/final sectors,
copying, object publication, SIO preparation, wire activity, timeout and terminal
completion. Check cancellation versus success and error precedence, one reply,
bounded retirement, next-request recovery and unaffected clients. Exercise both
sector sizes, 125 kbaud and the shell's 57.6 kbaud profile, raw and optimized.

### B5: shell behavior and interruption limits

Bracket each running built-in with a foreground scope; keep prompt editing a
separate scope. TYPE/DIR and CPU loops poll the durable break between bounded
steps, and blocked DOS calls use B2–B4. Restore temporary Input/Output, close
owned command resources and redraw the prompt. CD changes directory only after
successful acquisition/exchange; a canceled candidate leaves the old selection.
Preserve the first causal error through cleanup. A completed command cannot
deliver its late break into the next prompt/command.

Use these initial acceptance targets on the pinned PAL 8× eight-task profile:
capture to durable break at most 100 ms; a queued operation's terminal reply at
most 250 ms after cancellation publication; a healthy command back at a usable
prompt within 500 ms of capture. Active error recovery additionally has the
existing finite transport timeout/recovery allowance, stated numerically for
each profile in the B1 contract. Measure capture, delivery, cancellation,
collection and prompt visibility separately. A missed target blocks dependent
work until its cause is resolved or the contract is explicitly revised with
evidence; it is not permission to weaken serial deadlines.

**Acceptance:** interrupt TYPE, DIR, CD and a compute fixture, including redirected
input/output, a queued filesystem operation and an active transfer. Then execute
another command successfully. Repeat under eight-task observation/replay and
prove no handles, locks, requests or foreground bindings remain owned by the
finished command.

## W: independent console windows

### W1: instance binding and lifetime

Implement the first stage of the
[required window follow-up](console-io-implementation-plan.md#required-multiwindow-follow-up).
Specify create/destroy, instance identity, owner/reference lifetime, dimensions
and admission limits before exposing them. Extend OpenDevice binding through
io_Unit; the existing default console remains available. Make the DOS endpoint
registry per instance and let CON/RAW sessions bind a selected instance without
encoding raw pointers in names. The exact selection API/name grammar belongs in
the separate window contract.

**Acceptance:** two instances own independent cells, cursors, input, pending
reads and write queues. Hidden output completes; closing one does not affect
the other. Test allocation failure, active close rejection, stale identity and
reuse. Demonstrate multiple windows owned by one application, using the same
single worker and existing physical screen.

### W2: tiled presentation and keyboard focus

Present at least two nonoverlapping text windows simultaneously with clipping,
dirty redraw and one focused cursor. Use B1's captured route identity: a key
captured before a focus change stays with the old console, and events from a
closed instance cannot reach one that reuses its slot. Retain route records
until capture drains; reject/defer a handoff whose bounded route storage is full.
The IRQ only captures identity and wakes the worker; it performs no window scan.

Bind each foreground Task to its console's input/break scope. Background
reads may remain pending without stealing focused input, and unfocused output
must continue. Initially defer overlapping windows, movement, resize/reflow,
scrollback and escape-sequence emulation.

**Acceptance:** exact clipped screen/cursor oracles, focus changes with queued
keys/BREAK and overflow, hidden-to-visible redraw, closing focused/unfocused
instances, retained routes and foreground Task removal/reuse. Test raw/optimized code
with nondefault kernel placement and unchanged OS restoration.

### W3: fairness, capacity and combined qualification

Rotate runnable instances at bounded quanta, preserving each instance's FIFO
write order. Input, cancellation and redraw get service even when another
instance continuously floods output. Use existing 64-source-byte, 40-edit-cell
and 38-redraw-cell limits as the starting budgets; changes need their own latency
and stack evidence. No worker, stack, DP or physical screen is allocated per window.

**Acceptance:** a flooding producer, a small-write client, pending reads, focus
changes and foreground commands run alongside eight-task DOS/SIO work. Freeze
numeric per-instance progress/echo limits before the final matrix and report
both retained-write completion and visible display. Verify the single-console
scroll benchmark too. Report per-window upper allocation, peak route storage,
allocation exhaustion and complete cleanup. Window release qualification remains incomplete until this full gate passes;
a two-instance model alone is insufficient. The development tier uses a bounded
eight-Task case; it does not replace the release matrix.

## Integration and memory

| Area | Existing integration points / proposed additions |
| --- | --- |
| DOS console and shell | `lib/dos/doscalls.act`, `dosclient.act`, `dosraw.act`, `dosstreams.act`, `dosobjects.act`; proposed cooked-session module; `examples/shell/shell-session.inc` and shell fixtures |
| Foreground routing | `lib/console/consoleinput.act`, `consoledriver.act`, `task-console.inc`, `platform/altirraos/console.s`, `abi/console.json`, `tools/generate_console.py` |
| DOS cancellation | `lib/dos/dosclient.act`, `fshandler.act`, `fsmux.act`, `fspacket.act`, `fsworker.act`, `fsio.act`, `blockwire.act`; generated DOS request/operation definitions |
| Windows | `lib/console/consoletypes.act` via generation, console core/input/display/worker, DOS endpoint registry, route/foreground records |
| Evidence | `tests/test_sio_sector_record.py`, `tools/sio_sector_record.py`; focused native fixtures, existing shell/device/SIO runners and new qualification collectors |

Public console/DOS layouts belong in `abi/console.json` and `abi/dos.json` with
generated Action!/assembly definitions. Cooked sessions, break delivery and
windows use the existing worker; they add no Task, stack or DP reservation.
Target reserved bank-zero delta: **zero fixed and zero per Task**, including
all guards, alignment and unused capacity. Preserve the
[shared memory gates](interactive-programs-implementation-plan.md#memory-gates).

| Resource | Planning budget / accounting requirement |
| --- | --- |
| Cooked session | Target at most 512 upper-RAM payload bytes including the 256-byte line, editing/EOF state and redraw scratch; report allocator rounding and metadata |
| Foreground scope | Target at most 64 upper-RAM bytes per participating scope, plus one dynamically allocated signal; no new bank-zero per-Task field |
| Captured route generation | A four-byte tag per 64 ring slots adds 256 active upper-RAM bytes; regenerate capture/boot/table placement and prove nonoverlap within or beyond the actual reserved arena |
| Window | Geometry-sized retained cells, session/input state, view and route records in upper RAM; report measured per-instance and shared costs separately |

Completion requires all 12 slices, including W3's fairness and integrated SIO
checks. Keep the scrolling gate and publish cooked input/break/window timings
separately. History, completion, cursor navigation, overlapping/resizable windows,
scrollback and escape-sequence emulation remain outside this plan.
