# DOS simplification development record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

Follow the [plan](../plans/dos-simplification-plan.md). The baseline is the standard
optimized image from `2bca1c8`, using compiler `5f62c9fd` with stack checks:
480,792 Action! routine bytes, 493,778 loaded-segment bytes, 68,835 DOS routine
bytes including DOS-specific Task policy. Filesystem, Process and loader code
are excluded from that DOS subtotal. No compiler pin change is planned.

## D1 — Close semantics

The RAW close path now calls the infallible Exec procedure directly. It still
rejects an active final close before consuming ownership and keeps CLOSING set
through reclamation. Cooked close uses the result rather than searching for a
freed wrapper. The lifetime fixtures retain close/free race checkpoints and use
actual active-endpoint state for teardown rejection instead of inventing an
error return from CloseDevice.

The first run exposed an earlier console migration regression: the shared DOS
endpoint retained its first opener even after that Task closed its own handle.
Independent PA_IGNORE endpoint opens now follow their shared reference lifetime;
ordinary Task-owned opens keep the removal lease. This restores the existing
first-opener-exit contract without a DOS-only device operation.

Reserved bank-zero delta: **0 fixed / 0 per-Task bytes**. Record sizes, heap
allocations, workers, upper arenas and task pools are unchanged.

Validation: optimized native DOS stream lifetime passed 171 root and three child
checks. The paced console lifetime checks passed both ordinary-open removal
rejection and clean close/stop. Python syntax and whitespace checks passed.

## D2 — Reuse operation context and shared bindings

DOS calls now resolve their Task-local slot once and pass it through admission,
handle lookup and packet delivery. The existing convenience admission entry
for other callers shares the same implementation. Open/Lock carry their parsed
unit or validated relative directory forward; configured-name screening still
precedes filesystem startup.

The fixed filesystem registry uses one generated DOSCORE binding. Its former
Control selector and duplicate filesystem address wrappers are gone. RAW buffer
validation calls the same TASKMEMORY helper used by Task policy directly, removing
the temporary extent record and private validation selector. Internal callers
and generated-source provenance follow the shared binding.

Reserved bank-zero delta: **0 fixed / 0 per-Task bytes**. Public ABI contracts,
record sizes, allocation strategy and memory reservations are unchanged.

Validation: optimized packet/reentrancy and relative-path native fixtures passed.
The relative fixture exercises missing defaults, retained handles, root/parent
paths, malformed names and ownership cleanup on the 128-byte MyDOS volume.

## D3 — Native copy spans

Detached inheritance wrappers and cooked-line drains use A816MEMORY.Move. Pipe
transfers now split a quantum at the ring end into at most two native copies.
The existing 64-byte quantum, exclusion, waiters, wakeups and partial-transfer
rules are unchanged. Head/tail and used count are published once per quantum.
The native memory implementation is already present in the standard image.

Reserved bank-zero delta: **0 fixed / 0 per-Task bytes**. Ring capacity, session
records, inheritance allocations and native memory reservations are unchanged.

Validation: raw and optimized native pipe fixtures each passed 8,520 checks;
cooked-line fixtures each passed 192 operations with buffer guards. Optimized
inheritance passed 388 functional checks and 11 checks before the expected
busy-close teardown rejection, with retained ownership inspected afterwards.
Stale fixture assertions were brought forward to the existing 402-byte cooked
session and 140/118-byte filesystem records; these sizes did not change here.
Port-allocation hooks now match the current source. A local name collision in
the updated teardown fixture was corrected before these passing runs.

## D4 — Direct command dispatch

PROGRAMAPI keeps its checked opaque-handle entries and command signatures, but
calls DOSCALLS, DOSCLIENT and DOSBREAK directly. This removes one forwarding hop
(two for BreakPending) without bypassing stack checks or changing the exported
command contract. The loaded-command Write observer follows the same path and
now rejects a stale injection point explicitly.

Reserved bank-zero delta: **0 fixed / 0 per-Task bytes**. Provider capacity,
public signatures, stream records and memory reservations are unchanged.

Validation: all 235 host checks and generated DOS/program definition checks
passed. Packaged-image execution and exact provider-contract comparison are
recorded with the final measurements below.

## Final image and measurements

The standard optimized image was rebuilt from `da7cb3f` using the unchanged
`5f62c9fd` compiler pin with stack checks. Both `build/demo/program.xex` and
`build/demo/sdfs.atr` are refreshed. The smoke passed SYS: navigation, shared
SYS:/physical-drive cache hits, loaded HELLO, CAT→WC, EXIT, ownership/heap cleanup
and exact OS display/input restoration. Every exported provider contract matches
the baseline, including signatures, argument layout and stack-check policy.

| Responsibility | Before bytes | After bytes | Change |
| --- | ---: | ---: | ---: |
| DOS API, client and registry binding | 24,546 | 24,997 | +451 |
| Streams and cooked-line editing | 22,553 | 22,191 | −362 |
| Pipes | 6,732 | 7,162 | +430 |
| DOS Task policy | 3,809 | 3,449 | −360 |
| **DOS subtotal, including unchanged BREAK/arguments** | **68,835** | **68,994** | **+159** |
| Inheritance | 4,491 | 4,165 | −326 |
| Command providers | 1,512 | 1,426 | −86 |
| **Whole-image Action! routines** | **480,792** | **480,535** | **−257** |
| **Whole-image loaded segments** | **493,778** | **493,521** | **−257** |
| XEX file | 508,444 | 508,187 | −257 |

Size remains almost flat. Passing resolved context adds argument setup, and pipe
span handling adds code while replacing per-byte copying and ring updates. The
cooked native copy also adds 51 bytes. Removed close/gateway/copy helpers and the
shorter command path offset these costs. The shared-endpoint console lifetime
fix adds 210 bytes; removed filesystem registry wrappers save 214 bytes. These
shared changes are included in the whole-image totals. No timing claim is made
from these functional checks.

Action! code still occupies banks **1–8**. Reserved bank-zero usage remains
**24,672 bytes excluding OS reservations**: 10,560 fixed, 2,080 for the root,
1,568 per child slot (seven slots), and 1,056 for idle. Fixed and per-Task deltas
are both **0 bytes**, including guards, alignment and unused reserved capacity.
Upper reservations and provider capacity are unchanged.

The [machine-readable development record](../development/dos-simplification.json)
contains source/image identities, sizes and passing native fixture records. Host
validation passed 235 checks; generated definitions, documentation links and
whitespace checks passed. This is focused development validation; the full
release matrix remains separate.

The subsequent [compiler-only refresh](compiler-main-refresh.md) uses the same
Exec sources with current actionc main plus the native memory helpers, reducing
the loaded image by another 20,487 bytes.
