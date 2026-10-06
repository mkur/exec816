/* A second linked binding instance has its own private contexts table. */
#define ExecAESPointer Peer_ExecAESPointer
#define ExecAESContext Peer_ExecAESContext
#define ExecAESAttach Peer_ExecAESAttach
#define ExecAESDetach Peer_ExecAESDetach
#define ExecAESDiagnostic Peer_ExecAESDiagnostic
#define appl_init Peer_appl_init
#define appl_exit Peer_appl_exit
#define appl_write Peer_appl_write
#define evnt_mesag Peer_evnt_mesag
#define evnt_timer Peer_evnt_timer
#define wind_update Peer_wind_update
#define evnt_multi Peer_evnt_multi
#define evnt_multi_moblk Peer_evnt_multi_moblk
#define aes_call Peer_aes_call
#include "../../c/calypsi/aes.c"
