# Persistent FastBasic interpreter

[History index](README.md) · [Current contract](../reference/fastbasic.md#persistent-interpreter-sessions) ·
[Workbench controls](../guides/fastbasic-workbench.md) · [Implementation plan](../plans/fastbasic-session-plan.md)

BASIC.APP keeps one interpreter Process and its Image between runs. Each Run
submits the current unsaved source to that Process and receives a completion
reply. Variables, copied strings, DIM arrays, random state, DEG/RAD and open
channels survive END, Stop and recoverable errors. Invocation stacks restart
at the source's beginning. Program → Restart interpreter stops an active run
and resets BASIC state inside the same Process. Changing numeric mode replaces
the engine; final Quit shuts it down and collects it. Canceling Quit keeps it.
Shell FB/FBI remain one-shot commands.

The implementation uses ordinary Exec message ports and the existing combined
AES/Exec wait. A waiting session retains one public Task and one shared guest
slot. No kernel operation is added. The version-2 source descriptor, session
channel, request and result follow the generated interpreter schema. The target
is `$4705`; C import ABI 26 adds Wait/PutMsg/GetMsg. Native provider ABI 20 and
AES wire 17 remain unchanged. Rebuild the matching applications and engines.

Stable symbol slots and a separate guest data arena preserve bindings across
source edits. Failed parsing cannot overwrite data or commit new bindings.
Repeated matching DIM preserves contents; changed types or dimensions require
restart. Source/parser/code workspace remains invocation-owned, including raw
addresses of inline DATA. Source and parser tables must fit below `$A000`;
variables occupy 512 bytes there and the bump heap begins at `$A200`.
The technical contract records the resulting source/heap limits.

The C session block explicitly aligns its bootstrap message and pads the next
request header: packed C types alone did not meet Exec's even-address message
contract. Raw/optimized emitted checks cover both actual message addresses.

Automated Check/Build use NIL input and shared output, leaving the retained
interpreter's console keyboard ownership intact.

The expanded Program menu needed 34 objects. The previous 33-object registration
limit rejected the menu and caused the application to withdraw after opening.
The general menu limit is now 34; its native record grows from 380 requested / 384
rounded bytes to 390 / 392. The interpreter extension requests 2,096 bytes,
528 more rounded bytes than FI0–FI7, plus a dynamically copied symbol table.
The editor's resident-session control uses 86 static upper bytes. All fixed,
root/kernel, per-public-Task and idle **reserved bank-zero deltas are zero**,
including guards, alignment and unused capacity.

[Development evidence](../development/fastbasic-session.json) records the exact
emitted tests, raw/optimized C layouts, machine pins, local fault injection,
packaged GUI walkthrough and artifacts. Native cases cover integer/FP values,
strings, arrays, declaration changes, modes, retained files, source-capacity and
runtime allocation failures, parse errors, Stop, reset with open files and final
collection. A request-port startup failure also verifies that collection ends
the session borrow and permits a one-shot retry on the same Image.

These are development checks. They do not establish full hosted-system,
interrupt-placement or physical-hardware qualification. The source archive is
separate from the OF816 boot ZIP and includes the modified donor and Exec source.
