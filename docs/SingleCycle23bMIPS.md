### Single-Cycle 23-Bit MIPS (Logisim Evolution Build Guide)

This guide describes how to implement a single-cycle 23-bit MIPS-like CPU in Logisim Evolution using the provided ISA and a 32×23-bit register file.

- Data path width: 23 bits
- Register file: 32 registers, 23 bits each; `$r0` (aka `$zero`) is hardwired to 0
- Instruction width: 23 bits
- Word-addressed memories (PC increments by 1)

### Instruction Formats (bit ranges)
- R-type: op[22:18] | rs[17:13] | rt[12:8] | rd[7:3] | shamt[2:0]
- I-type: op[22:18] | rs[17:13] | rt[12:8] | imm[7:0]
- J-type:  op[22:18] | address[17:0]

### Opcode Table
- bne  (I): 00000 – Branch if `rs != rt`
- jmp  (J): 00001 – Unconditional jump
- sw   (I): 00010 – Store word to memory
- srl  (R): 00011 – Shift right logical by `shamt`
- andi (I): 00100 – Bitwise AND with zero-extended immediate
- add  (R): 00101 – Add `rs + rt` → `rd`
- nop  (R): 00110 – No operation (no writes, no mem, no branch)
- or   (R): 00111 – Bitwise OR `rs | rt` → `rd`
- lw   (I): 01000 – Load word from memory
- sub  (R): 01001 – Subtract `rs - rt` → `rd`
- slti (I): 01010 – Set `rt = (rs < imm_signed) ? 1 : 0`

### Block-Level Components
- PC: 23-bit register; next PC selected by jump/branch/seq logic; increments by 1 each instruction
- Instruction ROM: width 23, addressed by `PC` (word addressed)
- Register File: 32×23 with 2 read ports and 1 write port (see next section)
- ALU: 23-bit; supports operations: ADD, SUB, OR, AND (for andi), SLT (for slti)
- Shifter: 23-bit logical right; shift amount `shamt[2:0]`
- Data Memory: 23-bit width; word-addressed; used by `lw`/`sw`
- Sign-extender: 8→23 (for bne, lw, sw, slti)
- Zero-extender: 8→23 (for andi)
- Comparator/Zero flag: from ALU SUB result; used by `bne`

### 32×23 Register File (RegisterFile.circ)
- Place 32 `Register` components (Memory library); set Data Bits = 23
- Write decoder: 5-to-32 `Decoder` (Plexers); `WriteReg[4:0]` → select lines
- For i in 0..31: `enable_i = RegWrite AND decoder_out_i`
- Wire `WriteData[22:0]` to D of all 32 registers
- Two read ports: two 32-to-1 `Multiplexer`s; Select Bits=5, Data Bits=23
  - Connect each register `Q` to both multiplexers inputs 0..31
  - `ReadReg1` → MUX A select; `ReadReg2` → MUX B select
- `$r0` hardwire to zero:
  - Do NOT connect `enable_0` (leave disabled / grounded)
  - Feed input 0 of both read multiplexers from a `Constant(23'h000000)` instead of reg0.Q

Port mapping for CPU:
- ReadReg1=rs, ReadReg2=rt, WriteReg=RegDst?rd:rt; WriteData comes from MemToReg?DataMemOut:ALU/ShifterOut

### Datapath Wiring
- PC path:
  - `PCPlus1 = PC + 1`
  - Branch target: `PCBranch = PCPlus1 + SignExtImm` (no left shift; word-addressed)
  - Jump target: `PCJump = { PCPlus1[22:18], address[17:0] }`
  - NextPC select (priority): `Jump ? PCJump : (BranchTaken ? PCBranch : PCPlus1)`
- Instruction decode fields:
  - op = instr[22:18]
  - rs = instr[17:13], rt = instr[12:8]
  - rd = instr[7:3] (R-type only)
  - shamt = instr[2:0] (R-type srl)
  - imm8 = instr[7:0] (I-type)
- Immediate extension:
  - `immZ = ZeroExtend(imm8)` for andi
  - `immS = SignExtend(imm8)` for bne, lw, sw, slti
- ALU/Operand select:
  - `srcA = ReadData1`
  - `srcB = ALUSrc ? (IsAndi ? immZ : immS) : ReadData2`
- Shifter path (srl only):
  - `ShiftOut = srcA >> shamt`
- Result select to writeback:
  - `ALUOrShift = UseShamt ? ShiftOut : ALUOut`
  - `WriteData = MemToReg ? DataMemOut : ALUOrShift`
- Register write address:
  - `WriteReg = RegDst ? rd : rt`
- Branch decision:
  - For bne: compute `ALUOut = srcA - srcB`, set `Zero = (ALUOut == 0)`
  - `BranchTaken = Branch AND (NOT Zero)`

### Control Signals
- RegDst (R=1, I=0)
- RegWrite
- ALUSrc (I-type using immediate, lw/sw/andi/slti = 1)
- MemRead, MemWrite
- MemToReg (lw=1)
- Branch (bne)
- Jump (jmp)
- ZeroExtendImm (for andi)
- UseShamt (for srl; selects shifter output)
- ALUOp[2:0] (choose ALU function)

### Control Truth Table
Use this as the main decoder mapping from opcode to control signals. ALUOp encodes the ALU’s function; shifter bypasses ALU when `UseShamt=1`.

