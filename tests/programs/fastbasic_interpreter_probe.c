/* Exercise public record bytes and huge pointers through the C/native bridge. */
#include <exec816/fastbasic-interpreter.h>
#include "../../examples/gem-basic/build-job.h"
#include <stddef.h>
#include <string.h>
volatile UWORD InterpreterChecks;
static struct ExecBasicSource source;
static struct ExecBasicResult result;
static UBYTE copy[FBI_RESULT_BYTES];
struct BasicInterpreterSession InterpreterSessionBlock __attribute__((aligned(2)));
static UWORD word(const UBYTE *p) { return p[0]+((UWORD)p[1]<<8); }
#define CHECK(c) do { if (!(c)) return InterpreterChecks+1; ++InterpreterChecks; } while (0)
LONG InterpreterProbe(void)
{
    const UBYTE *p=(const UBYTE *)&source;
    CHECK(sizeof(source)==28);CHECK(sizeof(result)==128);
    source.version=FBI_VERSION;source.bytes=FBI_SOURCE_BYTES;
    source.source=(const UBYTE *)0x2ffffeUL;source.length=32768UL;
    source.job=0x12345678UL;source.generation=0x9abcdef0UL;source.result=&result;
    CHECK(word(p)==FBI_VERSION);CHECK(word(p+2)==28);
    CHECK(word(p+4)==0xfffe && word(p+6)==0x2f);
    CHECK(source.source+3==(const UBYTE *)0x300001UL);
    CHECK(word(p+8)==0x8000 && word(p+10)==0);
    CHECK(word(p+12)==0x5678 && word(p+14)==0x1234);
    CHECK(source.result==&result);
    result.version=FBI_VERSION;result.bytes=128;result.job=source.job;
    result.generation=source.generation;result.phase=FBI_PHASE_PARSE;
    result.location=1;result.primary=20;result.cause=306;
    result.line=4096;result.column=255;strcpy((char *)result.message,"parse error");
    memcpy(copy,&result,sizeof(copy));
    CHECK(word(copy+12)==FBI_PHASE_PARSE);CHECK(word(copy+14)==1);
    CHECK(word(copy+16)==20);CHECK(word(copy+20)==306);
    CHECK(word(copy+26)==4096 && word(copy+28)==255);
    CHECK(!strcmp((const char *)copy+32,"parse error"));
    CHECK(sizeof(struct ExecBasicSession)==19);
    CHECK(sizeof(struct ExecBasicRequest)==46);
    CHECK(offsetof(struct ExecBasicRequest,source)==18);
    CHECK(offsetof(struct ExecBasicSession,port)==16);
    CHECK(sizeof(struct BasicInterpreterSession)==86);
    CHECK(offsetof(struct BasicInterpreterSession,child)==4);
    CHECK(offsetof(struct BasicInterpreterSession,channel)==12);
    CHECK(offsetof(struct BasicInterpreterSession,request)==32);
    return 0;
}
int main(void) { return 0; }
