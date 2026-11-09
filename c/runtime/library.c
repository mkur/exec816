/* SPDX-License-Identifier: MIT */
#include "internal.h"
#include <calypsi/stubs.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>

static char *cursor;
static char *empty[1];
void ExecCRuntimeLibraryBegin(void)
{
    cursor=NULL;empty[0]=NULL;srand(1);errno=0;
}
char *strtok(char *text,const char *delimiters) { return !text && !cursor ? NULL:strtok_r(text,delimiters,&cursor); }
char **_Stub_environ(void) { return empty; }
/* File DateStamps remain separate metadata; there is no native UTC clock. */
time_t time(time_t *value)
{
    if (value) *value=(time_t)-1;
    errno=ENOSYS;return (time_t)-1;
}
