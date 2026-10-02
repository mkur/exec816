#ifndef GEM_INTERACTIVE_H
#define GEM_INTERACTIVE_H
#include "ui-abi.h"
#include <exec816/address.h>
#include "gem-vbxe.h"
#include <exec/input.h>
#include <hardware/vbxe.h>
#include <exec816/runtime.h>
void GemApplication(void);
void UiDisarmPointer(void);
extern struct UiBoot boot;
extern volatile UWORD stage, rootValue, finished, failures, firstFailure, checks;
extern struct GemServer server;
extern struct GemClient client;
#endif
