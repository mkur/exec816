/* Actual path owner; assignment changes use an ordinary native child. */
#include "qed-path.h"
#include "qed-runtime.h"
#include <exec816/program.h>
#include <string.h>
static struct QedPath first,second;
static struct FileInfoBlock info;
static char overlong[257];
#define CHECK(x,n) do { if(!(x))return n; } while(0)
static int assign(const char *target)
{
    struct ExecProgramResult result;
    struct ExecProgramStart start={0};
    ULONG child;
    start.arguments=target;start.length=(UWORD)strlen(target);
    child=ExecStartProgram("SYS:REASSIGN",&start);
    return child && ExecWaitProgram(child,&result) && !result.primary;
}
static int body(int argc,char **argv)
{
    BPTR lock,file;struct QedHeapStats stats,warm;
    char sibling[256];
    QedHeapSnapshot(&warm);
    /* Pure builder boundary: current 16-level 8.3 namespaces cannot reach
       every nominal 255-byte canonical name. This creates no filesystem. */
    memset(first.name,'A',255);first.name[255]=0;first.prefix=243;
    CHECK(QedPathSibling(&first,"Q0000000.TMP",sibling) && strlen(sibling)==255,125);
    first.prefix=244;CHECK(!QedPathSibling(&first,"Q0000000.TMP",sibling) && IoErr()==ERROR_LINE_TOO_LONG,126);
    memset(&first,0,sizeof(first));
    memset(overlong,'A',256);overlong[256]=0;
    CHECK(!QedPathPrepare(&first,overlong,1) && !first.parent && IoErr()==ERROR_BAD_ARGUMENTS,127);

    CHECK(QedPathPrepare(&first,"leaf.txt",1) && !strcmp(first.name,"RAM:NEST/LEAF.TXT"),101);
    CHECK(QedPathPrepare(&second,"QW:leaf.txt",0) && QedPathEqual(first.name,second.name),102);
    QedPathRelease(&second);QedPathRelease(&first);
    CHECK(QedPathPrepare(&first,"SYS:LEAF.TXT",0) && !strcmp(first.name,"D1:LEAF.TXT"),103);
    QedPathRelease(&first);
    CHECK(!QedPathPrepare(&first,"NIL:",0) && !first.parent,104);
    CHECK(!QedPathPrepare(&first,"RAM:NEST/*.TXT",0) && !first.parent,105);
    CHECK(!QedPathPrepare(&first,"RAM:NEST/123.TXT",0) && !first.parent,106);
    CHECK(!QedPathPrepare(&first,"RAM:NEST/TOOLONGXX.TXT",0) && !first.parent,107);
    CHECK(!QedPathPrepare(&first,"RAM:MISSING/LEAF.TXT",0) && !first.parent,108);
    lock=CreateDir("RAM:OTHER");CHECK(lock,109);UnLock(lock);
    CHECK(QedPathPrepare(&first,"QW:FROZEN.TXT",1),110);
    CHECK(assign("RAM:OTHER"),111);
    CHECK(QedPathPrepare(&second,"QW:FROZEN.TXT",1) && !strcmp(second.name,"RAM:OTHER/FROZEN.TXT") &&
        !strcmp(first.name,"RAM:NEST/FROZEN.TXT"),112);
    CHECK(QedPathSibling(&first,"Q0000000.TMP",sibling) && !strcmp(sibling,"RAM:NEST/Q0000000.TMP"),113);
    QedPathRelease(&second);QedPathRelease(&first);
    CHECK(assign("RAM:NEST") && DeleteFile("RAM:OTHER"),114);
    lock=CreateDir("RAM:NEST/HOLD");CHECK(lock,115);UnLock(lock);
    CHECK(QedPathPrepare(&first,"RAM:NEST/HOLD/FILE.TXT",1),116);
    CHECK(!DeleteFile("RAM:NEST/HOLD") && IoErr()==ERROR_OBJECT_IN_USE,117);
    CHECK(!Rename("RAM:NEST/HOLD","RAM:NEST/MOVED") && IoErr()==ERROR_OBJECT_IN_USE,118);
    QedPathRelease(&first);
    CHECK(Rename("RAM:NEST/HOLD","RAM:NEST/MOVED") && DeleteFile("RAM:NEST/MOVED"),119);
    CHECK(QedPathInfo("RAM:NEST/ABSENT.TXT",&info)==0 && IoErr()==ERROR_OBJECT_NOT_FOUND,120);
    file=Open("RAM:NEST/FILE.TXT",MODE_CREATE_EXCLUSIVE);CHECK(file && Close(file),121);
    CHECK(QedPathInfo("RAM:NEST/FILE.TXT",&info)==1 && info.fib_DirEntryType==ST_FILE,122);
    CHECK(Rename("RAM:NEST/FILE.TXT","RAM:NEST/OTHER.TXT") && DeleteFile("RAM:NEST/OTHER.TXT"),123);
    QedHeapSnapshot(&stats);CHECK(stats.blocks==warm.blocks && stats.backing==warm.backing,124);
    return -321;
}
int main(void){return QedRuntimeRun(body);}
