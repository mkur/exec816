# Shell TAB completion

[History](README.md) · [Plan](../plans/shell-completion-implementation-plan.md) ·
[Shell guide](../guides/shell.md#editing-and-break) ·
[DOS contract](../reference/dos.md#resumable-console-editing)

SC1–SC3 deliver case-insensitive prefix completion for builtins, live aliases,
filenames and PATH. Unique names extend in place; directories gain `/` and
ambiguous matches extend only their common prefix. Typed spelling, trailing
text and the logical cursor are preserved. Empty, quoted and wildcard tokens,
and command words after RUN or a pipe, remain unsupported. There is no listing
or cycling. Ordinary programs reading CON retain TAB-as-space.

The native DOS revision is 12. `ConsoleEdit` pauses on TAB with its input lease
and cooked-session ownership intact, while freeing the collected request and
DOS client for filesystem work. No caller buffer is retained. This is an
Exec816 native console extension: application-specific discovery belongs in the
shell, with no recursive DOS callback, kernel operation, worker or driver policy.
The loaded COMMAND and C ABIs remain versions 19 and 20.

Directory discovery uses public Lock/Examine/ExNextBatch/UnLock, with four
records in the existing transfer buffer. It resolves current PATH and ASSIGN
names on each attempt, scans through EOF, and discards the entire result after
an incomplete scan. The candidate buffer and FIB reuse existing shell scratch;
a single additional parent-path buffer survives FIB updates. A failed UnLock
remains reachable for fatal shell cleanup. Job collection does not use these
borrowed buffers or announce output during an edit.

## Development checks

The [machine-readable record](../development/shell-completion.json) contains
source/artifact hashes, compiler and machine pins, actual test selections,
resource comparison, stack observations and timings. The compiler remains the
clean revision in `toolchain/actionc.json`; no compiler override was needed.
These are development checks, not a release matrix or physical Atari qualification.

| Scope | Result |
| --- | --- |
| Host and generated bindings | 498 host tests; DOS, COMMAND and Calypsi generator checks. Two stale host expectations were updated to the already-current C ABI and provider count. |
| Existing cooked editor | 639 optimized operations, including narrow/36/37-column viewports, history allocation failure, discard, EOF and guards. |
| Matching | 48 optimized checks: contexts, folded duplicates/common prefixes, aliases, trailing text, directory separators and atomic 254/255-byte limits. |
| Filesystem | 182 optimized checks on RAM, MyDOS and SpartaDOS; 0/1/4/5/8 entries, late ambiguity, duplicates, PATH/ASSIGN changes, missing/offline paths, partial failure, real enumeration-epoch mutation and retained cleanup after UnLock failure. |
| Native continuation | Small raw ABI probe; 149 optimized owner checks and five peer checks across 21 physical input phases. Covers repeat/resume/cancel, busy rejection, same-Task disk I/O while paused and afterward, inherited CON/RAW readers, EOF, loss, BREAK, echo failure, quarantine and ordinary Read. |
| Physical shell | 21 TAB cases, 273 accepted keys, exact output bytes, retained cells, physical screen/caret and clean EXIT. A separate small check verifies one history-allocation attempt and continued editing. |
| Extracted standard demo | Five-second OF816 autoboot into shell/prime, TAB, completion in recalled input, completed redirection, BREAK during a live directory batch, inherited CAT input, history, 255-byte input, EOF, heap/ownership and OS restoration. |
| Extracted bitmap demo | Unique completion, following text, mid-line caret and horizontal viewport, checked against independent pixels; clean EXIT. This is a separate development artifact. |

The existing shell fixture needed a known clear screen after CON adopted the
loader's OS text, and owner-relative include resolution for the new include.
These changes affect the test harness, not the product's startup display.

## Resource costs

The comparison starts at `606207e0` and uses the same pinned compiler and demo
options. The parent already needs 6,771 static data bytes, exceeding its old
6,400-byte arena. Its isolated measurement build therefore uses the same
7,168-byte arena as the implementation, with that single build-setting override.
No baseline source or compiler workaround was used.

| Resource | Before → after | Delta |
| --- | --- | --- |
| Cooked payload / rounded allocation | 410 / 416 → 414 / 416 bytes | +4 / **0** |
| SC1 shell bookkeeping | +20 payload bytes | +24 rounded bytes |
| SC2 parent path | +256 payload bytes | +256 rounded bytes |
| Total shell allocation | 2,336 → 2,612 payload; 2,336 → 2,616 rounded | +276 payload / **+280 allocated** |
| Standard resident executable bytes | 1,094,355 → 1,106,394 | +12,039 |
| Standard static data used | 6,771 → 6,806 | +35 |
| Configured standard data arena | 6,400 → 7,168 | +768 reserved upper-RAM bytes; 362 unused in final build |
| Compressed native XEX | 352,491 → 356,544 | +4,053 |

SC1, SC2 and the final package add **0 fixed, 0 per-public-Task and 0 idle
reserved bank-zero bytes**, including alignment, guards and unused capacity.
The complete bank-zero budget and all Task/stack/DP pools match the parent.
Some existing runners also report deltas against an older bank-zero-compaction
record; those inherited differences are not caused by completion.
There is no per-candidate allocation. History remains 2,824 optional bytes.

The standard walkthrough touched at most 545 bytes in the shell's 1,536-byte
stack, leaving 735 untouched bytes above its 256-byte interrupt reserve.
All checked native stack/domain guards passed. Watermarks are observations,
not a proof of every possible future call path.

## Timings and remaining limits

Accurate PAL 8× timing, pinned AltirraOS 3.44 and the standard 256-byte SpartaDOS
system disk were used. Physical TAB and passive native instruction markers
measure the extracted distribution with the prime Task running.

| Case | Resolver elapsed | TAB to visible redraw | Directory / batch / candidate counts |
| --- | --- | --- | --- |
| Resident names with empty RAM search directories | 191–200 ms | 301–321 ms | 2 / 2 / 23 |
| Alias with the same empty RAM search | 175–186 ms | 281–301 ms | 2 / 2 / 23 |
| Default current-directory + C: command search, warm | 588–652 ms | 702–782 ms | 2 / 8 / 47 |
| Current-directory filename, warm | 175–187 ms | 301–321 ms | 1 / 2 / 7 |
| Explicit SYS:SELECT filename, cold | 1,569 ms | 1,685 ms | 1 / 4 / 14 |
| Same explicit path, warm | 327 ms | 441 ms | 1 / 4 / 14 |

The cold path performs three SIO transactions, totaling 1,121 ms of wire/device
elapsed time; the warm attempt performs none. Resident-name matching itself
uses 5.6–8.7 ms; replacement rendering uses 0.21–0.58 ms. Physical BREAK during
an active enumeration returns to the prompt in the observed 221 ms interval.
Filesystem calls dominate, including worker CPU, scheduling and waits.

Routine timings include preemption; they are not exclusive CPU measurements.
TAB-to-visible and BREAK samples include physical-key and observation intervals.
Two attempts per case establish these samples, not a tail-latency bound. A
broader release matrix, pure CPU attribution and physical-drive qualification
remain separate work. No unmeasured responsiveness target is claimed.

The primary deliverable is `build/shell-completion/demo/exec816-demo.zip`:
boot XEX, matching system/work disks, pinned ROM, short guide, license notices
and checksums. OF816 build files and notices also remain under the development
bundle's `of816/`. Tests, manifests and intermediates stay outside the ZIP.
