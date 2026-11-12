/* SPDX-License-Identifier: MIT
 * Adapter for the original viewer's small Exec API subset on Atari MagiC.
 * No Exec kernel runs here: allocation and file calls use TOS/libc/GEMDOS. */
#include "examples/gem-text/text.h"
#include <exec816/aes.h>
#include <exec816/program.h>
#include <proto/exec.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

extern struct TextApp GEMText;
extern WORD reference_font[4];
void reference_mouse(WORD);
static LONG error;
static char arguments[130];
static ULONG allocations,files,locks;
WORD reference_update_depth;
struct FileLock { struct stat info; };

char *strcpy(char *destination,const char *source)
{
    char *result=destination;
    while ((*destination++=*source++)) {}
    return result;
}
char *strcat(char *destination,const char *source)
{
    strcpy(destination+strlen(destination),source);
    return destination;
}

/* The shared viewer accepts Exec-style SYS: and slash-separated paths.
 * Translate only at the filesystem/selector boundary. */
static void tos_path(const char *source,char *target)
{
    if (!strncmp(source,"SYS:",4)) {strcpy(target,"A:\\");target+=3;source+=4;}
    while (*source) {*target++=*source=='/' ? '\\':*source;++source;}
    *target=0;
}

static LONG io_error(void)
{
    return errno==ENOMEM ? ERROR_NO_FREE_STORE:
        errno==ENOENT ? ERROR_OBJECT_NOT_FOUND:ERROR_BAD_STREAM_NAME;
}

APTR AllocMem(ULONG bytes,ULONG attributes)
{
    APTR memory=malloc(bytes);
    (void)attributes;
    if (memory) ++allocations;
    return memory;
}
void FreeMem(APTR memory,ULONG bytes)
{
    (void)bytes;
    if (memory) {free(memory);--allocations;}
}
LONG IoErr(void) {return error;}
BPTR Lock(CONST_STRPTR name,LONG mode)
{
    char path[132];
    struct FileLock *lock;
    (void)mode;
    tos_path(name,path);
    lock=malloc(sizeof(*lock));
    if (!lock) {error=ERROR_NO_FREE_STORE;return 0;}
    if (stat(path,&lock->info)<0) {error=io_error();free(lock);return 0;}
    error=0;++locks;
    return (BPTR)(uintptr_t)lock;
}
void UnLock(BPTR handle) {free((void *)(uintptr_t)handle);--locks;}
LONG Examine(BPTR handle,struct FileInfoBlock *info)
{
    const struct FileLock *lock=(const struct FileLock *)(uintptr_t)handle;
    memset(info,0,sizeof(*info));
    info->fib_DirEntryType=S_ISDIR(lock->info.st_mode) ? ST_USERDIR:ST_FILE;
    info->fib_Size=lock->info.st_size;
    info->fib_InfoFlags=FIB_SIZE_EXACT;
    error=0;return DOSTRUE;
}
BPTR Open(CONST_STRPTR name,LONG mode)
{
    char path[132];
    int fd;
    (void)mode;
    tos_path(name,path);fd=open(path,O_RDONLY);
    if (fd<0) {error=io_error();return 0;}
    error=0;++files;return fd+1;
}
LONG Read(BPTR file,void *buffer,LONG length)
{
    LONG result=read(file-1,buffer,length);
    error=result<0 ? io_error():0;
    return result;
}
LONG Close(BPTR file)
{
    int result=close(file-1);
    --files;error=result<0 ? io_error():0;
    return result<0 ? DOSFALSE:DOSTRUE;
}

void reference_arguments(const char *path)
{
    if (!*path) {arguments[0]=0;return;}
    arguments[0]='"';strcpy(arguments+1,path);strcat(arguments,"\"");
}
CONST_STRPTR ExecGetArgStr(void) {return arguments;}
UWORD ExecAESDiagnostic(void) {return AES_OK;}
WORD ExecAESBeginUpdate(WORD window) {(void)window;return wind_update(BEG_UPDATE);}
/* MagiC has no Exec presentation cache or paint-completion journal. */
WORD ExecAESPainted(WORD window,WORD x,WORD y,WORD w,WORD h)
{(void)window;(void)x;(void)y;(void)w;(void)h;return 1;}

WORD __real_wind_update(WORD);
WORD __wrap_wind_update(WORD mode)
{
    WORD result;
    if (mode==END_UPDATE) reference_mouse(257);
    result=__real_wind_update(mode);
    if (mode==BEG_UPDATE && result) {++reference_update_depth;reference_mouse(256);}
    if (mode==END_UPDATE && result) --reference_update_depth;
    return result;
}
WORD __real_wind_set(WORD,WORD,WORD,WORD,WORD,WORD);
WORD __wrap_wind_set(WORD h,WORD field,WORD a,WORD b,WORD c,WORD d)
{
    if (field==AES_WF_EXEC_PRESERVE) return 1;
    return __real_wind_set(h,field,a,b,c,d);
}
void __real_v_opnvwk(WORD *,WORD *,WORD *);
void __wrap_v_opnvwk(WORD *in,WORD *handle,WORD *out)
{
    __real_v_opnvwk(in,handle,out);
    GEMText.cellw=reference_font[2];GEMText.cellh=reference_font[3];
}
WORD __real_menu_bar(OBJECT *,WORD);
WORD __wrap_menu_bar(OBJECT *tree,WORD on)
{
    if (on) {
        /* The shared menu uses Exec's 11-pixel bar. MagiC's system menu
         * font is 8x16 even though this viewer selects 8x8 VDI text. */
        tree[0].ob_height=400;
        tree[1].ob_height=tree[2].ob_height=tree[3].ob_height=19;
        tree[3].ob_width=64;
        tree[4].ob_y=19;tree[4].ob_height=381;
        tree[5].ob_width=144;tree[5].ob_height=60;
        for (WORD i=6;i<9;++i) {
            tree[i].ob_y=(i-6)*20;tree[i].ob_height=20;tree[i].ob_width=144;
        }
    }
    return __real_menu_bar(tree,on);
}
WORD __real_fsel_exinput(char *,char *,WORD *,const char *);
void reference_selector(WORD,WORD,const char *);
WORD __wrap_fsel_exinput(char *path,char *file,WORD *button,const char *title)
{
    char converted[132];
    WORD result;
    tos_path(path,converted);strcpy(path,converted);
    reference_selector(-1,-1,file);
    result=__real_fsel_exinput(path,file,button,title);
    for (char *p=path;*p;++p) if (*p=='\\') *p='/';
    reference_selector(result,*button,file);
    return result;
}
WORD __real_appl_exit(void);
WORD __wrap_appl_exit(void)
{
    WORD okay=1;
    if (GEMText.menuInstalled) {
        if (menu_bar(GEMText.menu,0)) GEMText.menuInstalled=0;else okay=0;
    }
    if (GEMText.opened) {
        if (wind_close(GEMText.window)) GEMText.opened=0;else okay=0;
    }
    if (GEMText.window>=0 && !GEMText.opened) {
        if (wind_delete(GEMText.window)) GEMText.window=-1;else okay=0;
    }
    if (GEMText.vdi) {v_clsvwk(GEMText.vdi);GEMText.vdi=0;}
    if (!__real_appl_exit()) okay=0;
    return okay;
}
void reference_resources(FILE *report)
{
    dprintf(fileno(report),"resources allocations=%lu files=%lu locks=%lu window=%d vdi=%d menu=%d update=%d\n",
        (unsigned long)allocations,(unsigned long)files,(unsigned long)locks,
        GEMText.window,GEMText.vdi,GEMText.menuInstalled,reference_update_depth);
}
