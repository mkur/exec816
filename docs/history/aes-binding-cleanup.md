# AES binding cleanup

[History index](README.md) · [AES contract](../reference/aes.md) ·
[Evidence](../development/aes-binding-cleanup.json) ·
[Caller-local UPDATE plan](../plans/gem4xe/caller-local-update-plan.md)

This preparatory cleanup removes redundant caller lookup and admission work
before changing UPDATE ownership. BEGIN and END still exchange messages with
the presenter. Kernel dispatch, scheduling, drawing batches and timer semantics
are unchanged.

## Changes

- `ExecAESSubmit` compares the reply owner with the identity established before
  submission, avoiding a reply-time `FindTask(NULL)` gateway call.
- Scoped BEGIN, window operations, attached-menu setters, drawing and the core
  parameter-block dispatcher pass their established context through private
  helpers. Window deletion and detach also reuse the context for cleanup.
- Direct admission keeps the local registered/busy checks and removes the
  redundant shared-endpoint audit and its Forbid/Permit pair. Only the owning
  Task can exit/detach; registration pins the endpoint until that lifecycle ends.
  Shared context-table lookup, window snapshot, event epoch/loss/commit and
  message publication guards remain.

Public signatures and shared record layouts do not change. This is a bounded
hot-path cleanup: resource loading and composite form/editing event loops still
contain public calls and can be audited separately.

A normal Files full redraw now has five context lookups instead of eight.
Those remaining calls select the Task's context; they are not five independent
ownership validations. The context pointer is stable from attach through detach,
so a cheaper task-local retrieval mechanism remains a separate opportunity.

## Measurements

The same small optimized fixture runs eight successful calls per path beside
a second registered Task querying desktop geometry. The named query also runs
once under inherited Forbid. Passive PC traces cover probe entry through return;
outer argument setup/JSL is excluded. Scheduler observations separate caller
CPU from interrupts and time spent running other Tasks, including the presenter.

| Path | Current-Task queries before → after | Mean caller CPU before → after | Median caller CPU before → after |
| --- | ---: | ---: | ---: |
| Named window query | 1 → 1 | 1.180 → 1.082 ms | 1.182 → 1.034 ms |
| Parameter-block window query | 2 → 1 | 2.676 → 1.833 ms | 2.597 → 1.757 ms |
| Scoped BEGIN + END | 5 → 2 | 7.131 → 5.475 ms | 6.933 → 5.576 ms |
| Parameter-block BEGIN + END | 6 → 2 | 9.093 → 7.189 ms | 9.026 → 6.807 ms |
| Attached menu enable | 3 → 1 | 3.857 → 2.776 ms | 3.859 → 2.627 ms |
| Parameter-block menu check | 4 → 1 | 5.386 → 3.386 ms | 5.173 → 3.238 ms |
| Named small object draw | 1 → 1 | 3.550 → 3.144 ms | 3.196 → 2.997 ms |
| Parameter-block small object draw | 2 → 1 | 4.871 → 3.813 ms | 4.482 → 3.585 ms |

Both UPDATE messages remain in each pair. Named `wind_get` retains two
Forbid/Permit pairs (context lookup and snapshot), down from three. Named
`objc_draw` retains one, down from two. This is small-sample binding evidence,
not a whole-Files redraw, dropdown or input-latency claim. Scheduling phases and
peer work differ between builds; no p95 conclusion follows from these samples.

The parent is `ffa8d2b`, with identical fixture source and production source
hashes checked against that commit. The candidate uses the same compiler pin,
Calypsi 5.18, dedicated AltirraOS ROM and PAL/8x 65816/VBXE configuration.
Exact build, source, image and trace hashes are retained in the evidence.

## Development checks and resources

The focused binding fixture covers named/PB calls, two independent application
contexts, busy rejection without sequence changes, inherited Forbid, messaging,
window/drawing lifecycle, detach and re-registration, heap restoration and
stack/domain guards: **380 assertions pass**. Existing optimized event and
registration fixtures pass **371 and 233 assertions**, covering wait/cancellation
and endpoint publication/retirement separately. The registration
fixture's second linked binding needed its private symbol renames brought up to
date; no production lifecycle workaround was introduced.

The host suite passes 487 tests with four historical-source skips. These are
development checks, without a full qualification matrix, compiler test suite,
demo refresh or hardware qualification.

Reserved bank-zero delta is **0 fixed bytes, 0 per public Task and 0 idle bytes**,
including guards, alignment and unused capacity. No new upper-RAM state or VRAM
reservation is added. The linked fixture C image shrinks by **558 bytes** and
zero-fill stays unchanged. Root stack peak changes from 821 to 825 bytes, leaving
455 bytes above the protected floor in its existing reservation.

Reproduce the focused binding observation:

```sh
python3 tools/test_aes_bindings.py --output build/aes-binding-cleanup/after
```

Use `--replay` to reanalyze the saved trace without rebuilding or executing the
guest. The parent capture, full traces and intermediate builds stay in `build/`.
