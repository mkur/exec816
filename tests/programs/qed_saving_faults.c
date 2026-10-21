/* Physical loaded editor: pause/refuse only fixture boundaries, forward success. */
#include "qed_editing_faults.c"
#include "qed-save.h"
#include "qed-files.h"
#include <exec816/runtime.h>
volatile UWORD QedSaveHoldWrite,QedSaveHoldRename,QedSaveWriteCalls,QedSaveCloseCalls,QedSaveRenameCalls,QedSaveDeleteCalls;
volatile UWORD QedSaveFailWrite,QedSaveFailClose,QedSaveFailRename,QedSaveFailDelete;
volatile UWORD QedSaveFailAlert,QedSaveAlertFailures,QedSaveAlertDiagnostic,QedSaveAlerts;
LONG QedSaveFaultWrite(WORD fd,LONG bytes,const void *data)
{
    LONG result;++QedSaveWriteCalls;
    while(QedSaveHoldWrite)ExecYield();
    if(QedSaveFailWrite){
        QedSaveFailWrite=0;result=Fwrite(fd,bytes>1 ? 1:bytes,data);SetIoErr(ERROR_DISK_FULL);return result;
    }
    return Fwrite(fd,bytes,data);
}
LONG EXEC_CALL QedSaveFaultClose(BPTR file)
{
    LONG result=Close(file);++QedSaveCloseCalls;
    if(QedSaveFailClose){QedSaveFailClose=0;SetIoErr(ERROR_SEEK_ERROR);return 0;}
    return result;
}
LONG EXEC_CALL QedSaveFaultRename(CONST_STRPTR before,CONST_STRPTR after)
{
    ++QedSaveRenameCalls;while(QedSaveHoldRename)ExecYield();
    if(QedSaveFailRename && --QedSaveFailRename==0){SetIoErr(ERROR_OBJECT_IN_USE);return 0;}
    return Rename(before,after);
}
LONG EXEC_CALL QedSaveFaultDelete(CONST_STRPTR name)
{
    ++QedSaveDeleteCalls;
    if(QedSaveFailDelete){QedSaveFailDelete=0;SetIoErr(ERROR_OBJECT_IN_USE);return 0;}
    return DeleteFile(name);
}
WORD QedSaveAlert(WORD def,const char *text)
{
    struct Held {struct Held *next;ULONG bytes;};
    struct Held *held=NULL,*block;ULONG bytes;WORD answer;
    if(QedSaveFailAlert){
        QedSaveFailAlert=0;
        while((bytes=AvailMem(MEMF_UPPER|MEMF_LARGEST))>=sizeof(*block)){
            block=(struct Held *)AllocMem(bytes,MEMF_UPPER);if(!block)break;
            block->next=held;block->bytes=bytes;held=block;
        }
    }
    ++QedSaveAlerts;answer=form_alert(def,text);QedSaveAlertDiagnostic=ExecAESDiagnostic();
    if(held && QedSaveAlertDiagnostic==AES_RESOURCE)++QedSaveAlertFailures;
    while(held){block=held;held=block->next;FreeMem(block,block->bytes);}
    return answer;
}
const UWORD QedSavingLayout[]={
    sizeof(struct QedSave),offsetof(struct QedSave,target)+offsetof(struct QedPath,name),
    offsetof(struct QedSave,stage)+offsetof(struct QedStage,name),offsetof(struct QedSave,backup),
    offsetof(struct QedSave,escrow),offsetof(struct QedSave,cause),offsetof(struct QedSave,cleanup),
    offsetof(struct QedSave,phase),offsetof(struct QedSave,result),offsetof(struct QedSave,published),
    offsetof(struct QedSave,stage)+offsetof(struct QedStage,confirmed),
    offsetof(struct QedSave,stage)+offsetof(struct QedStage,expected),
    offsetof(struct QedSave,backup_exists),offsetof(struct QedSave,critical)};
