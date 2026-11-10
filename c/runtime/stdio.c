/* SPDX-License-Identifier: MIT */
#include "internal.h"
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include "libc.h"

extern void __initialize_global_streams(void);
/* The pinned vendor objects require this ordinary C-call initializer symbol. */
void __call_initialize_global_streams(void) { __initialize_global_streams(); }

void ExecCRuntimeStdioBegin(void)
{
    UWORD index;
    __initialize_global_streams();
    for (index=0;index<3;++index) memset(__global_streams.sl_std[index],0,sizeof(FILE));
    memset(&__global_streams,0,sizeof(__global_streams));
    __initialize_global_streams();
}
static void mark(FILE *stream,int fd)
{
    if (stream && stream->fs_fd==fd) stream->fs_flags|=__FS_FLAG_ERROR;
}
void ExecCRuntimeStreamError(int fd)
{
    FILE *stream;
    UWORD index;
    for (index=0;index<3;++index) mark(__global_streams.sl_std[index],fd);
    for (stream=__global_streams.sl_head;stream;stream=stream->fs_next) mark(stream,fd);
}
int ferror(FILE *stream)
{
    int result=stream->fs_flags&__FS_FLAG_ERROR;
    if (result) ExecCRuntimeAcknowledge(stream->fs_fd);
    return result;
}
void clearerr(FILE *stream)
{
    ExecCRuntimeAcknowledge(stream->fs_fd);
    stream->fs_flags&=~(__FS_FLAG_ERROR|__FS_FLAG_EOF);
}
static void discard(FILE *stream)
{
#ifndef _CONFIG_STDIO_DISABLE_BUFFERING
    stream->fs_bufpos=stream->fs_bufread=stream->fs_bufstart;
#endif
}
LONG ExecCRuntimeStdioFinish(int abnormal)
{
    FILE *stream;
    UWORD index;
    ExecCRuntimeFilesCleaning();
    while ((stream=__global_streams.sl_head)!=NULL) {
        if (abnormal) discard(stream);
        fclose(stream);
    }
    for (index=0;index<3;++index) {
        stream=__global_streams.sl_std[index];
        if (stream) {
            if (abnormal) discard(stream);
            else if (stream->fs_fd>=0 && (stream->fs_oflags&O_WROK)) fflush(stream);
        }
    }
    return ExecCRuntimeFilesFinish();
}
