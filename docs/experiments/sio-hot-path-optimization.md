# Filesystem/SIO hot-path optimization

This slice removes repeated work identified by the
[HELLO path measurements](sio-path-analysis.md). It leaves the Exec gateway,
scheduler, native serial engine and wire profile unchanged.

## Changes

- `FSWORKER` passes its retained registry and active operation scope to
  `BLOCKWIRE.Transfer`. Sector transfers no longer call `DOSCORE.Control`
  twice and `FindTask(NULL)` to rediscover that context. Standalone block
  callers pass null context and retain exact request collection.
- `FSOPERATION.Pump` receives that registry and returns immediately when its
  cancellation queue appears empty. It retains the guarded queue-processing
  path for pending work.
- `PROGRAMFILE.Load` requests up to 4,096 bytes per DOS read instead of 512.
  It uses the existing whole-file staging allocation. HELLO's 2,359-byte payload
  therefore takes one DOS read instead of five; sector transfers and backend
  cancellation checkpoints remain bounded as before.

Cold operations such as worker admission, signal allocation, device opening and
resource teardown keep their existing implementations. There is no new public
Exec ABI or alternate kernel implementation.

## Same-profile results

The [measurement record](sio-hot-path-optimization.json) compares the same
2,359-byte HELLO on the unchanged 720-sector, 128-byte SDFS disk, using the
pinned PAL 65816 at 8× and GENERIC57600 profile. SIO patches and burst I/O are
off; accurate rotating-media timing remains enabled. Both runs use bounded
loader/sector counters and passive hardware-event tracing.

| Measurement | Before | After |
| --- | ---: | ---: |
| Payload phase, prime task running | 3.44 s | 2.42 s |
| Open through prompt, prime task running | 5.20 s | 4.14 s |
| Mean data-sector request gap, prime task running | 38.85 ms | 20.88 ms |
| Payload phase, prime task stopped | 2.84 s | 2.46 s |
| Open through prompt, prime task stopped | 4.52 s | 4.10 s |
| Mean data-sector request gap, prime task stopped | 34.74 ms | 17.70 ms |

The eighteen gaps total 699.26 → 375.91 ms with the prime task running and
625.32 → 318.54 ms with it stopped. There are still nineteen payload-sector
reads and one file-map read in the payload phase, at unchanged serial bit
timings. Only the DOS packet grouping and software between transfers changed.

Phase timings have 20-ms resolution. These are observations of this workload:
rotational waiting changes when commands start earlier, so elapsed savings
cannot all be attributed to CPU cycles removed. The stopped task remains
stopped throughout its control run; the active task continues making progress.
At this measurement point the shipped `build/demo` bundle was unchanged.
The subsequent [play refresh and profile](sio-hot-path-profile.md) records the
updated uninstrumented image and the remaining per-sector costs.

## Empty-queue protocol

The initial queue-head test is advisory. It does not dereference or retain a
scope pointer. Producers prepend under `Forbid` and post the worker's durable
cancellation signal before releasing that exclusion. Only the filesystem
worker removes entries; IRQ/NMI handlers do not mutate this queue.

When the advisory test sees work, Pump enters `Forbid` and reloads the head
before inspecting or changing a scope. All authority checks, the capacity
bound, queue unlinking and exact reply publication stay under that exclusion.
The existing terminal-reply path also removes any retained cancellation link
before the client can collect and release its scope.

A producer can run between the instructions of the 24-bit advisory read. A
false nonempty result only causes a guarded recheck. A false empty result can
defer work until the next bounded checkpoint; it cannot lose the notification.
Both the worker's idle Wait and its in-flight transfer Wait include the
cancellation signal, and neither clears a newly posted signal before waiting.
The transfer continues collecting its exact request before releasing the
adapter or caller buffer.

## Development checks

Use the existing active-cancellation fixture in raw and optimized modes for
before-send, wire, final-sector, copy, preparing and terminal races. The queued
cancellation fixture covers another caller cancelling while a long peer read
continues, plus claim/reply ordering. These checks retain buffer guards,
committed cursor checks, ownership cleanup and OS restoration.

The shorter demo command below reuses a built image to exercise disk commands,
physical BREAK during loading, prompt recovery and warmed heap/ownership
restoration without running the complete showcase walkthrough:

```sh
python3 tools/test_demo.py \
  --bundle build/development/sio-hot-path/measurement/bundle --loading-smoke
```

Validation passed: 193 host tests; six active-cancellation cases each in raw
and optimized emitted code; the optimized queued-cancellation fixture with a
70,003-byte peer read; the standalone real-SIO block adapter; and the focused
demo loading/BREAK check. CAT and WC also load successfully across the new
4-KiB request boundary. The demo check uses the same diagnostic image as the
timing run, with the prime task running.

Reproduce the timing comparison without rebuilding the external commands:

```sh
EXEC816_LATENCY_TRACE=1 python3 tools/measure_command_loading.py \
  --prepare --bundle build/demo --format sdfs --prime-worker stopped \
  --output build/development/sio-hot-path/measurement
EXEC816_LATENCY_TRACE=1 python3 tools/measure_command_loading.py \
  --bundle build/development/sio-hot-path/measurement/bundle \
  --format sdfs --prime-worker active \
  --output build/development/sio-hot-path/measurement-active
```

Reserved bank-zero change: **0 fixed bytes, 0 per Task**. Existing stacks,
direct-page domains, guards, alignment and reserved capacity are unchanged;
the loader adds no staging allocation. Full release qualification and compiler
qualification are separate from these development checks.
