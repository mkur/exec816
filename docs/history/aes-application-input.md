# AES application input implementation

[History index](README.md) · [Implementation plan](../plans/gem4xe/aes-application-input-implementation-plan.md) ·
[Current INPUT contract](../reference/input.md) · [Current AES contract](../reference/aes.md)

Status: AI1 implemented, 2026-10-07. AI2–AI7 remain pending. Public AES input
waits are not implemented yet. These are development checks, not hosted-system
qualification; PI4/HY4 and the observed flicker remain open.

## AI1 — Capture route policy and button qualifiers

[Evidence](../development/aes-application-input-ai1.json) records nine focused
emitted-code runs, the 406-test host suite with four expected historical skips,
and generated-definition checks.

INPUT version 4 adds `ROUTE_UNFILTERED` for keyboard routes. The Task-side native
transaction publishes route identity and filter policy with IRQ masked; NMI can
tick without switching across the publication. IRQ checks one resident byte.
Unfiltered routes receive Ctrl-C/Escape as keys; physical BREAK stays durable,
and existing shell/native routes retain their configured filters.

Pointer button edges and baselines capture Shift/Control qualifiers, including
retained BUTTON output after simultaneous relative movement. Pure motion and
idle sampling do not read additional modifier state. Physical tests cover
Shift-click, held-key Control-click and clearing modifiers after key release;
standalone Control-click remains outside the platform's hardware contract.

Optimized capture, relative decoding, interrupted route publication and 57.6k
SIO checks pass. The disk case observes fifteen addressed pointer samples with
zero losses and checks transfer bytes, ownership and restoration. Small native
registration and C bridge/layout probes pass in raw and optimized modes.
The publication fixture's completion lookup now selects its own module after
the recent merge introduced another symbol named `phase`.

Reserved bank-zero delta is **0 fixed + 0 per public Task + 0 private idle**,
including guards, alignment and unused capacity. Two upper descriptors grow
from 144 to 160 bytes; keyboard capture reuses one padding byte. Existing upper
reservations stay unchanged. The matched console-enabled adapter gains 34 code
bytes in signal code and 48 in native work code, within its existing extents.
