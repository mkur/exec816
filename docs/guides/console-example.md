# Resident console and MyDOS example

[console.act](../../examples/console.act) links a small interactive client into the
current image. It uses the public Exec device API, separate input/output
requests over one exclusive open, and one persistent file-reading Task. It has
no executable loader or application binary-format dependency.

Use the clean [compiler pin](../../toolchain/actionc.json), the
[console machine pin](../../toolchain/altirra-console.json), and the independently
produced MyDOS ATRs in [the fixture manifest](../../tests/fixtures/mydos/manifest.json).
For the 256-byte fixture, create a mount configuration in the output directory:

```sh
mkdir -p build/console-example
cat > build/console-example/mounts.json <<'JSON'
{"mounts":[{"alias":"D1","unit":49,"sectors":2000,"sector_bytes":256,"profile":1}]}
JSON
python3 tools/native_program.py --compiler-dir build/actionc \
  --tasks --task-capacity 8 --console \
  --source examples/console.act --output build/console-example \
  --dos-mounts build/console-example/mounts.json
```

Load `build/console-example/program.xex` with the pinned ROM and mount
`tests/fixtures/mydos/mydos450-256.atr` as D1. Use the FASTEST125 drive profile,
SIO patch off, burst I/O off and accurate disk timing on. The console needs the
pinned GRAPHICS 0 screen at startup. Add `--no-opt` for raw compiler output.
For the 128-byte fixture, use 720 sectors and `sector_bytes: 128` instead.

At the prompt, type a single command followed by Return:

- `r` sends work to the existing reader Task. It opens `D1:TOOLS/SUB/DATA.BIN`
  and issues exactly one `DOS.Read(..., 70003)`. The supplied file is 777 bytes,
  so the ordinary short read reaches EOF. Change `readPath` in
  [console-session.inc](../../examples/console-session.inc) to `D1:LARGE.BIN` on
  the 256-byte fixture for the full 70,003-byte case used by qualification.
  Input and echo continue while this separate Task waits for DOS/SIO.
- `t` reads and previews up to 259 bytes from `D1:TEXT.TXT`. The example converts
  ATASCII `$9B` to LF itself and displays other nonprinting/high-bit bytes as
  dots. The fixture named TEXT.TXT contains a byte-test pattern, so its preview
  is not prose. DOS returns the original bytes unchanged. This command runs in the
  console client and can wait behind a current filesystem operation.
- `e` attempts to open an absent file and reports the ordinary DOS error.
- `q` waits for any active read, retires the reader, collects/closes the console
  requests and exits. The kernel then retires resident services and restores
  the borrowed OS screen. Completion text is visible before quitting.

Backspace edits the current line using BS-space-BS. The line is limited to 36
characters plus its two-column prompt, so editing never crosses a wrapped row.
Extra printable characters are ignored. Ctrl-C/BREAK clears the current line;
it does not cancel an already-running DOS request. No key repeat or escape
sequence editing is provided. Commands other than the four single letters
simply start another prompt.

The reader is created once and waits on a signal between reads; no Task is
created per request, file or redraw. Before the first file open, three public
Tasks are live (client, console worker, reader). Lazy filesystem/SIO startup
raises that to five. Repeated text opens and ordinary errors retain the same
five Tasks. The private idle context is additional.

The common [session implementation](../../examples/console-session.inc) is also
used by [the emitted fixture](../../tests/programs/native_console_dos.act), which
adds independent payload/cleanup assertions. Reproduce physical-key interaction
with `tools/test_console_dos.py --case raw|opt --sector-size 128|256 --output
build/console-slice7/<case>`. The fixture uses the 777-byte file on 128-byte
media and the 70,003-byte file on 256-byte media, verifies every returned byte,
and exercises editing, text conversion, repeated opens, errors and shutdown.

The [eight-task stress qualification](../history/console-io-implementation.md#slice-8-eight-task-and-serial-timing-qualification)
also runs the same reader while console, allocator, message and signal work
continue. It passes the 125 kbaud serial deadlines. Under heavy scrolling,
observed visible echo can take about one second. The raw reader leaves only
8 bytes above its 256-byte interrupt reserve; extending its call chain requires
fresh stack measurements.

This is an example command loop, not a complete shell. Multiple independent
text windows remain the required follow-up in the
[console plan](../plans/console-io-implementation-plan.md#required-multiwindow-follow-up).
