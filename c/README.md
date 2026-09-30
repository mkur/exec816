# C examples and binding

The initial SDK targets Calypsi 65816 5.18 and the standalone hosted image.
See [the C binding guide](../docs/guides/calypsi-c.md) for build instructions,
supported calls, ABI details and current limits.

- [examples/messages.c](examples/messages.c): a small Amiga-style message exchange.
- [include/proto/exec.h](include/proto/exec.h): the supported classic Exec calls.
- [include/clib/alib_protos.h](include/clib/alib_protos.h): classic CreateTask signature.
- [include/exec816/runtime.h](include/exec816/runtime.h): explicit Yield extension for probes.
- [calypsi/exec.c](calypsi/exec.c) and [gateway.s](calypsi/gateway.s): the shim.

Build with `python3 tools/build_calypsi.py` from the repository root.
