/* MIT fixture-only failure at the resident retirement boundary. */
#include <exec816/aes.h>
#include <exec816/program.h>
BOOL RuntimeTestDetach(void)
{
    const char *arguments=ExecGetArgStr();
    if (arguments && *arguments=='D') return FALSE;
    return ExecAESDetach();
}
