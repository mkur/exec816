/* C child uses the same selected-I/O contract and returns a signed result. */
#include <exec816/program.h>
#include <proto/dos.h>
#include <gem.h>
volatile UWORD ChildRuns;
int main(void)
{
    char c;
    const char *args=ExecGetArgStr();
    ++ChildRuns;
    if (args && args[0]=='H') { evnt_timer(1000,0);return -321; }
    if (!args || args[0]!='C' || args[1]) return 41;
    if (Read(Input(),&c,1)!=1 || c!='A' || Write(Output(),"c",1)!=1) return 42;
    return -321;
}
