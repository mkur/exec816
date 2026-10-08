/* Private data, runtime pointers, calls and bank relocations in a disk image. */
#include <exec/types.h>
#include <proto/exec.h>
#include <exec816/runtime.h>
static volatile ULONG initialized=0x12345678UL;
static volatile ULONG cleared;
static const char text[]="bank relocated";
static const char *volatile words=text;
static LONG transform(LONG value) { return value*7-3; }
static LONG (*volatile transformPointer)(LONG)=transform;
typedef void EXEC_CALL YieldFunction(void);
static YieldFunction *volatile yieldPointer=ExecYield;
static struct Object { WORD next,type; const char *label; } objects[]={
    {1,21,text},{-1,26,"second"}
};
static void select_case(UWORD value)
{
    /* Distinct volatile operations keep this switch live in both C modes. */
    switch (value) {
    case 0:initialized+=0;break;
    case 1:initialized+=1;break;
    case 2:initialized+=2;break;
    case 3:initialized+=3;break;
    case 4:initialized+=4;break;
    case 5:initialized+=5;break;
    case 6:initialized+=6;break;
    default:initialized+=7;break;
    }
}
LONG EXEC_CALL main(ULONG argument)
{
    UWORD i;
    ULONG previous=cleared;
    if (initialized!=0x12345678UL+previous || words[5]!='r' ||
        transformPointer(9)!=60 || objects[objects[0].next].label[0]!='s' ||
        objects[1].type!=26) return 100;
    for (i=0;i<8;++i) select_case(i);
    initialized-=28;
    for (i=0;i<80;++i) yieldPointer();
    ++cleared;++initialized;
    return -((LONG)argument+(LONG)cleared);
}
