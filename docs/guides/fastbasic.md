# Writing BASIC programs

[Guide index](README.md) · [Target contract](../reference/fastbasic.md) ·
[Build instructions](../../ports/fastbasic/README.md)

Prepare the pinned SDX originals using the [SDX utilities guide](sdx-utilities.md);
the demo builder expects them in `build/sdx-inputs`. Then build:

```sh
python3 tools/build_demo.py --fastbasic --release-compiler \
  --output build/fastbasic-demo/text
```

Add `--bitmap-shell-only` for the 80×30
graphical console. Both builds include OF816 and the matching system disk, ROM
and WORK: disk. The standard demo keeps its five-second shell/prime autoboot.
Start it with the generated `launch-altirra.command`.

The compiler and SDX tools are in SYS:C; the writable examples are in WORK:.
At the shell:

```text
CD WORK:
EDX HELLO.BAS
FBCI HELLO.BAS HELLO.COM
HELLO
```

In EDX, Ctrl-Z goes to the end of a line. Ctrl-S saves; Return confirms the
filename; Escape exits. Use ATASCII EOL files when editing with EDX. FBCI also
accepts LF, CRLF, CR and a missing final EOL. With no arguments it prompts for
source and output names. Quote filenames containing spaces. Each argument is
limited to 255 bytes; file paths are limited to 254.

FBCI and FBC compile on the Atari and write new Exec-loadable files. You can use an
optional `.COM` suffix when launching it. Literal names take priority, so a
HELLO.COM in the current directory precedes the native HELLO in C:. `C:HELLO`
continues to run that native example. A parse error reports line and column;
the shell remains usable. Failed writes may leave an incomplete output file.

`INPUT.BAS` demonstrates cooked line input and single-key GET. Compile BUSY.BAS
to try BREAK on a loop with no I/O. Redirection, including `HELLO >WORK:OUT.TXT`,
uses ordinary Process streams. Output files retain ATASCII `$9B` line endings.
Keep a backup of WORK:; the supplied disk is disposable.

For floating point, use FBC and the `%` variable suffix:

```text
EDX CALC.BAS
FBC CALC.BAS CALC.COM
CALC
```

The supplied CALC prints 3.75, 9 and 1. Compile DECIMAL.BAS with FBC to try
decimal INPUT. Bare FBC prompts for source/output names, like FBCI. The smaller
FBCI compiler accepts integer/string programs; FBC adds six-byte Atari numbers,
arrays, conversions and math functions. Both use the same console/file backend.
Rebuild older `$4701` executables; the current target identity is `$4702`.

The integrated IDE remains a follow-on. Hardware-dependent PEEK/POKE,
Atari graphics/sound and external USR routines are outside this target.
See the target contract for KEY(), timing and memory differences.
