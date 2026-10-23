/* SPDX-License-Identifier: MIT */
#ifndef QED_SAVE_H
#define QED_SAVE_H
#include "qed-stage.h"
enum { QED_SAVE_PENDING,QED_SAVE_SAVED,QED_SAVE_CANCELLED,QED_SAVE_FAILED,QED_SAVE_UNCERTAIN };
enum { QED_SAVE_PREPARED,QED_SAVE_STAGING,QED_SAVE_OLDER_BACKUP,QED_SAVE_OLD_TARGET,
       QED_SAVE_PUBLISH,QED_SAVE_CLEANUP,QED_SAVE_RESTORE_TARGET,QED_SAVE_RESTORE_BACKUP,
       QED_SAVE_CLEAN_STAGE,QED_SAVE_DONE };
struct QedSave {
    struct QedPath target;struct QedStage stage;
    char backup[256],escrow[256];struct FileInfoBlock info;
    LONG cause,cleanup,target_flags,backup_flags;
    unsigned short phase,result,cause_phase,cleanup_phase,attempts;
    unsigned short target_exists,backup_exists,moved_target,moved_backup,published,critical,cancel;
};
struct QedSave *QedSavePrepare(const char *path);
int QedSaveStart(struct QedSave *save,RINGP ring,int replace,int recycle_backup);
short QedSavePoll(struct QedSave *save);
int QedSaveCanCancel(const struct QedSave *save);
void QedSaveCancel(struct QedSave *save);
void QedSaveDispose(struct QedSave *save);
#endif
