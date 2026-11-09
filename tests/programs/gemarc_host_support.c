#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include "arcfile.h"
static FILE *read_target;
static int read_error,write_short,close_failure,rename_failure,rename_calls,cancel_at,polls;
FILE *GemArcHostOpen(const char *name,const char *mode)
{
    FILE *file=fopen(name,mode);
    if (strstr(name,"READERR.DAT")) read_target=file;
    return file;
}
size_t GemArcHostRead(void *data,size_t size,size_t count,FILE *file)
{
    if (read_error && file==read_target) { errno=EIO;return (size_t)-1; }
    return fread(data,size,count,file);
}
size_t GemArcHostWrite(const void *data,size_t size,size_t count,FILE *file)
{
    if (write_short) { write_short=0;errno=ENOSPC;return fwrite(data,size,count ? 1:0,file); }
    return fwrite(data,size,count,file);
}
int GemArcHostClose(FILE *file)
{
    int result=fclose(file);
    if (close_failure && --close_failure==0) { errno=EIO;return EOF; }
    return result;
}
int GemArcHostRename(const char *from,const char *to)
{
    ++rename_calls;
    if (rename_failure && rename_calls==rename_failure) { errno=EACCES;return -1; }
    if (!access(to,F_OK)) { errno=EEXIST;return -1; }
    return rename(from,to);
}
void GemArcHostFault(int read,int write,int close,int rename,int cancel)
{read_error=read;write_short=write;close_failure=close;rename_failure=rename;rename_calls=0;cancel_at=cancel;polls=0;}
int GemArcPoll(void) { return cancel_at && ++polls>=cancel_at; }
void arc_progress(const char *name) {(void)name;}
void GemArcIOBegin(void);
void GemArcHostBegin(void)
{
    arc_tables(calloc(8192,2),calloc(8192,1),calloc(8192,1),calloc(5003,4),calloc(5003,2));
    arc_buffers(calloc(2048,1),calloc(2048,1),2048);
    GemArcIOBegin();
}
