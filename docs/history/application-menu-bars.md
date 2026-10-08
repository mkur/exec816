# Application menu bars

[History](README.md) · [Design](../plans/gem4xe/application-menu-bar-design.md) ·
[Implementation plan](../plans/gem4xe/application-menu-bar-implementation-plan.md)

## AM1 — Registration and withdrawal

Implemented on the `7492958` baseline. AES wire version 10 keeps the 112-byte
request and sixteen ordinary records. The GUI record grows from 36 to 40 bytes;
the private C context grows from 288 to 308 bytes. Registration retains a caller's
OBJECT tree through the existing Task lease and allocates a 336-byte association
record per installed menu in upper memory. No tree or strings are copied.

Install/replace admits supported shape and geometry once. Failed replacement
preserves the previous registration. Mutations and withdrawal wait for the
existing native paint boundary, including under the caller's UPDATE/MCTRL.
Closing a window keeps installation; application exit withdraws before releasing
caller storage. Private transport is present; public `menu_bar` awaits AM4.

Development checks: 137 optimized menu assertions, two simultaneous owners,
pre-open installation, owner locks, replacement/geometry failures, hide/reopen,
generation exhaustion, poisoned retired storage and heap return. Both raw and
optimized context/layout probes passed, including bank-crossing request access,
register/DP restoration and opposite bridge stack parities. Host suite: 417 tests,
four historical skips. [Evidence](../development/application-menu-bars-am1.json).
The menu fixture's presenter stack peak was 700 bytes, leaving 1604 bytes above
the interrupt reserve. No complete desktop/package or hardware claim yet.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 private idle**. This
includes guards, alignment and spare reservation. Further integrated code/data,
manifest and cartridge accounting belongs to AM3/AM6.
