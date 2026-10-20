/* Exercise the production window lifecycle with private image state. */
#include "../../examples/gem-basic/basic.h"
#include <exec816/program.h>
static struct BasicApp app;
static WORD runs;
int main(void)
{
    const char *args=ExecGetArgStr();
    if (!BasicOpen(&app)) return 50;
    if (app.cellw!=8 || app.cellh!=8 || !app.ready) return 51;
    if (!evnt_timer(args && *args=='B' ? 1000:20,0)) return 52;
    if (!BasicClose(&app)) return 53;
    return -123-++runs;
}
