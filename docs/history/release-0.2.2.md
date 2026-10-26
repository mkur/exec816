# Exec816 0.2.2 patch preparation

[History](README.md) · [Release notes](../releases/0.2.2.md) ·
[Machine record](../development/release-0.2.2.json)

The 0.2.2 draft prerelease fixes the XLOS boot failure identified in the
[ROM audit](xlos-sdx-audit.md). Its native distribution is built from clean
`v0.2.2`, source `3881c641ae8c37f7c2eccf36f3a1535f33ce2258`, with the pinned
Action! compiler. Startup and physical Shell `VER` show
`Exec816 0.2.2 (v0.2.2)`. Existing v0.2.1 tags and GitHub assets are preserved.

## Frozen candidate checks

| Check | Result |
| --- | --- |
| Host suite | 656 tests pass. |
| Hosted console/context matrix | All 28 raw/optimized cases pass. |
| Cooperative matrix | All 46 raw/optimized scheduling, context, IRQ/NMI and explicit forwarding cases pass. |
| Preemptive matrix | All 60 raw/optimized cases pass, including all eighteen NMI checkpoints, forwarding signatures, timer and keyboard IRQ work. |
| Firmware component matrix | 54 cases cover three ROMs, two guest-bank/DP placements, IRQ-enabled/masked contexts and reachable transition phases. |
| XLOS native ROM boundary | Eighteen cases cover both F images, all M/X/I combinations and real COP `$00` with private D/DBR/stack/context checks. |
| Resident stack matrix | Sixty raw/optimized cases on all three ROMs; 3,018 assertions cover minimum-depth scrolling, accepted/rejected headroom, all four borrow phases and all three lease phases. |
| Final boot packages | Nine boot walks cover combined ATR on all three ROMs, new Atarimax on all three, old Atarimax on AltirraOS and XLOS 2.49F, and XEX on AltirraOS. |

Each boot walk checks the exact tagged version, MD5, argument-free ARC help,
archive listing, WORK write/read, `FBI WORK:HELLO.BAS`, `FB WORK:CALC.BAS`, guards,
ownership and clean EXIT. ATR loading also verifies expanded native bytes and
zero-fill, loader guards, five-second OF816 countdown and firmware context.
The actual hashes/configurations and observer sources are embedded in the
machine record. Native application development evidence remains in the
[XLOS implementation history](xlos-sdx-support.md); it is separate from these
final-package checks.

Release preflight corrected two older oracles that counted every OS console
write as a forwarded COP. Production now uses CIOV directly; only explicit
nonzero forwarding probes expect those COP counts. An unbanked bounds branch
also needed a long displacement when an NMI checkpoint was assembled. This
branch is excluded from the banked distribution. The component selector omits
the owned-IRQ injection phase when I is set, because that IRQ cannot occur;
the other NMI transition phases still run with IRQs masked.

The added BASIC boot check initially used relative source paths. The corrected
walks use the documented WORK paths and fresh media copies. Initial attempts
are retained in the development build directory and are not counted as passes.

## Distribution

`exec816-demo.zip` contains the combined writable ATR, matching OF816 XEX and
Atarimax images, licensed AltirraOS ROM, short guide, notices under `licenses/`
and per-file checksums. QED and XLOS ROMs are absent. The accompanying
`exec816-fastbasic-source.zip` contains the tagged Exec source and pinned patched
FastBasic donor tree; all 4,524 source-file checksums pass. Both ZIPs have
separate SHA-256 files.

All eight application binaries match v0.2.1 byte for byte. The release-specific
changes add **0 reserved bank-zero bytes**, fixed/root/kernel, each of twelve
public Tasks and idle, including guards, alignment and unused capacity. The
firmware adapter's previously recorded upper-memory costs and 119/121-byte ROM
stack bounds are unchanged.

## Remaining gates

This is release preparation for a draft preview. The selected matrices pass;
full hosted-system/release qualification remains open. The complete o65 release
matrix and accurate 256-byte MyDOS COPY matrix were not rerun for this draft.
Physical accelerator/cartridge hardware and XLOS FujiNet CONFIG/OPTION boot
remain unqualified. No editor-latency or boot-speed qualification is claimed.
