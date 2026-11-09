/* SPDX-License-Identifier: MIT
 * Synchronous caller-context phases. No callback escapes this invocation.
 */
#include "internal.h"

LONG ExecCRuntimePhase(struct ExecCRuntimeState *state,struct ExecCRuntimeCall *call,
                      const struct ExecCRuntimeOps *ops)
{
    switch (call->phase) {
    case EXEC_CRT_INIT:
        if (call->version!=EXEC_CRT_VERSION ||
            (state->state!=EXEC_CRT_STATE_EMPTY && state->state!=EXEC_CRT_STATE_RELEASED)) return 0;
        state->state=EXEC_CRT_STATE_INITIALIZING;
        call->primary=20;call->secondary=0;
        if (!ops->initialize(call)) return 0;
        state->state=EXEC_CRT_STATE_READY;
        return 1;
    case EXEC_CRT_RUN:
        if (state->state!=EXEC_CRT_STATE_READY) return 0;
        state->state=EXEC_CRT_STATE_RUNNING;
        call->primary=ops->run(call);
        state->state=EXEC_CRT_STATE_RETURNED;
        return 1;
    case EXEC_CRT_FINISH:
        if (state->state!=EXEC_CRT_STATE_INITIALIZING &&
            state->state!=EXEC_CRT_STATE_READY && state->state!=EXEC_CRT_STATE_RETURNED) return 0;
        ops->finish(call);
        state->state=EXEC_CRT_STATE_FINISHED;
        return 1;
    case EXEC_CRT_RELEASE:
        if (state->state!=EXEC_CRT_STATE_FINISHED) return 0;
        ops->release(call);
        state->state=EXEC_CRT_STATE_RELEASED;
        return 1;
    default:return 0;
    }
}
