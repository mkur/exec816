/* SPDX-License-Identifier: GPL-3.0-only */
#include "qed-files.h"
#include <calypsi/stubs.h>
#include <time.h>
#include <errno.h>

extern void __initialize_global_streams(void);
void __call_initialize_global_streams(void)
{
    __initialize_global_streams();
}

char **_Stub_environ(void)
{
    static char *empty[1]={NULL};
    return empty;
}
/* There is no native UTC clock. File DateStamps remain separate metadata. */
time_t time(time_t *value)
{
    if (value) *value=(time_t)-1;
    errno=ENOSYS;
    return (time_t)-1;
}
void _Stub_exit(int status)
{
    static const char message[]="QED unexpected library exit; Process retained.\n";
    Write(Output(),message,sizeof(message)-1);
    for (;;) Wait(0);
}
void _Stub_assert(const char *file,int line)
{
    static const char message[]="QED assertion; Process retained.\n";
    Write(Output(),message,sizeof(message)-1);
    for (;;) Wait(0);
}
