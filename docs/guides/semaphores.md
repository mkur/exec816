# Protect a shared resource

[Guides](README.md) · [Semaphore contract](../reference/semaphores.md) ·
[Measured delivery](../history/native-semaphores.md)

Initialize the caller-owned object before publishing it to Tasks. Every
successful Obtain or Attempt needs a Release by that same Task. This Action!
module illustrates the resource side; call Start once before starting users.

```action
MODULE SHAREDCOUNTER
USE EXEC

EXEC.SignalSemaphore lock
CARD value

PUBLIC PROC Start()

  EXEC.InitSemaphore(@lock)

RETURN

PUBLIC PROC Increment()

  EXEC.ObtainSemaphore(@lock)
  value==+1
  EXEC.ReleaseSemaphore(@lock)

RETURN

ENDMODULE
```

Other Tasks can run while Increment owns the resource. A competing Obtain
sleeps and receives ownership in FIFO order. Recursive calls are supported;
balance every level. Keep the object live until ownership and waiting end,
and release ownership before Task exit. No signal bit is needed.

In C, include `<proto/exec.h>` and declare storage explicitly aligned:
`struct SignalSemaphore lock __attribute__((aligned(2)));`.
The four function names and ownership semantics are the same. Rebuild loaded
APPs and their provider together when updating the APP ABI.

The focused reproducible fixtures are [Action!](../../tests/programs/semaphores.act)
and [C](../../tests/programs/semaphores.c). Their runners select individual
cases and can reuse emitted images; see the execution record for exact scope.
