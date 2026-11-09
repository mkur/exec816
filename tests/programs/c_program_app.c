/* MIT: typed C main, with full-width helper values and private retained state. */
#include <exec/types.h>
LONG EXEC_CALL CRelocationProbe(ULONG);
static UWORD executions;
int main(void)
{
    if (CRelocationProbe(70000UL)!=-70001L-executions) return 111;
    return -321-executions++;
}
