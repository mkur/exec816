#include <proto/dos.h>

LONG main(void)
{
    struct FileInfoBlock *info = (struct FileInfoBlock *)0x2dfff0;
    BPTR lock = Lock("D1:CHECK", SHARED_LOCK);
    UWORD flags;
    if (!lock || !ExamineExact(lock, info)) return 1;
    if (info->fib_Size != 3 || info->fib_NumBlocks != 2 ||
        info->fib_InfoFlags != (FIB_SIZE_EXACT | FIB_BLOCKS_EXACT)) return 2;
    flags = info->fib_InfoFlags;
    if (ExamineExact(0, info) || IoErr() != ERROR_INVALID_LOCK ||
        info->fib_InfoFlags != flags || info->fib_Size != 3) return 3;
    if (!Examine(lock, info) || info->fib_Size != 3 ||
        info->fib_NumBlocks != -1 || info->fib_InfoFlags != FIB_SIZE_EXACT) return 4;
    UnLock(lock);
    if (DeleteFile("D1:CHECK") || IoErr() != ERROR_DISK_WRITE_PROTECTED) return 5;
    return 0;
}
