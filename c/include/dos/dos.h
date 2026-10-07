/* Generated from abi/dos.json by tools/generate_calypsi.py. */
#ifndef EXEC_DOS_H
#define EXEC_DOS_H
#include <exec/types.h>
#define DOSFALSE (0L)
#define DOSTRUE (-1L)
#define MODE_OLDFILE (1005L)
#define MODE_NEWFILE (1006L)
#define MODE_READWRITE (1004L)
#define OFFSET_BEGINNING (-1L)
#define OFFSET_CURRENT (0L)
#define OFFSET_END (1L)
#define SHARED_LOCK (-2L)
#define EXCLUSIVE_LOCK (-1L)
#define FIBF_DELETE (1L)
#define FIBF_WRITE (4L)
#define ST_ROOT (1L)
#define ST_USERDIR (2L)
#define ST_FILE (-3L)
#define PIPE_BUFFER_BYTES (1024L)
#define FAULT_BUFFER_BYTES (384L)
#define ERROR_NO_FREE_STORE (103L)
#define ERROR_BAD_TEMPLATE (114L)
#define ERROR_BAD_NUMBER (115L)
#define ERROR_REQUIRED_ARG_MISSING (116L)
#define ERROR_TOO_MANY_ARGS (118L)
#define ERROR_UNMATCHED_QUOTES (119L)
#define ERROR_LINE_TOO_LONG (120L)
#define ERROR_NO_DEFAULT_DIR (201L)
#define ERROR_OBJECT_IN_USE (202L)
#define ERROR_DIR_NOT_FOUND (204L)
#define ERROR_OBJECT_NOT_FOUND (205L)
#define ERROR_BAD_STREAM_NAME (206L)
#define ERROR_OBJECT_TOO_LARGE (207L)
#define ERROR_ACTION_NOT_KNOWN (209L)
#define ERROR_INVALID_COMPONENT_NAME (210L)
#define ERROR_INVALID_LOCK (211L)
#define ERROR_OBJECT_WRONG_TYPE (212L)
#define ERROR_DISK_NOT_VALIDATED (213L)
#define ERROR_DISK_WRITE_PROTECTED (214L)
#define ERROR_TOO_MANY_LEVELS (217L)
#define ERROR_DEVICE_NOT_MOUNTED (218L)
#define ERROR_SEEK_ERROR (219L)
#define ERROR_NOT_A_DOS_DISK (225L)
#define ERROR_NO_DISK (226L)
#define ERROR_NO_MORE_ENTRIES (232L)
#define ERROR_BUFFER_OVERFLOW (303L)
#define ERROR_BREAK (304L)
#define ERROR_BROKEN_PIPE (310L)
#define ERROR_BAD_ARGUMENTS (311L)
#define ERROR_OBJECT_EXISTS (203L)
#define ERROR_RENAME_ACROSS_DEVICES (215L)
#define ERROR_DIR_NOT_EMPTY (216L)
#define ERROR_DISK_FULL (221L)
#define ERROR_DELETE_PROTECTED (222L)
#define ERROR_WRITE_PROTECTED (223L)
struct DateStamp {
    LONG ds_Days;
    LONG ds_Minute;
    LONG ds_Tick;
};
struct FileInfoBlock {
    LONG fib_DiskKey;
    LONG fib_DirEntryType;
    UBYTE fib_FileName[108];
    LONG fib_Protection;
    LONG fib_EntryType;
    LONG fib_Size;
    LONG fib_NumBlocks;
    struct DateStamp fib_Date;
    UBYTE fib_Comment[80];
    UWORD fib_OwnerUID;
    UWORD fib_OwnerGID;
    UBYTE fib_Reserved[32];
};
#endif
