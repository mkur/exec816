/* Add only a real-forward E-delete checkpoint to the saving fixture. */
#define QedSaveFaultDelete QedSavingOrdinaryDelete
#include "qed_saving_faults.c"
#undef QedSaveFaultDelete
volatile UWORD QedSaveHoldDelete,QedSaveDeleteEntered;
LONG EXEC_CALL QedSaveFaultDelete(CONST_STRPTR name)
{
    ++QedSaveDeleteEntered;while(QedSaveHoldDelete)ExecYield();
    return QedSavingOrdinaryDelete(name);
}
