# Guides

- [FastBasic workbench](fastbasic-workbench.md) · [Bundled quickstart](../basic-workbench-distribution.txt): editor controls and delivery status.

[Documentation home](../README.md)

## Running Exec816

- [FujiNet split-disk boot](fujinet-split-boot.md): XEX on D1, SYS on D2 and
  writable WORK on D8, including CONFIG's OPTION → Boot path.
- [Bootable system ATR](bootable-system-atr.md): one writable D1 disk containing OF816, Exec and system/workspace files.
- [Demo](demo.md): build artifacts, machine setup and a walkthrough.
- [Bitmap console preview](bitmap-console.md): optional 80×30 VBXE shell, setup and measured limits.
- [IDE Plus development setup](ideplus.md): optional APT disk, native ATA driver and writable admission.
- [Shell](shell.md): commands, paths, redirection and pipes.
- [Command toolbox](toolbox.md): comparison, checksums, byte inspection, filtering,
  directory listing and paging.
- [OF816 boot monitor](boot-monitor.md): interrupt autoboot and choose boot settings.

- [Optional interactive GEM/VDI demo](gem-vdi.md): ST mouse and keyboard controls during disk I/O, with VBXE graphics.

## Writing programs

- [FastBasic programs](fastbasic.md): edit with EDX, compile with integer FBCI or floating-point FBC on the Atari and run the result.

- [Disk commands](commands.md): `Main`, arguments, streams and return codes.
- [Tasks](tasks.md): build and run the Task and signal examples.
- [Message passing](messages.md): a small port of an Amiga Exec example.
- [Console example](console-example.md): asynchronous console device I/O.
- [DOS stream example](streams-example.md): standard streams and ownership.
- [Calypsi C](calypsi-c.md): the standalone C binding and its limits.
- [GEM applications](aes-applications.md): AES event loops, startup, retirement, interactive apps and the GEM panel/Files desktop.
- [AES latency diagnostics](aes-latency-diagnostics.md): caller CPU categories,
  presenter scheduling delay and equal offered load alongside HY4 acceptance.

- [One C example on Exec816 and classic Amiga](amiga-c.md): build and run the
  same message exchange on both systems.

- [SDX utilities](sdx-utilities.md): build and use the pinned MD5, ARC and EDX development programs.

For semantics beyond an example, use the [API reference](../reference/README.md).
