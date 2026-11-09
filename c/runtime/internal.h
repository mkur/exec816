/* SPDX-License-Identifier: MIT */
#ifndef EXEC_C_RUNTIME_INTERNAL_H
#define EXEC_C_RUNTIME_INTERNAL_H
#include <exec816/c-runtime.h>

struct ExecCRuntimeState { UWORD state; };
struct ExecCRuntimeOps {
    LONG (*initialize)(struct ExecCRuntimeCall *);
    LONG (*run)(struct ExecCRuntimeCall *);
    void (*finish)(struct ExecCRuntimeCall *);
    void (*release)(struct ExecCRuntimeCall *);
};
LONG ExecCRuntimePhase(struct ExecCRuntimeState *,struct ExecCRuntimeCall *,
                      const struct ExecCRuntimeOps *);
#endif
