# IDE diagnostics implementation plan

Status: in progress. Development checks follow the
[testing policy](../contributing/testing.md); physical hardware remains unqualified.

## Outcome

Retain the IDE Plus startup observations and show controller detection, IDENTIFY
capacity, supported APT mappings and the exact failed mount phase and error.
Verbose boot prints the report after filesystem startup; `MOUNT DIAGNOSTICS`
repeats it and supports ordinary redirection for hardware reports. Plain `MOUNT`
keeps its compact table and adds a retained mount failure when present.

Reports copy existing observations. They never start a controller, probe a disk,
call BIOS, flush, repair or retry I/O. An unattempted controller says so. Capacity
uses sectors and MiB, avoiding overflow at the LBA28 limit. Unsupported/inactive
APT slots are distinguished from a malformed table. A failed table publishes no
partially accepted mappings. Preserve ATA status/error separately from the driver
error, and retain observations after worker cleanup.

## D1: driver observations

Add generated pointer-free controller and partition records and named failure
reasons in `abi/ideplus.json`. Store the 24-byte controller observation in unused
space at offset 704 of the existing 1024-byte upper-memory arena. Reuse the
partition record's padding byte for its admission reason; keep its 24-byte layout.
Copied Task-only queries use the existing lifetime exclusion and expose no
partially initialized mappings. Record worker/resource/timer/controller/IDENTIFY
failure, capacity, card protection and precise APT validation failures with the
table LBA and slot. Keep transport and admission policy unchanged.

Validate emitted snapshot records, valid direct/even/MBR/chained APT images,
unsupported slots, malformed table cases, controller/disk absence, retained
observations and repeated snapshots without extra I/O or allocations.

## D2: retained mount failures

Keep the failing configured slot, phase and causal error outside the disposable
filesystem worker. Add six bytes to the private upper-memory DOS registry and
advance its reservation together. Distinguish allocation, device open, geometry
admission, filesystem recognition and header read. Geometry reports identify
sector-size/count mismatch, partition/board protection and lack of durable-write
support without duplicating the existing admission checks. Copy mount identity
and configured geometry for reports; preserve the original DOS IoErr. Published
offline mounts retain their existing causal error in the compact snapshot.

Validate native failed startup and remount paths, cleanup lifetime, incorrect
geometry, read-only admission, bad filesystem header and successful retry.

## D3: presentation and documentation

Add a shared shell report for verbose boot and `MOUNT DIAGNOSTICS`. Keep ordinary
lines within 40 columns on both consoles. Include state, failure phase/reason,
numeric error, ATA registers when relevant, physical sector count and each
discovered mapping's unit/LBA/count/access. A failed startup always prints its
specific mount failure even without verbose mode. Update shell/device references
and the development record. Exercise the actual emitted shell report, redirection
and standard/IDE demo startup at the development tier.

## Memory and boundaries

All slices reserve **zero additional bank-zero bytes**: fixed 0, per Task 0,
idle 0. D1 consumes already reserved upper-memory capacity; D2 increases the
upper DOS registry by six bytes (subsequent alignment may add padding). D3 uses
caller stack and the existing 512-byte shell transfer buffer. Measure native
stack headroom after adding the reports; do not enlarge pools without evidence.
No interrupt entry, queue ownership, deadlines, partition layout, filesystem
write ordering or public DOS/COMMAND ABI changes are required.
