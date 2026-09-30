# One C example on Exec816 and classic Amiga

[messages.c](../../c/examples/messages.c) now builds and runs unchanged for both
systems. It creates a worker with CreateTask, sends `(10,20)`, receives `(60,70)`
in the same message, prints through DOS `Output`/`Write`, and releases its
resources. Startup and retirement use
signals. The file has no Exec816 include, platform conditional or Yield call.

The [output binding record](../development/c-dos-output.json) identifies the
exact shared-source hash and successful runs. This demonstrates the small
supported Exec and DOS API subset; it does not establish general Amiga
application compatibility.

## Exec816

Use the [Calypsi build guide](calypsi-c.md), with Calypsi 65816 5.18 and the pinned
Action! compiler:

```sh
python3 tools/test_calypsi.py --mode opt --output build/calypsi/messages
```

The C main routine displays the send and reply values and checks each write's
byte count. The Action! bootstrap supplies the console and waits for Return.
The runner checks output, message identity, cleanup, native guards and OS
restoration.

## Classic Amiga

The checked setup uses vbcc's m68k backend, its normal absolute-global code model
(no A4 small-data dependency), the classic NDK headers and `amiga.lib` CreateTask.
It runs on FS-UAE 3.2.35 emulating a 68000 A500+ with 1 MiB chip RAM, 4 MiB fast
RAM and Kickstart 2.04 rev 37.175. Exact compiler, linker, SDK and ROM hashes live
in [amiga-messages.json](../../toolchain/amiga-messages.json).

The SDK inputs are the [vbcc m68k Amiga target](https://server.owl.de/~frank/vbcc/current/vbcc_target_m68k-amigaos.lha)
and [NDK 3.2 R4](https://www.hyperion-entertainment.com/index.php/downloads?view=download&format=raw&file=126).
Extract both into `build/amiga-sdk` and verify their archive hashes against the
pin. The builder also checks the extracted include/library trees. The vbcc,
vasm, vlink and FS-UAE executables must match the recorded host build; those
binary hashes describe the tested macOS installation. Other host builds need
their own recorded pin and execution evidence.

Supply your local Kickstart ROM; the repository does not redistribute it, the
SDK or the toolchain. No Workbench disk is needed for this small test: FS-UAE
boots the generated host-directory volume and its startup sequence.

```sh
python3 tools/build_amiga_messages.py \
  --target build/amiga-sdk/vbcc_target_m68k-amigaos/targets/m68k-amigaos \
  --ndk build/amiga-sdk/Include_H \
  --output build/amiga-messages \
  --run --rom /path/to/kickstart-2.04.rom \
  --exec-results build/calypsi/messages/results.json
```

Omit `--run` and the ROM argument for a build only. The executable is
`build/amiga-messages/MessageDemo`; the generated FS-UAE configuration and system
volume remain alongside it for manual inspection.

The [Amiga observer](../../c/amiga/observe.c) is outside the shared source. The
build renames only the example's `main` symbol to `ExecMessageMain`, calls it
three times, checks its status and result fields, and writes a closed result
file through AmigaDOS. The harness checks all three lines and the effective
emulator configuration, then stops its own emulator process. `--exec-results`
also checks that the passing Exec816 run used the exact same source hash.

Each line must be `PASS 60,70 same message`. Repeated calls exercise allocation,
Task creation, notification, removal and cleanup on the actual Amiga OS. The
[earlier CreateTask validation](../development/create-task.json) also records a
second cold boot and a repeat of its identical Exec816 image. The output binding
record covers the current source and its checked writes.

These are focused development checks. The shared API adds no bank-zero
reservation on Exec816: fixed and per-Task deltas are both zero.
