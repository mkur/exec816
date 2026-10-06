# AES latency diagnostics

[Guides](README.md) · [Hybrid AES history](../history/aes-hybrid.md) ·
[HY4 acceptance](../plans/gem4xe/hybrid-aes-implementation-plan.md)

Use these development probes to separate caller CPU cost, presenter scheduling
delay and changed offered load. They do not replace HY4's continuous workloads,
pixel checks or frozen acceptance limits. Priorities and production code remain
unchanged.

## Caller and presenter timing

Add `--breakdown` to the existing bounded call probe. A loaded desktop image
keeps its original continuous exchange and 100 ms sender delay:

```sh
python3 tools/measure_aes_calls.py \
  --program build/aes-hybrid/hy4/optimized/program \
  --output build/aes-hybrid/diagnostic/caller --frames 100 --breakdown
```

`caller_breakdown` splits charged CPU into context lookup/admission, clock
handling, deadline calculation, alarm submission/retirement, message operations,
device I/O, Wait and remaining wrapper/event work. Nested calls charge the
innermost category once. Device calls also have individual inclusive intervals.
Sleeping and other Tasks' execution remain off-CPU time; native interrupt bodies
remain separate. Percentiles of different categories must not be added together.

For the original Control Panel workload, keep its gesture and scanout checks:

```sh
python3 tools/test_widget_panel.py \
  --program build/aes-hybrid/hy4/optimized/program \
  --output build/aes-hybrid/diagnostic/panel \
  --count 10 --feedback --breakdown
```

The same breakdown is available for the original raw-pointer cohort:

```sh
python3 tools/measure_desktop.py \
  --program build/aes-hybrid/hy4/pointer-optimized/program \
  --output build/aes-hybrid/diagnostic/pointer \
  --count 30 --loads two_clients --quiet-app --breakdown
```

`input_breakdown` records capture, first ready publication, first selection and
input consumption. Ready is the existing kernel routine's return after queue
publication; selected is the checked context-restore boundary after D has been
restored. An already-ready or already-selected presenter has zero initial delay
for that phase. Selection does not imply uninterrupted execution: cumulative
runnable off-CPU time includes later preemptions. Blocked off-CPU, charged CPU
and native interrupt time complete the accounting. The presenter's observed
signal waits determine blocked state; this is not a general profiler for Tasks
using every possible sleep mechanism.

These are passive emitted-instruction probes. They check pointer identity,
instruction patterns, complete call returns and CPU accounting. Calypsi local
helper names can collide, so caller sites resolve from emitted sections and
relocated call operands. Missing evidence fails analysis instead of becoming a
zero-duration observation. First selection and CPU charges retain the existing
profiler's conservative treatment of kernel/interrupt return tails.

## Equal offered load

Build the diagnostic with initially parked clients:

```sh
python3 tools/build_aes_desktop.py --output build/aes-hybrid/diagnostic/desktop
```

For each of `idle`, `scroll` and `disk`, run:

```sh
python3 tools/measure_aes_calls.py \
  --program build/aes-hybrid/diagnostic/desktop/program \
  --output build/aes-hybrid/diagnostic/fixed-idle \
  --load idle --frames 400 --offer-period 20 --button-period 25 --breakdown
```

This offers 20 exchanges in 400 PAL frames, with 16 physical button edges on the
Control Panel. Offers follow absolute frame offsets, independent of completion.
The debugger publishes a fixture-owned counter; the root's existing pump signals
the sender. Each offer performs one request/reply and the sender's 100 ms timer.
The receiver uses a 5 s safety timeout between offers. That receiver behavior is
part of this diagnostic, distinct from continuous acceptance's 100 ms polling.

`AESOffered`, `AESStarted` and `AESCompleted` have separate writers. The host
records their values at each offer and at the window boundary. Late admission
or slow completion remains visible as backlog. A missed external frame fails
the run; the producer never silently drops or postpones offers. Outstanding
work drains after the measured window before normal shutdown and ownership
checks. Native disk/scroll progress is counted inside the measured window.
Root DOS/console operations can delay its pump, so offers may reach the sender
in bursts. The started counter distinguishes that admission delay from an
exchange still in progress. Backlog alone is not a measurement of AES service
capacity. The first sender offer also includes any lazy timer-device opening;
individual device-call records identify that setup cost.

Compare matched results:

```sh
python3 tools/compare_aes_diagnostics.py \
  build/aes-hybrid/diagnostic/fixed-idle/results.json \
  build/aes-hybrid/diagnostic/fixed-scroll/results.json \
  build/aes-hybrid/diagnostic/fixed-disk/results.json \
  --output build/aes-hybrid/diagnostic/equal-load.json
```

The comparator requires equal machine settings, duration, relative offer times
and button-edge schedules. It preserves backlog and reports completed calls,
caller costs and input delay. A public call crossing a window boundary is not
included in its complete-call distribution; offer counters still account for
the work. Input consumption uses passive boundaries, with no scanout latency
claim in this fixed-rate probe.

Use `--continuous` in place of `--offer-period` to start the original exchange
on the same parked-client image. This is a useful control, but it is not an
equal-offer comparison. Results from older production implementations need the
same diagnostic workload before an equal-rate performance claim is possible.

The call and panel tools support `--analyze-only` after a clean guest execution.
Keep failed records and their traces in distinct output directories. These
changes reserve **0 additional bank-zero bytes**, fixed or per Task, including
guards and unused capacity. Only the optional test fixture adds upper-RAM
counters; the native desktop and distributed demo are unchanged.
