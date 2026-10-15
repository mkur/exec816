#ifndef EXEC816_AES_PRIVATE_H
#define EXEC816_AES_PRIVATE_H
#include <exec816/aes.h>
#include <gem.h>
extern void EXEC_PTR *ExecAESUpdateEntry;
UWORD EXEC_CALL _AESUpdateCall(struct AESRequest *);
struct AESWindowView *ExecAESFindView(struct ExecAESContext *, WORD);
BOOL ExecAESWindowEpoch(struct ExecAESContext *, WORD, ULONG);
void ExecAESChanged(struct ExecAESContext *,LONG,LONG,LONG,LONG);
void ExecAESResourceFree(struct ExecAESContext *);
BOOL ExecAESResources(struct ExecAESContext *,AESPB *);
/* Private entry points reuse the public caller's established context.
 * These perform their own admission; callers have not set busy yet. */
WORD ExecAESUpdate(struct ExecAESContext *,WORD,WORD);
WORD ExecAESWindowCall(struct ExecAESContext *,UWORD,WORD,WORD,WORD,WORD,WORD,WORD);
WORD ExecAESWindowFind(struct ExecAESContext *c, WORD x, WORD y);
WORD ExecAESWindowDelete(struct ExecAESContext *c, WORD handle);
WORD ExecAESWindowGet(struct ExecAESContext *c, WORD handle, WORD field, WORD *o1, WORD *o2, WORD *o3, WORD *o4);
WORD ExecAESWindowCalc(struct ExecAESContext *c, WORD type, WORD kind, WORD x, WORD y, WORD w, WORD h,
               WORD *ox, WORD *oy, WORD *ow, WORD *oh);
WORD ExecAESDraw(struct ExecAESContext *c, OBJECT *tree,WORD start,WORD depth,WORD x,WORD y,WORD w,WORD h);
WORD ExecAESGrafHandle(struct ExecAESContext *c, WORD *cw,WORD *ch,WORD *bw,WORD *bh);
BOOL ExecAESMenus(struct ExecAESContext *,AESPB *);
BOOL ExecAESObjects(struct ExecAESContext *,AESPB *);
BOOL ExecAESForms(struct ExecAESContext *,AESPB *);
BOOL ExecAESFormFinish(struct ExecAESContext *);
WORD ExecAESFormBegin(struct ExecAESContext *,const GRECT *,const char *);
void ExecAESFormExtent(OBJECT *,GRECT *);
void ExecAESDrawEdit(struct ExecAESContext *,OBJECT *,WORD,WORD,WORD);

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
UWORD ExecAESInputLevel(struct ExecAESContext *c, UWORD ready, UWORD flags);
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
WORD ExecAESPoll(struct ExecAESContext *,UWORD,WORD *);
BOOL ExecAESFileSelector(struct ExecAESContext *,AESPB *);
#define AES_ALARM_IDLE 0
#define AES_ALARM_OUTSTANDING 1
#define AES_ALARM_RETIRING 2
#endif
