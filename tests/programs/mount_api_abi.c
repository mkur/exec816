#include <proto/dos.h>

int main(void)
{
    struct SioMountSpec spec = {2, MOUNT_MYDOS, 4, MOUNT_READONLY};
    unsigned char buffer[64];
    BPTR file;

    if (sizeof(spec) != 8 || spec.drive != 2 || spec.format != MOUNT_MYDOS ||
        spec.profile != 4 || spec.access != MOUNT_READONLY)
        return 1;
    if (!MountVolume("CAPI", &spec))
        return 2;
    file = Open("CAPI:TOOLS/SUB/DATA.BIN", MODE_OLDFILE);
    if (!file || Read(file, buffer, sizeof(buffer)) != sizeof(buffer))
        return 3;
    if (UnmountVolume("CAPI") || IoErr() != ERROR_OBJECT_IN_USE)
        return 4;
    if (!Close(file) || !UnmountVolume("CAPI"))
        return 5;
    if (MountVolume("CAPI", 0) || IoErr() != ERROR_DEVICE_NOT_MOUNTED)
        return 6;
    return 0;
}
