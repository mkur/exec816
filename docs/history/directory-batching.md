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

## EB2 Shared scanner

Files, desktop folder windows and the standard file selector now share
eight-entry refills. FileScan allocates its upper-memory buffer before taking
the directory lock, retains each batch's terminal status, and consumes records
locally. Cleanup releases both resources once, including failed begin and early
stop. The selector retains its existing event checks between entries.

The 256-entry display limit uses one final record to distinguish an exact fit
from truncation. A real error takes precedence over truncation and clears the
incomplete displayed list. Browser totals now use compact record sizes and
flags: SDFS/RAM totals remain exact; MyDOS bounds say “bytes or less”; unknown
sizes stay unknown. The rendering and selection paths are unchanged.

An optimized emitted C scanner probe passes 0/8/9/255/256/257 entries, final
prefix errors, allocation failure, early/repeated cleanup and path helpers.
RAM's 256-node limit includes its root, so large-count scanner boundaries use
controlled DOS replies. Maximum observed Task stack touch is 165 bytes; guards
and ownership checks pass. Emitted Browser/FileScan and selector layout probes
also pass. All application artifacts were rebuilt. Real desktop root/C/RAM
navigation and Refresh work in the packaged demo; the standalone Files and
selector walkthrough is shared with EB3's delivery/measurement run.

FileScan grows **20→38 bytes**, Browser **4,039→4,059**, and selector
**3,242→3,260**. Eight-byte heap rounding makes the owner reservation increases
24 and 16 bytes respectively. The temporary eight-record buffer has **946
payload bytes / 952 allocated bytes**; sixteen would use **1,890 / 1,896**.
AllocMem adds no per-allocation prefix. FileEntry remains 112 bytes. The Service
size change in EB1 stays within its previous 520-byte rounded heap allocation.
Reserved bank-zero change remains **0 fixed, 0 per Task, 0 idle bytes**.

## Remaining measurements

EB3 compares eight versus sixteen, competing-client delay and complete UI paths,
and completes the shared packaged walkthrough and OF816 delivery.
