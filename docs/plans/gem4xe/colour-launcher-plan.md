# CG4 implementation plan

[Design](colour-launcher-design.md) · [Roadmap](../../roadmap.md#colour-gem-desktop-roadmap)

Status: implemented; focused development checks pass. This is not release qualification.

1. Move launch handles from directory windows into the desktop owner. Start
   optional tools on demand, collect completions and retain the shell. Prove a
   launched application survives its originating folder window closing.
2. Add a bounded file association table and copied path arguments, reporting
   unavailable programs or Task slots without discarding directory state.
3. Add Copy/Delete commands and existing-dialog integration, with incremental
   copy progress, Cancel, overwrite confirmation and exact I/O error handling.
4. Add explicit Save Settings and startup restore through WORK:DESKTOP.CFG. Keep
   defaults usable when the file is missing, malformed or unwritable.
5. Build and exercise the OF816 ZIP through independent launches, file mutations,
   cancellation, settings restart, focus/exposure and orderly desktop shutdown.
   Record reserved memory, stack headroom and median/p95 interaction latency.

The disk-full fixture leaves 21 free sectors on disposable 256-byte SDFS media,
so normal small copies fit and the large copy fails after several chunks. An
earlier, less-full fixture reached its 240-second test limit with 20,480 bytes
in the temporary file and the original target intact; it had not reached disk
full. This is an incomplete stress run, not a successful failure check. Profile
desktop copy throughput separately before increasing its 512-byte event-loop
work unit. The [filesystem buffering record](../../history/spartados-write-buffering.md)
explains why small Write requests settle metadata more often than shell COPY's
16 KiB requests.

[Development evidence](../../development/colour-gem-cg4.json) records the OF816
walkthrough: New Folder/Rename, default-cancel Delete and Replace, confirmed
file/empty-directory deletion, copy/replace, cancellation, read-only failure,
partial disk-full failure, TXT launch and child collection. Independent SDFS
read-back verifies copied bytes, preservation of the old destination and removal
of temporary files. A second boot restores the saved WORK: folder and List view.
The shell still executes HELLO after the mutation cases and exits cleanly.

Confirmations use the folder's existing inline dialog and keep processing sibling
events. The test opens and closes another folder while confirmation remains
active. No file-operation daemon or additional Task is introduced.

Reserved bank-zero deltas are **0 fixed, 0 per public Task, 0 idle**, including
guards, alignment and unused reservation. The copy job is 1,302 upper-memory
bytes, including its 512-byte payload buffer; settings use a temporary 1 KiB
buffer. The full file walkthrough leaves 164 bytes above the smallest observed
public-Task interrupt floor and 125 bytes for idle, with all stack guards intact.

The execution record identifies the exact packages and source hashes for the
file/settings walkthrough and the subsequent background-selection refinement.
Interaction measurements use forty samples each with desktop, one folder, shell
and on-demand Panel; they are frame-granular scanout measurements, not a matched
comparison against CG2's different startup applications. Large-copy throughput,
multiple selection, dragging and recursive file operations remain follow-up work.

The final preview measures **80.3 ms median / 100.3 ms p95** Panel press feedback
and **180.4 / 180.6 ms** icon-selection feedback. Earlier runs of this series put
Panel's median near 100 ms; frame phase affects this distribution. The background
selection refinement is not evidence of a Panel speedup.
