# Command Main return-value implementation plan

Status: **M1–M3 implemented; development checks passed.** Scope spans **actionc** and **Exec816**. See the
[development record](../development/command-main.json).
Follow the [development testing tier](../contributing/testing.md#development-checks) and
[bank-zero budget](../reference/platform.md#bank-zero-memory-budget).

## Target contract

Commands use the existing Action! function syntax:

```action
LONGINT FUNC Main()
  ; command body
RETURN(COMMAND.RETURN_OK)
```

The return value becomes the Process primary result. Keep `RETURN_OK`,
`RETURN_ERROR` and `RETURN_FAIL` as named constants and preserve arbitrary signed
32-bit results. Every normal command exit returns a value.

Replace public `COMMAND.SetResult` and `PROCESS.SetResult` with normal function
returns. Add `LONGINT FUNC SetIoErr(LONGINT error)` to DOS and COMMAND; it sets
the calling Task's secondary error and returns the previous value. A failed DOS
call already supplies `IoErr()`. Commands only need `SetIoErr` for their own
errors or to restore an error saved across their own cleanup.

After successful Process setup, clear the child's `IoErr()` before entering its
command. On return, save the primary result, then snapshot `IoErr()` immediately,
before finalization can change it. Preserve that secondary value even when the
primary is success. Setup failures record `RETURN_FAIL` and their cause without
calling the command. Waiting, collection and resource retirement keep their
existing semantics.

Resident Process callbacks use the same no-argument `LONGINT` function contract.
The Process Task trampoline and finalizer remain procedures, as do ordinary
`EXEC.AddTask` entries and standalone examples such as AMIGAPRT. Command arguments
now use `GetArgStr()` returning `CSTRING`; the original pointer/length getters
have been removed. See the [Process text-argument contract](../reference/process.md).

## M1 — actionc: selectable function entry and compact profile

Implemented in compiler commit `f3ad9693247b4a918b84e8ec81f0683cb6cc90b9`.
The [compiler patch](../../toolchain/patches/actionc-command-main.patch) applies
on top of the previous `a62ee9e7` pin. Focused checks (20 tests), the NIR snapshot
check, the 51-fixture sweep and all 3,545 compiler tests passed.

1. Add optional `--entry <name>` to `actionc-65816` and its frontend preparation
   API, including `--emit-interfaces`. Resolve a root-module routine through
   semantic identity before NIR lowering and optimization; carry its stable ID
   through the existing entry mechanism. Diagnose missing, ambiguous, external
   or absolute-address selections. Without this option, retain Action!'s current
   last-procedure entry rule. Exec command builds will supply `--entry Main`.
2. Replace the current compact profile with `actionc.o65.compact.v2`. Require a
   no-argument, signed `LONGINT` function entry, including its exact signature,
   existing native return convention and incoming-frame shape. Derive/check the
   signature from compiler callable types, rather than treating any four-byte
   result as equivalent. Reuse existing function and indirect-call lowering.
3. Use descriptor export `__a816_o65_compact_v2` and magic `A8C2`. Keep the same
   eight-byte header and four bytes per import. The profile implies the entry
   type; no per-file entry-signature field is needed. Keep native ABI v1 and the
   shared `__a816_entry_v1` export: the descriptor identifies the new entry
   contract. The rich host proof's version and unrelated detailed o65 profiles
   do not change merely because the compact profile advances.
4. Update compact emission, inspection, reference relocation, CLI diagnostics
   and `docs/MIR65816_O65_PROFILE.md` together. Remove active compact-v1 support;
   retain old-format bytes only as rejection fixtures.

**Checks:** raw/optimized entry selection with helpers after `Main`, retention
through optimization, and a source containing only a function entry. Exercise
direct and indirect `LONGINT` returns including `123456` and `-70000`, with native
stack/register checks. Reject a procedure, arguments, wrong signedness/width,
old descriptor and malformed new descriptor under compact v2. Confirm the exact
metadata size and unchanged default procedure selection.

This changes the shared program-entry contract. actionc's contributor rules
therefore require `cargo test nir_fixtures_match_snapshots`,
`cargo run --bin actionc-nir-sweep -- fixtures/nir` and `cargo test` before the
compiler commit, in addition to focused 65816 regressions. Run these once after
the coherent change, rather than on each edit.

## M2 — Exec816: migrate the complete Process and command contract

Implemented in Exec816 commit `47df5a1` with the M1 compiler pin.
Raw/optimized Process lifetime, CAT/WC,
loader validation and relocation/execution checks passed, as did 214 host tests
and the affected generators. The delivery rule is to keep the previous pin until
this slice is ready; then update `toolchain/actionc.json` and any reproducible
compiler patch/provenance together with the consumers.

1. Update `abi/program.json`, `abi/process.json`, `abi/dos.json` and their
   generators. Advance the changed contract revisions, replace `SetResult` with
   `SetIoErr` in the command providers, and generate the new declarations and
   signatures. Keep unchanged provider symbols stable. Implement the DOS setter
   using the existing Task-local error slot, with no allocation or new COP call.
2. Change Process command-entry fields, admission records, `Start` and
   `StartForeground` parameters, and the loaded Image entry to
   `LONGINT FUNC POINTER`. Make `ExecuteImage` return the loaded function's
   result. Have the existing `Run` procedure capture both results as specified
   above; keep `Finish` responsible for teardown. Pointer sizes, Process record
   offsets and the 128-byte record remain unchanged.
3. Separate resident Process-entry validation from Task procedure validation.
   The packager must select exact no-argument `LONGINT` signatures from admitted
   application routines, plus `PROCESS.ExecuteImage`; four-byte width alone is
   insufficient. Store their addresses and a count in unused space in the
   existing 128-byte upper-RAM DOS descriptor, with generated bounds and an
   explicit overflow error. Keep the Task entry table procedure-only. Check the
   Process callback against its own list and the trampoline/finalizer against
   the Task list. Preserve rejection of kernel helpers, mid-routine addresses
   and arbitrary loaded entries passed to `AddTask`.
4. Update `O65WIRE`/`O65` validation and host fixture/oracle tools for compact v2.
   Reject old procedure-entry binaries even when they import no `SetResult`.
   Preserve loading, relocation, provider checks and image ownership. Add
   `--entry Main` to both command interface discovery and emission.
5. Migrate HELLO, ECHOARGS, CAT, WC, resident Process callers, loaded fixtures,
   generated command sources and command-test adapters together. Preserve errors
   across `Close` where needed. Ordinary Task fixtures keep procedure entries.
   Update the current Process/program-loading/API documentation; historical
   qualification records retain their original contracts.

**Checks:** host suite and affected generator checks; focused raw/optimized
Process lifetime and o65 execution/validation fixtures. Cover normal and wide
results, initial zero error, setter returning the previous error, independent
child errors, setup failure, and cleanup changing the live error slot without
changing the collected result. Verify Task/Process entry rejection in both
directions. Adapt existing CAT/WC stream tests to collect the returned status.
Keep their error/BREAK assertions and normalize LF/CRLF before fixture rewriting.

Existing lifetime checks must still prove bounded completion, stack/DP guards,
OS restoration and release of owned memory/handles. Reuse these fixtures rather
than adding a second broad lifetime matrix.

## M3 — Exec816: rebuild the play image and check integration

Completed: both physical shell sessions passed, including exact output/screen,
foreground BREAK, recovery, ownership and OS restoration; the optimized session
also passed CAT-to-WC. The refreshed `build/demo/program.xex` and
`build/demo/sdfs.atr` use the clean M1 pin. Their loading smoke passed HELLO,
CAT-to-WC, BREAK during loading, recovery and heap/ownership restoration, on the
pinned paced emulator with 128-byte SpartaDOS media and the Generic 56k profile.
The final host suite passed all 214 tests. Full release qualification was not run.

Against the previous compact-profile builds, HELLO is 991 bytes (was 1,314),
CAT 4,569 (was 4,692), and WC 4,163 (was 4,449). Metadata remains eight bytes plus
four per import. The play image's four resident function entries use 13 bytes
in the existing 128-byte descriptor. Optimized `Process.Run` has an 18-byte fixed
frame and 28-byte local stack peak; `ExecuteImage` uses 14 and 21 bytes. All stack
reservations are unchanged, with guards intact in the executed fixtures.

The development record preserves the initial unpaced timeout and the raw
instrumented pipeline's heap exhaustion; neither attempt is counted as passing.
The successful raw run reuses the same native image and retains every original
serial-session assertion.

Build the resident kernel and all bundled commands from the same new pin and
ABI. Refresh the play image and build provenance using the normal packaging
flow. Do not combine old command files with the new loader.

Use the existing raw/optimized shell integration fixture for successful execution,
arguments/redirection, a failing command and foreground BREAK. Exercise one
CAT-to-WC pipeline in the optimized shell to confirm status collection and slot
reuse. The raw instrumented resident image leaves three heap banks (192 KiB);
the 80 KiB console recorder plus two aligned command allocations exceed that
budget. Raw mode retains the full serial shell checks, including BREAK, cleanup
and slot reuse. Both modes use the paced emulator already used by the pipeline
fixture. Reuse matching
builds/results from M2; do not repeat passing checks without changed inputs.
Record development results and update this plan's status after completion.
Full release qualification and SIO timing matrices remain separate work.

## Size and completion criteria

- Compact metadata stays **8 bytes + 4 bytes per import**. New marker names have
  the same length. Measure complete HELLO file/code size separately, since its
  generated code and import list may change.
- Reserved bank-zero change is **0 fixed bytes and 0 bytes per Task** in every
  slice, including guards/alignment/capacity. Keep existing stack reservations;
  check any change in actual wrapper stack use.
- Process/Image pointer widths and Process record size stay unchanged. The
  resident function list uses already reserved upper RAM; report used bytes and
  verify descriptor bounds instead of adding another reservation.
- Active APIs, commands and fixtures contain no `SetResult`. Both resident and
  loaded Processes return their primary result, and old compact-v1 commands are
  rejected. General DOS scalar narrowing remains a separate backlog item.
