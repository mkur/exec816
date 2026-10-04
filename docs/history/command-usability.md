# Command usability

[History](README.md) · [Shell guide](../guides/shell.md) ·
[Implementation plan](../plans/command-usability-implementation-plan.md)

U1–U6 are complete at the development tier. Each shell owns a bounded PATH,
initially SYS: after implicit current-directory lookup. The exact public loader
is unchanged. Shared Fault/PrintFault services explain DOS and executable errors,
and all ten supplied commands use ReadArgsOrHelp. Help uses the foreground
console without consuming Input or writing data Output. Shell diagnostics name
the selected failing stage after stream restoration and preserve its results.

DOS ABI revision 4 and program ABI version 8 publish the new services. Rebuild
the resident system and commands together. The provider manifest grows from
1,111 to 1,218 bytes for 36 providers, inside the unchanged 1,664-byte reservation.
The pinned compiler is used without an override; no compiler or emulator change
was required.

PATH adds four 256-byte strings to the shell's upper allocation: 1,288 to 2,312
requested bytes, both already eight-byte aligned. Count/reporting fields use
two reserved header bytes; the header remains 128 bytes. No persistent locks
are retained by PATH. The formatter's 384-byte scratch bound is caller owned;
the shell reuses its existing 512-byte transfer area after command completion.
Formatting uses no heap allocation or mutable global buffer.

Reserved bank-zero change for every slice is **0 fixed bytes and 0 bytes per
Task**, including guards, alignment and unused capacity. The shell/prime demo
needs a 4 KiB upper-RAM data arena, up from 2 KiB, for both applications' globals
and the shared fault strings. The image uses 2,391 bytes, leaving 1,705 bytes
of reserved capacity. The default standalone profile stays 2 KiB. The
first composed-demo build exposed this capacity limit; its explicit profile
change was then built and exercised through OF816. Larger data arenas in controlled tests
hold observers and expected strings only. Code and constant strings grow in
the ordinary resident image; existing Task stacks, direct pages and interrupt
protocols are unchanged. Raw/optimized usability sessions retain at least
266/297 bytes above the checked floor in active public worker stacks; the shell
itself retains 700/754 bytes. These are observed headrooms, not worst-case bounds.

The [evidence record](../development/command-usability.json) identifies source
hashes, pinned compiler/ROM/emulator, per-build stack observations and artifacts.
The selected development checks passed:

| Scope | Executed checks |
| --- | --- |
| Host and generated interfaces | 332 host tests; DOS/program generator checks; documentation links and content. |
| PATH policy | 118 assertions per mode, including canonical mutation, duplicate/capacity bounds, failed cleanup/BREAK rollback, independent shell state, explicit paths and loader-error precedence. |
| Fault services | 181 real-DOS assertions per mode plus 42 controlled-I/O assertions: all messages, signed extremes, exact/short buffers, invalid ranges, partial writes, BREAK and independent buffers; IoErr preserved. |
| Command UI and behavior | 136 cases per mode across all ten commands, including help with zero data reads, unavailable/failed consoles and cleanup. |
| Existing parser and commands | ReadArgs 88, CAT 17 and WC 16 cases per mode. |
| Real shell | Raw/optimized PATH, help, redirection and pipeline sessions; broken local executable, second-load failure, WARN/error precedence, secondary-zero failure, line-overflow header, recovery and physical MORE controls. |
| Shell allocation | Eight checks per mode: stable header, directory-lock overlap, complete resource/heap retirement. |
| Exact packaged demo | Five-second OF816 autoboot with clock wrap; final-second cancellation, Forth/manual handoff with SYS on D2; PATH-loaded HEAD and pipeline, missing-file explanation, help, EXIT, BYE and occupied-IOCB handling. |

The shell sessions compare exact accepted output and retained/physical screens,
check ownership and stack/domain guards, and restore the OS. Controlled fixtures
supply failure cases without claiming real-device fault qualification. The demo
uses the pinned AltirraOS 65816 ROM and paced AltirraSDL configuration. Full release
qualification and physical-hardware validation remain separate gates.

`build/usability/demo/exec816-demo.zip` was built from clean commit `a049eab` with
`tools/build_demo.py`. Its ten members contain only the OF816 boot XEX, matching
system disk with all ten rebuilt commands, pinned ROM, short guide, license
notices and checksums. The archive members and every checksum were verified;
intermediates and reports remain outside the ZIP. The standard five-second boot
still enters the shell/prime demo.

The implementation retains the plan's bounds: four explicit PATH entries,
255-byte executable paths, two pipeline stages, existing argument templates
and read-only filesystems. Multiple-file arguments, wildcards, general assigns,
scripts and additional commands remain follow-on work.
