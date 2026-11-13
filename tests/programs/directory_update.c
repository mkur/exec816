/* Test-only UPDATE owner used by the native directory publisher probe. */
#include <gem.h>
#include <proto/exec.h>
#include <exec816/aes.h>
LONG EXEC_CALL DirectoryUpdate(ULONG service)
{
    if (service) return ExecAESAttach((struct MsgPort *)service) && appl_init()>0 && wind_update(BEG_UPDATE);
    return wind_update(END_UPDATE) && appl_exit() && ExecAESDetach();
}
