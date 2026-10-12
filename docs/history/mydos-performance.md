# MyDOS performance implementation

[Plan](../plans/mydos-performance-implementation-plan.md) ·
[Historical records](README.md) · [Testing policy](../contributing/testing.md)

Development evidence uses the pinned compiler and AltirraOS ROM; it does not
qualify real hardware or a release. All slices add zero fixed, per-Task and idle
bank-zero bytes, including alignment, guards and unused capacity. Buffer and
Task stack reservations remain unchanged.

## MP0: baseline

The [baseline record](../development/mydos-performance-baseline.json) captures
matched instrumented COPY of 23,872 bytes through a 16 KiB buffer. Accurate
Generic 57600 timing gives 3,879 PAL frames, 99 reads and 341 writes for cold
creation; warm creation takes 2,982 frames, two reads and the same 341 writes.
Cold replacement takes 9,001 frames, 290 reads and 720 writes; warm replacement
8,066 frames, 193 reads and 720 writes. Command loading is excluded. Observer
calls contribute overhead; final comparisons use identical observers.

The operation fixture additionally isolates writable Open, seek, enumeration,
truncation, deletion and directory creation. It audits persisted allocation and
unrelated files and checks buffer and Task ownership guards. Large native images
and frozen library inputs remain under `build/mydos-performance/mp0/`.
Host development checks: 447 passed.
