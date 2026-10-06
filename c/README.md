# C examples and binding

This directory is licensed under the [MIT License](../LICENSE-MIT), including
the public headers, Calypsi shim and examples. Exec816's OS implementation is
GPL-3.0-only; the [application permission](../LICENSING.md#application-permission)
allows independent applications to use its public interfaces under their own
licences. Compiler runtimes retain their own licences.

The initial SDK targets Calypsi 65816 5.18 and the standalone hosted image.
See [the C binding guide](../docs/guides/calypsi-c.md) for build instructions,
supported calls, ABI details and current limits.

- [examples/messages.c](examples/messages.c): a small Amiga-style message exchange.
- [include/proto/exec.h](include/proto/exec.h): the supported classic Exec calls.
- [include/clib/alib_protos.h](include/clib/alib_protos.h): classic CreateTask signature.
- [include/exec816/runtime.h](include/exec816/runtime.h): explicit Yield extension for probes.
- [calypsi/exec.c](calypsi/exec.c) and [gateway.s](calypsi/gateway.s): the shim.
- [include/exec/io.h](include/exec/io.h) and [include/devices/timer.h](include/devices/timer.h): generated device and VBI timer records.
- [calypsi/io.c](calypsi/io.c), [io.s](calypsi/io.s) and [io-bridge.inc](calypsi/io-bridge.inc): caller-context device I/O binding installed by the launcher.
- [include/gem.h](include/gem.h) and [calypsi/aes.c](calypsi/aes.c): the optional [AES application profile](../docs/reference/aes.md), with Task-local attachment in [include/exec816/aes.h](include/exec816/aes.h).

Build with `python3 tools/build_calypsi.py` from the repository root.

Stored ABI pointers use `__far24`, while ordinary C pointers are huge. Use
`ExecSameAddress` from `<exec816/address.h>` when comparing a stored pointer
with a C address; it checks the complete value without narrowing. This avoids
Calypsi 5.18's incorrect bank relocation for implicit comparisons with static
symbols. `IsListEmpty` uses the same helper for embedded upper-bank ports.
It is a C bridge helper, with no kernel call or selector.

Exec messages and input records require even addresses. `AllocMem` provides
suitable alignment; request `__attribute__((aligned(2)))` explicitly for static
records. C record size alone does not guarantee this placement. The private
[GEM application](../ports/gem4xe/interactive/README.md) demonstrates aligned
preallocated messages and a retained retirement handshake.
