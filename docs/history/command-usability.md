# Command usability

[History](README.md) · [Shell guide](../guides/shell.md) ·
[Implementation plan](../plans/command-usability-implementation-plan.md)

U1–U5 are implemented; U6 distribution validation is in progress. Each shell
owns a bounded PATH, initially SYS: after implicit current-directory lookup.
The exact public loader is unchanged. Shared Fault/PrintFault services explain
DOS and executable errors, and all ten supplied commands use ReadArgsOrHelp.
Help uses the foreground console without consuming the command's Input or
writing its data Output. Shell diagnostics identify the selected failing stage
after stream restoration and preserve the original results.

DOS ABI revision 4 and program ABI version 8 publish the new services. Rebuild
the resident system and commands together. The provider manifest grows from
1,111 to 1,218 bytes for 36 providers, inside the unchanged 1,664-byte reservation.
The pinned compiler is used without an override.

PATH adds four 256-byte strings to the shell's upper allocation: 1,288 to 2,312
requested bytes, both already eight-byte aligned. Count/reporting fields use
two reserved header bytes; the header remains 128 bytes. No persistent locks
are retained by PATH. The formatter's 384-byte scratch bound is caller owned;
the shell reuses its existing 512-byte transfer area after command completion.
Formatting uses no heap allocation or mutable global buffer.

Reserved bank-zero change for every slice is **0 fixed bytes and 0 bytes per
Task**, including guards, alignment and unused capacity. Production upper-RAM
reservation sizes also stay unchanged. Larger data arenas in controlled tests
hold observers and expected strings only. Code and constant strings grow in
the ordinary resident image; existing Task stacks, direct pages and interrupt
protocols are unchanged.

Development validation uses raw and optimized emitted machine code, the pinned
AltirraOS 65816 ROM and paced AltirraSDL bridge. Full qualification and physical
hardware validation remain separate release gates. The final execution counts,
stack observations, source hashes and distribution will be recorded with U6.

The implementation retains the plan's bounds: four explicit PATH entries,
255-byte executable paths, two pipeline stages, existing argument templates
and read-only filesystems. Multiple-file arguments, wildcards, general assigns,
scripts and additional commands remain follow-on work.
