/* SPDX-License-Identifier: MIT
 * Exec startup only. The two application bodies use conventional GEM. */
#include <exec816/program.h>
#include <gem.h>
#include <string.h>

int main(int argc,char **argv)
{
    struct ExecProgramStart start={0};
    struct ExecProgramResult result;
    ULONG widget,counter=0;
    WORD status=0;
    const char *mode=argc>1 ? argv[1]:"paint";
    if (strcmp(mode,"solo") && strcmp(mode,"silent") && strcmp(mode,"paint")) return 10;
    /* The C APP runtime registers with AES before main. This supervisor owns
     * no window: release its application identity before starting the pair,
     * leaving the four client slots to Desktop, Terminal, Widget and Counter.
     * The runtime still owns and later detaches its C binding. */
    if (!appl_exit()) return 15;
    if (strcmp(mode,"solo")) {
        start.arguments=mode;
        start.length=(UWORD)strlen(mode);
        counter=ExecStartProgram("SYS:C/PULSE.APP",&start);
        if (!counter) return 11;
    }
    widget=ExecStartProgram("SYS:C/WIDGET.APP",NULL);
    if (!widget) {
        if (counter) {
            ExecBreakProgram(counter);
            ExecWaitProgram(counter,&result);
        }
        return 12;
    }
    if (!ExecWaitProgram(widget,&result) || result.primary) status=13;
    /* Counter remains independent after Widget closes. Close its own window
     * to finish the pair, then collect both child Process identities. */
    if (counter && (!ExecWaitProgram(counter,&result) || result.primary)) status=14;
    return status;
}
