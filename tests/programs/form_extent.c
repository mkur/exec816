#include "../../c/calypsi/aes-form-private.h"
#include <proto/exec.h>
static OBJECT object;
static const ULONG specs[]={0x58801170UL,0x58fd1170UL,0x58ff1170UL,0x58001170UL,
                            0x58011170UL,0x58031170UL,0x587f1170UL};
static const WORD borders[]={-128,-3,-1,0,0,0,0};
LONG EXEC_CALL FormExtentProbe(ULONG unused)
{
    GRECT r;
    WORD i,kind,border;
    (void)unused;
    object.ob_x=240; object.ob_y=92; object.ob_width=160; object.ob_height=80;
    for (kind=0;kind<2;++kind) {
        object.ob_type=kind ? G_IBOX:G_BOX;
        for (i=0;i<7;++i) {
            object.ob_spec=specs[i]; border=borders[i];
            ExecAESFormExtent(&object,&r);
            if (r.g_x!=240+border || r.g_y!=92+border ||
                r.g_w!=160-2*border || r.g_h!=80-2*border) return 1+kind*7+i;
        }
    }
    return 0;
}
int main(void) { return 0; }
