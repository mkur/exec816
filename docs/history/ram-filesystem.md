# RAM filesystem development

The [current contract](../reference/ram-filesystem.md) describes supported
behavior. The [implementation plan](../plans/ram-filesystem.md) splits the work
into backend/ownership and shell integration. This is development evidence,
not hosted-system or physical-hardware qualification.

R1 adds the third backend to the existing filesystem worker. Nodes retain
opaque identities and ordinary DOS leases. File data uses geometric contiguous
upper allocations with `MEMF_LINEAR`, so files can cross native banks. Empty
RAM mounts allocate 200 rounded upper bytes, including the root, volume,
metadata and request port. A RAM-only worker uses 1,912 rounded bytes of common
service/workspace/control allocations, including the existing 1,192-byte write
workspace; caller contexts and reserved kernel metadata are separate. Each
additional node costs 56 rounded bytes, plus
payload capacity for a nonempty file and ordinary DOS objects while open.

The ninth mount slot grows the shared Service record from 460 to 464 bytes;
both already round to the same 464-byte allocation. Descriptors occupy existing
upper image storage. The RAM modules emit 11,214 optimized code bytes in the R1
fixture, excluding common dispatch changes. No Task, direct page, stack or
reserved bank-zero capacity is added: fixed and per-Task deltas are zero.

The optimized RAM-only fixture passes 165 checks: directories, case folding,
70,001 independently checked binary bytes, EOF and bank-boundary overwrite,
seek bounds, writer leases, parent paths, rename/delete rules, enumeration
epochs, allocation exhaustion and shutdown/restart. Exhaustion commits 57,344
append bytes before returning `ERROR_NO_FREE_STORE`, preserves the original
bytes and leaves the volume usable. Both stops restore the complete heap.
The focused raw fixture passes 20 checks and agrees with optimized record
sizes/access. The nine-mount diagnostic and a 256-byte MyDOS write regression
also pass, retaining native stack/domain guards, OS restoration and ownership
checks. The host suite passes 397 tests.

The deepest R1 observed application stack use is 283 bytes and filesystem-worker
use is 217 bytes. These are measured watermarks, not new reservations or static
whole-program upper bounds. The normal eight-slot profile and interrupt
headroom remain unchanged.

Exact compiler, ROM and emulator hashes, emitted modes, input hashes and selected
results are in [ram-filesystem.json](../development/ram-filesystem.json).
The compiler source is the clean pinned revision; its host binary was built
with dev `opt-level=1`/`debug=0` for build speed, with no language/ABI override.

R2 enables RAM in shell/demo configurations and names it in startup diagnostics
and MOUNT. The physical-keyboard shell check passes loaded COPY in both
directions, CMP, append, pipe output, a RAM-backed EXECUTE script, relative and
parent paths, directory creation, rename and deletion. Its saved SpartaDOS
file independently matches all 70,001 source bytes, with the other files
unchanged. Console writes, OS restoration and final ownership checks pass.
The final review corrected zero-length RAM Read; a subsequent optimized small
probe passes 21 checks, including `Read(file, NULL, 0)` and unchanged position.
The large shell run precedes this small follow-up; it was not repeated because
the follow-up changes only zero-length admission. Final RAM-module code sizes
and hashes are recorded in the JSON. No demo ZIP or release matrix was built
as part of this implementation.
