/* SPDX-License-Identifier: MIT. Fail each of the real application's nine tables. */
#include "platform.h"
#include <errno.h>
static unsigned int executions,allocation,failed,alerts;
extern int GemArcApplication(int,char **);
void *GemArcTestMalloc(size_t bytes)
{
    if (++allocation==failed) { errno=ENOMEM;return NULL; }
    return malloc(bytes);
}
WORD EXEC_CALL GemArcTestAlert(WORD button,CONST_STRPTR message)
{
    (void)button;(void)message;++alerts;return 1;
}
int main(int argc,char **argv)
{
    int result;
    failed=1+(executions++%9);allocation=alerts=0;
    result=GemArcApplication(argc,argv);
    if (result!=20 || allocation!=9 || alerts!=1 || IoErr()!=ERROR_NO_FREE_STORE) return 100+failed;
    return -321;
}
