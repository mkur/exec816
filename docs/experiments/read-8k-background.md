# An 8 KiB read with a CPU worker running

Measured 2026-09-26. Keeping a second application Task continuously runnable
adds **10.8 ms (0.14%)** to the read under the existing GENERIC57600 disk
profile. It has almost no effect on elapsed read time in this experiment.

| One 8,192-byte read | Time |
| --- | ---: |
| Original SpartaDOS X 4.50, previous measurement | 7.553584 s |
| Exec, worker stopped before Read | 7.610687 s |
| Exec, worker continuously computing during Read | 7.621472 s |

The two new Exec cases use the **same compiled image**. Both create the worker;
the control lets it exit before Read. A host-supplied input byte selects the
mode before application startup. The original reader without this worker
setup measured 7.623775 s. Small differences between that build and the new
control include changes in the disk's rotational phase at the first request.

The worker has the reader's priority (0) and repeatedly performs 256 iterations
of integer shifts and XORs. It makes no I/O, Yield, Sleep or other kernel calls
inside its work loop. Native preemption provides scheduling. Passive instruction
observations show **1,524 work entries during Read**, with progress during
**all 66 sector transactions**. Entries in the four successive quarters of
Read are 378, 386, 385 and 375. The worker's final computed value also matches
an independent host calculation.

This uses the exact ATR from the [original comparison](read-8k-comparison.md):
720 sectors of 128 bytes, the same 8,192-byte payload, PAL 800XL, 8x 65816,
pinned AltirraOS and emulator, and the nominal 57.6 kbaud SIO profile. Accurate
disk timing is enabled; SIO patching, burst I/O and random delay are disabled.
Only the read call is timed. Loading, Open, worker setup, verification, worker
shutdown and Close remain outside the interval. There is no shell or console
activity during the read. SpartaDOS remains the previously measured foreground
baseline; no additional DOS run or DOS multitasking claim is made here.

## Why the added work barely changes the total

The timing partition shows the additional contention:

| Elapsed-time component within Read | Worker stopped | Worker running |
| --- | ---: | ---: |
| Outside SIO transactions | 1.075 s | 1.706 s |
| Drive ACK-end to Complete-start waiting | 4.798 s | 4.178 s |
| Mean interval between sector transactions | 16.094 ms | 25.394 ms |

The first two rows are disjoint components of Read; the third is a diagnostic
within the first row and must not be added again. Time outside transactions
increases by 630 ms, while peripheral response waiting falls by 619 ms. The
remaining wire/protocol components are almost unchanged. The accurate disk
model largely absorbs the changed request timing. These results show little
end-to-end slowdown on this profile, not zero scheduling cost or a prediction
for a peripheral without mechanical delays.

## Validation and reproduction

Two independent cold boots per mode return all 8,192 bytes correctly and
produce identical read-call timings. A further hardware-only replay per mode,
with CPU observation/profiling disabled, reproduces its data-sector span
exactly. Both modes fetch the same 64 data sectors and two file-map sectors,
without payload retries, at the same observed baud. Media hashes are unchanged.
Native guards, interrupt headroom, worker termination, OS restoration,
heap/bank ownership and released-bus checks pass.

Only this optimized benchmark was built and exercised; the compiler pin and
production code are unchanged. No full qualification matrix or play-image
refresh ran. Reserved bank-zero growth is **0 fixed bytes and 0 per Task**.
The worker occupies an existing slot: 1,024 stack bytes, 32 stack-guard bytes,
and a 512-byte DP reservation including its guards, alignment and unused
capacity—**1,568 already reserved bytes**. The eight-slot memory layout and
total reservation are identical to the original benchmark.

The [record](../development/read-8k-background.json) retains the inputs,
timings, progress observations and validation results. The original comparison's
artifacts under `build/development/read-8k` supply the unchanged disk and DOS
baseline. New artifacts are under `build/development/read-8k-background`.

```sh
python3 tools/measure_read_8k.py --prepare --system exec --background running
python3 tools/measure_read_8k.py --system exec --background stopped
python3 tools/measure_read_8k.py --system exec --background running --hardware-only --repetitions 1
python3 tools/measure_read_8k.py --system exec --background stopped --hardware-only --repetitions 1
```

Omit `--prepare` on subsequent runs to reuse the same hash-checked image.

The [2/4/6-application follow-up](read-8k-scaling.md) extends this workload to
five computing workers, filling the existing eight public Task slots.
