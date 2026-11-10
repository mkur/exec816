/* SPDX-License-Identifier: MIT */
#include "../../examples/gem-counter/counter.h"
#include <exec816/program.h>
#include <proto/exec.h>
#include <proto/dos.h>

struct Counter GEMCounter;
volatile WORD GFIOReady,GFIOPhase,GFIOError;
volatile ULONG GFIOLoops,GFIOBytes;
static const struct CounterConfig configs[2]={
    {"Counter A",32,48,144,48,4,0},
    {"Counter B",320,144,144,48,2,0}
};

/* A separate client deliberately blocks its event loop; CounterRun is shared
 * unchanged with the production application. All read storage is upper RAM. */
static int io_client(char mode)
{
    WORD id,window,event,message[8],mx,my,mb,ks,kr,br,quit=0,result=0;
    BPTR file;
    UBYTE *buffer;
    LONG amount,error;
    UWORD i;
    id=appl_init();
    if (id<0) return 1;
    window=wind_create(NAME|CLOSER|MOVER,320,144,144,48);
    if (window<0) { appl_exit();return 2; }
    if (!wind_set_str(window,WF_NAME,"Read test") ||
        !wind_open(window,320,144,144,48)) {
        wind_delete(window);appl_exit();return 3;
    }
    buffer=AllocMem(16384UL,MEMF_PUBLIC);
    if (!buffer) { wind_close(window);wind_delete(window);appl_exit();return 4; }
    GFIOReady=1;
    while (!quit) {
        event=evnt_multi(MU_MESAG|MU_TIMER,0,0,0,
            0,0,0,0,0,0,0,0,0,0,message,1000,0,&mx,&my,&mb,&ks,&kr,&br);
        if (!event) { result=5;break; }
        if ((event&MU_MESAG) && message[0]==WM_CLOSED) quit=1;
        if (event&MU_TIMER) {
            ++GFIOLoops;
            if (GFIOLoops==2 && !GFIOPhase) {
                if (mode=='u' && !wind_update(BEG_UPDATE)) { result=6;break; }
                file=Open("D1:LOAD.BIN",MODE_OLDFILE);
                if (!file) { result=7;break; }
                GFIOPhase=1;
                amount=Read(file,buffer,16384L);error=IoErr();
                GFIOBytes=amount<0 ? 0:(ULONG)amount;
                GFIOError=(WORD)error;
                if (!Close(file)) result=8;
                if (mode=='u' && !wind_update(END_UPDATE)) result=9;
                if (mode=='c') {
                    if (amount==16384L || error!=304L) result=10;
                    GFIOPhase=3;
                } else {
                    if (amount!=16384L || error) result=11;
                    else for (i=0;i<16384;++i)
                        if (buffer[i]!=(UBYTE)((i^(i>>8))^0x5a)) { result=12;break; }
                    GFIOPhase=2;
                }
                if (result) break;
            }
        }
    }
    GFIOReady=0;
    FreeMem(buffer,16384UL);
    if (!wind_close(window) || !wind_delete(window) || !appl_exit()) result=13;
    return result;
}

int main(void)
{
    const char *args=ExecGetArgStr();
    char mode=args ? args[0]:'1';
    if (mode=='i' || mode=='u' || mode=='c') return io_client(mode);
    GEMCounter.config=&configs[mode=='2'];
    return CounterRun(&GEMCounter);
}
