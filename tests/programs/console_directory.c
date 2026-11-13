/* SPDX-License-Identifier: MIT */
/* Every watch operation uses the production console C/Action bridge. */
#include <exec816/console-view.h>
#include <proto/exec.h>
ULONG DirectoryHandles[2];
UWORD DirectoryChecks[2];
#define REQUIRE(c) do { ++DirectoryChecks[index]; if (!(c)) return DirectoryChecks[index]; } while (0)

LONG EXEC_CALL DirectoryProbe(ULONG value)
{
    UWORD index=value>>8,stage=value&255;
    ULONG mask=0x80000000UL;
    struct ExecConsoleViewDirectory directory;
    if (stage==0) {
        REQUIRE(!ExecConsoleViewWatchDirectory(0));
        REQUIRE(!ExecConsoleViewWatchDirectory(~FindTask(NULL)->tc_SigAlloc));
        DirectoryHandles[index]=ExecConsoleViewWatchDirectory(mask);
        REQUIRE(DirectoryHandles[index]!=0);
        REQUIRE(ExecConsoleViewTakeDirectoryChange(DirectoryHandles[index])==1);
        REQUIRE(ExecConsoleViewTakeDirectoryChange(DirectoryHandles[index])==0);
        REQUIRE(SetSignal(0,0)&mask);
        REQUIRE(Wait(mask)==mask);
    } else if (stage==1) {
        REQUIRE(ExecConsoleViewTakeDirectoryChange(DirectoryHandles[index])==1);
        REQUIRE(ExecConsoleViewTakeDirectoryChange(DirectoryHandles[index])==0);
    } else if (stage==2) {
        REQUIRE(ExecConsoleViewDirectory(&directory)==EXEC_CONSOLE_VIEW_OK);
        REQUIRE(ExecConsoleViewTakeDirectoryChange(DirectoryHandles[index])==0);
    } else if (stage==3) {
        REQUIRE(ExecConsoleViewUnwatchDirectory(DirectoryHandles[index])==EXEC_CONSOLE_VIEW_OK);
        DirectoryHandles[index]=0;
    } else if (stage==4) {
        REQUIRE(ExecConsoleViewWatchDirectory(mask)==0);
    } else return 99;
    return 0;
}

