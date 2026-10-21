/* Public C/native canonical path boundary; no private lock inspection. */
#include <proto/dos.h>
#include <string.h>
static char guarded[258];
#define CHECK(x,n) do { if (!(x)) return n; } while (0)
static int name(const char *path,const char *expected)
{
    BPTR lock=Lock(path,SHARED_LOCK);
    LONG size=(LONG)strlen(expected)+1;
    int failed=0;
    if(!lock)return 101;
    memset(guarded,0xa5,sizeof(guarded));
    if(!NameFromLock(lock,guarded+1,size) || strcmp(guarded+1,expected) ||
        (unsigned char)guarded[0]!=0xa5 || (unsigned char)guarded[size+1]!=0xa5)failed=102;
    memset(guarded,0xa5,sizeof(guarded));
    if(NameFromLock(lock,guarded+1,size-1) || IoErr()!=ERROR_LINE_TOO_LONG ||
        (unsigned char)guarded[1]!=0xa5)failed=103;
    if(NameFromLock(lock,guarded+1,0) || IoErr()!=ERROR_BAD_NUMBER)failed=104;
    if(NameFromLock(lock,(char *)0x1000000UL,20) || IoErr()!=ERROR_BAD_NUMBER)failed=105;
    UnLock(lock);
    return failed;
}
int main(void)
{
    int result;
    result=name("RAM:","RAM:");if(result)return result;
    result=name("RAM:NEST","RAM:NEST");if(result)return result;
    result=name("QW:","RAM:NEST");if(result)return result;
    result=name("","RAM:NEST");if(result)return result;
    result=name("SYS:","D1:");if(result)return result;
    CHECK(!NameFromLock((BPTR)0x1000000UL,guarded,256) && IoErr()==ERROR_BAD_NUMBER,106);
    return -321;
}
