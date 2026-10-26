# SDX firmware admission and ROM shadow

[Reference index](README.md) · [Resident runtime](sdx-runtime.md)

One adapter and boot image admit AltirraOS 3.44/65816 and stock XLOS816F 2.48
and 2.49. Exact file hashes and CPU-visible checksums are maintained in the
[firmware catalog](../../platform/altirraos/sdx-firmware.json). Native Tasks,
guest patches, BASIC parking and the COP `$50` gateway have one implementation.
The OS's COP `$00` vector remains preserved and forwarded.

## Admission

Installation requires native mode, 16-bit registers, decimal clear, I set,
NMIEN zero, no active ROM call, and a stack/code outside the ROM windows. The
caller owns exclusion until vector publication is complete.

The adapter captures `$C000–$CFFF` and `$D800–$FFFF` into its existing 16 KiB
upper snapshot. It identifies all 14,336 bytes with CRC-32/ISO-HDLC in address
order, then checks the original emulation NMI/IRQ vector destinations against
the selected profile. The inaccessible I/O interval is excluded. Host fixtures
also verify the complete ROM file SHA-256. Runtime CRC is accidental-change
identification, not cryptographic authentication. Customized visible ROM bytes
and arbitrary files named `XLOS816F.ROM` are unsupported.

The snapshot's unused `$1000–$17FF` interval contains installation-only profile
and checksum scratch. It is never copied into bank zero. No XLOS ROM payload is
embedded in the kernel or redistributed in the demo.

Unknown firmware returns status 2 before mapping or underlying RAM changes.
Installation retains status 1 for mapping mismatch and 3 for state mismatch.
An already installed owner cannot install again.

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
