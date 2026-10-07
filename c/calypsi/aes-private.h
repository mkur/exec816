#ifndef EXEC816_AES_PRIVATE_H
#define EXEC816_AES_PRIVATE_H
#include <exec816/aes.h>
#include <gem.h>
BOOL ExecAESObjects(struct ExecAESContext *,AESPB *);

/* A reservation pins the destination until publication.
 * These helpers require an admitted caller; they do not enter GEM recursively. */
struct AESDelivery *ExecAESReserve(struct ExecAESContext *c, WORD id,
                                 struct AESEndpoint **destination);
void ExecAESPublish(struct ExecAESContext *c, struct AESEndpoint *destination,
                    struct AESDelivery *record);
void ExecAESRecycle(struct ExecAESContext *c, struct AESDelivery *record);
BOOL ExecAESMessageReady(struct ExecAESContext *c);
WORD ExecAESSubmit(struct ExecAESContext *c, UWORD operation);
UWORD ExecAESInputArm(struct ExecAESContext *c, UWORD flags);
void ExecAESInputDisarm(struct ExecAESContext *c);
UWORD ExecAESInputRecover(struct ExecAESContext *c, UWORD flags);
UWORD ExecAESInputState(struct ExecAESContext *c, UWORD flags);
UWORD ExecAESInputSelect(struct ExecAESContext *c, UWORD flags);
BOOL ExecAESInputStable(struct ExecAESContext *c, UWORD flags);
UWORD ExecAESInputLevel(struct ExecAESContext *c, UWORD ready);
UWORD ExecAESInputCommitState(struct ExecAESContext *c, UWORD flags);
void ExecAESInputResult(struct ExecAESContext *c, UWORD ready);
BOOL ExecAESEnter(struct ExecAESContext *c);
BOOL ExecAESTimerRead(struct ExecAESContext *c);
BOOL ExecAESTimerDeadline(struct TimerClockRequest *clock, ULONG milliseconds);
BOOL ExecAESTimerCollect(struct ExecAESContext *c, BOOL cancel);
BOOL ExecAESTimerClose(struct ExecAESContext *c);
void ExecAESTimerSend(struct ExecAESContext *c, ULONG high, ULONG low);
WORD ExecAESTimerWait(struct ExecAESContext *c, ULONG milliseconds);
WORD ExecAESEvents(struct ExecAESContext *c, UWORD flags, ULONG milliseconds,
                   WORD *message);
#define AES_ALARM_IDLE 0
#define AES_ALARM_OUTSTANDING 1
#define AES_ALARM_RETIRING 2
#endif
