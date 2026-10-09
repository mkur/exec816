#include "../../c/calypsi/aes-alert-private.h"
__attribute__((section("exec_layout")))
const UWORD FormLayout[]={
    sizeof(struct ExecAESForm),offsetof(struct ExecAESForm,focus),offsetof(struct ExecAESForm,alert),
    sizeof(struct ExecAESAlert),offsetof(struct ExecAESAlert,icon)
};
