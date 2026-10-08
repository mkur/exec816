#include <gem.h>
#include <exec816/aes.h>
#include <proto/exec.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
static void check(WORD okay)
{
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
}
#define CHECK(x) check((x)!=0)
void AESClientOne(void) { }
void AESClientTwo(void) { }
UWORD AESRun(void)
{
    WORD round;
    ULONG available=AvailMem(0);
    CHECK(ExecAESMouseProfile(AES_MOUSE_QUERY)==-1);
    for (round=0;round<3;++round) {
        struct ExecAESContext *c;
        CHECK(ExecAESAttach((struct MsgPort *)AESService));
        CHECK(appl_init()>0);
        CHECK(ExecAESMouseProfile(AES_MOUSE_QUERY)==AES_MOUSE_MILD);
        CHECK(ExecAESMouseProfile(AES_MOUSE_OFF)==AES_MOUSE_OFF);
        CHECK(ExecAESMouseProfile(AES_MOUSE_QUERY)==AES_MOUSE_OFF);
        c=ExecAESContext();
        c->busy=1;
        CHECK(ExecAESMouseProfile(AES_MOUSE_MILD)==-1);
        c->busy=0;
        CHECK(ExecAESMouseProfile(AES_MOUSE_QUERY)==AES_MOUSE_OFF);
        CHECK(appl_exit());
        CHECK(ExecAESMouseProfile(AES_MOUSE_QUERY)==-1);
        CHECK(appl_init()>0);
        CHECK(ExecAESMouseProfile(AES_MOUSE_QUERY)==AES_MOUSE_OFF);
        CHECK(ExecAESMouseProfile(AES_MOUSE_MILD)==AES_MOUSE_MILD);
        CHECK(ExecAESDetach());
        CHECK(AvailMem(0)==available);
    }
    return AESFailures;
}
