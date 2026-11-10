/* SPDX-License-Identifier: MIT. Existing DOS DateStamp operation through C. */
#include <proto/dos.h>
int main(void)
{
    static const char name[]="SYS:DATE.DAT";
    struct DateStamp date={16860,1439,2900}; /* 2024-02-29 23:59:58 */
    struct FileInfoBlock info;
    BPTR file=Open(name,MODE_NEWFILE),lock;
    if (!file || Write(file,"date",4)!=4 || !Close(file)) return 101;
    if (!SetFileDate(name,&date)) return 102;
    lock=Lock(name,SHARED_LOCK);
    if (!lock) return 103;
    if (!ExamineExact(lock,&info)) { UnLock(lock);return 104; }
    UnLock(lock);
    if (info.fib_Date.ds_Days!=date.ds_Days || info.fib_Date.ds_Minute!=date.ds_Minute ||
        info.fib_Date.ds_Tick!=date.ds_Tick) return 105;
    if (SetFileDate((const char *)0x01000000UL,&date) || IoErr()!=ERROR_BAD_NUMBER) return 106;
    if (SetFileDate(name,(const struct DateStamp *)0x01000000UL) || IoErr()!=ERROR_BAD_NUMBER) return 107;
    SetIoErr(0);
    return -321;
}
