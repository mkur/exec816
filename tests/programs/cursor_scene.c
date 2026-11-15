/* Controlled physical completion; native cursor policy remains production code. */
#include <exec816/aes.h>
#include <proto/exec.h>

ULONG CursorSceneMouse,CursorSceneCaller;
UWORD CursorSceneCalls,CursorSceneFailures;

LONG EXEC_CALL CursorSceneApply(ULONG value)
{
    struct AESRequest *request=(struct AESRequest *)value;
    struct AESMouseState *mouse=(struct AESMouseState *)CursorSceneMouse;
    ++CursorSceneCalls;
    if ((ULONG)FindTask(NULL)!=CursorSceneCaller) ++CursorSceneFailures;
    mouse->completed=mouse->revision;
    request->mouseWait=0;
    return 1;
}

int main(void) { return 0; }
