/* SPDX-License-Identifier: MIT */
#ifndef QED_STAGE_H
#define QED_STAGE_H
#include "global.h"
#include "qed-path.h"
enum { QED_STAGE_PENDING,QED_STAGE_READY,QED_STAGE_CANCELLED,QED_STAGE_FAILED,QED_STAGE_UNCERTAIN };
struct QedStage {
    RINGP ring;const struct QedPath *target;LINEP line;char *buffer;
    char name[256];LONG expected,confirmed,cause,cleanup;
    unsigned short offset,used,sent,separator,attempts,phase,result;
    unsigned short visits,produced,owned,cancel,safe;
    short descriptor;
    unsigned short created,close_done,close_ok,cause_phase,cleanup_phase;
};
int QedStageBegin(struct QedStage *stage,RINGP ring,const struct QedPath *target);
short QedStagePoll(struct QedStage *stage);
void QedStageCancel(struct QedStage *stage);
void QedStageDispose(struct QedStage *stage);
int QedSaveLogicalError(LONG cause);
int QedTemporaryName(const struct QedPath *target,const char *extension,char *name);
#endif
