# Exec816 documentation

Start with the [demo guide](guides/demo.md) to run Exec816, or the
[architecture overview](architecture/overview.md) to understand it.

| I want to… | Start here |
| --- | --- |
| Install the ZIP and use its shell | [Installation](../README.md#installation), [demo](guides/demo.md), [shell](guides/shell.md) |
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
