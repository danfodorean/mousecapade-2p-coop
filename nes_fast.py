#!/usr/bin/env python3
"""Fast headless 6502 harness for Mickey Mousecapade menu testing.
Opcode handlers are exec-compiled closures with inlined RAM/ROM access.
"""

class Halt(Exception): pass

# (mnemonic, mode) per opcode - official set used by this game
MODES = {
 'imm': ('v = prg[pc - 0x8000] if pc >= 0x8000 else rd(pc)\npc += 1', 1),
 'zp':  ('ea = prg[pc - 0x8000] if pc >= 0x8000 else rd(pc)\npc += 1', 1),
 'zpx': ('ea = ((prg[pc - 0x8000] if pc >= 0x8000 else rd(pc)) + self.x) & 0xFF\npc += 1', 1),
 'zpy': ('ea = ((prg[pc - 0x8000] if pc >= 0x8000 else rd(pc)) + self.y) & 0xFF\npc += 1', 1),
 'abs': ('ea = (prg[pc - 0x8000] | (prg[pc - 0x7FFF] << 8)) if pc >= 0x8000 else (rd(pc) | (rd(pc+1) << 8))\npc += 2', 2),
 'abx': ('ea = (((prg[pc - 0x8000] | (prg[pc - 0x7FFF] << 8)) if pc >= 0x8000 else (rd(pc) | (rd(pc+1) << 8))) + self.x) & 0xFFFF\npc += 2', 2),
 'aby': ('ea = (((prg[pc - 0x8000] | (prg[pc - 0x7FFF] << 8)) if pc >= 0x8000 else (rd(pc) | (rd(pc+1) << 8))) + self.y) & 0xFFFF\npc += 2', 2),
 'inx': ('z = ((prg[pc - 0x8000] if pc >= 0x8000 else rd(pc)) + self.x) & 0xFF\npc += 1\nea = ram[z] | (ram[(z + 1) & 0xFF] << 8)', 1),
 'iny': ('z = prg[pc - 0x8000] if pc >= 0x8000 else rd(pc)\npc += 1\nea = ((ram[z] | (ram[(z + 1) & 0xFF] << 8)) + self.y) & 0xFFFF', 1),
}

LOAD = 'v = ram[ea & 0x7FF] if ea < 0x2000 else (prg[ea - 0x8000] if ea >= 0x8000 else rd(ea))'
STORE = '''if ea < 0x2000: ram[ea & 0x7FF] = v
else: wr(ea, v)'''

