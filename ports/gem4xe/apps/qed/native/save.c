/* SPDX-License-Identifier: GPL-3.0-only
 * D/T/B/E publication over public no-replacement namespace operations.
 */
#include "qed-save.h"
#include <stdlib.h>
#include <string.h>
static void finish(struct QedSave *s,short result)
{s->result=result;s->phase=QED_SAVE_DONE;SetIoErr(s->cause);}
void QedSaveDispose(struct QedSave *s)
{
    LONG cause=IoErr();
    if(!s)return;
    QedStageDispose(&s->stage);QedPathRelease(&s->target);free(s);SetIoErr(cause);
}
static int admitted(struct QedSave *s,LONG *flags)
{
    if(s->info.fib_DirEntryType!=ST_FILE){SetIoErr(ERROR_OBJECT_WRONG_TYPE);return 0;}
    *flags=s->info.fib_Protection;
    if(*flags&FIBF_DELETE){SetIoErr(ERROR_DELETE_PROTECTED);return 0;}
    if(*flags&FIBF_WRITE){SetIoErr(ERROR_WRITE_PROTECTED);return 0;}
    return 1;
}
struct QedSave *QedSavePrepare(const char *path)
{
    struct QedSave *s;const char *leaf,*dot;char backup[13];unsigned length;LONG cause;int found;
    s=calloc(1,sizeof(*s));
    if(!s){SetIoErr(ERROR_NO_FREE_STORE);return NULL;}
    s->stage.descriptor=-1;
    if(!QedPathPrepare(&s->target,path,1))goto failed;
    leaf=s->target.name+s->target.prefix;dot=strchr(leaf,'.');
    length=dot ? (unsigned)(dot-leaf):(unsigned)strlen(leaf);
    memcpy(backup,leaf,length);strcpy(backup+length,dot && !strcmp(dot,".BAK") ? ".BKP":".BAK");
    if(!QedPathSibling(&s->target,backup,s->backup))goto failed;
    found=QedPathInfo(s->target.name,&s->info);if(found<0)goto failed;
    s->target_exists=found;
    if(found){
        if(!admitted(s,&s->target_flags))goto failed;
        found=QedPathInfo(s->backup,&s->info);if(found<0)goto failed;
        s->backup_exists=found;
        if(found && !admitted(s,&s->backup_flags))goto failed;
    }
    SetIoErr(0);return s;
failed:
    cause=IoErr();QedSaveDispose(s);SetIoErr(cause);return NULL;
}
int QedSaveStart(struct QedSave *s,RINGP ring,int replace,int recycle_backup)
{
    if(s->phase!=QED_SAVE_PREPARED)return 0;
    if((s->target_exists && !replace) || (s->backup_exists && !recycle_backup)){
        finish(s,QED_SAVE_CANCELLED);return 0;
    }
    QedStageBegin(&s->stage,ring,&s->target);s->phase=QED_SAVE_STAGING;return 1;
}
int QedSaveCanCancel(const struct QedSave *s)
{return s->result==QED_SAVE_PENDING && !s->critical;}
void QedSaveCancel(struct QedSave *s)
{
    if(!QedSaveCanCancel(s))return;
    s->cancel=1;
    if(s->phase==QED_SAVE_PREPARED){finish(s,QED_SAVE_CANCELLED);return;}
    QedStageCancel(&s->stage);s->phase=QED_SAVE_STAGING;
}
static void forward_failed(struct QedSave *s,LONG cause)
{
    if(!s->cause){s->cause=cause;s->cause_phase=s->phase;}
    if(!QedSaveLogicalError(cause)){finish(s,QED_SAVE_UNCERTAIN);return;}
    s->phase=s->moved_target ? QED_SAVE_RESTORE_TARGET:
        (s->moved_backup ? QED_SAVE_RESTORE_BACKUP:QED_SAVE_CLEAN_STAGE);
}
static void recovery_failed(struct QedSave *s,LONG cause)
{
    if(!s->cleanup){s->cleanup=cause;s->cleanup_phase=s->phase;}
    finish(s,QedSaveLogicalError(cause) ? QED_SAVE_FAILED:QED_SAVE_UNCERTAIN);
}
short QedSavePoll(struct QedSave *s)
{
    short result;LONG cause;
    if(s->phase==QED_SAVE_DONE || s->phase==QED_SAVE_PREPARED)return s->result;
    if(s->phase==QED_SAVE_STAGING){
        result=QedStagePoll(&s->stage);
        if(result==QED_STAGE_PENDING)return QED_SAVE_PENDING;
        QedStageDispose(&s->stage);
        if(result!=QED_STAGE_READY){
            s->cause=s->stage.cause;s->cleanup=s->stage.cleanup;
            s->cause_phase=s->cleanup_phase=QED_SAVE_STAGING;
            finish(s,result==QED_STAGE_CANCELLED ? QED_SAVE_CANCELLED:
                (result==QED_STAGE_UNCERTAIN ? QED_SAVE_UNCERTAIN:QED_SAVE_FAILED));
            return s->result;
        }
        s->phase=s->backup_exists ? QED_SAVE_OLDER_BACKUP:
            (s->target_exists ? QED_SAVE_OLD_TARGET:QED_SAVE_PUBLISH);
        return QED_SAVE_PENDING;
    }
    if(s->phase==QED_SAVE_OLDER_BACKUP){
        if(s->attempts>=256){forward_failed(s,ERROR_OBJECT_EXISTS);return s->result;}
        s->attempts++;
        if(!QedTemporaryName(&s->target,"OLD",s->escrow)){forward_failed(s,IoErr());return s->result;}
        if(QedPathEqual(s->escrow,s->target.name))return QED_SAVE_PENDING;
        s->critical=1;
        if(Rename(s->backup,s->escrow)){s->moved_backup=1;s->phase=QED_SAVE_OLD_TARGET;}
        else{cause=IoErr();if(cause!=ERROR_OBJECT_EXISTS)forward_failed(s,cause);}
        return s->result;
    }
    if(s->phase==QED_SAVE_OLD_TARGET){
        s->critical=1;
        if(Rename(s->target.name,s->backup)){s->moved_target=1;s->phase=QED_SAVE_PUBLISH;}
        else forward_failed(s,IoErr());
        return s->result;
    }
    if(s->phase==QED_SAVE_PUBLISH){
        s->critical=1;
        if(Rename(s->stage.name,s->target.name)){
            s->stage.owned=0;s->published=1;
            if(s->moved_backup)s->phase=QED_SAVE_CLEANUP;
            else finish(s,QED_SAVE_SAVED);
        }else forward_failed(s,IoErr());
        return s->result;
    }
    if(s->phase==QED_SAVE_CLEANUP){
        if(DeleteFile(s->escrow)){s->moved_backup=0;finish(s,QED_SAVE_SAVED);}
        else{
            cause=IoErr();s->cause=cause;s->cause_phase=s->phase;
            recovery_failed(s,cause);
        }
        return s->result;
    }
    if(s->phase==QED_SAVE_RESTORE_TARGET){
        if(Rename(s->backup,s->target.name)){s->moved_target=0;
            s->phase=s->moved_backup ? QED_SAVE_RESTORE_BACKUP:QED_SAVE_CLEAN_STAGE;
        }else recovery_failed(s,IoErr());
        return s->result;
    }
    if(s->phase==QED_SAVE_RESTORE_BACKUP){
        if(Rename(s->escrow,s->backup)){s->moved_backup=0;s->phase=QED_SAVE_CLEAN_STAGE;}
        else recovery_failed(s,IoErr());
        return s->result;
    }
    /* Reversals have completed. Delete only our confirmed T, never D/B/E. */
    QedStageCancel(&s->stage);result=QedStagePoll(&s->stage);
    if(result!=QED_STAGE_PENDING){
        if(result!=QED_STAGE_CANCELLED){
            if(!s->cause){s->cause=s->stage.cause;s->cause_phase=s->phase;}
            s->cleanup=s->stage.cleanup ? s->stage.cleanup:s->stage.cause;
            s->cleanup_phase=s->phase;
            finish(s,result==QED_STAGE_UNCERTAIN ? QED_SAVE_UNCERTAIN:QED_SAVE_FAILED);
        }else finish(s,s->cause ? QED_SAVE_FAILED:QED_SAVE_CANCELLED);
    }
    return s->result;
}