| op     | Instr | RegDst | RegWrite | ALUSrc | MemRead | MemWrite | MemToReg | Branch | Jump | ZeroExtImm | UseShamt | ALUOp   |
|--------|-------|--------|----------|--------|---------|----------|----------|--------|------|------------|----------|---------|
| 00000  | bne   |   X    |    0     |   0    |    0    |    0     |    X     |   1    |  0   |     0      |    0     | SUB     |
| 00001  | jmp   |   X    |    0     |   X    |    0    |    0     |    X     |   0    |  1   |     X      |    0     | N/A     |
| 00010  | sw    |   X    |    0     |   1    |    0    |    1     |    X     |   0    |  0   |     0      |    0     | ADD     |
| 00011  | srl   |   1    |    1     |   0    |    0    |    0     |    0     |   0    |  0   |     0      |    1     | OR/ADD* |
| 00100  | andi  |   0    |    1     |   1    |    0    |    0     |    0     |   0    |  0   |     1      |    0     | AND     |
| 00101  | add   |   1    |    1     |   0    |    0    |    0     |    0     |   0    |  0   |     0      |    0     | ADD     |
| 00110  | nop   |   X    |    0     |   X    |    0    |    0     |    X     |   0    |  0   |     X      |    0     | NOP     |
| 00111  | or    |   1    |    1     |   0    |    0    |    0     |    0     |   0    |  0   |     0      |    0     | OR      |
| 01000  | lw    |   0    |    1     |   1    |    1    |    0     |    1     |   0    |  0   |     0      |    0     | ADD     |
| 01001  | sub   |   1    |    1     |   0    |    0    |    0     |    0     |   0    |  0   |     0      |    0     | SUB     |
| 01010  | slti  |   0    |    1     |   1    |    0    |    0     |    0     |   0    |  0   |     0      |    0     | SLT     |

Notes:
- X means “don’t care” for that instruction
- For `srl`, ALUOp can be arbitrary because `UseShamt=1` chooses the shifter result
- `SLT` computes signed less-than. Implementation options below.

### ALU Control Encoding (example)
Define a compact 3-bit ALUOp and map it to functions:
- 000: ADD
- 001: SUB
- 010: AND
- 011: OR
- 100: SLT

Drive these from the main decoder directly based on opcode. For `srl`, ALUOp can be 000.

### Implementing SLTI (Signed Compare)
- Option A (preferred): dedicated signed comparator
  - `LessThan = (srcA[22] != srcB[22]) ? srcA[22] : (SUB(srcA, srcB).Sign)`
  - Result is 1 if `srcA < srcB` else 0. Zero-extend to 23 bits
- Option B: Use ALU subtract and derive sign/overflow. If complexity is high in Logisim, Option A’s small comparator is simpler.

### Memory Interface (lw/sw)
- Address = `rs + SignExtImm`
- Word-addressed; no left shift
- `lw`: `DataMemOut` → `WriteData` when `MemToReg=1`
- `sw`: write `ReadData2` to memory

### PC/Control Edge Behavior
- All state (PC, register file) updates on rising edge of `CLK`
- Memories: use synchronous write for data memory; ROM/Instruction memory combinational read is fine

### NOP Behavior
- Ensure NOP writes no register or memory and does not branch/jump
- You can implement NOP by forcing `RegWrite=0`, `MemRead=0`, `MemWrite=0`, `Branch=0`, `Jump=0`

### Step-by-Step Build Order (recommended)
1) Register File (`RegisterFile.circ`) per spec above; verify reads/writes and `$zero`
2) PC and `PC+1` adder; tie PC input to `PCPlus1`; step clock to verify counting
3) Instruction ROM and field splitters; probe fields to ensure correctness
4) ALU + shifter; add/and/or/sub paths; verify with constants
5) Immediate extenders and ALUSrc multiplexer
6) Writeback multiplexer (`MemToReg`) and `RegDst` select; complete register write path
7) Data memory; hook lw/sw via `MemRead`, `MemWrite`
8) Branch/jump path and next-PC selection; verify `bne` and `jmp`
9) Control unit: implement the table above; use a ROM-based decoder or gates
10) Full integration and test

### Minimal Test Program Ideas
- Arithmetic and writeback:
  - `add r1, r0, r0` (expect r1=0)
  - `andi r2, r0, 0xFF` (expect r2=0x00)
  - `slti r3, r0, 1` (expect r3=1)
- Shift:
  - `srl r4, r3, shamt=1` (expect r4=0)
- Memory:
  - `sw r3, 0(r0)` then `lw r5, 0(r0)` (expect r5=1)
- Control flow:
  - `bne r3, r5, +2` (not taken), then `jmp label`

Encode per the bit layout and load into Instruction ROM via Logisim’s contents editor.

### Notes and Tips
- Keep bus widths consistent at 23 bits; use splitters to manage fields
- For `$r0`, forcing MUX input 0 to constant zero ensures all reads of register 0 yield 0 regardless of register 0 contents
- Use labeled wires and buses to keep the schematic readable
- Validate each instruction path independently before running full programs

---
This doc specifies all wiring, control, and behavior needed to convert the project into a single-cycle 23-bit MIPS per the provided ISA. Use it to assemble the top-level CPU circuit and to guide testing.