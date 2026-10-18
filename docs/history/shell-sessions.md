# Multiple shell sessions implementation

[History](README.md) · [Design](../plans/shell-sessions-design.md) ·
[Implementation plan](../plans/shell-sessions-implementation-plan.md) ·
[Development record](../development/shell-sessions.json)

Implementation proceeds through SS1–SS8. This record distinguishes the
completed foundation from the session controller and presentation work still
planned. Separate desktop windows remain outside this plan.

## SS1 — explicit shell contexts

All mutable shell state now belongs to a caller-owned `ShellContext`. Shared
resident routines take that context explicitly: parsing, aliases, PATH,
completion, foreground dispatch, scripts, redirection, reporting and background
jobs use the same implementation for every caller. Existing entry programs
each supply one context; there is no shared current-shell pointer or callback
lookup. DOS selectors, errors and owned objects continue to belong to the
calling Task. Formatting scratch is local or borrowed from its shell context;
immutable names and service-owned worker state remain shared.

The private application schema and generator were introduced in SS1 so host
observers can use generated context offsets immediately. Small native probes
check the compiler's layout and nested pointer access in raw and optimized
builds. This changes neither the DOS/COMMAND ABI nor the Exec gateway.

The two-Task fixture uses distinct console instances. While the first Task is
blocked in the real console editor, the second changes its aliases, PATH,
directory and output; then their roles reverse. It checks retained status and
scratch, separate selected streams, exact cleanup and complete heap recovery.
Input injection is confined to this fixture's translated-key boundary; the
ordinary shell read and command routines remain in use.

Development checks include 498 host tests, 13 layout/access checks in each
mode, 39 optimized concurrent checks, 48 completion-matching checks, 182
filesystem-completion checks across RAM/MyDOS/SpartaDOS, and the physical
shell smoke test with exact echo, retained/physical screen and OS restoration.
The updated EXECUTE, append and alias instrumentation also passes native
interface analysis; that is a source check, not runtime coverage of those
complete scenarios. The optimized background-job fixture also passes, including loaded commands,
foreground execution, pipeline admission, cancellation, collection and cleanup.

The context occupies 24 upper-RAM bytes, replacing the same 24 bytes of
separate mutable globals. The shell's 2,612-byte payload, alias allocation,
cooked state and optional history allocations are unchanged. SS1 adds **0
fixed, 0 per-public-Task and 0 idle reserved bank-zero bytes**, including guards,
alignment and unused capacity. Task/stack/DP pools remain unchanged.

Against the retained completion baseline at `cad12ab3`, the matching and
filesystem fixtures each touch eight additional root-stack bytes. The new
concurrent fixture touches 384 bytes on root and 370 bytes on ordinary slot 3,
leaving 896 and 686 bytes above their 256-byte interrupt reserves. Both exceed
the plan's 128-byte headroom gate. These are observations of the exercised
paths, not worst-case stack proofs. All observed native guards pass.

The background-job fixture's old 4 KiB data arena overlaps resident code with
the current shared boot/fault text. Its test-only upper-RAM arena is now 8 KiB,
also accommodating its command strings and capacity Tasks. Production memory
reservations are unchanged. No compiler override is used.

SS1 preserves the existing single-shell product entry. User-facing creation,
selection, cooperative close and desktop tabs arrive in subsequent slices.
These development checks do not qualify the hosted system for release or
physical hardware.
