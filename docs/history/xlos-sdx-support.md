# XLOS816F SDX adapter implementation

[History](README.md) · [Firmware contract](../reference/sdx-firmware.md) ·
[Implementation plan](../plans/xlos-sdx-implementation-plan.md)

XF0–XF4 replace the AltirraOS-only ROM comparison and three hardcoded emulation
interrupt destinations with one firmware adapter. Current builds admit stock
AltirraOS 3.44/816, XLOS816F 2.48 and XLOS816F 2.49. The exact identities are in
the [catalog](../../platform/altirraos/sdx-firmware.json); hashes, actual executed
cases and artifact identities are in the
[development record](../development/xlos-sdx-support.json).

The [original audit](xlos-sdx-audit.md) explains the reported v0.2.1 `$0002`
startup halt. This implementation changes development builds; it does not
modify that release, its clean tag or its published packages.

## Implementation

The adapter captures CPU-visible ROM before unmapping it, checks its CRC and
original emulation vector destinations, then initializes the existing NMI,
nested-VBI and IRQ chain operands. The ROM snapshot and checksum scratch fit
the existing upper bridge bank. Unknown images fail before mapping or
underlying RAM changes. Repeated installation, foreign mapping and reversible
underlay restoration retain their previous semantics. No XLOS ROM bytes or
emulator-only ROM/jump injection are needed in the implementation or acceptance
checks. The default demo continues to distribute the licensed AltirraOS ROM.

Console ROM output now enters emulation explicitly and JSRs public CIOV from
bank zero. This removes the extra firmware COP trampoline frame below a
suspended guest. The saved OS COP `$00` forwarding interface remains intact;
Exec still uses COP `$50`. Guest page-one ownership, idle BASIC parking and
asynchronous context/stack gates keep one implementation.

The XLOS E: stack walk explores both branch arms, all twenty ordinary/shifted
control entries and temporary native scrolling. Only the reviewed GR.0 mode
branch is constrained. Both ROMs visit 6,703 states and require at most fifteen
editor-body bytes. The reviewed CIO/interrupt envelopes give a complete
conservative bound of **121 bytes**, versus **119** for AltirraOS, within the
existing 128-byte reserve. Unknown transfers/stack operations fail the walk.
This is scoped to the stock reviewed ROM handlers; third-party interrupt/PBI
extensions are not covered.

## Executed development checks

The runs use the pinned Action! compiler revision
`05c01f39ff3beef97af0e65b0a16666f5a1bd805`, with no local compiler override,
and the recorded AltirraSDL bridge binaries/configurations. The main fixture
machine is 65C816 at 8x, PAL, 64 KiB plus 63 high banks, private VBXE FX 1.26 at
`$D600` and an ST mouse on port 2. Legacy ARC/EDX runners retain their existing
shell-paced pin. Exact ROM, emulator and emitted-image hashes accompany the
individual results. XLOS XEX fixtures use the emulator's Disk Boot loader;
the mixed-I/O fixture uses physical D2 so it cannot conflict with that loader's
virtual D1. Its native volume alias remains D1.

| Check | Executed scope and result |
| --- | --- |
| Host suite | 656 tests pass, including generated admission metadata, changed/truncated ROM rejection and package contents. |
| Native ROM boundary | Nine cases per XLOS image: eight M/X/I combinations with private D/DBR, hidden accumulator/status/stack guards and clock progress; one real COP `$00` round trip. |
| Shadow/early routing | Five transition phases per XLOS image, plus the AltirraOS component run; install/remove, unknown admission, repeated install, foreign mapping, underlay/vector restoration, real VBI and POKEY IRQ work pass. |
| Resident minimum stack | Optimized XLOS 2.48F and focused raw XLOS 2.49F each pass 113 assertions at anchor `$0190`; the current optimized fixture also passes on both ROMs in the boundary runner. The borrow-transition phase passes 49 assertions with real NMIs. Raw is limited to this bridge/ABI boundary. |
| MD5 | 136 digest/output/context assertions per image, plus 192 real SDFS/SIO assertions on 2.49F. The initial 2.48F-only MD5 fixture predates the direct-CIO change; the current mixed workload below also covers MD5 on that ROM. |
| EDX | 57 assertions per image: physical typing/cursor keys in the text console, existing-file editing, save/new-file contents, ownership, guards and native exit. |
| FastBasic | 631 assertions per image in the retained-session group: repeated Run, state retention, idle parking, MD5 alongside parked BASIC, restart/reset, resource failures, guards and cleanup. |
| Mixed ARC/MD5 | 276 assertions per image: create/list/extract, native peer progress, real SIO, cancellation, ownership/guards, persisted file audit and shell recovery. |
| Argument-free ARC | Additional 128 assertions on 2.49F: empty/null/space argument help, original output comparison, overlay/missing/corrupt failure and recovery. The packaged boot smoke also runs ARC without arguments. |
| Packaged boot | Current OF816-enabled combined ATR and new Atarimax cartridge, five-second autoboot, desktop shell, MD5, argument-free ARC, archive listing, WORK write/read and EXIT. The machine record enumerates the firmware/route pairs actually executed. |

The stale host QED fixture expected notices from a disk intentionally excluded
from the ZIP. It now supplies the required version metadata and asserts that
QED remains separate; production packaging policy is unchanged.

## Memory and artifacts

Reserved bank-zero growth is **0 bytes** for fixed/root/kernel storage, **0 per
public Task** (all twelve) and **0 for idle**, including guards, alignment and
unused reservation. The three JML operands are reused. The upper bridge remains
64 KiB. Compared with the unmodified v0.2.1 demo, its emitted bridge code grows
from 3,066 to 4,324 bytes (+1,258); console adapter instructions grow by three
bytes inside the unchanged 4,096-byte hosted reservation.

The smallest SDX native image-data arena grows from 4,096 to 4,352 upper bytes
(one page) because its current BSS exceeded 4 KiB by seventeen bytes. The full
demo's larger arena does not change. This is upper image storage, not a new
bank-zero or per-Task reservation.

The development demo is built with:

```sh
python3 tools/build_demo.py --output build/xlos-refactor/demo \
  --basic-workbench --release-compiler
```

`build/xlos-refactor/demo/exec816-demo.zip` contains the combined writable
2 MiB-class ATR, matching OF816 XEX/cartridges, short guide, AltirraOS ROM,
license notices and verified checksums. MD5/ARC/EDX, FastBasic and WORK remain on
the same D1. QED and XLOS ROMs are absent. A guide-only disk refresh preserves
the frozen emitted kernel/XEX; the final boot case uses that refreshed media.
The local launch scripts remain beside the development build.

Reproduce selected checks using the commands in the
[building guide](../contributing/building.md#firmware-diagnostics) and the
case arguments in the machine record. Supplying a ROM changes the explicit
firmware input; it does not relax machine/emulator pins.

## Limits

These are development checks, not a new full hosted-system qualification.
Physical accelerator hardware, FujiNet-PC CONFIG/OPTION boot under XLOS, other
XLOS variants/custom images, arbitrary OS high-memory allocation, third-party
PBI/native handlers and the broader firmware service surface remain unqualified.
No boot-speed or editor-latency improvement is claimed by this refactor.
