# Directory batching

[Design](../plans/directory-batching-design.md) ·
[Plan](../plans/directory-batching-implementation-plan.md) ·
[Machine-readable evidence](../development/directory-batching.json)

## EB1 Public operation

ExNextBatch returns up to sixteen compact entries through one filesystem packet.
Native DOS, loaded COMMAND and C share action 28. DOS/COMMAND/C-program versions
are 11/19/20; applications must be rebuilt. DirEntry uses `kind` rather than the
design's original `type` spelling because TYPE is an Action! keyword.

The worker reuses ordinary directory metadata and ancestry, checks the cookie
once, and publishes each record with its cursor and count. Errors and active
cancellation retain that prefix; only final publication enters completion-wins
retirement. Ordinary ExNext remains available and can share a cursor with batches.

Development checks used the pinned compiler, Calypsi 5.18 and the pinned
shell-paced Altirra bridge/AltirraOS ROM. Emitted optimized SDFS, MyDOS and RAM
cases cover capacities 1/8/16, empty and exact-multiple termination, invalid
capacities, independent/interleaved cursors, directory ancestry, compact metadata,
unchanged non-cookie FIB fields, RAM epoch rejection and loaded COMMAND calls.
The C layout probe and 1,890-byte result buffer cross a bank boundary. A small
raw C/native/COMMAND run covers the same ABI in unoptimized emission.

Seven optimized retirement cases inject real foreground delivery before send,
while queued, before publication, after three records, during SIO activity,
after final publication, and after a causal prefix error. Each checks reply
collection, resumable cursor position and cleanup. Hooks exist only in copied
test modules. Guards and ownership checks pass; maximum observed Task stack
touch was 391 bytes. These are development checks, not platform qualification.

ABI generators and six DOS packaging host checks pass. The older metadata
regression compiled but its removed historical emulator binary prevented that
runner from executing; the new focused suite uses the available pinned bridge.

Reserved bank-zero change: **0 fixed, 0 per Task, 0 idle bytes**, including
guards and unused capacity. Upper-memory Service size grows **516→520 bytes**
(five field bytes consume one existing padding byte). The C DOS table grows
**72→75 bytes**. The seven changed DOS/FS native modules grow by 2,844 emitted
code bytes against the retained optimized demo; this excludes wrapper/provider
code. Provider usage and capacity are recorded in the JSON. No worker buffer,
Task, port or per-entry heap allocation is added.

## Remaining slices

EB2 adopts eight-entry refills in the shared scanner. EB3 measures eight versus
sixteen, competing-client latency and complete UI paths, then refreshes OF816.
RAM's 256-node limit includes its root; the 255/256/257 scanner boundaries use
controlled emitted DOS replies rather than enlarging the filesystem for a test.
