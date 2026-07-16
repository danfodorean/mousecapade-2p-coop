"""Empirical bank-0 tile audit: run each screen loader with a CNROM+PPU shim
and record every tile the game actually writes to a nametable."""
from nes_fast import NES, Halt

ROM = 'Mickey_Mousecapade__USA_.nes'
CHR = open(ROM,'rb').read()[0x10+0x8000:]

def make(site):
    n = NES(ROM)
    st = {'t':0,'v':0,'latch':0,'buf':0,'inc':1,'bank':0,'writes':[],'reads':0}
    orig_rd, orig_wr = n.rd, n.wr
    def rd(a):
        a &= 0xFFFF
        if 0x2000 <= a < 0x4000:
            r = a & 7
            if r == 2:
                st['latch'] = 0          # reading $2002 resets the address latch
                return orig_rd(a)
            if r == 7:
                addr = st['v'] & 0x3FFF
                out = st['buf']
                st['buf'] = CHR[st['bank']*0x2000 + addr] if addr < 0x2000 else 0
                st['v'] = (st['v'] + st['inc']) & 0xFFFF
                st['reads'] += 1
                return out
        return orig_rd(a)
    def wr(a, v):
        a &= 0xFFFF; v &= 0xFF
        if 0x2000 <= a < 0x4000:
            r = a & 7
            if r == 0:
                st['inc'] = 32 if (v & 4) else 1
            elif r == 6:
                if st['latch'] == 0:
                    st['t'] = ((v << 8) | (st['t'] & 0x00FF)) & 0xFFFF
                    st['latch'] = 1
                else:
                    st['t'] = (st['t'] & 0xFF00) | v
                    st['v'] = st['t']
                    st['latch'] = 0
            elif r == 7:
                st['writes'].append((st['v'] & 0x3FFF, v))
                st['v'] = (st['v'] + st['inc']) & 0xFFFF
            return
        if a >= 0x8000:
            st['bank'] = v & 3           # CNROM bank latch
            return
        return orig_wr(a, v)
    n.rd, n.wr = rd, wr
    n.s = 0xFD; n.push(0x7F); n.push(0xEF)
    n.pc = site
    return n, st

SITES = [(0xDD93,"title      (idx $00)"), (0xDCBC,"screen     (idx $02)"),
         (0xDB47,"screen     (idx $04)"), (0xDA42,"screen     (idx $06)"),
         (0xD84B,"sign/OCEAN (idx $08)")]

def audit(verbose=True):
    used = set()
    for site, name in SITES:
        n, st = make(site)
        try:
            for _ in range(120):
                if n.run(n.instr + 40_000, stop_in_wait=True) == 'wait':
                    n.nmi()
        except Halt:
            pass
        tiles = {v for a, v in st['writes'] if 0x2000 <= a < 0x23C0 or 0x2400 <= a < 0x27C0}
        used |= tiles
        if verbose:
            flag = "  <-- writes $C1 ('A')" if 0xC1 in tiles else ""
            print(f"{name}: {len(tiles):3d} distinct tiles{flag}")
    return used

if __name__ == '__main__':
    used = audit()
    free = sorted(t for t in range(0x100) if t not in used)
    print("\ndistinct tiles used on bank-0 screens:", len(used))
    print(f"{len(free)} never used: " + " ".join(f"${t:02X}" for t in free))
    import json; json.dump(sorted(used), open('used_tiles.json','w'))
