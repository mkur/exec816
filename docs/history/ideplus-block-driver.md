# IDE Plus block driver development

[History index](README.md) · [Implementation plan](../plans/ideplus-block-driver-implementation-plan.md)

## IP0 — transport separation

The block adapter uses IOStdReq and a small transport dispatcher. SIO retains
its commands, profiles, reply ownership and cancellation. Mount identity includes
a backend byte at offset 45 of the unchanged 46-byte descriptor. Offline handling
invalidates only mounts using that controller; RAM volumes remain independent.
IDE configurations are rejected until the driver is connected.

Development checks with pinned actionc `6510ea1` passed optimized fixture and
real-SIO block reads/cache/cancellation, verified persisted SIO sector writes,
a persisted SpartaDOS 256-byte-sector file create/append smoke check,
and raw/optimized emitted mount layout probes. Eight mount-generator host tests
passed. Evidence is in `build/development/ideplus-ip0/`. This is development
coverage, not hosted-system qualification.

Reserved bank-zero delta: **0 bytes fixed, 0 per Task, 0 idle**; guards, alignment
and reserved pool capacities are unchanged. Request storage remains 52 bytes.
The extra volume backend uses upper-memory record space only.

The filesystem write fixture had outgrown its 2 KiB upper static-data arena and
its injected path buffer overlapped emitted code. It now uses the demos' 4 KiB
static-data arena and puts paths at `$2D1000`, outside the kernel image.
