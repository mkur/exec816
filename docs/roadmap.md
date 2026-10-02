# Remaining work

[Documentation home](README.md)

This page tracks open directions, not completed implementation history. The
[architecture overview](architecture/overview.md) describes what exists now;
the [earlier roadmap](history/roadmap-chronology.md) preserves the milestone log.

## Before a public release

- Run the [release qualification tier](contributing/testing.md#release-qualification)
  against the selected compiler, ROM, emulator and final distribution. Focused
  development records do not replace it.
- Confirm the supported machine and disk profiles, document remaining limits,
  and verify the packaged OF816 boot XEX, system disk, ROM and notices together.

## Follow-on capabilities

These are possible next milestones, without a delivery order:

- Filesystem writing, beginning with a separate SpartaDOS milestone. Current
  [disk support](reference/dos.md) is read-only.
- A RAM filesystem and broader volume assignments beyond the implemented
  [SYS: alias](reference/sys-volume.md).
- Longer shell pipelines, scripts and background execution beyond the current
  [two-command foreground pipeline](guides/shell.md).
- Broader C bindings and more Amiga examples beyond the
  [standalone Calypsi binding](guides/calypsi-c.md).
- Physical pointer support, AES and desktop integration beyond the implemented
  [minimal hosted VDI subset](reference/gem-vdi.md) and [keyboard input](reference/input.md).
  The [optional interactive demo](guides/gem-vdi.md) now provides keyboard controls,
  console handoff and bounded redraws during physical I/O. The completed
  [I0–I7 plan](plans/gem4xe/input-and-events-implementation-plan.md) records the
  cursor/injected-event boundary. The proposed
  [physical mouse design](plans/gem4xe/physical-mouse-design.md) targets the
  configured ST mouse on port 1, with shared SIO timing and reusable capture
  feeding the existing cursor and controls. Shared timing and reusable ST capture
  now pass M0–M4 development checks, including GUI controls; timing/failure
  acceptance and the artifact refresh remain. Its
  [M0–M6 implementation plan](plans/gem4xe/physical-mouse-implementation-plan.md)
  separates timing migration, input capture, GUI integration and artifact checks.
- Priority scheduling and larger Task capacities. Current priorities are stored
  but selection is FIFO; capacities beyond the supported four/eight layouts need
  separate memory budgeting and qualification.
- Additional platforms and physical-device qualification. Emulator evidence
  applies only to its recorded configuration.

## Deferred API and compiler work

- **Narrow DOS scalar types.** Review `Open` modes and Boolean return widths
  together across DOS, COMMAND and providers. Retain 32-bit positions and counts
  where needed. This is an ABI migration requiring rebuilt callers; expected
  savings are small and do not imply faster disk transfers.
- **CSTRING API migration.** Move selected text signatures together with their
  checked provider declarations. Keep counted binary I/O. The literal type and
  allocation-free library are already implemented.
- **Near/far data pointers.** Define bank context, conversions and signature
  identity in actionc before migrating internal objects. Public pointers remain
  far for now. Near callable pointers need their own calling-convention design.
- **Dynamic libraries and general resource tracking.** Resident command
  providers, explicit memory release and current Process cleanup remain the
  supported scope; general discovery/unloading and automatic raw-Task memory
  reclamation need separate designs.

Implementation plans, including completed ones, are indexed under
[plans](plans/README.md). Completed console scrolling, `Main` return values,
CSTRING, command arguments and SYS work belong in their current documentation
and [history](history/README.md), rather than the open backlog.
