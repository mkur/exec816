# Input registration and lifetime refactor plan

[Implementation plans](README.md) · [Design note](input-registration-lifetime-design.md) ·
[Current input contract](../reference/input.md) · [Open roadmap](../roadmap.md)

Status: IR1 complete, 3 October 2026; IR2–IR5 pending.
[IR1 development evidence](../development/input-registration-ir1.json) records
raw/optimized C ABI, physical keyboard capture and pointer-failure execution,
single-resolution emitted-code checks and zero reserved bank-zero change.

Implement the design note's registration and lifetime contract for keyboard and
pointer input. Acquire establishes the registration, ordinary calls trust its
documented lifetime and consumer, and Release retires the producer before
storage or signals can be reused. Keep IRQ capture, bounded queues, durable
notices and the existing Task consumers.

Work through IR1–IR5 in order. Commit each executable slice after its development
checks pass, recording the actual checks, memory delta and remaining limits.
Reuse the saved baseline; there is no preliminary baseline-measurement slice.

## Scope and constraints

- Keep one public INPUT API, the eight-entry C bridge, configuration version 2,
  existing status values and the 32-byte lease/configuration and 24-byte event.
  Change behavioral documentation and affected callers/tests together.
- Keep Acquire and Release checked. Ordinary Take, Pending and route operations
  must eventually perform no INPUT authority-related `TASKMEMORY.Writable`,
  `TypeOfMem` or `FindTask(NULL)` calls, including Take returning EMPTY.
- Keep constant-cost C huge-pointer representation checks before narrowing.
  Output memory is borrowed for one synchronous call; valid storage is a caller
  obligation, not an additional registration or pinned-buffer service.
- Preserve route/acquisition checks on deferred data, queue bounds, pointer
  overflow and clipping, cancellation, loss recovery and safe retirement.
- Preserve Task-side Forbid and native IRQ/NMI transactions. Keep the console's
  outer Pump exclusion and current drain budgets during the comparison.
- Add no Task, message per event, private kernel operation or callback in IRQ
  context. Leave Exec TaskLease and general writable-memory validation intact.
- Keep the eight-Task configuration, current stack/DP reservations, mouse
  protocol and sampling frequency, scheduler and drawing policy unchanged.
  Smaller or overlapping DPs require separate compiler/ABI work. A future
  shared input service can multiplex clients on a long-lived worker; creating
  a Task per device is outside this refactor.

Read the [platform contract](../reference/platform.md),
[code style](../contributing/style.md) and
[development testing policy](../contributing/testing.md) before implementing.
Use the compiler recorded in [actionc.json](../../toolchain/actionc.json).
Compiler defects belong in actionc with focused regressions, not INPUT-specific
code-generation exceptions.

## Implementation boundaries

| Area | Planned change |
| --- | --- |
| [Native INPUT](../../lib/input/input.act) | Separate pure address shape, memory audits and registration resolution; pass resolved state to trusted helpers. |
| [C bridge](../../c/calypsi/input-bridge.inc) | Preserve complete huge values until checked; remove duplicate full audits. |
| [Task generation](../../tools/generate_tasks.py) and [native builds](../../tools/native_program.py) | Generate diagnostic audits only when explicitly enabled and record the setting in provenance. |
| [Input generator](../../tools/generate_input.py) and [ABI](../../abi/input.json) | Maintain shared constants/layouts and update generated contract comments. |
| [Console capture](../../lib/console/consolecapture.act), [input](../../lib/console/consoleinput.act), [foreground](../../lib/console/consoleforeground.act) and [lifetime](../../lib/console/console-lifetime.inc) | Verify stable storage, shared registration use, wake handling and owner-controlled retirement. |
| [Hosted GEM](../../ports/gem4xe/interactive/ui.c) | Preserve keyboard/mouse acquisition rollback, bounded drains and close order. |

The native ordinary-call structure is: enter existing Task exclusion, resolve
the original lease against the two fixed descriptors once, optionally audit in
a diagnostic build, perform the protected operation, then leave exclusion.
Never retain the borrowed descriptor across Permit, yield or wait. Internal
helpers receive the resolved state/capture; they do not rediscover the lease.

Resolve a null lease as absent before comparing it with descriptor fields:
free descriptors currently have `current = NULL`. A missing registration may
still return INVALID_OWNER cheaply. This lookup does not make a pointer safe
after its storage is freed or reused, nor prove an old acquisition identity.

