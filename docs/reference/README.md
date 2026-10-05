# Reference

[Documentation home](../README.md)

These pages describe the current interfaces. Generated declarations and the
machine-readable files in [abi/](../../abi/) define exact layouts and selectors;
rebuild programs when the ABI changes.

| Area | Contracts |
| --- | --- |
| Exec core | [Tasks](tasks.md), [signals and Wait](signals.md), [lists](lists.md), [memory](memory.md) |
| Communication | [Messages and ports](ports.md), [device I/O and SIO](device-io.md), [timer.device](timer.md), [resident drivers](resident-drivers.md) |
| Input | [Ownership, routes and events](input.md) |
| Files and streams | [DOS](dos.md), [console/NIL streams](streams.md), [pipes](pipes.md), [MyDOS](mydos.md), [SpartaDOS](spartados.md), [filesystem writes](filesystem-writes.md), [SYS:](sys-volume.md), [ASSIGN](assigns.md) |
| Console | [Device](console.md), [instances and windows](console-windows.md), [cooked input](cooked-console.md), [foreground BREAK](foreground-break.md) |
| Graphics | [Desktop client service](desktop.md), [AES applications](aes.md), [AES widgets](widgets.md), [Layers and regions](layers.md), [minimal GEM/VDI hosting](gem-vdi.md) |
| Programs | [Processes](process.md), [loading and imports](program-loading.md), [arguments](command-arguments.md), [C strings](cstrings.md) |
| Filesystem internals | [Block adapter](block-io.md) |
| Machine boundary | [Platform contract](platform.md), [display ownership](display.md) |

For the reason these services are organized this way, read the
[architecture](../architecture/README.md). For runnable examples, use the
[guides](../guides/README.md). Earlier proposals are retained in
[history](../history/README.md).
