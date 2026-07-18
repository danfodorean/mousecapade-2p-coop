"""v33 gate pack: ONE PLAYER mode restores vanilla behavior via $07FF gates.

Space map (all verified dead or freed):
  $838B-$8403  DoorEither' (121)   original blob + two 6-byte internal gates
  $8404-$8434  MENU' (49)          MenuInput $8404 / Init $842A (relocated, no pad)
  $DDED-$DE1B  Coll2 (47)          relocated NewCollision + 1P gate (Mickey-only)
  $DE1C-$DE33  GateSwim (24)       1P: vanilla ocean X-convergence
  $DE34-$DE3E  GateAnimVal (11)    1P: $37=$2D (LSR trick)
  $DE3F-$DE54  StartRandom (22)    Start path + random start SFX ($06/$0A)
  $DE55-$DE67  GateMinnieIn (19)   1P: input recorder + JMP $99C8
  $DE68-$DE7B  GateOwl (20)        1P: kidnap restored
  $FEF8-$FF20  GateJump2 (41)      2P: JumpHold (relocated); 1P: vanilla $91 logic
  $FFCB-$FFDA  GateAnchor (16)     1P: JSR $AF46 / BCC restored
  $950B-$9512  GateYconv (8)       1P: JSR $ADDF (BNE -> RTS at $9506)
Dead regions: demo timeout code+tables $DDED-$DE3E, cheat body $DE4C-$DE62,
demo helper+table $DE63-$DE7B. v38 repacks $DE3F-$DE7B (61B): the live Start
path is rewritten in place and the two gates slide to the end, merging the
$DE5F-$DE62 and $DE77-$DE7B gaps into contiguous room for the random SFX.
Both gates are position-independent (internal branches relative, external JMPs
absolute) and each has exactly one caller ($99C0 / $C264), both re-pointed.
"""

def _hx(s):
    return bytes.fromhex(s.replace(" ", "").replace("\n", ""))

# ---------- DoorEither' with internal 1P gates ----------
DOOR_EITHER_V33 = _hx(
    "A531 0534 D03B"        # 838B grounded check; BNE .rts (+6 for gate1)
    "A559 2908 F00C"        # 8391 Mickey Up? BEQ .gate1 (target unchanged)
    "A57D 38 E53C 20AB81"   # 8397 |MickeyX - door|
    "C908 9018"             # 839F BCC .open (+6)
    "ADFF07 D001 60"        # 83A3 GATE1: 1P -> RTS (no Minnie door clause)
    "A55A 2908 F01D"        # 83A9 Minnie Up? BEQ .rts (unchanged, both shifted)
    "A57E 38 E53C 20AB81"   # 83AF |MinnieX - door|
    "C908 B011"             # 83B7 BCS .rts (unchanged)
    "A53C 857D"             # 83BB .open: snap Mickey to door
    "A580 857F"             # 83BF
    "A53F 852F"             # 83C3 door target
    "A9F0 8579"             # 83C7 Mickey enters
    "60"                    # 83CB RTS
    "60"                    # 83CC .rts: RTS
    # NearObj @ $83CD (site $B0B8 -> JMP $83CD)
    "A57D 38 E53C 20AB81"   # 83CD |MickeyX - obj|
    "C90A B00C"             # 83D5 BCS .gate2 (target unchanged)
    "A57F 38 E53D 20AB81"   # 83D9 |MickeyY - obj|
    "C90A 901D"             # 83E1 BCC .close (+6)
    "ADFF07 D001 60"        # 83E5 GATE2: 1P -> RTS (carry=1 = far)
    "A57E 38 E53C 20AB81"   # 83EB |MinnieX - obj|
    "C90A B00A"             # 83F3 BCS .far (unchanged)
    "A580 38 E53D 20AB81"   # 83F7 |MinnieY - obj|
    "C90A"                  # 83FD carry = result
    "60"                    # 83FF .far: RTS
    "18 60"                 # 8400 .close: CLC / RTS
)
assert len(DOOR_EITHER_V33) == 0x8404 - 0x838B, len(DOOR_EITHER_V33)

