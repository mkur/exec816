# Demo implementation record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/README.md) and [history index](README.md).

The [implementation plan](../plans/demo-implementation-plan.md) delivers a development
play image. Scoped development checks do not qualify a general platform release.

## D1: tiled shell and computation

[demo.act](../../examples/demo.act) uses the shared shell on a 40×18 CON: instance
and runs a resident prime-search Process in a separate 40×6 instance. Keyboard
focus remains with the shell. The worker uses an ascending bit sieve through
10,000, restarts with a visible pass number, and updates at most once per second.
Its 1,251-byte bitmap and 160-byte display buffer share a 1,416-byte upper-heap
allocation, including alignment and spare bytes. Two console instances account
for another 1,408 allocated payload bytes, before handles and contexts.

Startup unwinds partial console creation. EXIT requests cooperative worker stop,
collects retirement, closes the shell and destroys its owned instances before
normal service shutdown. The shell startup accepts its console binding; ordinary
boot still selects unit zero. The focused fixture exercises unavailable console
capacity, independent scrolling, physical ECHO/BREAK/EXIT, continued prime progress,
exact retained/physical cells and OS restoration.

Reserved bank-zero delta: **0 fixed and 0 per Task**, including guards, alignment
and unused capacity. Existing eight-slot stack/DP reservations are unchanged.
Full window release qualification remains pending.

[Raw/optimized development evidence](../development/demo-d1.json) records the frozen
inputs and guard/context observations. Both modes passed. The current host suite
also passed 186 tests; the shared shell startup is exercised by the CAT disk smoke.

## D2: CAT and media sources

[CAT](../../examples/commands/cat.act) copies selected Input or one named file to
selected Output with a 512-byte buffer. It accepts a quoted filename, including
the shell's star escapes, preserves bytes, completes short writes, retains the
causal error through cleanup and closes only a file it opened.

Fifteen controlled-stream cases pass in each emitted raw/optimized mode: empty
and binary inputs, multi-chunk/short transfers, quoting, invalid arguments,
open/read/write/close failures, zero-progress writes and BREAK. The optimized
physical shell loads CAT from MyDOS and checks named input, redirected file/NIL
input, missing files and extra operands. These are development checks; see the [D2 evidence](../development/demo-d2.json).

The [demo media sources](../../examples/demo-disk) include these exact LF text totals:

| File | Lines | Words | Bytes |
| --- | --- | --- | --- |
| README.TXT | 18 | 60 | 339 |
| STORY.TXT | 24 | 133 | 746 |
| LONG.TXT | 768 | 4,256 | 23,872 |

Reserved bank-zero delta: **0 fixed and 0 per Task**. Loaded command buffers and
data occupy their existing upper-RAM Image allocations.

## D3: anonymous pipes

[DOS.Pipe](../reference/pipes.md) creates inherited, owned endpoints over a 1,024-byte
upper-RAM ring. Read/Write block with Task signals; closure and cancellation wake
waiters before storage can retire. The current backing record is 1,038 bytes,
rounded to 1,040; two 12-byte endpoint records round to 32 bytes combined. Thus a
new pipe reserves 1,072 upper-heap payload bytes including allocation padding,
plus allocator metadata. Each blocked call temporarily owns one signal and a
stack-local waiter; no additional worker is created.

[Raw/optimized evidence](../development/demo-d3.json) covers transfers beyond the
buffer capacity, wraparound, inherited handles and clone rollback, last-reader
and last-writer closure, empty/full BREAK, creation/signal exhaustion, invalid
directions and Seek, exact bytes and recovered heap/Task ownership. Both modes
pass stack/domain/context and OS restoration checks. The host suite passes 186
tests. These are focused development checks; no new timing qualification is claimed.

Reserved bank-zero delta: **0 fixed and 0 per Task**, including guards, alignment
and unused capacity. ERROR_BROKEN_PIPE uses 310; the DOS generator rejects error
collisions with Process and executable-loading errors.

## D4: grouped foreground lifetime

The resident [pipeline coordinator](../../lib/dos/pipeline.act) prepares two loaded
Processes, restores its stream selections and closes parent pipe copies before
launch. Both children retain a shared foreground group through collection. BREAK
fans out to their independent signals and durable cancellation state; a late
join inherits an already pending BREAK. The parent resumes DOS activity only
after every member has retired and been collected. Group handoff renews the
console route at both boundaries, rejecting stale input and BREAK.

