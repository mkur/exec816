# SDX firmware admission and ROM shadow

[Reference index](README.md) · [Resident runtime](sdx-runtime.md)

The dedicated 65816 platform assumes two firmware families: AltirraOS and XLOS.
One adapter recognizes AltirraOS 3.44/65816 and names the exact stock XLOS816F
2.48 and 2.49 profiles. Other ROM bytes select **XLOS (assumed)** and continue
startup. Exact file hashes and CPU-visible checksums are maintained in the
[firmware catalog](../../platform/altirraos/sdx-firmware.json). Native Tasks,
guest patches, BASIC parking and the COP `$50` gateway have one implementation.
The OS's COP `$00` vector remains preserved and forwarded.

## Admission

Installation requires native mode, 16-bit registers, decimal clear, I set,
NMIEN zero, no active ROM call, and a stack/code outside the ROM windows. The
caller owns exclusion until vector publication is complete.

The adapter captures `$C000–$CFFF` and `$D800–$FFFF` into its existing 16 KiB
upper snapshot. It identifies all 14,336 bytes with CRC-32/ISO-HDLC in address
order, then checks the original emulation NMI/IRQ vector destinations to select
an exact version label. If no complete match exists, it selects the XLOS
fallback. Both paths chain the actual captured vectors. The inaccessible I/O
interval, including the ROM file's self-test slot, is excluded. Host fixtures
also record the complete ROM file SHA-256. CRC identifies the visible bytes;
it is not an executable-compatibility test or an authentication check.

The snapshot's unused `$1000–$17FF` interval contains installation-only profile
and checksum scratch. It is never copied into bank zero. No XLOS ROM payload is
embedded in the kernel or redistributed in the demo.

Installation returns 0 for exact profiles and assumed XLOS, 1 for mapping
mismatch and 3 for state mismatch. A different checksum no longer returns 2.
An already installed owner cannot install again. Executed firmware/stack
evidence covers the pinned stock images; the fallback is the platform's family
assumption, not qualification of every modification or expansion mapping.

## Startup diagnostics

Admitted kernel initialization always prints the same version/source identity
as shell `VER`, before `BOOT MEMLO`, RAM adoption and Task/heap initialization.
It uses the captured build record, including a clean release tag or commit and
dirty state. Quiet mode retains this identity.

After `KERNEL READY`, verbose startup prints `ROM CRC32`, `ROM PROFILE` and
`SDX ROM=OK`. Assumed XLOS prints this block even in quiet mode, together with
the original emulation NMI/IRQ destinations and individual CRC-32 values for
`$C000–$CFFF`, `$D800–$DFFF` and `$E000–$FFFF`. These identify a localized math
pack or PBI overlay without changing the captured ROM or device selection.
`VBI/IRQ=OK` follows successful installation and reporting.

Mapping failure prints `$0001 MAPPING`, PBCTL/PORTB and unavailable checksum/
profile fields. Repeated installation prints `$0003 ALREADY INSTALLED` and
unavailable fields rather than values from the earlier attempt. Failure detail
is unconditional. Terminal reporting retains the original cause even if
cleanup then requires a reset.

ROM diagnostic lines use the existing direct screen writer, preserve registers,
IOCB0 and margins, and call no firmware. IRQ/NMI exclusion covers the whole
block; success resumes normal VBI, while failure proceeds to terminal cleanup
with NMI disabled. Formatting uses a bounded 40-byte buffer on the existing
native stack. No snapshot, bank-zero or per-Task reservation grows.

## Publication and removal

Before enabling IRQ/NMI, initialize the three existing bank-zero JML operands
from the admitted snapshot's original `$FFFA`/`$FFFE` destinations. The NMI
destination serves ordinary chaining and nested ROM VBI; IRQ has its own
destination. Do not read these destinations from the patched hardware vectors.
Operands remain immutable throughout the installed lifetime.

Save PORTB, unmap ROM, back up all 14 KiB beneath it, copy the captured ROM into
that RAM and replace only the emulation IRQ/NMI vectors. Then publish ownership.
The native RAM vectors and normal Exec routing retain their current protocol.

Removal first verifies mapping ownership. Restore all underlying RAM before
re-enabling the original ROM, then release ownership. Foreign mapping returns
an error without restoring into somebody else's mapping. Warm/cold reset,
self-test and third-party PORTB changes are outside this installed lifetime.

## Stack and memory

Console I/O selects the shared page-one stack, saves native S, enters emulation
and JSRs public CIOV from bank zero with D=DBR=0. It returns to native mode before
restoring its caller. IRQs remain enabled; OS_BUSY prevents Task dispatch across
the activation. The explicit transition avoids relying on a firmware-specific
COP trampoline's extra frame.

The conservative complete chain is 119 bytes for AltirraOS and 121 for XLOS,
including public CIO dispatch, editor/native scrolling, one nested VBI,
owned/ROM IRQ, acknowledge-only NMI and the retiring VBI tail. The reserve stays
128 bytes; minimum borrow anchor remains `$0190` above floor `$0110`.
Assumptions are stock GR.0 IOCB0 E: output, the reviewed ROM/Exec vectors,
serialized ROM state and no third-party handlers. The XLOS editor walk includes
all control entries and its temporary native-mode scrolling, with unknown
transfers/stack effects rejected.

Reserved bank-zero growth is **zero**, fixed, root/kernel, each of twelve public
Tasks and idle, including guards, alignment and spare capacity. Snapshot,
backup, profile scratch and CRC table fit the existing 64 KiB upper bridge
reservation; its maximum reservation does not grow. The minimal SDX native
image data arena uses 17 upper pages (4,352 bytes); larger demo arenas are
unchanged.

The admitted profiles do not authorize arbitrary XLOS high-memory allocations
or third-party PBI/native extensions alongside Exec's memory owner. Preserve
bank `$01` and the existing memory-adoption contract.
