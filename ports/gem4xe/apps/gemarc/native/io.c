/* SPDX-License-Identifier: MIT
 * GemARC's integer stream adapter. The common CRT owns every FILE/backing.
 */
#ifdef EXEC_GEMARC_HOST
#include "arcfile.h"
#include <sys/stat.h>
extern int GemArcPoll(void);
#else
#include "platform.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>

struct Stream { FILE *file; long size; };
static struct Stream streams[16];
static long cause;
static unsigned int poll_bytes;
static int cancelled;

static void failure(void)
{
    if (cause) return;
#ifdef EXEC_GEMARC_HOST
    cause=errno;
#else
    cause=IoErr();
    if (!cause) cause=errno==ENOMEM ? ERROR_NO_FREE_STORE:ERROR_BAD_NUMBER;
#endif
}
void pf_reset(void)
{
    cause=0;cancelled=0;errno=0;
#ifndef EXEC_GEMARC_HOST
    SetIoErr(0);
#endif
}
void GemArcIOBegin(void)
{
    memset(streams,0,sizeof(streams));poll_bytes=0;pf_reset();
}
long GemArcCause(void) { return cause; }
#ifndef EXEC_GEMARC_HOST
int GemArcFailure(LONG error)
{
    if (!cause) cause=error;
    SetIoErr(error);return -1;
}
#endif
int pf_missing(void) { return errno==ENOENT; }
int pf_collision(void) { return errno==EEXIST; }
int pf_cancelled(void) { return cancelled; }

static int budget(unsigned int bytes)
{
    poll_bytes+=bytes;
    if (!cancelled && poll_bytes>=4096) {
        poll_bytes=0;
        cancelled=GemArcPoll();
    }
    if (cancelled) {
        errno=EINTR;
#ifndef EXEC_GEMARC_HOST
        SetIoErr(ERROR_BREAK);
#endif
    }
    return cancelled;
}

static int open_stream(const char *name,int create)
{
    unsigned int index;
    FILE *file;
    long length=0;
    for (index=0;index<16 && streams[index].file;++index) {}
    if (index==16) {
        errno=EMFILE;
#ifndef EXEC_GEMARC_HOST
        SetIoErr(ERROR_NO_MORE_ENTRIES);
#endif
        failure();return -1;
    }
    file=fopen(name,create ? "wbx":"rb");
    if (!file) { failure();return -1; }
    if (setvbuf(file,NULL,_IONBF,0) ||
            (!create && (fseek(file,0,SEEK_END) || (length=ftell(file))<0 ||
                         fseek(file,0,SEEK_SET)))) {
        failure();fclose(file);return -1;
    }
    streams[index].file=file;streams[index].size=length;
    return index;
}
int pf_open(const char *name) { return open_stream(name,0); }
int pf_create(const char *name) { return open_stream(name,1); }
long pf_length(int handle) { return streams[handle].size; }
long pf_read(int handle,uint8_t *data,long bytes)
{
    FILE *file=streams[handle].file;
    size_t done;
    if (budget((unsigned int)bytes)) return -1;
    done=fread(data,1,(size_t)bytes,file);
    if (ferror(file)) { failure();return -1; }
    return done;
}
long pf_write(int handle,const uint8_t *data,long bytes)
{
    FILE *file=streams[handle].file;
    size_t done;
    if (budget((unsigned int)bytes)) return -1;
    done=fwrite(data,1,(size_t)bytes,file);
    if (done!=(size_t)bytes || ferror(file)) failure();
    return done;
}
long pf_seek(int handle,long offset)
{
    FILE *file=streams[handle].file;
    long position;
    if (fseek(file,offset,SEEK_SET) || (position=ftell(file))<0) {
        failure();return -1;
    }
    return position;
}
int pf_close(int handle)
{
    FILE *file=streams[handle].file;
    int result;
    streams[handle].file=NULL;
    result=fclose(file);
    if (result) failure();
    return result ? -1:0;
}
int pf_delete(const char *name)
{
    int result=remove(name);
    if (result) failure();
    return result;
}
int pf_rename(const char *before,const char *after)
{
    int result=rename(before,after);
    if (result) failure();
    return result;
}
int pf_exists(const char *name)
{
#ifdef EXEC_GEMARC_HOST
    struct stat info;
    if (!stat(name,&info)) {
        if (S_ISREG(info.st_mode)) return 1;
        errno=EISDIR;failure();return -1;
    }
    if (errno==ENOENT) return 0;
#else
    struct FileInfoBlock info;
    BPTR lock=Lock(name,SHARED_LOCK);
    int result;
    LONG error;
    if (lock) {
        result=ExamineExact(lock,&info);
        error=IoErr();UnLock(lock);SetIoErr(error);
        if (result && info.fib_DirEntryType<0) return 1;
        if (result) SetIoErr(ERROR_OBJECT_WRONG_TYPE);
        failure();return -1;
    }
    if (IoErr()==ERROR_OBJECT_NOT_FOUND || IoErr()==ERROR_DIR_NOT_FOUND) {
        SetIoErr(0);return 0;
    }
#endif
    failure();return -1;
}
int GemArcExists(const char *name) { return pf_exists(name); }

/* Date words are added by the platform metadata adapter; no UTC clock is
 * fabricated for a source without representable metadata. */
#ifdef EXEC_GEMARC_HOST
void pf_stamp(const char *name,uint16_t *date,uint16_t *time)
{
    (void)name;*date=*time=0;
}
int pf_setstamp(const char *name,uint16_t date,uint16_t time)
{
    (void)name;(void)date;(void)time;return 0;
}
#endif
