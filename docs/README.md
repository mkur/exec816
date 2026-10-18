# Exec816 documentation

Start with the [GEM desktop guide](gem-desktop-distribution.txt) to run Exec816, or the
[architecture overview](architecture/overview.md) to understand it.

| I want to… | Start here |
| --- | --- |
| Install the ZIP and use its desktop | [Installation](../README.md#installation), [GEM desktop](gem-desktop-distribution.txt), [shell](guides/shell.md) |
| Choose the system drive or cache size | [OF816 boot monitor](guides/boot-monitor.md) |
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
Production guest admission and the remaining P2 gates are still open.
