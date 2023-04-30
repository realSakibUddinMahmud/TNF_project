


Data in instruction:
clk 1:	0		none, initial
clk 2:	28210000	Lw r1, 0(r1)
clk 3:	28420001 	Lw r2, 1(r2)
clk 4:	221820 		Add r3, r1,r2
clk 5:	30630002 	Sw r3, 2(r3)
clk 6:	0 		none, to Store in cache
clk 7:	222022 		Sup r4,r1,r2
clk 8:	30840003	Sw r4,3(r4)
clk 9:	0 		none, to Store in cache
clk 10:	20a1000a 	Addi r5,r1,10
clk 11:	30a60020 	Sw r5,4(r5)
clk 12:	0 		none, to Store in cache
clk 13:	34220002 	Beq r1,r2,2
clk 14:	8000002		J 2