/* Loaded private adapter against the actual native selector and filesystem. */
#include "qed-runtime.h"
#include "qed-commands.h"
#include <exec816/aes.h>
#include <string.h>
volatile short QedSelectorPhase;
static char selected[256];
static WORD message[8];
#define CHECK(test,code) do{if(!(test))return code;}while(0)
static int body(int argc,char **argv)
{
    WORD window,result;
    CHECK(appl_init()>=0,101);
    window=wind_create(NAME|CLOSER|MOVER,24,24,592,208);
    CHECK(window>0 && wind_open(window,24,24,592,208),102);
    QedSelectorPhase=1;
    result=QedChooseFile(NULL,selected,"Open reference text");
    CHECK(result==QED_DIALOG_ACCEPTED && !strcmp(selected,"SYS:DATA.TXT"),103);
    strcpy(selected,"unchanged");QedSelectorPhase=2;
    result=QedChooseFile("SYS:DATA.TXT",selected,"Cancel reference text");
    CHECK(result==QED_DIALOG_CANCELLED && !strcmp(selected,"unchanged"),104);
    QedSelectorPhase=3;
    result=QedChooseFile("SYS:DATA.TXT",selected,"Move interrupts selection");
    CHECK(result==QED_DIALOG_INTERRUPTED && !strcmp(selected,"unchanged") && ExecAESDiagnostic()==AES_PENDING,105);
    CHECK(evnt_mesag(message) && message[0]==WM_MOVED && message[3]==window,106);
    CHECK(wind_set(window,WF_CURRXYWH,message[4],message[5],message[6],message[7]),107);
    QedSelectorPhase=4;
    result=QedChooseFile(NULL,selected,"After interrupted selection");
    CHECK(result==QED_DIALOG_CANCELLED && !strcmp(selected,"unchanged"),108);
    CHECK(wind_close(window) && wind_delete(window) && appl_exit(),109);
    return -321;
}
int main(void){return QedRuntimeRun(body);}