OPS = {
 # opcode: (mode, body_using_v_or_ea)
 0xA9:('imm','self.a = self.setnz(v)'), 0xA5:('zp','self.a = self.setnz(ram[ea])'),
 0xB5:('zpx','self.a = self.setnz(ram[ea])'), 0xAD:('abs',LOAD+'\nself.a = self.setnz(v)'),
 0xBD:('abx',LOAD+'\nself.a = self.setnz(v)'), 0xB9:('aby',LOAD+'\nself.a = self.setnz(v)'),
 0xA1:('inx',LOAD+'\nself.a = self.setnz(v)'), 0xB1:('iny',LOAD+'\nself.a = self.setnz(v)'),
 0xA2:('imm','self.x = self.setnz(v)'), 0xA6:('zp','self.x = self.setnz(ram[ea])'),
 0xB6:('zpy','self.x = self.setnz(ram[ea])'), 0xAE:('abs',LOAD+'\nself.x = self.setnz(v)'),
 0xBE:('aby',LOAD+'\nself.x = self.setnz(v)'),
 0xA0:('imm','self.y = self.setnz(v)'), 0xA4:('zp','self.y = self.setnz(ram[ea])'),
 0xB4:('zpx','self.y = self.setnz(ram[ea])'), 0xAC:('abs',LOAD+'\nself.y = self.setnz(v)'),
 0xBC:('abx',LOAD+'\nself.y = self.setnz(v)'),
 0x85:('zp','ram[ea] = self.a'), 0x95:('zpx','ram[ea] = self.a'),
 0x8D:('abs','v = self.a\n'+STORE), 0x9D:('abx','v = self.a\n'+STORE),
 0x99:('aby','v = self.a\n'+STORE), 0x81:('inx','v = self.a\n'+STORE), 0x91:('iny','v = self.a\n'+STORE),
 0x86:('zp','ram[ea] = self.x'), 0x96:('zpy','ram[ea] = self.x'), 0x8E:('abs','v = self.x\n'+STORE),
 0x84:('zp','ram[ea] = self.y'), 0x94:('zpx','ram[ea] = self.y'), 0x8C:('abs','v = self.y\n'+STORE),
 0x29:('imm','self.a = self.setnz(self.a & v)'), 0x25:('zp','self.a = self.setnz(self.a & ram[ea])'),
 0x35:('zpx','self.a = self.setnz(self.a & ram[ea])'), 0x2D:('abs',LOAD+'\nself.a = self.setnz(self.a & v)'),
 0x3D:('abx',LOAD+'\nself.a = self.setnz(self.a & v)'), 0x39:('aby',LOAD+'\nself.a = self.setnz(self.a & v)'),
 0x21:('inx',LOAD+'\nself.a = self.setnz(self.a & v)'), 0x31:('iny',LOAD+'\nself.a = self.setnz(self.a & v)'),
 0x09:('imm','self.a = self.setnz(self.a | v)'), 0x05:('zp','self.a = self.setnz(self.a | ram[ea])'),
 0x15:('zpx','self.a = self.setnz(self.a | ram[ea])'), 0x0D:('abs',LOAD+'\nself.a = self.setnz(self.a | v)'),
 0x1D:('abx',LOAD+'\nself.a = self.setnz(self.a | v)'), 0x19:('aby',LOAD+'\nself.a = self.setnz(self.a | v)'),
 0x01:('inx',LOAD+'\nself.a = self.setnz(self.a | v)'), 0x11:('iny',LOAD+'\nself.a = self.setnz(self.a | v)'),
 0x49:('imm','self.a = self.setnz(self.a ^ v)'), 0x45:('zp','self.a = self.setnz(self.a ^ ram[ea])'),
 0x55:('zpx','self.a = self.setnz(self.a ^ ram[ea])'), 0x4D:('abs',LOAD+'\nself.a = self.setnz(self.a ^ v)'),
 0x5D:('abx',LOAD+'\nself.a = self.setnz(self.a ^ v)'), 0x59:('aby',LOAD+'\nself.a = self.setnz(self.a ^ v)'),
 0x41:('inx',LOAD+'\nself.a = self.setnz(self.a ^ v)'), 0x51:('iny',LOAD+'\nself.a = self.setnz(self.a ^ v)'),
 0x69:('imm','self.adc(v)'), 0x65:('zp','self.adc(ram[ea])'), 0x75:('zpx','self.adc(ram[ea])'),
 0x6D:('abs',LOAD+'\nself.adc(v)'), 0x7D:('abx',LOAD+'\nself.adc(v)'), 0x79:('aby',LOAD+'\nself.adc(v)'),
 0x61:('inx',LOAD+'\nself.adc(v)'), 0x71:('iny',LOAD+'\nself.adc(v)'),
 0xE9:('imm','self.adc(v ^ 0xFF)'), 0xE5:('zp','self.adc(ram[ea] ^ 0xFF)'), 0xF5:('zpx','self.adc(ram[ea] ^ 0xFF)'),
 0xED:('abs',LOAD+'\nself.adc(v ^ 0xFF)'), 0xFD:('abx',LOAD+'\nself.adc(v ^ 0xFF)'),
 0xF9:('aby',LOAD+'\nself.adc(v ^ 0xFF)'), 0xE1:('inx',LOAD+'\nself.adc(v ^ 0xFF)'), 0xF1:('iny',LOAD+'\nself.adc(v ^ 0xFF)'),
 0xC9:('imm','self.cmp_(self.a, v)'), 0xC5:('zp','self.cmp_(self.a, ram[ea])'),
 0xD5:('zpx','self.cmp_(self.a, ram[ea])'), 0xCD:('abs',LOAD+'\nself.cmp_(self.a, v)'),
 0xDD:('abx',LOAD+'\nself.cmp_(self.a, v)'), 0xD9:('aby',LOAD+'\nself.cmp_(self.a, v)'),
 0xC1:('inx',LOAD+'\nself.cmp_(self.a, v)'), 0xD1:('iny',LOAD+'\nself.cmp_(self.a, v)'),
 0xE0:('imm','self.cmp_(self.x, v)'), 0xE4:('zp','self.cmp_(self.x, ram[ea])'), 0xEC:('abs',LOAD+'\nself.cmp_(self.x, v)'),
 0xC0:('imm','self.cmp_(self.y, v)'), 0xC4:('zp','self.cmp_(self.y, ram[ea])'), 0xCC:('abs',LOAD+'\nself.cmp_(self.y, v)'),
 0x24:('zp','v = ram[ea]\nself.p = (self.p & 0x3D) | (v & 0xC0) | (0x02 if (self.a & v) == 0 else 0)'),
 0x2C:('abs',LOAD+'\nself.p = (self.p & 0x3D) | (v & 0xC0) | (0x02 if (self.a & v) == 0 else 0)'),
 0xE6:('zp','ram[ea] = self.setnz(ram[ea] + 1)'), 0xF6:('zpx','ram[ea] = self.setnz(ram[ea] + 1)'),
 0xEE:('abs',LOAD+'\nv = self.setnz(v + 1)\n'+STORE), 0xFE:('abx',LOAD+'\nv = self.setnz(v + 1)\n'+STORE),
 0xC6:('zp','ram[ea] = self.setnz(ram[ea] - 1)'), 0xD6:('zpx','ram[ea] = self.setnz(ram[ea] - 1)'),
 0xCE:('abs',LOAD+'\nv = self.setnz(v - 1)\n'+STORE), 0xDE:('abx',LOAD+'\nv = self.setnz(v - 1)\n'+STORE),
 0x06:('zp','v = ram[ea]\nself.p = (self.p & 0xFE) | (v >> 7)\nram[ea] = self.setnz((v << 1) & 0xFF)'),
 0x16:('zpx','v = ram[ea]\nself.p = (self.p & 0xFE) | (v >> 7)\nram[ea] = self.setnz((v << 1) & 0xFF)'),
 0x0E:('abs',LOAD+'\nself.p = (self.p & 0xFE) | (v >> 7)\nv = self.setnz((v << 1) & 0xFF)\n'+STORE),
 0x1E:('abx',LOAD+'\nself.p = (self.p & 0xFE) | (v >> 7)\nv = self.setnz((v << 1) & 0xFF)\n'+STORE),
 0x46:('zp','v = ram[ea]\nself.p = (self.p & 0xFE) | (v & 1)\nram[ea] = self.setnz(v >> 1)'),
 0x56:('zpx','v = ram[ea]\nself.p = (self.p & 0xFE) | (v & 1)\nram[ea] = self.setnz(v >> 1)'),
 0x4E:('abs',LOAD+'\nself.p = (self.p & 0xFE) | (v & 1)\nv = self.setnz(v >> 1)\n'+STORE),
 0x5E:('abx',LOAD+'\nself.p = (self.p & 0xFE) | (v & 1)\nv = self.setnz(v >> 1)\n'+STORE),
 0x26:('zp','v = ram[ea]\nc = self.p & 1\nself.p = (self.p & 0xFE) | (v >> 7)\nram[ea] = self.setnz(((v << 1) | c) & 0xFF)'),
 0x36:('zpx','v = ram[ea]\nc = self.p & 1\nself.p = (self.p & 0xFE) | (v >> 7)\nram[ea] = self.setnz(((v << 1) | c) & 0xFF)'),
 0x2E:('abs',LOAD+'\nc = self.p & 1\nself.p = (self.p & 0xFE) | (v >> 7)\nv = self.setnz(((v << 1) | c) & 0xFF)\n'+STORE),
 0x3E:('abx',LOAD+'\nc = self.p & 1\nself.p = (self.p & 0xFE) | (v >> 7)\nv = self.setnz(((v << 1) | c) & 0xFF)\n'+STORE),
 0x66:('zp','v = ram[ea]\nc = self.p & 1\nself.p = (self.p & 0xFE) | (v & 1)\nram[ea] = self.setnz((v >> 1) | (c << 7))'),
 0x76:('zpx','v = ram[ea]\nc = self.p & 1\nself.p = (self.p & 0xFE) | (v & 1)\nram[ea] = self.setnz((v >> 1) | (c << 7))'),
 0x6E:('abs',LOAD+'\nc = self.p & 1\nself.p = (self.p & 0xFE) | (v & 1)\nv = self.setnz((v >> 1) | (c << 7))\n'+STORE),
 0x7E:('abx',LOAD+'\nc = self.p & 1\nself.p = (self.p & 0xFE) | (v & 1)\nv = self.setnz((v >> 1) | (c << 7))\n'+STORE),
}

