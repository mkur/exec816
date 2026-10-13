# Loaded Process Task names

[Process contract](../reference/process.md) ·
[Development evidence](../development/process-task-names.json)

The desktop's `(unnamed)` Task came from the shared Process launch path, which
never assigned `tc_Node.ln_Name`. Services named themselves separately. The
loader now retains the executable's leaf filename, and Process preparation
borrows that stable string before making the Task runnable. `DESKTOP.APP`,
`COUNTER.APP` and native disk commands therefore identify themselves in `TASKS`.
Resident entries default to `process`; unnamed memory-loaded Images use
`program`. Names are diagnostic labels and need not be unique.

The existing Image reference protects the name through retirement and collection,
including early owner unload. No extra allocation, reference count, lock, kernel
service or public ABI is introduced. The private Image record gains a 24-byte
name buffer (23 characters and NUL), increasing from 42 to 66 bytes; its rounded
upper-heap allocation grows from 48 to 72 bytes. Fixed, per-Task and idle reserved
bank-zero changes are all **zero**, including guards, alignment and unused
capacity. The Process record remains 128 bytes.

Development checks cover resident setup failures, slot reuse and collection;
disk-loaded C/native execution; overwritten caller path buffers; concurrent
instances, early owner unload and repeat execution. The C child checks its actual
Exec Task name both before and after waiting. The packaged desktop check uses
physical input to inspect `TASKS` with Desktop, Counter and a native background
TICK, then after Counter/TICK retirement. It also runs HELLO and orderly EXIT.
Exact results and guard observations are recorded in the linked evidence.
All three focused runs pass with intact guards. The host suite passes 455 tests
with four existing skips; the packaged run completes with no live Tasks left.

The existing resident lifecycle fixture was updated for the current port-source
layout, deferred console support and the installed pinned paced bridge. These
are test-harness updates. Compiler revision and public contracts are unchanged;
no compiler suite or full hosted/hardware qualification is claimed.

The refreshed OF816 distribution is
`build/task-names/demo/exec816-demo.zip`. It retains the five-second autoboot,
pinned ROM, system/WORK disks, user guide, notices and checksums. Launch with:

```sh
./build/task-names/demo/launch-altirra.command
```