# ---------- MENU' (relocated, no padding) ----------
MENU_V33 = _hx(
    # MenuInput @ $8404 -- edge-detect via pressed = cur & (cur ^ prev);
    # toggle plays the star-shot SFX ($09) then queues the BG cursor packets.
    "A557 A8"               # 8404 A = cur, Y = cur
    "4D0701"                # 8407 A = cur ^ prev
    "8C0701"                # 840A prev = cur
    "2557 290C"             # 840D pressed & (Up|Down)
    "F008"                  # 8411 none -> done
    "A909 8D8001"           # 8413 star-shot SFX
    "20DBFF"                # 8418 toggle mode + queue cursor
    "A557 2910 60"          # 841B done: Start test for caller
    # Init @ $8420: vanilla init first (needs empty buffer), then mode=1 so
    # QueueCursor's toggle lands on 0 and draws the cursor. Edge-state $0107
    # self-heals on the first MenuInput call, so no explicit clear.
    "2080DE"                # 8420 JSR $DE80 (vanilla arm + present + fade)
    "A901 8DFF07"           # 8423 mode = 1 (pre-toggle)
    "4CDBFF"                # 8428 tail-jump: toggle -> 0, queue cursor
    # Packet templates @ $842B (mode*8): [addr hi, addr lo, len, tile] x2
    "22CA0101 230A0146"     # 842B TPL0: star on ONE, blank on TWO
    "22CA0146 230A0101"     # 8433 TPL1: blank on ONE, star on TWO
)
assert len(MENU_V33) == 0x843B - 0x8404, len(MENU_V33)

# StartRandom @ $DE3F -- the vanilla Start path with the SFX folded in.
# Vanilla was: LDA $5B / BNE $DDDB / INC $5B / JSR $881C / JSR $9127 / RTS.
# Frame counter $5D (INC'd every NMI) picks the sound: bit 3 flips every 8
# frames, so a human press lands on either value unpredictably.
#   A = $5D & $08  -> {$00,$08};  LSR -> {$00,$04} and clears carry (bit0 is
#   always 0, so the shift-out is 0), which makes the ADC exact: {$06,$0A}.
# Sound is stored BEFORE the fade so it starts on the press frame; the tail
# JMP $9127 replaces vanilla's JSR+RTS (its RTS returns for us) to save 1 byte.
# MinnieInput @ $AE1B -- called by CharShoot with A = $59,X (the character's own
# input) and X = character. Returns the input its shot decision should use.
#   2P            -> unchanged: each player uses their own pad.
#   1P, $BC == 3  -> A = $59, so Minnie fires on Mickey's B press. This is what
#                    vanilla did: her shot spawn sat inside Mickey's fresh-B
#                    branch, gated on both star upgrades -- she has no input of
#                    her own. The $99C0 recorder only replays Mickey's input into
#                    $5A in $74 == 0 rooms, so in the side-scrolling rooms ($74
#                    != 0, dispatched to $934E) $5A never carries B and she went
#                    silent. Reading $59 fixes both room types without touching
#                    $5A, which drives her movement (2P) and is read by the
#                    shared $59,X update code.
#   1P, $BC < 3   -> A unchanged: vanilla keeps her silent without both stars.
# No-op for Mickey: $59,X is already $59 when X = 0.
MINNIE_INPUT = (
    "ACFF07"                # AE1B LDY $07FF    ; mode
    "D008"                  # AE1E BNE $AE28    ; 2P -> keep own input
    "A4BC"                  # AE20 LDY $BC      ; 1P: star level
    "C003"                  # AE22 CPY #$03     ; both upgrades?
    "D002"                  # AE24 BNE $AE28    ; no -> stays silent (vanilla)
    "A559"                  # AE26 LDA $59      ; yes -> fire on Mickey's B
    "60"                    # AE28 RTS
)

START_RANDOM = _hx(
    "A55B"                  # DE3F LDA $5B      ; already starting?
    "D098"                  # DE41 BNE $DDDB
    "E65B"                  # DE43 INC $5B
    "A90A"                  # DE45 LDA #$0A     ; v40: fixed start SFX (was random $06/$0A)
    "8D8001"                # DE47 STA $0180    ; store BEFORE the fade -> fires on the press frame
    "201C88"                # DE4A JSR $881C
    "4C2791"                # DE4D JMP $9127
    + "FF" * 5              # DE50-DE54 spare (freed by dropping the randomiser)
)
assert len(START_RANDOM) == 0xDE55 - 0xDE3F, len(START_RANDOM)

# QueueCursor @ $FFDB (replaces DrawCursor): toggle $07FF, then copy the
# mode's 8-byte template into the $0200 draw buffer at write index $64.
# $64 is published last, so the NMI flush never sees a partial packet.
QUEUE_CURSOR = _hx(
    "ADFF07 4901 8DFF07"    # FFDB toggle mode
    "0A0A0A A8"             # FFE3 Y = mode*8
    "A664"                  # FFE7 X = buffer write index
    "B92B84"                # FFE9 loop: LDA TPL,Y
    "9D0002"                # FFEC STA $0200,X
    "E8 C8"                 # FFEF
    "98 2907 D0F3"          # FFF1 8 bytes copied?
    "8664"                  # FFF6 publish write index
    "60"                    # FFF8 RTS
)
assert len(QUEUE_CURSOR) == 0xFFF9 - 0xFFDB, len(QUEUE_CURSOR)

