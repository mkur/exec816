#ifndef EXEC816_AES_FSEL_PRIVATE_H
#define EXEC816_AES_FSEL_PRIVATE_H
#include "aes-form-private.h"
#include "file-list.h"
enum { FS_CAPTION=1,FS_PATH_LABEL,FS_PATH,FS_FILE_LABEL,FS_FILE,FS_UP,
       FS_REFRESH,FS_LINE_UP,FS_LINE_DOWN,FS_PAGE_UP,FS_PAGE_DOWN,FS_STATUS,
       FS_OK,FS_CANCEL,FS_ROW,FS_OBJECTS=FS_ROW+16 };
struct ExecAESFileSelector {
    OBJECT tree[FS_OBJECTS];
    TEDINFO ted[20];
    struct FileEntry *entries;
    struct FileScan scan;
    struct FileInfoBlock info;
    WORD indices[FILE_LIST_LIMIT];
    char path[128],file[13],title[31],directory[128],mask[128];
    char requested[128],filter[128],savedName[108],labels[16][16],status[80];
    WORD count,first,visible,selected,valid,loading,result;
};
WORD ExecAESFileSelect(char *,char *,WORD *,const char *);
void ExecAESFileFree(struct ExecAESFileSelector *);
#endif
