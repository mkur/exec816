# Resident DOS console streams example

[dos-streams.act](../../examples/dos-streams.act) opens RAW: and selects the same
owned handle as Input and Output. It echoes bytes using ordinary DOS Read/Write.
A second application Task reads `D1:LARGE.BIN` with one 70,003-byte Read and
prints `DISK DONE` through its own RAW handle. Both clients share the existing
console endpoint; there is no additional stream worker or executable loader.

Build with the [compiler pin](../../toolchain/actionc.json) and run with the
[console machine/ROM pin](../../toolchain/altirra-console.json):

```sh
mkdir -p build/dos-streams-example
cat > build/dos-streams-example/mounts.json <<'JSON'
{"mounts":[{"alias":"D1","unit":49,"sectors":2000,"sector_bytes":256,"profile":1}]}
JSON
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
  python3 tools/native_program.py --compiler-dir build/actionc \
  --tasks --task-capacity 8 --console --source examples/dos-streams.act \
  --dos-mounts build/dos-streams-example/mounts.json \
  --output build/dos-streams-example
```

Add `--no-opt` for raw compiler output. Mount the original
[256-byte MyDOS fixture](../../tests/fixtures/mydos/mydos450-256.atr) as D1 and load
`build/dos-streams-example/program.xex`. Use FASTEST125, accurate disk timing,
SIO patch off and burst I/O off. The console requires the pinned GRAPHICS 0
screen at startup.

Type ordinary characters to echo them; no Return is needed. Type `q` to leave.
If the disk read is still active, exit joins that reader before releasing
buffers and handles. The reader can finish and print while the console Task
is blocked on its next Read. Its completion signal does not complete that
Read: another keyboard byte is still required. The existing
[asynchronous Exec example](console-example.md) keeps its separate multi-event
wait loop.

Before interaction, the example runs a small command twice with temporary file
Input and NIL Output. The command borrows those defaults and retains neither
handle. One invocation copies four bytes; the other deliberately submits a
negative read length. Both restore the saved defaults and close the temporary
handles. `commandError` preserves the causal IoErr before successful selectors
clear it. Closing each Task's owned RAW handle clears its selections, and each
Task calls ReleaseContext explicitly.

RAW supplies translated short reads and byte-stream writes. Echo is performed
by this application; there is no line editing or automatic echo in DOS. Write
completion releases the source buffer for reuse after device consumption;
physical redraw may finish later. This example adds no CON: discipline, shell
parser, o65 loading, stream inheritance or independent windows.

The shared [session](../../examples/dos-streams-session.inc) runs through an emitted
[fixture](../../tests/programs/dos_streams_example.act) with bounded physical-key
checkpoints, full payload verification, independent terminal/screen expectations
and final ownership checks. The fixture types `a` during the disk read, then
withholds `q` until `DISK DONE` is visible while the parent still waits for input.

```sh
python3 tools/test_dos_streams_example.py --case raw --output build/dos-streams-example-raw
python3 tools/test_dos_streams_example.py --case opt --output build/dos-streams-example-opt
```

The standalone [dos-nil.act](../../examples/dos-nil.act) selects a NIL handle for
both defaults, observes EOF on Read and discards a Write. It needs no mount or
console:

```sh
python3 tools/native_program.py --compiler-dir build/actionc \
  --tasks --task-capacity 8 --no-console --source examples/dos-nil.act \
  --output build/dos-nil-example
python3 tools/test_dos_streams_example.py --case opt --nil --output build/dos-nil-check
```

The interactive workload has five live public Tasks: console client, read client,
console worker, filesystem worker and SIO worker. Private idle is additional.
The example allocates an eight-byte input buffer and a 70,003-byte linear read
buffer (70,008 rounded bytes). Each application client uses the existing
80-byte DOS context and 32-byte reply port, one 16-byte RAW handle and one lazy
48-byte transfer request. They share a 104-byte endpoint; temporary file/NIL
handles and filesystem resources are separate. These are upper-RAM allocations;
fixed and per-Task bank-zero reservations do not grow.

The [qualification record](../qualification/dos-streams-example.json) covers both
compiler modes, both examples and the packaged resident entry points. Root stack
use peaks at 354/329 bytes raw/optimized; the reader uses 232/216 of 1,024 bytes,
leaving 536/552 beyond its protected 256-byte interrupt reserve. All guards and
reserves survive. Short checkpoints use 240 host seconds/12,000 guest frames;
full-read completion uses 1,800 seconds/30,000 frames. These hosted checks can
take several minutes and do not qualify physical hardware.
