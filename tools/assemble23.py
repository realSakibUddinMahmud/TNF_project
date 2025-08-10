#!/usr/bin/env python3
import argparse
import re
import sys
from typing import Dict, List, Tuple

OPCODES = {
    'bne':  0b00000,
    'jmp':  0b00001,
    'sw':   0b00010,
    'srl':  0b00011,
    'andi': 0b00100,
    'add':  0b00101,
    'nop':  0b00110,
    'or':   0b00111,
    'lw':   0b01000,
    'sub':  0b01001,
    'slti': 0b01010,
}

REG_PATTERN = re.compile(r'\$?(?:r)?(\d{1,2})$', re.IGNORECASE)
LABEL_PATTERN = re.compile(r'^([A-Za-z_][\w]*)\:$')
COMMENT_PATTERN = re.compile(r'[;#].*$|//.*$')

class AsmError(Exception):
    pass

def parse_register(token: str) -> int:
    m = REG_PATTERN.match(token.strip())
    if not m:
        raise AsmError(f"Invalid register '{token}'. Use r0..r31")
    idx = int(m.group(1))
    if not (0 <= idx <= 31):
        raise AsmError(f"Register out of range '{token}'")
    return idx

def parse_imm(token: str) -> int:
    t = token.strip().lower()
    base = 10
    if t.startswith('0x'):
        base = 16
    elif t.startswith('0b'):
        base = 2
    return int(t, base)


