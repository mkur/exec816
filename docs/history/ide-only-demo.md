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
