#include "../../c/calypsi/file-list.h"
#include <string.h>
#define CHECK(x) do { if (!(x)) return __LINE__; ++checks; } while (0)
static struct FileEntry entries[FILE_LIST_LIMIT];
static struct FileInfoBlock info;
static struct FileScan scan;
static WORD indices[FILE_LIST_LIMIT];
static char path[128],mask[128],joined[256];
static WORD total,at,fail,openFail,examineFail,locks,reads,checks;
static LONG error;
BPTR EXEC_CALL Lock(CONST_STRPTR name,LONG mode)
{
    (void)name;(void)mode;error=ERROR_OBJECT_NOT_FOUND;
    if (openFail) return 0;
    ++locks;at=0;return 1;
}
void EXEC_CALL UnLock(BPTR lock) { (void)lock;--locks;error=0; }
LONG EXEC_CALL Examine(BPTR lock,struct FileInfoBlock *p)
{
    (void)lock;p->fib_DirEntryType=examineFail==2 ? -1:1;
    error=ERROR_OBJECT_NOT_FOUND;return examineFail!=1;
}
LONG EXEC_CALL ExNext(BPTR lock,struct FileInfoBlock *p)
{
    char *name=(char *)p->fib_FileName;
    (void)lock;++reads;
    if (at==fail) { error=ERROR_OBJECT_NOT_FOUND;return 0; }
    if (at==total) { error=ERROR_NO_MORE_ENTRIES;return 0; }
    strcpy(name,"F000.TXT");name[1]='0'+at/100;name[2]='0'+at/10%10;name[3]='0'+at%10;
    p->fib_DirEntryType=at ? -1:1;++at;return 1;
}
LONG EXEC_CALL IoErr(void) { return error; }
LONG EXEC_CALL FileListProbe(ULONG unused)
{
    WORD i,n,before;
    (void)unused;
    CHECK(sizeof(struct FileEntry)==112);
    CHECK(sizeof(struct FileScan)==20);
    CHECK(FileMatch("*.*","README") && FileMatch("*.txt","a.TXT"));
    CHECK(FileMatch("A?.*","A") && FileMatch("A?.*","AB.C"));
    CHECK(!FileMatch("A?.*","ABC.TXT") && !FileMatch("*.TXT","A.BIN"));
    CHECK(FileSplit("",path,mask) && !strcmp(path,"SYS:") && !strcmp(mask,"*.*"));
    CHECK(FileSplit("WORK:DOCS/",path,mask) && !strcmp(path,"WORK:DOCS"));
    CHECK(FileJoin(joined,256,path,mask) && !strcmp(joined,"WORK:DOCS/*.*"));
    CHECK(FileSplit("SYS:*.TXT",path,mask) && !strcmp(mask,"*.TXT"));
    CHECK(!FileSplit("C:\\TEST\\*.*",path,mask));
    CHECK(!FileSplit("SYS:*/A",path,mask) && !FileSplit("NO_PREFIX",path,mask));
    strcpy(path,"SYS:");memset(path+4,'A',119);path[123]=0;
    CHECK(FileSplit(path,joined,mask));
    memset(path+4,'A',123);path[127]=0;CHECK(FileSplit(path,joined,mask));
    path[126]='/';path[127]=0;CHECK(!FileSplit(path,joined,mask));
    strcpy(path,"SYS:ABC/DEF");FileParent(path);CHECK(!strcmp(path,"SYS:ABC"));
    FileParent(path);FileParent(path);CHECK(!strcmp(path,"SYS:"));
    CHECK(FileJoin(path,128,path,"ABC") && !strcmp(path,"SYS:ABC"));
    strcpy(joined,"keep");CHECK(!FileJoin(joined,5,"SYS:","ABC") && !strcmp(joined,"keep"));
    CHECK(FileLeaf("A.TXT") && FileLeaf("README") && FileLeaf("@_`.a"));
    CHECK(!FileLeaf("") && !FileLeaf("A.") && !FileLeaf("A.*") && !FileLeaf("ABCDEFGHI.A") && !FileLeaf("1.A"));
    CHECK(FileFirst(25,20,5)==15 && FileFirst(0,0,5)==0);
    CHECK(FileExpose(0,8,4)==5 && FileExpose(8,2,4)==2);
    for (i=0;i<4;++i) {
        total=i==0 ? 0:i==1 ? 1:i==2 ? 256:257;fail=-1;reads=0;
        CHECK(FileScanBegin(&scan,"SYS:",&info,entries));
        while (FileScanNext(&scan)) {}
        CHECK(!locks && !scan.lock && !scan.error);
        CHECK(scan.count==(total>256 ? 256:total) && scan.truncated==(total>256));
        CHECK(reads==(total>256 ? 257:total+1));
        before=reads;n=FileFilter(entries,scan.count,"*.BIN",indices);
        CHECK(n==(total ? 1:0) && reads==before);
    }
    total=5;fail=3;CHECK(FileScanBegin(&scan,"SYS:",&info,entries));
    while (FileScanNext(&scan)) {}
    CHECK(!locks && scan.count==0 && scan.error==ERROR_OBJECT_NOT_FOUND);
    scan.count=17;openFail=1;CHECK(!FileScanBegin(&scan,"BAD:",&info,entries));
    CHECK(scan.count==17 && !locks && scan.error==ERROR_OBJECT_NOT_FOUND);
    openFail=0;examineFail=1;CHECK(!FileScanBegin(&scan,"SYS:",&info,entries));
    CHECK(scan.count==17 && !locks && scan.error==ERROR_OBJECT_NOT_FOUND);
    examineFail=2;CHECK(!FileScanBegin(&scan,"SYS:",&info,entries));
    CHECK(!locks && scan.error==ERROR_OBJECT_WRONG_TYPE);
    examineFail=0;fail=-1;CHECK(FileScanBegin(&scan,"SYS:",&info,entries));
    CHECK(FileScanNext(&scan));FileScanEnd(&scan);FileScanEnd(&scan);CHECK(!locks);
    return 0;
}

int main(void) { return 0; }
