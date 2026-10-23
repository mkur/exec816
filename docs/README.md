# Exec816 documentation

Start with the [GEM desktop guide](gem-desktop-distribution.txt) to run Exec816, or the
[architecture overview](architecture/overview.md) to understand it.

| I want to… | Start here |
| --- | --- |
| Install the ZIP and use its desktop | [Installation](../README.md#installation), [GEM desktop](gem-desktop-distribution.txt), [shell](guides/shell.md) |
| Choose the system drive or cache size | [OF816 boot monitor](guides/boot-monitor.md) |
| Boot and save on a single FujiNet disk | [Bootable system ATR](guides/bootable-system-atr.md) |
| Boot an XEX with separate FujiNet disks | [Split-disk FujiNet boot](guides/fujinet-split-boot.md) |
| Write a disk command | [Command guide](guides/commands.md) |
| Try Tasks and message passing | [Task examples](guides/tasks.md), [message example](guides/messages.md) |
| Understand which code runs in which Task | [Runtime model](architecture/runtime.md) |
| Understand mounts, files and SIO | [Filesystem architecture](architecture/filesystems.md) |
| Look up an API or machine contract | [Reference index](reference/README.md) |
| Build or change Exec816 | [Contributor guide](contributing/README.md) |

## Documentation by purpose

- [Guides](guides/README.md): how to use and program the current system.
- [Architecture](architecture/README.md): the main parts, ownership and execution.
- [Reference](reference/README.md): supported interfaces, limits and contracts.
- [Contributing](contributing/README.md): building, coding and validation.
- [Roadmap](roadmap.md): remaining work, without the completed milestone log.
- [Plans](plans/README.md): bounded implementation plans, including completed ones.
- [History](history/README.md): earlier designs, implementation reports and measurements.

Current guides and references describe supported behavior. Plans describe intended
work; a plan's presence does not mean it is still pending. Historical documents
and the records in [development](development/), [qualification](qualification/)
and [experiments](experiments/) apply to their recorded revisions and profiles.
They do not qualify a later build automatically.

The [emulation-mode preemption experiment](experiments/emulation-preemption.md)
records a bounded NMI/native-mode round trip for the proposed SDX personality.
The [implementation plan](plans/spartados-personality-implementation-plan.md)
uses private upper banks and audited binary patches, targeting MD5 then ARC.
The [patch infrastructure record](development/sdx-patches.md) covers the first
native identification/patching components and their executable checks.
The [guest runtime slice](development/sdx-runtime.md) adds synthetic guests on
ordinary Tasks, reversible early interrupt routing and pointer IRQ checks.
The remaining P2 qualification gates are still open.

The [native SDX decoder](development/sdx-loader.md) validates and relocates
the pinned module records. P3 adds synthetic command admission, ordinary Process
ownership and guest-slot reuse. The [P4 service subset](development/sdx-services.md)
adds fourteen MD5 imports, owned file handles, inline output and nonlocal traps.
Both slices pass development checks. [M1/M2 MD5](development/sdx-md5.md) add
real hashing, checksum verification, masks/P/H/A attributes, shell launch,
SDFS reads, cancellation and concurrent guests. [A1–A4 ARC](development/sdx-arc.md)
adds exact-overlay loading, listing, extraction, mutation and mixed-use/shell acceptance. These are
development results, not full hosted-system qualification.

The [ELSA X 1.05 compatibility audit](development/sdx-elsax105-audit.json)
records its native SDX dependencies, compact blocks and 16/24-bit fixups,
private stack/direct-page requirements and largest-free-block allocation.
Separate original-SDX/XLOS controls produce exact Atari XEX and SDX relocatable
output. Native Exec execution, repeated launches and the complete instruction
audit remain open; the current MD5/ARC personality does not admit ELSA.

The [EDX compatibility audit](development/sdx-edx-audit.json) inventories its
6502 code, keyboard dispatch and `_RAWCON` display interface. Original-SDX
edit/save and two-launch controls pass on the pinned AltirraOS/VBXE machine.
The [EDX development port](development/sdx-edx.md) adds pinned admission,
public console operations, qualified scan input and a bell patch. See the
[utility guide](guides/sdx-utilities.md) for builds and editor commands.
Development evidence does not qualify the general hosted system.