Keep full memory/owner audits in shared helpers used by lifecycle calls and
diagnostic builds. Diagnostic and production builds use the same queue and
retirement implementation. No runtime diagnostic branch belongs in the
production event path, and omission must hold in raw as well as optimized code.

## IR1 — Separate validation and resolve state once

Refactor the internals while retaining today's public validation behavior.

1. Split `Extent` into a pure full-address shape check and the existing memory
   membership audit. Keep the full check available for Acquire, Release and
   diagnostics. Check range, alignment, nonzero length and CPU-bank extent
   before pointer conversion or dereference.
2. Resolve source/state/capture once under Forbid. Pass those values to lease
   auditing, route validation/reference scans and keyboard/pointer read helpers.
   Keep lookup and descriptor types private to the implementation.
3. Guard null explicitly. Replace expressions that appear to conditionally
   perform `FindTask` with explicit control flow; do not rely on boolean
   short-circuiting to omit expensive calls.
4. Preserve every existing audit at each public boundary for this slice, with
   unchanged results and queue transactions. Avoid unrelated queue rewrites.

Run the host suite, generated-input checks, raw/optimized input ABI and capture
fixtures, and focused pointer-failure cases. Cover EMPTY output preservation,
both source descriptors, legal shared route use and null/unregistered lookup.
Inspect emitted call paths to confirm helpers no longer repeat resolution.

Exit: both languages retain the current checked contract and all internal
operations use one resolved registration. Record emitted code/data size and
stack high-water changes as well as the reservation delta.

Planned commit: `refactor(input): separate audits from resolved operations`.

## IR2 — Make Take and Pending trust live registrations

Introduce the cheaper event-consumption contract for Action! and C together.

1. Add an `input_diagnostics` build option, default false, propagated through
   generation, native/C build entry points and relevant test harnesses. Expose
   an explicit CLI switch such as `--input-diagnostics` and record both true
   and false in build provenance. These options are proposed, not available
   before this slice.
2. Generate diagnostic call sites around the same operations. Production Take
   and Pending omit full lease/output memory audits and immutable owner checks;
   the diagnostic variants retain them before mutation. Keep auditing helpers
   available for checked lifecycle calls.
3. Update C Take/Pending wrappers to perform only full huge-address shape
   checks before conversion, then call native INPUT. Diagnostic memory audits
   happen once in native code, not again in the bridge.
4. Preserve EMPTY without touching any output byte, observational Pending,
   complete event initialization, capture-time tags and pointer expansion.
   Keep pending-work and signal acknowledgements unchanged.
5. Update the input reference and generated header comments through the
   generator. State lease/storage lifetime, acquiring-consumer and shared
   Pending obligations explicitly. At this intermediate commit, document that
   route calls still perform full audits until IR3.
6. Audit Take/Pending callers before weakening their checks: console resident
   event storage, GEM event storage, stop paths and concurrent registration
   sharing. Any safety repair required by the new contract belongs here before
   enabling the fast path; IR4 adds broader integration coverage.

Add a small emitted contract fixture exercised in raw/optimized builds with
diagnostics off/on. Compare legal results across settings. Move ordinary-use
wrong-consumer, copied/corrupted-record and invalid writable-buffer assertions
to diagnostic tests. Checked lifecycle rejection tests remain in production.
Ordinary production misuse is not a promised safe-rejection test.
Keep null/unregistered lookup tests for the explicit cheap rejection behavior.

Extend the C ABI fixture with huge addresses above 24 bits, bank-zero, odd and
bank-crossing values, using a live lease where needed to reach the intended
check. Assert rejection before truncation and before native state mutation.
Keep valid per-call output-buffer changes covered; no buffer is retained.

Adapt the console pump fixture: its valid drains run in production, while the
intentional corrupted-lease fault runs with diagnostics. Preserve a check that
an unexpected INPUT status is not converted into EMPTY or a cleared wake.
Use a controlled test hook or the defined missing-registration rejection for
that production check, rather than undefined live-record corruption.

Run the host suite, the small four-build contract fixture, affected raw/optimized
C ABI and console pump/wake fixtures. Inspect emitted Take/Pending paths in both
compiler modes: production has no INPUT memory-table, heap or current-Task
audit calls; lifecycle and diagnostic paths still do.

