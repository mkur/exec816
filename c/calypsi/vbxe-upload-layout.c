#include <hardware/vbxe-upload.h>
__attribute__((section("exec_layout"))) const unsigned short __exec_layout[]={
    sizeof(struct VbxeUpload),offsetof(struct VbxeUpload,records),
    offsetof(struct VbxeUpload,count),
    sizeof(struct VbxeTextUpload),offsetof(struct VbxeTextUpload,text),
    offsetof(struct VbxeTextUpload,font),offsetof(struct VbxeTextUpload,destination),
    offsetof(struct VbxeTextUpload,count),offsetof(struct VbxeTextUpload,ink),
    offsetof(struct VbxeTextUpload,paper),
    offsetof(struct VbxeTextUpload,fillDestination),offsetof(struct VbxeTextUpload,fillBytes),
    offsetof(struct VbxeTextUpload,fillRows),offsetof(struct VbxeTextUpload,fillValue)
};
