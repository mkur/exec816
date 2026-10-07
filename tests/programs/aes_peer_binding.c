/* A second linked binding instance has its own private contexts table. */
#define ExecAESSubmit Peer_ExecAESSubmit
#define ExecAESPointer Peer_ExecAESPointer
#define ExecAESContext Peer_ExecAESContext
#define ExecAESAttach Peer_ExecAESAttach
#define ExecAESDetach Peer_ExecAESDetach
#define ExecAESDiagnostic Peer_ExecAESDiagnostic
#define appl_init Peer_appl_init
#define appl_exit Peer_appl_exit
#define appl_write Peer_appl_write
#define evnt_mesag Peer_evnt_mesag
#define evnt_keybd Peer_evnt_keybd
#define evnt_button Peer_evnt_button
#define evnt_timer Peer_evnt_timer
#define wind_update Peer_wind_update
#define evnt_multi Peer_evnt_multi
#define evnt_multi_moblk Peer_evnt_multi_moblk
#define aes_call Peer_aes_call
#define wind_create Peer_wind_create
#define wind_open Peer_wind_open
#define wind_close Peer_wind_close
#define wind_delete Peer_wind_delete
#define wind_get Peer_wind_get
#define wind_set Peer_wind_set
#define wind_set_str Peer_wind_set_str
#define wind_calc Peer_wind_calc
#include "../../c/calypsi/aes.c"
#include "../../c/calypsi/aes-windows.c"
