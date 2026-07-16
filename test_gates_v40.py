from nes_fast import NES, Halt

SENT = 0x7FF0  # sentinel return address (SRAM area, harmless)

def call(n, addr, mode, setup=None, carry=None, budget=20000, watch=()):
    n.ram[0x7FF] = mode
    n.s = 0xFD
    r = SENT - 1
    n.push(r >> 8); n.push(r & 0xFF)
    if setup: setup(n)
    if carry is not None:
        n.p = (n.p & ~1) | (1 if carry else 0)
    n.pc = addr
    n.trace_hits.clear()
    n.watch_exec = set(watch)
    for _ in range(budget):
        if n.pc == SENT:
            return 'ret'
        for w in watch:
            if n.trace_hits.get(w):
                pass
        try:
            n.step()
        except Halt as e:
            return 'halt:%s' % e
    return 'budget'

def hits(n, a): return n.trace_hits.get(a, 0)

n = NES('mousecapade_2p_v40.nes')
P = f = 0
def chk(name, cond):
    global P, f
    P += cond; f += (not cond)
    print(("PASS" if cond else "FAIL"), name)

# ---- GateAnimVal $DE34 ----
def s(nn): nn.ram[0x2D] = 5; nn.ram[0x37] = 0xEE
r = call(n, 0xDE34, 0, s)
chk("AnimVal 1P: $37=$2D", r == 'ret' and n.ram[0x37] == 5)
r = call(n, 0xDE34, 1, s)
chk("AnimVal 2P: $37=0", r == 'ret' and n.ram[0x37] == 0)

# ---- GateYconv $950B ----
r = call(n, 0x950B, 1, watch=(0xADDF,))
chk("Yconv 2P: no $ADDF, returns", r == 'ret' and hits(n, 0xADDF) == 0)
r = call(n, 0x950B, 0, watch=(0xADDF,), budget=40000)
chk("Yconv 1P: $ADDF executed", hits(n, 0xADDF) == 1)

# ---- GateAnchor $FFCB ----
r = call(n, 0xFFCB, 1, watch=(0xAF46,))
chk("Anchor 2P: returns w/o $AF46", r == 'ret' and hits(n, 0xAF46) == 0)
r = call(n, 0xFFCB, 0, watch=(0xAF46, 0xAD56), budget=40000)
chk("Anchor 1P: $AF46 executed", hits(n, 0xAF46) == 1)

# ---- GateSwim $DE1C ----
def far(nn): nn.ram[0x7D] = 0x80; nn.ram[0x7E] = 0x10
r = call(n, 0xDE1C, 1, far, watch=(0xFF22, 0xADB1))
chk("Swim 2P: MinnieSwim entered", hits(n, 0xFF22) == 1 and hits(n, 0xADB1) == 0)
r = call(n, 0xDE1C, 0, far, watch=(0xFF22, 0xADB1), budget=40000)
chk("Swim 1P far: vanilla $ADB1 convergence", hits(n, 0xADB1) == 1 and hits(n, 0xFF22) == 0)
def near(nn): nn.ram[0x7D] = 0x50; nn.ram[0x7E] = 0x4C
r = call(n, 0xDE1C, 0, near, watch=(0xADB1,))
chk("Swim 1P near: no convergence, returns", r == 'ret' and hits(n, 0xADB1) == 0)

# ---- Coll2 $DDED ----
r = call(n, 0xDDED, 0, carry=True, watch=(0x964F, 0x95E6))
chk("Coll2 1P miss: immediate return", r == 'ret' and hits(n, 0x964F) == 0 and hits(n, 0x95E6) == 0)
def st(nn): nn.ram[0x7FA % 0x800] = 0  # $07FA
def st2(nn):
    nn.ram[0x7FA] = 0; nn.ram[0x82] = 0
    nn.ram[0x7E] = 0x40; nn.ram[0x80] = 0x40
r = call(n, 0xDDED, 1, st2, carry=True, watch=(0x95E6,), budget=40000)
chk("Coll2 2P miss: Minnie box check runs", hits(n, 0x95E6) == 1)
r = call(n, 0xDDED, 0, carry=False, watch=(0x964F,), budget=40000)
chk("Coll2 1P hit: touch dispatch runs", hits(n, 0x964F) == 1)

# ---- GateMinnieIn via site $99C0 ----
def mi(nn):
    nn.ram[0x58] = 0x37; nn.ram[0x59] = 0x91
    nn.ram[0x710] = 0x25  # ring index -> X = 5
r = call(n, 0x99C0, 1, mi, watch=(0x99C8,))
chk("MinnieIn 2P: $5A=pad2, no recorder", r == 'ret' and n.ram[0x5A] == 0x37 and hits(n, 0x99C8) == 0)
n.ram[0x7FF] = 0
n.s = 0xFD; n.push((SENT-1) >> 8); n.push((SENT-1) & 0xFF)
mi(n); n.pc = 0x99C0
ok = False
for _ in range(200):
    if n.pc == 0x99C8:
        ok = (n.x == 5 and n.a == 0x91)
        break
    n.step()
