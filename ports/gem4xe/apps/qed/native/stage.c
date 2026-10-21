/* SPDX-License-Identifier: GPL-3.0-only
 * A closed exclusive sibling is staging readiness, never a Saved result.
 */
#include "qed-stage.h"
#include "qed-files.h"
#include "memory.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>
enum { COUNT,CREATE,WRITE,CLOSE,CLEAN,DONE,READY };
static ULONG sequence;
/* Known logical failures leave native mutation state usable. Unknown causes
 * (including transport errors and terminal Close failures) retain recovery. */
int QedSaveLogicalError(LONG cause)
{
    switch(cause){
    case ERROR_NO_FREE_STORE:case ERROR_OBJECT_IN_USE:case ERROR_OBJECT_EXISTS:
    case ERROR_OBJECT_NOT_FOUND:case ERROR_DIR_NOT_FOUND:case ERROR_BAD_ARGUMENTS:
    case ERROR_INVALID_COMPONENT_NAME:case ERROR_OBJECT_WRONG_TYPE:
    case ERROR_DISK_WRITE_PROTECTED:case ERROR_DELETE_PROTECTED:
    case ERROR_WRITE_PROTECTED:case ERROR_DISK_FULL:case ERROR_DIR_NOT_EMPTY:
    case ERROR_LINE_TOO_LONG:case ERROR_RENAME_ACROSS_DEVICES:return 1;
    default:return 0;
    }
}
int QedTemporaryName(const struct QedPath *target,const char *extension,char *name)
{
    char leaf[13];unsigned i;ULONG value;
    value=sequence=(sequence+1)&0x0fffffffUL;leaf[0]='Q';
    for(i=0;i<7;i++){leaf[7-i]="0123456789ABCDEF"[(unsigned)(value&15)];value>>=4;}
    leaf[8]='.';memcpy(leaf+9,extension,3);leaf[12]=0;
    return QedPathSibling(target,leaf,name);
}
static void fail(struct QedStage *s,LONG cause,int safe)
{
    if(!s->cause)s->cause=cause ? cause:ERROR_SEEK_ERROR;
    s->safe=safe;s->result=safe ? QED_STAGE_FAILED:QED_STAGE_UNCERTAIN;s->phase=CLEAN;
}
static void cursor(struct QedStage *s)
{s->line=FIRST(s->ring);s->offset=s->separator=0;}
int QedStageBegin(struct QedStage *s,RINGP ring,const struct QedPath *target)
{
    memset(s,0,sizeof(*s));s->descriptor=-1;s->ring=ring;s->target=target;s->safe=1;
    if(ring->ending!=lns_unix && ring->ending!=lns_tos){fail(s,ERROR_BAD_ARGUMENTS,1);return 0;}
    s->buffer=malloc(4096);
    if(!s->buffer){fail(s,ERROR_NO_FREE_STORE,1);return 0;}
    cursor(s);return 1;
}
/* Visit at most 256 boundaries and count/copy at most 4096 bytes per call.
 * Offset and pending CRLF suffix survive a budget boundary. */
