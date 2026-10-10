# IDE-only demo development record

[Implementation plan](../plans/ide-only-demo-implementation-plan.md)

## ID0 — IDE system volume

System selection now admits a configured IDE mount, preserving its unit and
physical alias. SYS shares that slot's identity and cache. The existing SIO
drive override remains limited to SIO-selected SYS; IDE uses a zero override
and its generated immutable unit. The eight-byte boot record and four-byte
upper captured settings retain their layouts.

All 425 host checks pass. A focused optimized emitted check opens both SYS:
and SYSTEM: on the same SpartaDOS partition, checks the canonical root name,
rejects creation on read-only SYS and retires filesystem ownership. A nonzero
SIO override falls back to the fixed IDE default with BAD_RECORD status.
Read-only media stays byte-exact. Evidence:
`build/development/ide-only/id0/results.json`.

Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**, including
guards, alignment and unused capacity. No pools or public layouts change.
This is development coverage, not hosted-system or physical qualification.

## ID1 — Driver selection

The generated admission/transport modules and native assembly can exclude SIO.
Keyboard, pointer, timer and interrupt services remain shared; timer callbacks
have a standalone bridge when the serial engine is absent. Reserved metadata
and Task pools are unchanged. OpenDevice on sio.device returns the ordinary
open failure, with no SIO worker, Action driver or native serial engine linked.

All 425 host checks and the optimized ordinary SIO public example pass. The
IDE-only SYS fixture passes both boot-setting cases, guarded cleanup and exact
read-only media comparison. Its IDE worker ordinary call bound is 458 bytes;
including the 256-byte interrupt reserve and 16-byte dispatch margin gives
730 of the existing 1,024 bytes (294 bytes headroom). Evidence:
`build/development/ide-only/id1/results.json` and `id1-sio/results.json`.
Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**.
