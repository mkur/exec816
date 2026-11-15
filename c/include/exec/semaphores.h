/* Generated from abi/semaphores.json. */
#ifndef EXEC_SEMAPHORES_H
#define EXEC_SEMAPHORES_H
#include <exec/types.h>
struct SignalSemaphore { UWORD ss_Private[6]; } __attribute__((aligned(2)));
#define EXEC_SEMAPHORE_ALIGNMENT 2
/* Calypsi packs record members; align storage explicitly, including enclosing records. */
void EXEC_CALL InitSemaphore(struct SignalSemaphore *semaphore);
void EXEC_CALL ObtainSemaphore(struct SignalSemaphore *semaphore);
LONG EXEC_CALL AttemptSemaphore(struct SignalSemaphore *semaphore);
void EXEC_CALL ReleaseSemaphore(struct SignalSemaphore *semaphore);
#endif
