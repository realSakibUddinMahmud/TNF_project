# Sample program for 23-bit single-cycle MIPS-like CPU
# Exercises: add, andi, slti, srl, sw/lw, bne, jmp, nop

        andi r1, r0, 0xFF     # r1 = 0
        add  r2, r1, r1       # r2 = 0
        slti r3, r0, 1        # r3 = 1
        srl  r4, r3, 1        # r4 = 0
        sw   r3, 0(r0)        # MEM[0] = 1
        lw   r5, 0(r0)        # r5 = 1
        bne  r3, r5, not_taken
        nop                   # delay slot not modeled; just a NOP
not_taken:
        or   r6, r3, r4       # r6 = 1
        sub  r7, r6, r3       # r7 = 0
        jmp  end
        add  r8, r0, r0       # filler
end:
        nop