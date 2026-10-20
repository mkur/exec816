/* WB5: exercise the public launcher from an ordinary loaded application. */
#include <exec816/program.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <string.h>
#define CHECK(x) do { ++LaunchChecks;if (!(x)) return __LINE__; } while (0)
UWORD LaunchChecks;
static char bytes[32];
static LONG contents(const char *path,const char *wanted,UWORD size)
{
    BPTR f=Open(path,MODE_OLDFILE);LONG n;
    if (!f) return 0;
    n=Read(f,bytes,sizeof(bytes));
    return Close(f) && n==size && !memcmp(bytes,wanted,size);
}
static LONG collected(ULONG child,LONG expected)
{
    struct ExecProgramResult result;
    return child && ExecWaitProgram(child,&result) && result.primary==expected && !result.secondary;
}
int main(void)
{
    struct ExecProgramStart start={0};
    struct ExecProgramResult result;
    BPTR parent=Output(),file,directory,input,output;
    APTR image;ULONG child,before;char raw[13];
    CHECK(parent && Input());
    /* Retained load reference, copied args, busy refusal and early private BREAK. */
    image=ExecLoadProgram("SYS:NATIVE");CHECK(image);
    start.arguments="H";start.length=1;
    child=ExecStartLoaded(image,&start);CHECK(child && Output()==parent);
    CHECK(!ExecStartLoaded(image,&start) && IoErr()==ERROR_OBJECT_IN_USE);
    ExecReleaseProgram(image);
    CHECK(ExecBreakProgram(child) && collected(child,-17));
    CHECK(!ExecCollectProgram(child,&result) && IoErr()==305);
    CHECK(!ExecProgramMask(child));
    /* Explicit streams and directory remain live after parent references retire. */
    input=Open("RAM:INPUT.TXT",MODE_OLDFILE);output=Open("RAM:NATIVE.TXT",MODE_NEWFILE);
    directory=Lock("RAM:PROJECT",SHARED_LOCK);CHECK(input && output && directory);
    start.arguments="R";start.input=input;start.output=output;start.directory=directory;
    child=ExecStartProgram("SYS:NATIVE",&start);CHECK(child && Output()==parent);
    CHECK(Close(input) && Close(output));UnLock(directory);
    CHECK(collected(child,7));CHECK(contents("RAM:NATIVE.TXT","Znative",7));
    CHECK(contents("RAM:PROJECT/REL.TXT","relative",8));
    CHECK(DeleteFile("RAM:NATIVE.TXT") && DeleteFile("RAM:PROJECT/REL.TXT"));
    /* A shared input/output identity is cloned once and shares file position. */
    file=Open("RAM:SHARED.TXT",MODE_NEWFILE);CHECK(file && Write(file,"ABC",3)==3);
    CHECK(Seek(file,0,OFFSET_BEGINNING)==3);
    memset(&start,0,sizeof(start));start.arguments="C";start.length=1;
    start.input=start.output=file;
    child=ExecStartProgram("SYS:CHILD.APP",&start);CHECK(collected(child,-321));
    CHECK(Seek(file,0,OFFSET_CURRENT)==2 && Close(file));
    CHECK(contents("RAM:SHARED.TXT","AcC",3) && DeleteFile("RAM:SHARED.TXT"));
    /* The FB65 service sees the same selected input and project directory. */
    input=Open("RAM:INPUT.TXT",MODE_OLDFILE);output=Open("RAM:GUEST.TXT",MODE_NEWFILE);
    directory=Lock("RAM:PROJECT",SHARED_LOCK);CHECK(input && output && directory);
    memset(&start,0,sizeof(start));start.input=input;start.output=output;start.directory=directory;
    child=ExecStartProgram("SYS:GUEST.COM",&start);
    CHECK(Close(input) && Close(output));UnLock(directory);
    CHECK(collected(child,0));CHECK(contents("RAM:GUEST.TXT","90\233",3));
    CHECK(contents("RAM:PROJECT/GREL.TXT","guest\233",6));
    CHECK(DeleteFile("RAM:GUEST.TXT") && DeleteFile("RAM:PROJECT/GREL.TXT"));
    /* Independent console setup is acknowledged before Start returns. */
    input=Open(ExecGetArgStr(),MODE_OLDFILE);CHECK(input);
    strcpy(raw,ExecGetArgStr());memcpy(raw,"RAW",3);output=Open(raw,MODE_NEWFILE);CHECK(output);
    memset(&start,0,sizeof(start));start.input=input;start.output=output;start.console=input;
    start.arguments="H";start.length=1;
    child=ExecStartProgram("SYS:NATIVE",&start);CHECK(child);
    CHECK(ExecBreakProgram(child) && collected(child,-17));
    /* Failed post-adoption console setup retires the invisible child completely. */
    before=AvailMem(0);start.console=output;
    CHECK(!ExecStartProgram("SYS:NATIVE",&start) && IoErr()==ERROR_OBJECT_WRONG_TYPE);
    CHECK(AvailMem(0)==before && Output()==parent);
    start.console=input;child=ExecStartProgram("SYS:NATIVE",&start);CHECK(child);
    CHECK(ExecBreakProgram(child) && collected(child,-17));
    CHECK(Close(input) && Close(output));
    CHECK(Write(parent,"P",1)==1);
    return 0;
}
