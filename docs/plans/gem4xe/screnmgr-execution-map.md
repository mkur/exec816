# SCRENMGR execution placement

[GEM plans](README.md) · [Migration plan](screnmgr-migration-plan.md) ·
[Task capacity](../../architecture/task-capacity.md) ·
[Input ownership](../../reference/input.md#calls-and-ownership)

MagiC's source baseline is scheduler-side deferred input delivery plus a separate
SCRENMGR application. Ordinary delivery is not a SCRENMGR turn and does not acquire
UPDATE. See the [pinned input/event model](../../architecture/magic.md#input-events-and-application-messages),
AESEVT `read_evnts_from_ringbuf` / `handle_key` / `write_key` and AESMAIN's
`_evnt_multi` → `update_1` → interaction → `update_0` loop.

## Selected direction

The user selected a Task-based input service **reusing the existing resident
console/system Task**, with Terminal as an ordinary GEM application. The
[input.device design draft](../input-device-design.md) makes the device
independent of AES, SCRENMGR and display ownership, with consumers for standard
Atari text, future VBXE text-mode and GEM operation. It proposes bounded consumer
handlers so AES event publication does not require another receiving Task.

This does not add a separate input Task or select a new native deferred-work
service. It also does not put live scene mutation or physical cursor drawing
inside the input dispatcher. Console stream/model work remains in the existing
CONSOLEBACKEND Task. Remaining Worker duties, including the SCRENMGR execution
context and standalone display work, still need explicit relocation/costing;
the complete Task count and stack bounds are not established by this selection.

The alternatives below retain the earlier comparison. They are not the selected
implementation map. Task-side delivery is an explicit Exec adaptation of
MagiC's scheduler-side input role, preserving its independence from SCRENMGR.
This documentation changes no Task, platform service or reserved bank-zero byte.

## Earlier alternative: add a dedicated input Task

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
work or GUI-specific kernel operation is proposed. This earlier option allowed
cursor access to wait for a bounded drawing grant. The selected design keeps
physical cursor work outside input dispatch so drawing cannot delay delivery.
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

## Alternative: keep the current input/display owner and add SCRENMGR

The existing Worker keeps INPUT acquisition, consumption and release, physical
cursor work and display completion. A new SCRENMGR Task consumes copied manager
interactions and uses delegated display access. Stream/model processing remains
in CONSOLEBACKEND. This avoids moving the input leases, but all manager graphics
must lose their current assumption that the caller owns the physical session.
It still consumes one Task slot. An ordinary pool costs 1,600 occupied bytes;
if measured manager depth requires the existing large class, that occupies
2,848 bytes instead. No new pool reservation is implied. Those bounds require
measurement rather than assuming the current large Worker can be replaced by
an ordinary manager unchanged.

## Alternative: a public native deferred-work platform service

There is relevant existing machinery, but not a reusable ordinary-callback API:

- [interrupt-work.s](../../../platform/altirraos/interrupt-work.s) admits bounded
  native work at safe native exits, with two callbacks per opportunity. Dispatch
  currently selects a fixed timer source and an optional test probe.
- [native-interrupts.json](../../../abi/native-interrupts.json) reserves 256 upper
  bytes for source state and 8,192 for native code. Production source capacity
  is one. Reserved slack is not proof that another implementation fits.
- [timer-device.s](../../../platform/altirraos/timer-device.s) performs bounded
  assembly completion with a per-source edit gate. Its callback borrows 26 stack
  bytes for its own temporary state; this is not a bound for arbitrary handlers.
- The [platform contract](../../reference/platform.md#deferred-native-completion)
  admits this work while Forbid is held. The ordinary COP gateway remains
  Task-only; the [native reply binding](../../reference/ports.md#native-interrupt-reply)
  permits bounded publication without scheduling, allocation or compiled policy.

Current AES input delivery cannot simply be registered there. `INPUT.Take`,
`AESSNAPSHOT.Select` and `AESINBOX.PublishEndpoint` are ordinary compiled routines
using Task gateways and Forbid. Their current Task guards do not exclude native
completion. In particular, native delivery would be able to interrupt a guarded
snapshot or inbox mutation unless a native-safe publication/edit protocol were
introduced. Display access and any waiting also remain outside this callback ABI.

The missing capability is a **general public deferred-service registration,
notification and retirement contract**, including callback context/stack bounds,
allowed native operations, edit exclusion and lifetime pins. If ordinary compiled
callbacks are required, their independent DP/stack context and legal gateway use
must also be provided; hiding those resources does not make them free. The
existing assembly ABI alone does not supply that context.

A restricted native service could avoid another Task and resemble MagiC's
scheduler-side delivery more closely. It is a platform project first: no GUI
callback may be added directly to the fixed timer dispatcher. Neither zero
bank-zero growth nor support for existing AES routines is established by this
audit. A separate design and explicit selection are required before implementing
this option, under the repository's missing-platform-service rule. Task-based
options use public services already available and preserve current Task-side
publication semantics.

## Acceptance dependencies

Move the input dispatcher only after its chosen storage and Task lifetimes are
explicit. Exercise delivery while an application holds UPDATE, cursor/display
contention, console I/O and capture loss/retirement. SM3 must move retained
caller effects and scene readers before removing AESGATE; SM4 then replaces the
combined loop. The placement decision does not authorize bypassing those steps.