Planned commit: `perf(input): trust registration lifetime during event reads`.

## IR3 — Complete route and lifecycle boundary migration

Apply the same ordinary-use contract to route operations and remove lifecycle
audit duplication across language boundaries.

1. Migrate CreateRoute, PublishRoute, RetireRoute and Discard together in native
   INPUT and C. Keep C scalar/range checks and output-tag shape checks. Keep
   dynamic tag validity, slot/epoch exhaustion and retained-reference scans.
2. Retain captured acquisition/route/notice qualification, including ring
   tombstones, durable BREAK/loss and pending pointer-button output. Retirement
   must still return BUSY while any relevant retained reference exists.
3. Make C Acquire/Release perform representation checks, then invoke native
   lifecycle validation once. Preserve native configuration/memory checks,
   allocated signal checks, original owner/identity checks and Exec retention
   primitives. Failed admission must unwind every partial binding/hold.
4. Preserve checked Release ordering: stop shared callers before entering the
   serialized transaction; mark RELEASING, stop capture, retire notifications,
   purge records and pending output, retire routes, release retention, then
   clear the registration. Do not expose a free source before this completes.
   Failed preflight leaves the live registration intact. Do not wait for other
   Tasks while holding Forbid.
5. Review console foreground callers and GEM route/close paths before removing
   their audits. Use the existing service lifetime to prevent new shared calls
   and join outstanding use. Do not add a hot-path reference counter or another
   kernel service merely to replace removed checks.
6. Finish the input reference/header migration for all ordinary operations.
   Rebuild affected consumers; retain one API with diagnostic instrumentation,
   not compatibility versions. Document that successful Release is required
   before freeing a lease or its signal.

Run the host suite and affected raw/optimized input capture, C ABI and pointer
failure fixtures. Extend the small diagnostic fixture for route-output audits
and shared caller rules. Cover route zero, invalid/exhausted tags, BUSY retirement,
failed Acquire/Release, release/reacquire and simultaneous keyboard/pointer use.
Verify full audits remain in lifecycle calls and are absent from all production
ordinary-call paths. Scope this assertion to INPUT authority checks, not other
Exec callers in the image.

Planned commit: `perf(input): move route audits to registration boundaries`.

## IR4 — Exercise consumers, wake races and retirement

Complete integration and race coverage using the migrated production contract.
Fix any uncovered caller defect in this slice; do not postpone known unsafe
lifetime behavior from IR2 or IR3 until here.

- Console: cover shared foreground changes, raw/cooked input, loss/BREAK,
  bounded drains and worker shutdown. Account for every lease and signal from
  acquisition through handoff, rollback and successful retirement.
- GEM: cover keyboard and mouse together, partial startup failure, close with
  a button held, route/session replacement and restart. Keep session and route
  checks on events already posted to the normalized queue.
- Wake races: schedule arrivals before/after EMPTY observation, at a drain
  budget boundary, during route publication and around release. Require no
  lost wake, torn record, duplicate acknowledgement or late post into retired
  state. A budget-limited drain keeps pending work set.
- Reuse: reacquire the source with the same lease address and with different
  storage. Deliver only the new acquisition's events, purge old notices and
  pending button output, and verify Task holds and signals balance.
- Coexistence: exercise physical keyboard/mouse with SIO and blitter completion
  active, including shutdown while other subsystems still have work. Preserve
  context, stack/domain guards, existing sampling-gap and serial assertions,
  and OS restoration.

Use selected raw/optimized console signals/focus and GEM pointer/mouse cases,
plus focused emitted race fixtures where existing harnesses cannot schedule the
required boundary. Run a diagnostic integration smoke using the same legal
inputs, and selected unobserved replays of unchanged binaries. Do not multiply
every integration case by all diagnostic settings; the small contract fixture
covers that cross-product. Run the host suite for code changes.

Planned commit: `test(input): cover registration lifetime and consumer races`.

## IR5 — Measure the final path and record results

Use the [archived active-input baseline](../development/input-registration-baseline.json)
and [CB4 loaded-console evidence](../development/console-circular-buffer-cb4.json).
Verify their recorded hashes and reuse the data. The baseline console service
cost is 8.59–8.89 ms charged CPU per single-key drain, including its final EMPTY;
the nested validation spans are not additive. No C timing baseline was recorded.

