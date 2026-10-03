#include <hardware/vbxe-copy.h>
__attribute__((section("exec_layout")))
const unsigned short __exec_layout[]={
    sizeof(struct VbxeSurface),
    offsetof(struct VbxeSurface, offset),
    offsetof(struct VbxeSurface, pitch),
    offsetof(struct VbxeSurface, width),
    offsetof(struct VbxeSurface, height),
    sizeof(struct VbxeCopy),
    offsetof(struct VbxeCopy, source),
    offsetof(struct VbxeCopy, destination),
    offsetof(struct VbxeCopy, sourceX),
    offsetof(struct VbxeCopy, sourceY),
    offsetof(struct VbxeCopy, destinationX),
    offsetof(struct VbxeCopy, destinationY),
    offsetof(struct VbxeCopy, width),
    offsetof(struct VbxeCopy, height),
};
