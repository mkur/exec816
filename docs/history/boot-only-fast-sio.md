# Boot-only fast SIO delivery

[Current boot contract](../reference/boot-loading.md#boot-only-sio-reader) ·
[Implementation plan](../plans/boot-only-fast-sio-implementation-plan.md) ·
[Development evidence](../development/boot-only-fast-sio.json)

The split FujiNet XEX now takes ownership through an ordinary guarded INIT
prefix, negotiates divisor 8 and streams the unchanged canonical OF816/native
image. The combined ATR uses the same serial engine and XEX parser with its
SDFS backend. Native Tasks, drivers, mount profiles and compiler ABI are
unchanged. `--boot-sio auto|standard` selects one transport policy;
`--refresh-boot-sio` preserves the frozen canonical image while rebuilding the
reader, matching media and distribution.

## Implementation and lifetime

`abi/boot-sio.json` defines the generated prefix descriptor and finite transport
bounds. `boot-takeover.inc` locates D1's DOS-linked AUTORUN stream and compares
its descriptor without reading PicoBoot's private state. An absent/unrelated
D1 returns to an external XEX loader before negotiation. A selected stream
never returns to the outer loader; failures print a cause and park.

`boot-xex.inc` supplies one parser. `boot-sio.inc` supplies synchronous requests
backed by ROM-dispatched serial RX/TX/completion IRQs. `boot-sio-policy.inc`
handles speed, callbacks and final retirement. Commands transmit from IRQs;
polling output-ready at 57,600 could miss an edge and was rejected during
bring-up. Frame data remains private until checksum admission. Terminal ERROR
and ERROR-plus-data are drained with finite deadlines.

The engine publishes vectors while serial IRQs are disabled and CRITIC is set.
ROM VBI remains active. Known local decoder/OF816-copy callbacks keep fast bus
ownership. Other callbacks receive a confirmed standard bus and restored OS
serial state. Split resumption compares the prefix identity using a separate
buffer, preserving the partial payload sector. Native handoff establishes the
configured divisor 8 and retires every handler before the arena becomes Task
stacks. A standard boot can load through OF816 on a standard-only peripheral,
but cannot enter this native storage profile unless divisor 8 is available.

## Measurements

The final complete matched pair used the same 663,395-byte canonical image,
pinned ROM, optimized native kernel and CONFIG/held-OPTION path:

| Policy | PAL frames to native handoff | Guest seconds |
| --- | ---: | ---: |
| Standard | 20,561 | 411.22 |
| Auto | 7,952 | 159.04 |

This is **2.59× faster** overall, including initial ROM/PicoBoot loading,
negotiation, OF816 and streaming decode. The countdown was 249 frames in both modes. An earlier matched pair measured
411.06/158.78 seconds, with 249/250-frame countdowns.
The frozen records contain the exact canonical hash and size; the table is a
measurement of that pair, rather than a payload-only baud estimate.

The final phase observations were:

| Phase | Standard seconds | Auto seconds |
| --- | ---: | ---: |
| CONFIG/prefix/bootstrap through first native INIT | 19.98 | 14.06 |
| First INIT to OF816 | 14.60 | 5.10 |
| Countdown | 4.98 | 4.98 |
| OF816 return through kernel transfer/decode/handoff | 371.66 | 134.90 |

The last phase improved 2.76×. Negotiations are included in their surrounding
phase; command/rate counters identify them without claiming isolated CPU cost.

Two short, matched 128-page cohorts each measured 1,501 frames standard versus
714 auto (2.10× including prefix overhead). The earlier 512-page cohort measured
4,454 versus 1,731 frames (2.57×). Callback counts, final pattern bytes, endpoint
rates and guards were checked. Phase counters in final package checks distinguish
first native INIT, OF816 entry/countdown/return and native handoff. Transport and
LZ4 decoding interleave; their individual CPU costs are not isolated by those
wall-clock phase measurements.

The NetSIO relay records host and peripheral rates independently and transmits
responses at the peripheral's actual period. NetSIO `$80` reports the peer rate;
it does not force the firmware rate. The firmware's mismatch corruption XORs
low baud bytes, which are both zero for 19,200 and 57,600. The relay therefore
corrupts mismatched command checksums explicitly, allowing the real firmware's
two-bad-frame speed recovery to execute. Deliberate mismatches must fail before
recovery succeeds. The relay waits for the asynchronous rate event after `$3F`;
this host synchronization is not evidence about physical UART turnaround.

## Executed development checks

Host packaging/schema tests and focused emitted checks cover the shared parser,
large fragmented/map-crossing files, direct XEX launch, malformed metadata,
truncated/cyclic chains, reader overlap, BREAK, partial/missing data, NAK,
terminal/data ERROR, checksums, supported/disabled/unsupported speed and lost
negotiation replies. Separate VBI checkpoints interrupt all four descriptor/
vector ownership transitions. A post-OF816 checksum fault stops before native
entry. The evidence records each result and exact fixture inputs.

Split package checks boot through real CONFIG with OPTION held, compare all
1,745,490 initialized/zero-fill bytes, run HELLO/FastBasic, save source/text/
preferences on D8, reboot, reload and EXIT. The combined ATR save/reboot checks
compare its own native image, audit saved bytes, and verify the protected boot
files, locator and boot sectors. Earlier historical evidence is preserved. The separate
[corresponding-source check](../development/boot-only-fast-sio-source.json)
rebuilt FB.COM, FBI.COM, FBCI.COM, FBC.COM, BASIC.APP and HELLO.COM offline
and matched all six products byte for byte.

These are development checks through actual FujiNet-PC firmware/media and
cycle-paced raw SIO on pinned AltirraSDL. Host response waits pause emulation;
physical FujiNet/accelerator UART timing and a release qualification matrix
remain unclaimed.

## Memory

The split loading union grows from 40,336 to **48,528 bytes**: the complete
**8,192-byte** reader arena includes two 16-byte guards, buffers, state,
alignment and unused capacity. It borrows these idle public Task stack pools:

| Slot | Reserved bytes borrowed, including intersecting guards |
| --- | ---: |
| 3 | 512 |
| 4 | 1,344 |
| 5 | 1,344 |
| 6 | 2,592 |
| 7 | 2,400 |

The reader uses **3,344 bytes** including both guards and assembly alignment;
4,848 reserved bytes remain unused. The generated record gives its input hashes. The ATR already reserves
this arena, so sharing the engine adds **zero further loading bytes** there.
Initialization remains 57,056 bytes and runtime 55,008. Reserved bank-zero
changes are **0 fixed, 0 root, 0 kernel, 0 per-public-Task and 0 idle bytes**.
No bank-$01 scratch, new Task, enlarged pool or public kernel operation is added.
