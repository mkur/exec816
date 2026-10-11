/* Private directory/viewport helpers shared with Files. */
#ifndef EXEC816_FILE_LIST_H
#define EXEC816_FILE_LIST_H
#include <proto/dos.h>
#define FILE_LIST_LIMIT 256
struct FileEntry { char name[108]; LONG kind; };
struct FileScan {
    BPTR lock;
    struct FileInfoBlock *info;
    struct FileEntry *entries;
    WORD count,truncated;
    LONG error;
};
WORD FileScanBegin(struct FileScan *,const char *,struct FileInfoBlock *,struct FileEntry *);
WORD FileScanNext(struct FileScan *);
void FileScanEnd(struct FileScan *);
WORD FileMatch(const char *,const char *);
WORD FileFilter(const struct FileEntry *,WORD,const char *,WORD *);
WORD FileFirst(WORD,WORD,WORD);
WORD FileExpose(WORD,WORD,WORD);
WORD FileJoin(char *,WORD,const char *,const char *);
void FileParent(char *);
WORD FileSplit(const char *,char *,char *);
WORD FileLeaf(const char *);
#endif