BRANCHES = {0x10:'not self.p & 0x80', 0x30:'self.p & 0x80', 0x50:'not self.p & 0x40',
            0x70:'self.p & 0x40', 0x90:'not self.p & 1', 0xB0:'self.p & 1',
            0xD0:'not self.p & 2', 0xF0:'self.p & 2'}

TEMPLATE = '''def h(self):
    ram = self.ram
    prg = self.prg
    rd = self.rd
    wr = self.wr
    pc = self.pc
{body}
    self.pc = pc & 0xFFFF
'''

def _indent(s, n=4):
    return "\n".join(" " * n + line for line in s.split("\n"))

class NES:
    def __init__(self, rom_path):
        rom = open(rom_path, 'rb').read()
        self.prg = rom[0x10:0x10 + 0x8000]
        self.ram = bytearray(0x800)
        self.sram = bytearray(0x2000)
        self.pad1 = 0
        self.pad2 = 0
        self._strobe = 0
        self._sh1 = 0
        self._sh2 = 0
        self._pstat = 0
        self.a = self.x = self.y = 0
        self.s = 0xFD
        self.p = 0x24
        self.instr = 0
        self.in_nmi = False
        self.trace_hits = {}
        self.watch_exec = set()
        self._spin = 0
        self._ops = self._build()
        self.pc = self.rd(0xFFFC) | (self.rd(0xFFFD) << 8)

    def rd(self, a):
        a &= 0xFFFF
        if a < 0x2000: return self.ram[a & 0x7FF]
        if a >= 0x8000: return self.prg[a - 0x8000]
        if a < 0x4000:
            if (a & 7) == 2:
                self._pstat ^= 0xC0
                return 0x80 | (self._pstat & 0x40)
            return 0
        if a == 0x4016:
            b = (self._sh1 >> 7) & 1
            self._sh1 = ((self._sh1 << 1) | 1) & 0xFF
            return b
        if a == 0x4017:
            b = (self._sh2 >> 7) & 1
            self._sh2 = ((self._sh2 << 1) | 1) & 0xFF
            return b
        if a >= 0x6000: return self.sram[a - 0x6000]
        return 0

    def wr(self, a, v):
        a &= 0xFFFF; v &= 0xFF
        if a < 0x2000: self.ram[a & 0x7FF] = v; return
        if a >= 0x8000: return
        if a >= 0x6000: self.sram[a - 0x6000] = v; return
        if a == 0x4016:
            if v & 1:
                self._sh1 = self.pad1; self._sh2 = self.pad2
            self._strobe = v & 1
            return
        return

    def setnz(self, v):
        v &= 0xFF
        self.p = (self.p & 0x7D) | (v & 0x80) | (0x02 if v == 0 else 0)
        return v

    def adc(self, v):
        r = self.a + v + (self.p & 1)
        self.p = (self.p & 0xBE) | (1 if r > 0xFF else 0) | (0x40 if (~(self.a ^ v) & (self.a ^ r) & 0x80) else 0)
        self.a = self.setnz(r & 0xFF)

    def cmp_(self, r, v):
        self.p = (self.p & 0xFE) | (1 if r >= v else 0)
        self.setnz((r - v) & 0xFF)

    def push(self, v): self.ram[0x100 + self.s] = v & 0xFF; self.s = (self.s - 1) & 0xFF
    def pop(self): self.s = (self.s + 1) & 0xFF; return self.ram[0x100 + self.s]

    def nmi(self):
        self.push(self.pc >> 8); self.push(self.pc & 0xFF); self.push(self.p & ~0x10)
        self.p |= 0x04
        self.pc = self.rd(0xFFFA) | (self.rd(0xFFFB) << 8)
        self.in_nmi = True

    def _build(self):
        ops = [None] * 256
        env = {}
        for op, (mode, body) in OPS.items():
            fetch, _ = MODES[mode]
            src = TEMPLATE.format(body=_indent(fetch + "\n" + body))
            g = {}
            exec(src, g)
            ops[op] = g['h']
        for op, cond in BRANCHES.items():
            src = TEMPLATE.format(body=_indent(
                "off = prg[pc - 0x8000] if pc >= 0x8000 else rd(pc)\npc += 1\n"
                f"if {cond}: pc += off - 256 if off > 127 else off"))
            g = {}
            exec(src, g)
            ops[op] = g['h']
        def mk(f):
            return f
        def imp(name, fn):
            ops[name] = fn
        def h_nop(self): pass
        imp(0xEA, h_nop)
        def h_brk(self): raise Halt(f"BRK at ${(self.pc - 1) & 0xFFFF:04X}")
        imp(0x00, h_brk)
        def h_jmp(self):
            pc = self.pc
            self.pc = (self.prg[pc - 0x8000] | (self.prg[pc - 0x7FFF] << 8)) if pc >= 0x8000 else (self.rd(pc) | (self.rd(pc + 1) << 8))
        imp(0x4C, h_jmp)
        def h_jmpi(self):
            pc = self.pc
            p = (self.prg[pc - 0x8000] | (self.prg[pc - 0x7FFF] << 8)) if pc >= 0x8000 else (self.rd(pc) | (self.rd(pc + 1) << 8))
            self.pc = self.rd(p) | (self.rd((p & 0xFF00) | ((p + 1) & 0xFF)) << 8)
        imp(0x6C, h_jmpi)
        def h_jsr(self):
            pc = self.pc
            t = (self.prg[pc - 0x8000] | (self.prg[pc - 0x7FFF] << 8)) if pc >= 0x8000 else (self.rd(pc) | (self.rd(pc + 1) << 8))
            r = pc + 1
            self.push(r >> 8); self.push(r & 0xFF)
            self.pc = t
        imp(0x20, h_jsr)
        def h_rts(self): self.pc = ((self.pop() | (self.pop() << 8)) + 1) & 0xFFFF
        imp(0x60, h_rts)
        def h_rti(self):
            self.p = (self.pop() | 0x20) & ~0x10
            self.pc = self.pop() | (self.pop() << 8)
            self.in_nmi = False
        imp(0x40, h_rti)
        def h_pha(self): self.push(self.a)
        imp(0x48, h_pha)
        def h_pla(self): self.a = self.setnz(self.pop())
        imp(0x68, h_pla)
        def h_php(self): self.push(self.p | 0x30)
        imp(0x08, h_php)
        def h_plp(self): self.p = (self.pop() | 0x20) & ~0x10
        imp(0x28, h_plp)
        for op, expr in [(0x18,'self.p &= ~1'),(0x38,'self.p |= 1'),(0x58,'self.p &= ~4'),
                         (0x78,'self.p |= 4'),(0xB8,'self.p &= ~0x40'),(0xD8,'self.p &= ~8'),(0xF8,'self.p |= 8'),
                         (0xAA,'self.x = self.setnz(self.a)'),(0xA8,'self.y = self.setnz(self.a)'),
                         (0x8A,'self.a = self.setnz(self.x)'),(0x98,'self.a = self.setnz(self.y)'),
                         (0xBA,'self.x = self.setnz(self.s)'),(0x9A,'self.s = self.x'),
                         (0xE8,'self.x = self.setnz(self.x + 1)'),(0xC8,'self.y = self.setnz(self.y + 1)'),
                         (0xCA,'self.x = self.setnz(self.x - 1)'),(0x88,'self.y = self.setnz(self.y - 1)'),
                         (0x0A,'self.p = (self.p & 0xFE) | (self.a >> 7)\n    self.a = self.setnz((self.a << 1) & 0xFF)'),
                         (0x4A,'self.p = (self.p & 0xFE) | (self.a & 1)\n    self.a = self.setnz(self.a >> 1)'),
                         (0x2A,'c = self.p & 1\n    self.p = (self.p & 0xFE) | (self.a >> 7)\n    self.a = self.setnz(((self.a << 1) | c) & 0xFF)'),
                         (0x6A,'c = self.p & 1\n    self.p = (self.p & 0xFE) | (self.a & 1)\n    self.a = self.setnz((self.a >> 1) | (c << 7))')]:
            g = {}
            exec(f"def h(self):\n    {expr}\n", g)
            imp(op, g['h'])
        return ops

    def step(self):
        pc = self.pc
        if pc in self.watch_exec:
            self.trace_hits[pc] = self.trace_hits.get(pc, 0) + 1
        op = self.prg[pc - 0x8000] if pc >= 0x8000 else self.rd(pc)
        self.pc = (pc + 1) & 0xFFFF
        self.instr += 1
        h = self._ops[op]
        if h is None:
            raise Halt(f"illegal opcode ${op:02X} at ${pc:04X}")
        h(self)

    def run(self, max_instr, nmi_every=2000, until_pc=None, stop_in_wait=False):
        last_nmi = self.instr
        step = self.step
        while self.instr < max_instr:
            pc = self.pc
            if until_pc is not None and pc == until_pc:
                return 'hit'
            in_nmi = self.in_nmi
            if not in_nmi and (pc == 0x8128 or (pc == 0x81F3 and self.ram[0x5F])):
                self._spin += 1
                if self._spin >= 3:
                    self._spin = 0
                    if stop_in_wait:
                        return 'wait'
                    self.nmi()
                    last_nmi = self.instr
            else:
                if in_nmi:
                    if pc == 0x8037:
                        self.x = 1
                        self.y = 1
                else:
                    if pc != 0x812A and pc != 0x81F5:
                        self._spin = 0
                    if self.instr - last_nmi > nmi_every:
                        self.nmi()
                        last_nmi = self.instr
            step()
        return 'budget'

BTN = dict(A=0x80, B=0x40, SELECT=0x20, START=0x10, UP=0x08, DOWN=0x04, LEFT=0x02, RIGHT=0x01)
