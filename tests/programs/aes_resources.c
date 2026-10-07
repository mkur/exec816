#include <gem.h>
#include <exec816/aes.h>
#include <proto/dos.h>
#include <proto/exec.h>
ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,ResourceStatus;
volatile LONG ResourceError;
static void check(WORD okay) { ++AESChecks;if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=AESChecks; } }
#define CHECK(x) check((x)!=0)
void AESClientOne(void) { }
void AESClientTwo(void) { }
UWORD AESRun(void)
{
    OBJECT *tree,*again,*popup;
    struct FileInfoBlock info;
    BPTR lock,file;
    ULONG memory;
    WORD x,y,words[8];
    struct ExecAESContext *context;
    /* Mount/cache allocations persist until system shutdown. Warm them before
       measuring the resource/context lifetime. */
    file=Open("D1:DESKTOP.RSC",MODE_OLDFILE);
    CHECK(file && Close(file)); CHECK(ExecDOSDetach()); memory=AvailMem(0);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    context=ExecAESContext();
    for (x=0;x<8;++x) context->deferredMessage[x]=123+x;
    context->messagePending=1;
    CHECK(evnt_mesag(words) && words[0]==123 && words[7]==130 && !context->messagePending);
    x=rsrc_load("D1:DESKTOP.RSC");ResourceStatus=ExecAESDiagnostic();ResourceError=IoErr();
    CHECK(x);if (!x) goto cleanup;
    CHECK(rsrc_gaddr(R_TREE,0,(void **)&tree));
    CHECK(tree[0].ob_width==224 && tree[0].ob_height==152);
    CHECK(tree[1].ob_type==G_BUTTON && ((char *)tree[1].ob_spec)[0]=='F');
    CHECK(objc_offset(tree,4,&x,&y) && x==8 && y==32);
    CHECK(rsrc_gaddr(R_TREE,1,(void **)&popup) && popup[0].ob_width==112);
    CHECK(!rsrc_load("D1:BAD.RSC"));
    CHECK(rsrc_gaddr(R_TREE,0,(void **)&again) && again==tree);
    CHECK(!rsrc_load("D1:SHORT.RSC"));
    CHECK(rsrc_gaddr(R_TREE,0,(void **)&again) && again==tree);
    CHECK(!rsrc_gaddr(R_TREE,2,(void **)&again) && !again);
    CHECK(menu_ienable(popup,1,0) && popup[1].ob_state==DISABLED);
    CHECK(menu_ienable(popup,1,1) && popup[1].ob_state==0);
    CHECK(menu_tnormal(popup,1,0) && popup[1].ob_state==SELECTED);
    CHECK(menu_text(popup,1,"Launch") && ((char *)popup[1].ob_spec)[0]=='L');
    CHECK(rsrc_free()); CHECK(!rsrc_gaddr(R_TREE,0,(void **)&again));
    CHECK(rsrc_load("D1:DESKTOP.RSC"));
    lock=Lock("D1:",SHARED_LOCK); CHECK(lock!=0);
    CHECK(Examine(lock,&info)!=0 && info.fib_DirEntryType>0);
    CHECK(ExNext(lock,&info)!=0 && info.fib_FileName[0]!=0);
    UnLock(lock);
    file=Open("D1:DESKTOP.RSC",MODE_OLDFILE);CHECK(file!=0);
    CHECK(Seek(file,36,OFFSET_BEGINNING)==0);CHECK(Seek(file,0,OFFSET_CURRENT)==36);
    CHECK(Close(file));
cleanup:
    CHECK(appl_exit());CHECK(ExecAESDetach());CHECK(ExecDOSDetach());
    CHECK(AvailMem(0)==memory);
    return AESFailures;
}