def sign_mask(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    return value & mask


def encode_r_type(op: int, rs: int, rt: int, rd: int, shamt: int) -> int:
    if not (0 <= shamt <= 7):
        raise AsmError(f"shamt out of range 0..7: {shamt}")
    word = ((op & 0x1F) << 18) | ((rs & 0x1F) << 13) | ((rt & 0x1F) << 8) | ((rd & 0x1F) << 3) | (shamt & 0x7)
    return word


def encode_i_type(op: int, rs: int, rt: int, imm: int, signed: bool) -> int:
    if signed:
        imm = sign_mask(imm, 8)
    else:
        imm = imm & 0xFF
    word = ((op & 0x1F) << 18) | ((rs & 0x1F) << 13) | ((rt & 0x1F) << 8) | (imm & 0xFF)
    return word


def encode_j_type(op: int, addr: int) -> int:
    word = ((op & 0x1F) << 18) | (addr & 0x3FFFF)
    return word


def parse_mem_operand(token: str) -> Tuple[int, int]:
    # imm(rs)
    t = token.strip()
    m = re.match(r'^([+-]?(?:0x[0-9a-fA-F]+|0b[01_]+|\d+))\(([^)]+)\)$', t)
    if not m:
        raise AsmError(f"Invalid memory operand '{token}', expected imm(rs)")
    imm = parse_imm(m.group(1))
    rs = parse_register(m.group(2))
    return imm, rs


def clean_line(line: str) -> str:
    line = COMMENT_PATTERN.sub('', line)
    return line.strip()


def first_pass(lines: List[str]) -> Dict[str, int]:
    labels: Dict[str, int] = {}
    pc = 0
    for raw in lines:
        line = clean_line(raw)
        if not line:
            continue
        m = LABEL_PATTERN.match(line)
        if m:
            name = m.group(1)
            if name in labels:
                raise AsmError(f"Duplicate label: {name}")
            labels[name] = pc
            continue
        # otherwise, instruction line
        pc += 1
    return labels


def encode_line(line: str, labels: Dict[str, int], pc: int) -> int:
    # split label-only lines earlier; here must be instruction
    tokens = [t.strip() for t in re.split(r'[\s,]+', line) if t.strip()]
    if not tokens:
        raise AsmError("Empty instruction")
    mnemonic = tokens[0].lower()
    if mnemonic not in OPCODES:
        raise AsmError(f"Unknown opcode: {mnemonic}")
    op = OPCODES[mnemonic]

    def resolve_label_or_imm(tok: str) -> int:
        if tok in labels:
            return labels[tok]
        return parse_imm(tok)

    if mnemonic == 'nop':
        return encode_r_type(op, 0, 0, 0, 0)

    if mnemonic in ('add', 'sub', 'or'):
        # add rd, rs, rt
        if len(tokens) != 4:
            raise AsmError(f"Syntax: {mnemonic} rd, rs, rt")
        rd = parse_register(tokens[1])
        rs = parse_register(tokens[2])
        rt = parse_register(tokens[3])
        return encode_r_type(op, rs, rt, rd, 0)

    if mnemonic == 'srl':
        # srl rd, rs, shamt
        if len(tokens) != 4:
            raise AsmError("Syntax: srl rd, rs, shamt")
        rd = parse_register(tokens[1])
        rs = parse_register(tokens[2])
        shamt = parse_imm(tokens[3])
        return encode_r_type(op, rs, 0, rd, shamt)

    if mnemonic in ('andi', 'slti'):
        # andi rt, rs, imm8 (zero-extended) ; slti rt, rs, imm8 (sign-extended)
        if len(tokens) != 4:
            raise AsmError(f"Syntax: {mnemonic} rt, rs, imm8")
        rt = parse_register(tokens[1])
        rs = parse_register(tokens[2])
        imm = parse_imm(tokens[3])
        return encode_i_type(op, rs, rt, imm, signed=(mnemonic == 'slti'))

    if mnemonic in ('lw', 'sw'):
        # lw rt, imm(rs)
        if len(tokens) != 3:
            raise AsmError(f"Syntax: {mnemonic} rt, imm(rs)")
        rt = parse_register(tokens[1])
        imm, rs = parse_mem_operand(tokens[2])
        return encode_i_type(op, rs, rt, imm, signed=True)

    if mnemonic == 'bne':
        # bne rs, rt, label/offset
        if len(tokens) != 4:
            raise AsmError("Syntax: bne rs, rt, label|offset")
        rs = parse_register(tokens[1])
        rt = parse_register(tokens[2])
        target = resolve_label_or_imm(tokens[3])
        offset = target - (pc + 1)
        if not (-128 <= offset <= 127):
            raise AsmError(f"bne offset out of 8-bit range: {offset}")
        return encode_i_type(op, rs, rt, offset & 0xFF, signed=True)

    if mnemonic == 'jmp':
        # jmp label|address (18-bit)
        if len(tokens) != 2:
            raise AsmError("Syntax: jmp label|address")
        addr = resolve_label_or_imm(tokens[1])
        if not (0 <= addr <= 0x3FFFF):
            raise AsmError("jmp address requires 18-bit value (0..0x3FFFF)")
        return encode_j_type(op, addr)

    raise AsmError(f"Unhandled mnemonic: {mnemonic}")


def second_pass(lines: List[str], labels: Dict[str, int]) -> List[int]:
    out: List[int] = []
    pc = 0
    for raw in lines:
        line = clean_line(raw)
        if not line:
            continue
        if LABEL_PATTERN.match(line):
            continue
        word = encode_line(line, labels, pc)
        out.append(word & 0x7FFFFF)  # 23-bit mask
        pc += 1
    return out


def to_logisim_raw(words: List[int]) -> str:
    # Use 6-hex digits (24-bit width), mask to 23 bits
    hex_words = [f"{w:06x}" for w in words]
    # Split lines to keep them readable
    lines = ["v2.0 raw"]
    if hex_words:
        lines.append(' '.join(hex_words))
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description='Assemble 23-bit MIPS-like ISA to Logisim v2.0 raw')
    p.add_argument('input', help='Assembly source file')
    p.add_argument('-o', '--output', help='Output .hex file (Logisim v2.0 raw)')
    args = p.parse_args()

    with open(args.input, 'r') as f:
        lines = f.readlines()

    try:
        labels = first_pass(lines)
        words = second_pass(lines, labels)
    except AsmError as e:
        print(f"Assembly error: {e}", file=sys.stderr)
        sys.exit(1)

    out_text = to_logisim_raw(words)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(out_text)
    else:
        sys.stdout.write(out_text)

if __name__ == '__main__':
    main()