# ---------- Coll2 @ $DDED (relocated NewCollision + gate) ----------
COLL2 = _hx(
    "B004"                  # DDED BCS .minnie
    "204F96"                # DDEF Mickey hit -> touch dispatch
    "60"                    # DDF2 RTS
    "ADFF07 F023"           # DDF3 .minnie: GATE: 1P -> rts
    "ADFA07 D01E"           # DDF8 Minnie kidnapped/absent? skip
    "A582 C903 B018"        # DDFD state<3 gate
    "A57E 850A"             # DE03 Minnie X -> temp
    "A580 850B"             # DE07 Minnie Y -> temp
    "A908 8502"             # DE0B hitbox
    "A90C 8503"             # DE0F
    "20E695"                # DE13 box check vs same enemy
    "B003"                  # DE16 BCS .rts
    "204F96"                # DE18 hit -> touch dispatch
    "60"                    # DE1B .rts: RTS
)
assert len(COLL2) == 0xDE1C - 0xDDED, len(COLL2)

# ---------- GateSwim @ $DE1C ----------
GATE_SWIM = _hx(
    "ADFF07 D010"           # DE1C 2P -> MinnieSwim
    "A57D 38 E57E"          # DE21 vanilla: |MickeyX - MinnieX|
    "20AB81"                # DE26
    "C919 9003"             # DE29 < $19 -> done
    "20B1AD"                # DE2D vanilla X-convergence step
    "60"                    # DE30 RTS
    "4C22FF"                # DE31 .2p: JMP MinnieSwim
)
assert len(GATE_SWIM) == 0xDE34 - 0xDE1C, len(GATE_SWIM)

# ---------- GateAnimVal @ $DE34 (LSR trick: mode->C, A->0) ----------
GATE_ANIM = _hx(
    "ADFF07"                # DE34 LDA $07FF
    "4A"                    # DE37 LSR: C=mode, A=0
    "B002"                  # DE38 2P -> store 0
    "A52D"                  # DE3A 1P: vanilla $2D
    "8537"                  # DE3C STA $37
    "60"                    # DE3E RTS  (last dead byte before live $DE3F)
)
assert len(GATE_ANIM) == 0xDE3F - 0xDE34, len(GATE_ANIM)

# ---------- GateMinnieIn @ $DE55 (v38: slid +9) ----------
GATE_MINNIE_IN = _hx(
    "ADFF07 D00D"           # DE55 2P -> RTS (site code takes over)
    "6868"                  # DE5A discard return into site
    "AD1007 290F AA"        # DE5C vanilla: recorder ring index
    "A559"                  # DE62 record Mickey's merged input
    "4CC899"                # DE64 JMP $99C8 (vanilla continuation)
    "60"                    # DE67 .r: RTS
)
assert len(GATE_MINNIE_IN) == 0xDE68 - 0xDE55, len(GATE_MINNIE_IN)

# ---------- GateOwl @ $DE68 (v38: slid +5) ----------
GATE_OWL = _hx(
    "ADFF07 D00C"           # DE68 2P -> damage
    "6868"                  # DE6D discard return into site
    "A902 8DFA07"           # DE6F vanilla: kidnap Minnie
    "A990 85F0"             # DE74 vanilla: owl carry timer
    "60"                    # DE78 RTS
    "4C7F96"                # DE79 .two: JMP $967F (damage; RTS -> site tail)
)
assert len(GATE_OWL) == 0xDE7C - 0xDE68, len(GATE_OWL)

# ---------- GateJump2 @ $FEF8 (JumpHold relocated here) ----------
GATE_JUMP2 = _hx(
    "ADFF07 F010"           # FEF8 1P -> vanilla (skip 16-byte JumpHold)
    "AD0601 F00A A534 C909 9004 A901 8500 60"   # FEFD MinnieJumpHold (16)
    "A591 D00A A534 C909 9004 A901 8500 A591 F002 C691"  # FF0D vanilla 20
    "60"                    # FF21 RTS
)
assert len(GATE_JUMP2) == 0xFF22 - 0xFEF8, len(GATE_JUMP2)