chk("MinnieIn 1P: reaches $99C8 with X=ring, A=$59", ok)

# ---- GateOwl via site $C264 ----
def ow(nn): nn.ram[0x7FA] = 0; nn.ram[0xF0] = 0
r = call(n, 0xC264, 0, ow, watch=(0x967F,))
chk("Owl 1P: kidnap ($07FA=2, $F0=$90), no damage call",
    r == 'ret' and n.ram[0x7FA] == 2 and n.ram[0xF0] == 0x90 and hits(n, 0x967F) == 0)
r = call(n, 0xC264, 1, ow, watch=(0x967F,), budget=60000)
chk("Owl 2P: damage call + $F0=$10", hits(n, 0x967F) == 1 and n.ram[0xF0] == 0x10)

# ---- GateJump2 $FEF8 ----
def j1(nn): nn.ram[0x106] = 1; nn.ram[0x34] = 9; nn.ram[0x00] = 0
r = call(n, 0xFEF8, 1, j1)
chk("Jump2 2P: JumpHold sets $00", r == 'ret' and n.ram[0x00] == 1)
def j2(nn): nn.ram[0x106] = 0; nn.ram[0x34] = 9; nn.ram[0x00] = 0
r = call(n, 0xFEF8, 1, j2)
chk("Jump2 2P: idle A -> $00 untouched", r == 'ret' and n.ram[0x00] == 0)
def j3(nn): nn.ram[0x91] = 0; nn.ram[0x34] = 9; nn.ram[0x00] = 0
r = call(n, 0xFEF8, 0, j3)
chk("Jump2 1P: vanilla $91=0 high -> $00=1", r == 'ret' and n.ram[0x00] == 1)
def j4(nn): nn.ram[0x91] = 5; nn.ram[0x00] = 0
r = call(n, 0xFEF8, 0, j4)
chk("Jump2 1P: vanilla $91=5 -> DEC to 4, $00 untouched",
    r == 'ret' and n.ram[0x91] == 4 and n.ram[0x00] == 0)

# ---- DoorEither' $838B ----
def d_base(nn):
    nn.ram[0x31] = 0; nn.ram[0x34] = 0
    nn.ram[0x3C] = 0x50; nn.ram[0x3F] = 0x07
    nn.ram[0x7D] = 0x20; nn.ram[0x7F] = 0x60; nn.ram[0x80] = 0x60
    nn.ram[0x79] = 0; nn.ram[0x2F] = 0
    nn.ram[0x59] = 0; nn.ram[0x5A] = 0; nn.ram[0x7E] = 0x20
def d_mick(nn):
    d_base(nn); nn.ram[0x59] = 0x08; nn.ram[0x7D] = 0x52
def d_minn(nn):
    d_base(nn); nn.ram[0x5A] = 0x08; nn.ram[0x7E] = 0x52
r = call(n, 0x838B, 0, d_mick, budget=60000)
chk("Door 1P Mickey Up+near: opens", r == 'ret' and n.ram[0x79] == 0xF0 and n.ram[0x2F] == 0x07)
r = call(n, 0x838B, 0, d_minn, budget=60000)
chk("Door 1P Minnie Up+near: gated off", r == 'ret' and n.ram[0x79] == 0x00)
r = call(n, 0x838B, 1, d_minn, budget=60000)
chk("Door 2P Minnie Up+near: opens", r == 'ret' and n.ram[0x79] == 0xF0)
r = call(n, 0x838B, 1, d_base, budget=60000)
chk("Door 2P no Up: closed", r == 'ret' and n.ram[0x79] == 0x00)

# ---- NearObj $83CD ----
def n_base(nn):
    nn.ram[0x3C] = 0x50; nn.ram[0x3D] = 0x60
    nn.ram[0x7D] = 0x00; nn.ram[0x7F] = 0x00   # Mickey far
    nn.ram[0x7E] = 0x52; nn.ram[0x80] = 0x62   # Minnie close
r = call(n, 0x83CD, 0, n_base, budget=60000)
chk("NearObj 1P Minnie-close: reports FAR (C=1)", r == 'ret' and (n.p & 1) == 1)
r = call(n, 0x83CD, 1, n_base, budget=60000)
chk("NearObj 2P Minnie-close: reports CLOSE (C=0)", r == 'ret' and (n.p & 1) == 0)
def n_mick(nn):
    n_base(nn); nn.ram[0x7D] = 0x52; nn.ram[0x7F] = 0x62
r = call(n, 0x83CD, 0, n_mick, budget=60000)
chk("NearObj 1P Mickey-close: CLOSE (C=0)", r == 'ret' and (n.p & 1) == 0)

print("\n%d passed, %d failed" % (P, f))
