#include <gem.h>
#include <exec816/program.h>
static UWORD runs;
static ULONG initialized=0x12345678UL;
int main(void)
{
    const char *args=ExecGetArgStr();
    WORD window;
    if (!args || args[1] || initialized!=0x12345678UL+runs) return 51;
    if (args[0]=='F') return -321;
    if (appl_init()<0) return 52;
    if (!rsrc_load("SYS:DESKTOP.RSC")) return 53;
    window=wind_create(NAME|CLOSER|MOVER,0,0,128,64);
    if (window<0 || !wind_set_str(window,WF_NAME,"Loaded probe") ||
        !wind_open(window,32+(WORD)runs*8,32,128,64)) return 54;
    ++runs;++initialized;
    if (!evnt_timer(args[0]=='B' ? 1000:20,0)) return 55;
    /* Leave the window, resource and timer context to shared teardown. */
    return -123-(int)runs;
}