static int fill(struct QedStage *s,int counting)
{
    unsigned available=4096,take;LONG bytes;
    s->visits=s->produced=0;
    while(!IS_TAIL(s->line) && available && s->visits<256){
        take=(unsigned)(s->line->len-s->offset);
        if(take>available)take=available;
        if(take){
            if(counting){
                bytes=(LONG)take;
                if(s->expected>LONG_MAX-bytes){fail(s,ERROR_BAD_NUMBER,1);return 0;}
                s->expected+=bytes;
            }else memcpy(s->buffer+s->produced,TEXT(s->line)+s->offset,take);
            s->produced+=take;s->offset+=take;available-=take;
        }
        if(s->offset!=(unsigned)s->line->len)break;
        if(IS_TAIL(s->line->next)){s->line=s->line->next;break;}
        if(!s->separator)s->separator=s->ring->ending==lns_tos ? 2:1;
        while(s->separator && available){
            if(counting){
                if(s->expected==LONG_MAX){fail(s,ERROR_BAD_NUMBER,1);return 0;}
                s->expected++;
            }else s->buffer[s->produced]=s->separator==2 ? 13:10;
            s->separator--;s->produced++;available--;
        }
        if(!s->separator){s->line=s->line->next;s->offset=0;s->visits++;}
    }
    return 1;
}
void QedStageCancel(struct QedStage *s){s->cancel=1;}
void QedStageDispose(struct QedStage *s)
{free(s->buffer);s->buffer=NULL;}
short QedStagePoll(struct QedStage *s)
{
    LONG count,cause,fd,requested;short closing;
    if(s->phase==DONE)return s->result;
    if(s->cancel && s->phase!=CLEAN){
        s->result=QED_STAGE_CANCELLED;s->phase=CLEAN;
    }
    if(s->phase==CLEAN){
        if(s->descriptor>=0){
            closing=s->descriptor;s->descriptor=-1;
            if(Fclose(closing)<0){
                cause=QedFileCloseError();if(!cause)cause=IoErr();
                if(!s->cleanup)s->cleanup=cause;
                if(!s->cause)s->cause=cause;
                s->safe=0;s->result=QED_STAGE_UNCERTAIN;
            }
            return QED_STAGE_PENDING;
        }
        if(s->owned && s->safe){
            if(!DeleteFile(s->name)){
                cause=IoErr();s->cleanup=cause;
                if(!s->cause)s->cause=cause;
                s->result=QedSaveLogicalError(cause) ? QED_STAGE_FAILED:QED_STAGE_UNCERTAIN;
            }else s->owned=0;
        }
        s->phase=DONE;SetIoErr(s->cause);return s->result;
    }
    if(s->phase==READY)return QED_STAGE_READY;
    if(s->phase==COUNT){
        if(!fill(s,1))return QED_STAGE_PENDING;
        if(IS_TAIL(s->line)){cursor(s);s->phase=CREATE;}
        return QED_STAGE_PENDING;
    }
    if(s->phase==CREATE){
        if(s->attempts>=256){fail(s,ERROR_OBJECT_EXISTS,1);return QED_STAGE_PENDING;}
        s->attempts++;
        if(!QedTemporaryName(s->target,"TMP",s->name)){fail(s,IoErr(),1);return QED_STAGE_PENDING;}
        if(QedPathEqual(s->name,s->target->name))return QED_STAGE_PENDING;
        fd=QedFileExclusive(s->name);
        if(fd<0){cause=IoErr();if(cause!=ERROR_OBJECT_EXISTS)fail(s,cause,cause==ERROR_NO_MORE_ENTRIES || QedSaveLogicalError(cause));}
        else{s->descriptor=(short)fd;s->owned=1;s->phase=WRITE;}
        return QED_STAGE_PENDING;
    }
    if(s->phase==CLOSE){
        closing=s->descriptor;s->descriptor=-1;
        if(Fclose(closing)<0)fail(s,IoErr(),0);
        else if(s->confirmed!=s->expected)fail(s,ERROR_SEEK_ERROR,1);
        else{s->phase=READY;return QED_STAGE_READY;}
        return QED_STAGE_PENDING;
    }
    if(s->sent==s->used){
        if(!fill(s,0))return QED_STAGE_PENDING;
        s->used=s->produced;s->sent=0;
        if(!s->used){s->phase=CLOSE;return QED_STAGE_PENDING;}
    }
    requested=(LONG)(s->used-s->sent);
    SetIoErr(0);count=Fwrite(s->descriptor,requested,s->buffer+s->sent);cause=IoErr();
    if(count>0 && count<=requested){s->sent+=(unsigned short)count;s->confirmed+=count;}
    if(count<=0 || count>requested || cause){
        if(!cause)cause=ERROR_DISK_FULL;
        fail(s,cause,QedSaveLogicalError(cause));
    }
    return QED_STAGE_PENDING;
}
