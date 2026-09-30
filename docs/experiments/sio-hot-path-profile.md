# Profile after the filesystem/SIO optimization

The [optimization](sio-hot-path-optimization.md) is committed as `aef6fb1`.
The play bundle has been rebuilt at `build/demo/program.xex` with the unchanged
`build/demo/sdfs.atr`. Its compiler pin, ROM, emulator and 128-byte SDFS geometry
are unchanged. The previous bundle is retained at
`build/development/sio-hot-path/previous-play`.

The [record](sio-hot-path-profile.json) identifies the new play image, its
focused loading/BREAK check, and the separate diagnostic image used for
profiling. The play image has no loader observers. The diagnostic image reuses
the optimized build from the preceding measurement, avoiding another compiler
run; its recorded Task, console and platform source inputs match the play
image, and its bounded loader/sector observers are recorded separately.

## What remains between sector requests

With the prime task stopped, the eighteen gaps between HELLO's nineteen data
sector requests average **17.70 ms**, totaling **318.54 ms**. The following
intervals are consecutive and do not overlap:

| Interval | Mean |
| --- | ---: |
| Last serial byte to SIO worker retirement entry | 1.03 ms |
| Retire, publish reply, wake/check/collect in filesystem worker | 4.86 ms |
| Finish cache and reach the consume step | 0.48 ms |
| Consume sector: copy and bookkeeping | 3.35 ms |
| Next filesystem step | 0.23 ms |
| Map lookup and next block preparation | 1.10 ms |
| Transfer entry through cancellation setup to SendIO | 0.22 ms |
| SendIO through SIO worker dequeue to RunRequest | 4.73 ms |
| Validate, prepare, publish active state and start command | 1.69 ms |
| **Total** | **17.70 ms** |

The two request-handoff intervals account for **9.59 ms per gap (54%)**.
The consume interval accounts for **3.35 ms (19%)**. These are elapsed times,
including any interruption or task suspension, not exclusive CPU profiles.

With the prime task running, the mean gap is **20.88 ms**, totaling **375.91 ms**.
The handoff intervals average 10.30 ms together; consume averages 4.38 ms.
This normal demo load is recorded separately from the stopped-task control.

## The previous costs are gone

- Empty Pump calls observed inside the gaps average **10.22 microseconds**.
  The stopped-task run has 48 such calls, totaling **0.49 ms**. None takes
  `Forbid`. The older empty-Pump measurement was about 2.31 ms per call;
  its timing endpoints and call count differ, so compare the aggregate gap
  measurements when assessing total savings.
- There are **zero intermediate DOS submissions** between the first and last
  HELLO data-sector request. The former four 512-byte read boundaries are gone.
- Serial completion reaches the SIO worker in about 1.03 ms, without waiting
  for a complete 20-ms VBI tick.

## Next optimization candidates

1. **Completion checking and collection.** Across the stopped-task gaps the
   filesystem makes 30 CheckIO calls and 18 WaitIO calls. Their mean whole-call
   elapsed times are 1.36 and 1.06 ms respectively. Investigate using the
   existing collection mechanism to test completion and collect once, while
   preserving cancellation waits and exact request ownership.
2. **SIO worker control calls.** Its stop check and request dequeue each run
   24 times across the same gaps, averaging 0.83 and 0.91 ms per call. Evaluate
   combining those repeated controls before changing general Exec dispatch.
3. **Sector copy.** Inspect the emitted consume loop and separate its copy
   instructions from bookkeeping before selecting a copy optimization.
   Reusable compiler/runtime primitives remain actionc's responsibility.

These call durations overlap the interval table and can overlap one another.
In particular, publishing a reply can suspend the SIO worker while the
filesystem runs: a long Control call interval is not all CPU spent in Control.
Wait intervals also include time suspended for I/O. They must not be summed
as independent costs or quoted as instruction execution times.

## Trace method and validation

The updated tracer detects DOS submissions rather than assuming a boundary
every four sectors. It observes Pump call-site entry and return, including
the new unguarded empty path. Native call intervals pair by call site and the
caller's direct-page domain, so task switches cannot pair another task's return.
Incomplete calls at the profiling window's edges are excluded.

Both stopped and active runs use passive instruction-boundary markers on the
unchanged diagnostic executable. Against the preceding runs without CPU
markers, each retains exactly the same relative loader phase ticks, transfer
counts and all eighteen hardware gap lengths. Trace timestamps use the PAL
master clock of 1,773,447.5 Hz; loader phase ticks have 20-ms resolution.
Generic57600 rotational timing remains enabled, so earlier requests can change
rotational waits. This is workload evidence, not a general throughput bound.

The new uninstrumented play image passes `--loading-smoke`: HELLO, CAT through
WC, physical BREAK during command loading, subsequent HELLO, warmed heap and
ownership restoration, and EXIT with OS state restoration. Host validation
passes 196 tests, including task-domain pairing and incomplete-window cases
for the updated trace reader. This is development-tier validation; no full
release matrix or compiler requalification was run.

```sh
python3 tools/build_demo.py --output build/demo
python3 tools/test_demo.py --bundle build/demo --loading-smoke
python3 tools/trace_command_io.py \
  --output build/development/sio-hot-path/profile
python3 tools/trace_command_io.py --prime-worker active \
  --output build/development/sio-hot-path/profile-active
```

The tracer defaults to the retained optimized diagnostic bundle. If rebuilding
that bundle is necessary, use the `measure_command_loading.py --prepare`
command in the [optimization record](sio-hot-path-optimization.md).
Reserved bank-zero change: **0 fixed bytes, 0 per Task**. The rebuilt play
image's complete memory reservations match the preceding play bundle.
