# Persistent FastBasic interpreter

Status: implemented; see the [development record](../history/fastbasic-session.md).

The workbench keeps its ordinary interpreter Process alive between runs. This
updates the FI design's per-invocation lifetime at the user's request. BASIC
values, arrays, strings, modes, random sequence and open channels survive END,
Stop and recoverable errors. Program → Restart interpreter resets them without
replacing the Process. Changing numeric mode replaces the engine; final Quit
collects it. Source remains FastBasic; direct mode/debugging are separate work.

The public [session contract](../reference/fastbasic.md#persistent-interpreter-sessions)
is authoritative. Use classic Exec request/reply ports and the existing combined
AES/Exec wait. Do not add private kernel coordination. An idle interpreter
retains one existing Task and guest slot; bank-zero reservation delta is zero
fixed, root/kernel, per Task and idle, including guards and unused capacity.

Implement and validate in three executable slices:

1. Extend the generated source ABI with a session channel and RUN/RESET/QUIT
   messages. Keep one Process waiting between requests. Preserve guest data and
   native resources, reset invocation stacks, reply only after publishing results,
   and retire resources only on RESET/QUIT. Keep CLI one-shot operation working.
2. Keep stable symbol slots across edits, with parser/source workspace below a
   fixed data arena. Commit bindings only after successful parsing. Preserve
   repeated DIM of matching type and size; reject type/size changes until RESET.
   Test integer and FP state, source reordering/deletion/addition, arrays/strings,
   modes/files, parse failure, allocation failure, Stop, reset and final collection
   through emitted machine code. Check raw/optimized public C message layouts.
3. Update BASIC.APP to retain its Image/Process, use reply signals for Run and
   expose Restart interpreter. Verify repeated unsaved Run, edits, Stop, reset,
   numeric-mode switching, Check/Build, output close and final/canceled Quit.
   Refresh the OF816 demo and corresponding source archive; record actual
   development checks and resource costs without claiming full qualification.
