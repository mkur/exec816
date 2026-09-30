# Build from source

[Contributor guide](README.md)

Building from source is optional. To run the prebuilt distribution, follow the
[ZIP installation guide](../../README.md#installation).

Run commands from the repository root. The hosted build uses Python 3, Rust/Cargo,
and ca65/ld65 from cc65. It also needs the pinned AltirraSDL bridge and 65816 ROM;
the demo builder verifies their hashes before compiling.

## Pinned inputs

| Input | Source of truth | Default local path |
| --- | --- | --- |
| Action! compiler and native ABI | [actionc.json](../../toolchain/actionc.json) | `build/actionc` |
| Demo emulator and ROM | [altirra-shell-paced.json](../../toolchain/altirra-shell-paced.json) | `build/shell-paced-bridge/AltirraBridgeServer`, `build/firmware/altirraos-816.rom` |
| OF816 | [of816.json](../../toolchain/of816.json) | `build/of816-upstream` |
| Kernel defaults | [kernel.json](../../config/kernel.json) | repository file |
| Default demo mounts | [shell-sdfs.json](../../config/shell-sdfs.json) | repository file |

Prepare the compiler checkout at the recorded revision:

```sh
git clone https://github.com/mkur/actionc.git build/actionc
actionc_revision=$(python3 -c 'import json; print(json.load(open("toolchain/actionc.json"))["revision"])')
git -C build/actionc checkout --detach "$actionc_revision"
```

For an existing checkout, fetch the recorded revision before checking it out.
The builders compile the compiler as needed. Use the exact bridge and ROM from
the platform pin; an arbitrary installed AltirraSDL build does not satisfy that
input check. The emulator is [AltirraSDL](https://github.com/ilmenit/AltirraSDL);
upstream Altirra will not run the current Exec816 build.
See the [platform contract](../reference/platform.md) for the
machine boundary and the pin's provenance for platform inputs.

## Build the demo

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/build_demo.py
```

The build always includes OF816 and produces `build/demo/exec816-demo.zip` with
the boot XEX, system disk and matching ROM. It fetches the pinned OF816 checkout
if absent. Build reports and intermediate files remain outside the ZIP.
See the [demo guide](../guides/demo.md) for machine setup, media alternatives and
the walkthrough, and the [boot monitor guide](../guides/boot-monitor.md) for
repackaging an existing image.

## Build an individual program

For a resident Task example with console support:

```sh
python3 tools/native_program.py --compiler-dir build/actionc --tasks --console --task-capacity 8 --source examples/tasks.act --output build/tasks
```

For a disk-loaded command:

```sh
python3 tools/build_command.py examples/commands/hello.act -o build/commands/HELLO
```

The command build produces an o65 file; it does not install it on a disk image.
See [writing commands](../guides/commands.md). The [C guide](../guides/calypsi-c.md)
has the separate Calypsi prerequisites and build command.

## Reading build results

Use each build's `build.json`, `memory.json` and image/compiler reports to inspect
resolved settings, occupied banks and reservations. The [Task-capacity note](../architecture/task-capacity.md)
explains why payload size and reserved bank-zero size are different quantities.
Record local toolchain overrides with results; they do not change the repository
pin or qualify the pinned system. Choose checks using the
[testing policy](testing.md).
