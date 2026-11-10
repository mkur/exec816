; MIT fixture: a nonreturning callee may borrow every preserved pseudo-register.
              .section farcode,text
              .public ClobberAndJump
              .extern _Dp,longjmp,setjmp
ClobberAndJump:
              stz dp:.tiny(_Dp+8)
              stz dp:.tiny(_Dp+10)
              stz dp:.tiny(_Dp+12)
              stz dp:.tiny(_Dp+14)
              lda ##1
              jmp long:longjmp
              .public CheckJumpRegisters
CheckJumpRegisters:
              pei dp:.tiny(_Dp+8)
              pei dp:.tiny(_Dp+10)
              pei dp:.tiny(_Dp+12)
              pei dp:.tiny(_Dp+14)
              lda ##0x1357
              sta dp:.tiny(_Dp+8)
              lda ##0x2468
              sta dp:.tiny(_Dp+10)
              lda ##0x5a3c
              sta dp:.tiny(_Dp+12)
              lda ##0xa5c3
              sta dp:.tiny(_Dp+14)
              jsl long:setjmp
              cmp ##0
              bne check_jump_return
              jmp long:ClobberAndJump
check_jump_return:
              lda dp:.tiny(_Dp+8)
              cmp ##0x1357
              bne check_jump_bad
              lda dp:.tiny(_Dp+10)
              cmp ##0x2468
              bne check_jump_bad
              lda dp:.tiny(_Dp+12)
              cmp ##0x5a3c
              bne check_jump_bad
              lda dp:.tiny(_Dp+14)
              cmp ##0xa5c3
              bne check_jump_bad
              lda ##1
              bra check_jump_restore
check_jump_bad:
              lda ##0
check_jump_restore:
              ply
              sty dp:.tiny(_Dp+14)
              ply
              sty dp:.tiny(_Dp+12)
              ply
              sty dp:.tiny(_Dp+10)
              ply
              sty dp:.tiny(_Dp+8)
              rtl
              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