[Raw/optimized development evidence](../development/demo-d4.json) passes 53 checks
per mode: loaded HELLO/WC byte counts, repeated resource recovery, both partial
launch failure points, failed child scope allocation, early consumer exit,
empty/full pipe cancellation, cancellation during a real filesystem Read, stale
route rejection and existing single-child foreground behavior. An unrelated
resident Process continues running. Both modes pass Task/heap ownership,
stack/domain/context guards and OS restoration. The host suite passes 186 tests;
DOS and Process generator checks pass. No timing or full release qualification
is added.

Process ABI version 4 consumes three reserved bytes in each existing 128-byte
upper-RAM row. Foreground scopes grow from 48 to 56 upper-heap bytes, retaining
one signal per participating Task. Pipe storage and the Task capacity are unchanged.
Reserved bank-zero delta: **0 fixed and 0 per Task**, including guards, alignment
and unused capacity.

## D5: shell pipelines

The shared parser accepts one unquoted `|`, including adjacent separators, and
preserves a separate quoted argument tail for each stage. Validation rejects
empty or built-in stages, another pipe, and conflicting redirection before
resource acquisition. Left input and right output redirection use the existing
stream ownership rules. The shell loads both Images, delegates lifetime to the
D4 coordinator and reports the first failing stage in command order.

[Development evidence](../development/demo-d5.json) records 71 parser cases and
332 assertions in each raw/optimized mode, including existing grammar and bounds.
Both modes also pass physical-keyboard sessions: HELLO/WC and CAT/STORY counts,
quoted filenames, redirected file/NIL input and NIL output, invalid syntax,
missing second Image, first-stage file failure, real file-read BREAK and a
successful next pipeline. The observer verifies exact bytes, retained/physical
screens, Task/heap ownership, guards and OS restoration. The host suite passes
186 tests. Console-disabled parser builds exercise the generated foreground stub.

The shell consumes seven bytes of its existing state padding and divides its
existing argument buffer between the two tails. Its 128-byte state and 1,288-byte
upper allocation are unchanged. Reserved bank-zero delta: **0 fixed and 0 per
Task**, including guards, alignment and unused capacity.

## D6: packaged demo

`python3 tools/build_demo.py` builds the pinned compiler inputs into
`build/demo/program.xex`, `mydos.atr`, a guide, its actual screen illustration and
`demo-manifest.json`. It uses the eight-Task profile, stack checks, dedicated
AltirraOS ROM, paced bridge and 57.6 kbaud mount. The build stages its entry outside
the examples directory to avoid unrelated example filenames shadowing libraries.
Serialized commands retain their exact bytes; text is normalized to LF. The
independent ATR reader verifies all six files and 372 free sectors.

The [guide](../guides/demo.md) includes an actual machine screenshot. [D6 evidence](../development/demo-d6.json)
records a physical walkthrough of the exact optimized bundle, without inserting
target-code observers: DIR, README, TASKS, both counting examples, redirected input,
repeated pipelines, physical BREAK during Image loading and active pipeline file
Read, subsequent successful commands, continued prime progress and EXIT.
The host observer compares retained cells with physical screen RAM, and counts
DOS objects only for live Tasks; unadmitted DOS table rows are uninitialized.

The idle baseline is five Tasks, with seven observed during the pipeline and one
public slot spare. Free upper RAM returns to **253,016 bytes**, with an ordinary
largest block of 65,536 and a linear largest block of 252,976. Both Image pointers,
Process/group references and active DOS object counts return to baseline. The
retained CAT and WC Image payload allocations are 73,376 and 72,104 bytes,
respectively: 145,480 combined, including each 65,535-byte text-alignment
reservation, allocation padding and Image header. Pipe, Process/DOS resources,
file staging and validation metadata are additional and fit the measured baseline.
No additional worker or enlarged Task pool is needed.

The final host suite passes 186 tests. Runtime checks cover stack/domain/context
guards, interrupt headroom, ownership and exact OS display/input/vector restoration.
Historical D1–D5 records keep their frozen scope; unchanged component evidence is
retained and the final optimized bundle provides integration coverage. Compiler
pin 47cd55b is unchanged; its deferred general qualification and the full release
matrices were not run.

Reserved bank-zero delta: **0 fixed and 0 per Task**, including guards, alignment
and unused capacity. The complete budget remains 61,536 runtime and 57,232 loading
bytes including OS reservations. Native scrolling optimization remains backlogged.
