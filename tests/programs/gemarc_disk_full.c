/* SPDX-License-Identifier: MIT. Real SDFS exhaustion before archive publication. */
#include "platform.h"
#include <stdio.h>
static unsigned char input[2048],output[2048],fill[8192];
int GemArcPoll(void) { ExecYield();return 0; }
void arc_progress(const char *name) { (void)name;ExecYield(); }
#define CHECK(test,n) do { if (!(test)) return n; } while (0)
int main(void)
{
    BPTR file;
    LONG wrote,total=0;
    int result;
    unsigned char contents[2];
    GemArcIOBegin();arc_buffers(input,output,sizeof input);
    CHECK(arc_new("SYS:FULL.ARC")==0,101);
    file=Open("SYS:FILL.DAT",MODE_NEWFILE);CHECK(file,102);
    do {
        wrote=Write(file,fill,sizeof fill);
        if (wrote>0) total+=wrote;
        CHECK(total<1024L*1024L,103);
        ExecYield();
    } while (wrote==sizeof fill);
    CHECK(IoErr()==ERROR_DISK_FULL && total>300000L,104);
    CHECK(Close(file),105);
    result=arc_new("SYS:FULL.ARC");
    CHECK(result!=0 && GemArcCause()==ERROR_DISK_FULL,106);
    CHECK(DeleteFile("SYS:FILL.DAT"),107);
    file=Open("SYS:FULL.ARC",MODE_OLDFILE);CHECK(file,108);
    CHECK(Read(file,contents,2)==2 && contents[0]==0x1a && contents[1]==0,109);
    CHECK(Close(file),110);
    SetIoErr(0);return -321;
}