# ---------- GateAnchor @ $FFCB ----------
GATE_ANCHOR = _hx(
    "ADFF07 D005"           # FFCB 2P -> RTS (site continues = compensate)
    "2046AF"                # FFD0 vanilla scroll test
    "9001"                  # FFD3 BCC .skip
    "60"                    # FFD5 .r: RTS -> $AD47
    "6868"                  # FFD6 .skip: discard return
    "4C56AD"                # FFD8 JMP $AD56 (vanilla skip target)
)
assert len(GATE_ANCHOR) == 0xFFDB - 0xFFCB, len(GATE_ANCHOR)

# ---------- GateYconv @ $950B ----------
GATE_YCONV = _hx(
    "ADFF07"                # 950B LDA $07FF
    "D0F6"                  # 950E 2P -> RTS at $9506
    "4CDFAD"                # 9510 1P: JMP $ADDF (tail-call Y-convergence)
)
assert len(GATE_YCONV) == 0x9513 - 0x950B, len(GATE_YCONV)

# ---------- site patches (addr, expected_vanilla, new_bytes, desc) ----------
V33_SITE_PATCHES = [
    (0xDDEA, _hx("C6B5D0"), _hx("4CDBDD"),
     "disable title demo timeout (3 bytes; $DDED now belongs to Coll2)"),
    (0x95A8, _hx("B003204F96"), _hx("4CEDDDEAEA"),
     "collision tail -> Coll2 (relocated, 1P-gated)"),
    (0x99C0, _hx("AD1007290FAAA559"), _hx("2055DEA558855A60"),
     "Minnie input: JSR gate; 2P tail inline (pad2 -> $5A)"),
    (0xC264, _hx("A9028DFA07A99085F060"), _hx("2068DEA91085F060EAEA"),
     "owl grab: JSR gate; 2P tail inline (damage timer)"),
    (0xAD15, _hx("A52D8537"), _hx("2034DEEA"),
     "walk-anim source via gate ($2D in 1P, 0 in 2P)"),
    (0xAD2F, _hx("A57D38E57E20AB81C919900320B1AD"),
     _hx("201CDE") + b"\xEA" * 12,
     "ocean X: gate (vanilla convergence in 1P, MinnieSwim in 2P)"),
    (0xAD42, _hx("2046AF900F"), _hx("20CBFFEAEA"),
     "scroll anchor: gate (vanilla conditional in 1P)"),
    (0xAD68, _hx("20DFAD"), _hx("200B95"),
     "ocean Y-convergence: gate (vanilla JSR $ADDF in 1P, off in 2P)"),
    (0xAE15, _hx("A591D00AA534C9099004A9018500A591F002C691"),
     _hx("20F8FE"                # AE15 JSR GateJump2
         "4C29AE"                # AE18 JMP $AE29  (was 17 dead NOPs)
         + MINNIE_INPUT),        # AE1B-AE28 MinnieInput helper
     "Minnie jump -> GateJump2; NOP padding reclaimed for MinnieInput"),
    (0xB0B8, _hx("20CCB0"), _hx("4CCD83"),
     "special-object pickup -> NearObj at new address (internally gated)"),
]

V33_BLOBS = [
    (0x838B, DOOR_EITHER_V33, "DoorEither'+NearObj with internal 1P gates"),
    (0x8404, MENU_V33, "MenuInput+Init+templates (BG-tile cursor)"),
    (0xFFDB, QUEUE_CURSOR, "QueueCursor in old DrawCursor space"),
    (0xDDED, COLL2, "Coll2: gated collision in dead demo space"),
    (0xDE1C, GATE_SWIM, "GateSwim"),
    (0xDE34, GATE_ANIM, "GateAnimVal"),
    (0xDE3F, START_RANDOM, "Start path + random start SFX"),
    (0xDE55, GATE_MINNIE_IN, "GateMinnieIn (slid +9 by v38 repack)"),
    (0xDE68, GATE_OWL, "GateOwl (slid +5 by v38 repack)"),
    (0xFEF8, GATE_JUMP2, "GateJump2 (+relocated JumpHold)"),
    (0xFFCB, GATE_ANCHOR, "GateAnchor in freed JumpHold space"),
    (0x950B, GATE_YCONV, "GateYconv in inter-routine padding"),
]

# hooks that must point at relocated MENU'
V33_HOOK_PATCHES = [
    (0xDDC1, _hx("2080DE"), _hx("202084"), "title init -> Init @ $8420"),
    (0xDDDB, _hx("A5572910"), _hx("200484EA"), "wait loop -> MenuInput @ $8404"),
]