1. Promote the existing passive key-service observer/analysis into reusable
   tracked tooling, extending [console turn profiling](../../tools/console_turn_profile.py)
   and [the loaded workload](../../tools/measure_async_scroll.py) as appropriate.
   Resolve symbols from the new build; removed helper names must not disable
   public-operation measurements. Add focused host fixtures for span accounting
   and missing-symbol handling.
2. Build one final optimized production image and run the matched phase-zero
   workload with complete service/Take/Pending and audit attribution. Compare
   the same single-key drains with the saved observations. Check empty, burst,
   loss and cancellation separately; do not divide total workload CPU by keys
   to infer latency.
3. Measure native and C consumers for keyboard and pointer paths, reporting C
   values as new measurements without inventing a before/after percentage.
   Confirm the production audit calls are absent from ordinary operations in
   emitted code and passive traces, including EMPTY. Acquire/Release may and
   must still reach their checks.
4. Reuse that exact final image for loaded phases 0, 3,547 and 14,188 base cycles,
   keeping the archived ROM/emulator configuration, compiler, physical input
   schedule, SIO, ST mouse, sampling and drawing settings. Reuse phase zero from
   step 2 if the image and workload are unchanged; do not rerun it just to fill
   another report. Explain any changed pin/workload and avoid an unmatched
   speedup claim.
5. Report maximum complete worker turns and Forbid intervals, service CPU,
   native IRQ CPU, off-worker delay, capture-to-visible latency, correctness and
   sample gaps. Replay selected final workloads without passive observation.
   Do not attribute all IRQ time to mouse sampling or claim unchanged elapsed
   latency from an improvement in charged CPU alone.
6. Write a development evidence record and a short implementation/measurement
   page in history; update its index, this plan, the design status and roadmap.
   Preserve the baseline and historical qualification records. State which
   goals remain open and the exact execution scope.

Target: every recorded matched single-key `CONSOLEINPUT.Service` drain takes
at most **2 ms charged CPU**, including final EMPTY. Keep the wider 4 ms worker,
20 ms scroll and 40 ms visible-input goals visible, without treating this
refactor as proof they have been met. If the target is missed, identify the
remaining measured cost and leave performance acceptance open. Correctness and
the agreed structural removal of audits are mandatory.

If full-ring drains still hold Forbid too long, report a separate follow-up to
decouple the per-turn event budget from queue capacity. Do not change the budget,
sampling or scheduler halfway through this comparison.

Planned commit: `perf(input): record registration contract measurements`.

## Memory and validation accounting

Expected reserved bank-zero change in **each** slice:

| Reservation | IR1 | IR2 | IR3 | IR4 | IR5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed/root/kernel | 0 B | 0 B | 0 B | 0 B | 0 B |
| Per public Task | 0 B | 0 B | 0 B | 0 B | 0 B |
| Private idle | 0 B | 0 B | 0 B | 0 B | 0 B |

Count guards, alignment and unused reserved capacity, not just live variables.
Verify generated placement in every executable slice and report actual deltas;
justify any departure before adding a reservation. Keep capture reservations
unchanged. Record upper code/data growth and stack high-water marks separately,
including diagnostic builds; diagnostics do not justify hidden bank-zero cost.

The [existing input harness](../../tools/test_input.py) provides `--case abi`
and `--case capture` with `--mode raw|opt`. Related focused harnesses include
[pointer failures](../../tools/test_pointer_failures.py),
[console pump](../../tools/test_console_input_pump.py),
[console wakes](../../tools/test_console_input_wake.py),
[console signals](../../tools/test_console_input_signals.py),
[GEM pointer](../../tools/test_gem_pointer.py) and
[GEM mouse](../../tools/test_gem_mouse.py). Extend them where specified instead
of substituting host models for execution of changed machine code.

Run `python3 tools/generate_input.py --check` for generated public interfaces
and the prescribed host suite for code changes. Record fixture cases, compiler
mode, diagnostic setting, image/toolchain/ROM/emulator hashes and actual machine
configuration in slice evidence. Broaden testing when failures or a changed
concurrency boundary justify it; reuse still-current results otherwise.

This is development-tier validation, not full hosted-system qualification.
Documentation-only updates need content and local-link checks. This plan does
not request a demo refresh, release package or publication.
