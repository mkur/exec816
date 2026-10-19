/* Exercise the port's types and timer adapter in the ordinary C Process fixture. */
#include "../../ports/gem4xe/apps/qed/native/qed-native.h"
#include <string.h>
#include <stddef.h>

__attribute__((section("exec_layout")))
const UWORD QedNativeLayout[]={sizeof(void *),sizeof(void EXEC_PTR *),sizeof(_WORD),
    sizeof(LONG),sizeof(OBJECT),offsetof(OBJECT,ob_spec),sizeof(TEDINFO)};

static LONG transform(LONG value) { return value*7-3; }
static LONG (*volatile callback)(LONG)=transform;

static int abi(void)
{
    unsigned char *block,*edge;
    ULONG boundary,largest;
    WORD message[8],x,y,b,k,key,count;
    struct Node node;
    unsigned char sample[16]={128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,255};
    if ((char)255!=255 || callback(9)!=60) return 71;
    largest=AvailMem(MEMF_UPPER|MEMF_LARGEST);
    if (!largest || largest>65536UL || AvailMem(MEMF_UPPER)<largest) return 75;
    block=AllocMem(65568UL,MEMF_UPPER|MEMF_LINEAR);
    if (!block) return 72;
    boundary=((ULONG)block&0xffff0000UL)+65536UL;
    edge=(unsigned char *)boundary;
    memcpy(edge-8,sample,sizeof(sample));
    node.ln_Name=(char EXEC_PTR *)(edge-8);
    if ((ULONG)node.ln_Name!=boundary-8 || memcmp(edge-8,sample,sizeof(sample)) ||
        edge[-8]!=128 || edge[7]!=255) { FreeMem(block,65568UL);return 73; }
    FreeMem(block,65568UL);
    if (QedEvntMulti(MU_TIMER,0,0,0,0,0,0,0,0,0,0,0,0,0,message,0,
            &x,&y,&b,&k,&key,&count)!=MU_TIMER) return 74;
    return 0;
}

#define main QedProcessScenario
#include "c_process.c"
#undef main
int main(void)
{
    int result=abi();
    return result ? result:QedProcessScenario();
}
