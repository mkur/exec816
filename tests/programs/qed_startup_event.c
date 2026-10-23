/* SPDX-License-Identifier: GPL-3.0-only */
#include "global.h"
#include "event.h"
#include <exec816/aes.h>
#include <proto/dos.h>
/* Pointer decoration is owned by the presenter in the adapted application. */
bool mouse_sleeps(void){return FALSE;}
void wake_mouse(void){}
static WORD notices;
/* Record an unexpected editor error; no fixture dialog is opened. */
short inote(short def,short undo,short index,short value){++notices;return 0;}
/* Include the actual private poller in this test translation unit. */
#include "event.c"
int main(void)
{
    WORD window=wind_create(AES_WINDOW_KIND,16,24,200,120);
    if(window<0)return 101;
    if(!wind_open(window,16,24,200,120))return 104;
    (void)idle();
    if(ExecAESDiagnostic()!=AES_OK || notices)return 102;
    if(!wind_close(window))return 105;
    if(!wind_delete(window))return 103;
    SetIoErr(0);return -321;
}
