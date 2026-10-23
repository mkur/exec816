/* Fixture-only faults at QED's ordinary acquisition calls. */
#include <gem.h>
#include <proto/dos.h>
#include <proto/exec.h>
#include "qed-runtime.h"
volatile UWORD QedFailurePoint,QedFailureAt,QedFailureCalls,QedFailureHits;
static WORD refuse(UWORD point)
{
    if(QedFailurePoint!=point)return 0;
    ++QedFailureHits;SetIoErr(ERROR_NO_FREE_STORE);return 1;
}
WORD QedFailAES(void){return refuse(1)?-1:appl_init();}
void QedFailVDI(WORD *in,WORD *handle,WORD *out)
{
    if(refuse(2)){*handle=0;return;}
    v_opnvwk(in,handle,out);
}
WORD QedFailResource(const char *name)
{
    if(refuse(3))return 0;
    if(QedFailurePoint==7 || QedFailurePoint==8){
        ++QedFailureHits;
        return rsrc_load(QedFailurePoint==7?"SYS:MISSING.RSC":"SYS:BAD.RSC");
    }
    return rsrc_load(name);
}
WORD QedFailMenu(OBJECT *tree,WORD show)
{return show&&refuse(4)?0:menu_bar(tree,show);}
WORD QedFailCreate(WORD kind,WORD x,WORD y,WORD w,WORD h)
{return refuse(5)?-1:wind_create(kind,x,y,w,h);}
WORD QedFailOpen(WORD handle,WORD x,WORD y,WORD w,WORD h)
{return refuse(6)?0:wind_open(handle,x,y,w,h);}
APTR EXEC_CALL QedFixtureAlloc(ULONG bytes,ULONG flags)
{
    ++QedFailureCalls;
    if(QedFailureAt && QedFailureCalls>=QedFailureAt){
        ++QedFailureHits;SetIoErr(ERROR_NO_FREE_STORE);return NULL;
    }
    return AllocMem(bytes,flags);
}
