# Resident shell report output

[History index](README.md) · [Development evidence](../development/shell-report-output.json)

TASKS and MOUNT now assemble each listing row before writing it. DEVICES, JOBS,
MEM, ALIAS, PATH, ECHO, bare CD, the HELP heading and IDE/mount diagnostics use
the same approach. The existing 128-byte shell draw buffer is reused; rows that
exceed it stream in bounded chunks. No text is truncated and no new buffer is
allocated. DIR already writes complete rows, TYPE already streams chunks, and
CLS and the prompt already use one Write each.

The snapshot routines still collect their records before output and release
Forbid before a Write can block. Every flush calls the existing ShellWrite,
which retains foreground BREAK, short-write handling and fatal-console policy.
The diagnostic wrappers retain their existing saved-IoErr handling. These changes
add no kernel operation, device buffering or filesystem I/O.

## Measured command latency

These are medians of three invocations in the pinned standalone VBXE IDE demo:
PAL at 8x, 4 MiB, eight Task slots, four live Tasks and three mounted filesystems.
The packaged OF816 image includes five-second autoboot. Each invocation begins
at an idle prompt with an unmeasured cooked-line prefill and a physical Return.
Passive PC markers measure the complete command and DOS Writes, excluding the
next prompt; elapsed times include interrupts and scheduling.

| Console output | Before ms | After ms | Writes before | Writes after | Kernel calls before | Kernel calls after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TASKS | 611 | 112 | 38 | 5 | 1,136 | 179 |
| MOUNT | 500 | 122 | 30 | 4 | 918 | 184 |
| DEVICES | 188 | 91 | 11 | 4 | 354 | 154 |
| MEM | 225 | 100 | 12 | 4 | 393 | 155 |

TASKS with NIL output falls from 118 to 53 ms; MOUNT from 103 to 52 ms.
Their snapshots remain about 2.18 and 1.13 ms. All measured report commands
perform zero executable loads and zero ATA commands. Empty JOBS already uses
one Write and remains about 36 ms. Running/stopping jobs now use one Write
instead of three; a finished job uses one instead of eight, verified separately
through emitted formatting cases.

The final session covers three console and three NIL invocations each of TASKS,
MOUNT, DEVICES, JOBS, MEM, ALIAS, PATH and ECHO. Independent bitmap pixels,
per-command resource ledgers, unchanged media, stack/domain guards and EXIT
restoration pass. These are development measurements for the pinned standalone
emulator configuration; GUI presentation and physical-hardware timing are
separate scopes.

## Bounds and memory

The optimized native formatter fixture passes 29 exact-byte and Write-count
cases. Controlled inspection inputs cover unnamed and 23-byte task names,
one/two-digit slots, all task labels, unknown device states, filesystem formats,
access modes, 31-byte mount names, offline errors, mount admission failures,
retained IDE status, hexadecimal registers and APT partitions. Job identities
cover MAXLONGCARD, and job results cover MINLONGINT/MAXLONGINT. Maximum alias,
PATH and ECHO rows, empty rows, 127/128/255-byte boundaries, draw neighbours and
snapshot-storage guards are checked. Its private capture/snapshot controls are
not latency evidence. The actual console and NIL path is exercised by the
packaged measurement.

The focused optimized PATH policy fixture also passes 118 checks, and all 457
host tests pass. The changed formatter is exercised optimized; this change does
not alter compiler or public ABI behavior. Full release qualification is
separate from these development checks.

The matched IDE kernel adds **3,139 executable bytes**. Its existing 6,400-byte
upper image-data capacity, ShellState header, draw/scratch/transfer capacities,
Task stacks and direct pages are unchanged. Reserved bank-zero deltas, including
guards, alignment and unused capacity, are **0 fixed, 0 per public Task and
0 private idle bytes**. No new heap allocation is introduced by report output.
The fixture's capture/oracle capacity is test-only upper storage.

Reproduce the focused checks and packaged timings with:

```sh
python3 tools/test_shell_reports.py --output build/development/shell-reports-format
python3 tools/measure_shell_reports.py --bundle build/development/shell-report-output/demo --output build/development/shell-reports-timing
```
