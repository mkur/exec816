# SCRENMGR execution placement

[GEM plans](README.md) · [Migration plan](screnmgr-migration-plan.md) ·
[Task capacity](../../architecture/task-capacity.md) ·
[Input ownership](../../reference/input.md#calls-and-ownership)

SM2 needs an execution placement decision before the manager can block on
UPDATE. The migration plan requires an explicit comparison; selection remains
pending. This note prepares that decision and does not introduce a Task or
change platform services.

## Recommended placement: dedicated input Task

| Context | Responsibility and resource lifetime |
| --- | --- |
| Existing console Worker, becoming SCRENMGR | Own the display session and manager interaction. Wait for copied interaction events, obtain UPDATE for the operation, execute shared window/menu helpers, complete its device work before blocking again. |
| New ordinary input Task | Acquire, consume and release both INPUT leases in this Task. Translate captured keys/buttons using published routing; deliver application events independently of UPDATE. Forward copied manager interactions through Exec messages. Use an existing delegated display grant for cursor work, holding no scene lock or UPDATE. |
| Existing CONSOLEBACKEND Task | Keep stream requests, cooked input and console models independent of GUI drawing and manager waits. |
| Application Tasks | Keep ordinary AES/VDI operations and their synchronous drawing in their callers. Retire caller-owned continuations in the owning operation. |

The proposed input Task requests the existing 1,312-byte stack class. Including
its 256-byte DP and two 16-byte guards, it occupies an existing 1,600-byte pool.
The eight/twelve-Task maps need no reservation growth: **0 fixed, root, kernel,
idle and per-slot reservation delta**. Concurrent free Task capacity falls by one.
The request is a proposed bound, not a measured stack claim; preserve the internal
interrupt floor and verify actual peaks before acceptance. Do not silently grow
the map or use a larger pool as an unrecorded cost change.

Startup initializes shared publication and manager event storage, starts the
input Task and waits for successful lease/grant admission before publishing AES
readiness. Failed startup retires the acquired prefix. Shutdown closes client
admission, drains client-owned operations, stops interaction intake, retires copied
route references and releases INPUT in its acquiring Task, then closes the
manager display/session after grants and physical effects retire. Retain state
on an unsafe device or lease retirement failure.

MagiC performs ordinary input delivery outside SCRENMGR, using its native
scheduler/deferred mechanisms. Exec's existing Task, signal, message, INPUT and
display services supply that execution role; no scheduler callback, IRQ-side AES
work or GUI-specific kernel operation is proposed. Cursor access can wait for a
bounded drawing grant, but it does not couple input progress to manager UPDATE.
Copied interactions must preserve capture identity, explicit loss/cancellation,
and route-retirement references; a wake is only an arrival hint.

## Alternative: share the console backend Task

Move INPUT acquisition/consumption/release into CONSOLEBACKEND, running routing
outside its existing guarded stream quantum. This adds no Task occupancy, but
couples input/cursor work and console I/O in one service context. A cursor wait
for physical access can delay stream processing. It requires an explicit combined
dispatch and teardown policy; merely calling input helpers inside the current
Forbid-wrapped callback is insufficient. Console model/driver policy must stay
with the driver rather than being moved into SCRENMGR.

Keeping capture consumption in SCRENMGR cannot meet independent delivery while
that Task blocks on UPDATE. Calling Take from a second Task violates current
INPUT ownership. Retiring all outstanding device work before a manager Obtain
is also required whichever input placement is chosen; do not rely on a blocked
owner to execute completion callbacks.

## Acceptance dependencies

Move the input dispatcher only after its chosen storage and Task lifetimes are
explicit. Exercise delivery while an application holds UPDATE, cursor/display
contention, console I/O and capture loss/retirement. SM3 must move retained
caller effects and scene readers before removing AESGATE; SM4 then replaces the
combined loop. The placement decision does not authorize bypassing those steps.
