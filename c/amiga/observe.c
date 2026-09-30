/* Amiga-only result observer. The message example is compiled unchanged,
 * with its main symbol renamed by the build recipe so it can run three times.
 */
#include <exec/types.h>
#include <dos/dos.h>
#include <proto/dos.h>

extern int ExecMessageMain(void);
extern volatile UWORD received_x, received_y, same_message;

#define REPEAT_COUNT 3

int main(void)
{
    static const char success[] = "PASS 60,70 same message\n";
    static const char failure[] = "FAIL\n";
    BPTR file;
    int iteration, status = 0;

    file = Open("SYS:results.tmp", MODE_NEWFILE);
    if (!file)
        return 20;
    for (iteration = 0; iteration < REPEAT_COUNT; ++iteration) {
        status = ExecMessageMain();
        if (status != 0 || received_x != 60 || received_y != 70 || same_message != 1) {
            Write(file, (APTR)failure, sizeof(failure)-1);
            status = 20;
            break;
        }
        if (Write(file, (APTR)success, sizeof(success)-1) != sizeof(success)-1) {
            status = 20;
            break;
        }
    }
    Close(file);
    /* Publish only a closed result file, after each example invocation returns. */
    if (!Rename("SYS:results.tmp", "SYS:results.txt"))
        return 20;
    return status;
}
