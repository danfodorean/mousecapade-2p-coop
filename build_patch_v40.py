#!/usr/bin/env python3
"""
Mickey Mousecapade (USA) — 2-Player Hack, v0.33 "ONE PLAYER mode gate: $07FF routes 10 sites back to vanilla behavior"
================================================================
Replaces the entire shoot handler with a unified per-character system:
  - star level 1 ($BC=%01): each character may have 1 star in flight
  - star level 2 ($BC=%11): each may have 2, shared pool of 3 slots
  - both characters trigger independently ($59/$5A bit 6), edge-detected
  - per-slot ownership tracked in repurposed ring-buffer RAM

RAM (new):
  $0701+char : B-button edge flags (Mickey/Minnie)
  $0703+slot : slot owner (0=Mickey, 1=Minnie), valid while state!=0
Character-indexed pairs used by the unified handler (X = 0/1):
  $59,X input   $7D,X posX   $7F,X posY   $81,X facing   $79,X vert var
Vanilla singletons: $BB Mickey hit-timer, $07FA Minnie kidnap state,
  $74 vertical-room mode, $BC star bitmask, $C2 shared HP.
Slot arrays (3 slots): $96 state, $99 X, $9C Y, $9F/$A2 counters.
Spawn offsets: facing 0 (left) X-4, facing 1 (right) X+5; Y always +8.

Usage:  python3 build_patch_v33.py original.nes
"""
import sys, struct

def cpu_to_file(addr): return 0x10 + (addr - 0x8000)

NEW_SHOOT = bytes.fromhex(
    # --- NewShoot @ $FE3D: gate on any star, run both characters ---
    # v40: rebased 3 bytes earlier into the $FE3A pocket so CharShoot can call
    # MinnieInput. Everything from $FE52 on keeps its old address untouched.
    "A5BC"        # FE3D LDA $BC
    "D001"        # FE3F BNE $FE42
    "60"          # FE41 RTS            <- shared exit for all aborts
    "A200"        # FE42 LDX #$00       ; Mickey
    "204DFE"      # FE44 JSR $FE4D
    "A201"        # FE47 LDX #$01       ; Minnie
    "204DFE"      # FE49 JSR $FE4D
    "60"          # FE4C RTS
    # --- CharShoot @ $FE4D (X = character 0/1) ---
    "B559"        # FE4D LDA $59,X      ; character's own input
    "201BAE"      # FE4F JSR $AE1B      ; v40: 1P -> Minnie fires on Mickey's B
    "2940"        # FE52 AND #$40       ; B button
    "D006"        # FE54 BNE $FE5C
    "A900"        # FE56 LDA #$00       ; released -> clear edge flag
    "9D0001"      # FE58 STA $0100,X
    "60"          # FE5B RTS
    "BD0001"      # FE5C LDA $0100,X    ; .held
    "F001"        # FE5F BEQ $FE62
    "60"          # FE61 RTS            ; still held from before
    "A901"        # FE62 LDA #$01       ; .fire: latch edge flag
    "9D0001"      # FE64 STA $0100,X
    "E000"        # FE67 CPX #$00
    "D00B"        # FE69 BNE $FE76      ; Minnie-specific check
    "A5BB"        # FE6B LDA $BB        ; Mickey: hit-stun gate (vanilla)
    "F00C"        # FE6D BEQ $FE7B
    "C920"        # FE6F CMP #$20
    "90CE"        # FE71 BCC $FE44      ; 1..$1F -> can't shoot
    "4C7BFE"      # FE73 JMP $FE7B
    "ADFA07"      # FE76 LDA $07FA      ; Minnie: not kidnapped/absent
    "D0C6"        # FE79 BNE $FE44
    "A574"        # FE7B LDA $74        ; .vert (vanilla vertical-room check)
    "F008"        # FE7D BEQ $FE87
    "B579"        # FE7F LDA $79,X
    "10BE"        # FE81 BPL $FE44
    "C9F0"        # FE83 CMP #$F0
    "B0BA"        # FE85 BCS $FE44
    "B581"        # FE87 LDA $81,X      ; .facing (only 0/1 may fire, vanilla)
    "C902"        # FE89 CMP #$02
    "B0B4"        # FE8B BCS $FE44
    "8502"        # FE8E STA $02        ; temp: facing
    "A002"        # FE90 LDY #$02       ; count my active shots
    "A900"        # FE92 LDA #$00
    "8503"        # FE94 STA $03        ; temp: count
    "B99600"      # FE96 LDA $0096,Y    ; .cnt
    "F008"        # FE99 BEQ $FEA3
    "8A"          # FE9B TXA
    "D90201"      # FE9C CMP $0102,Y    ; owner == me?
    "D002"        # FE9F BNE $FEA3
    "E603"        # FEA1 INC $03
    "88"          # FEA3 DEY            ; .next
    "10F0"        # FEA4 BPL $FE96
    "A901"        # FEA6 LDA #$01       ; max = 1 (+1 if second star)
    "8504"        # FEA8 STA $04
    "A5BC"        # FEAA LDA $BC
    "C903"        # FEAC CMP #$03
    "9002"        # FEAE BCC $FEB2
    "E604"        # FEB0 INC $04
    "A503"        # FEB2 LDA $03        ; .haveMax
    "C504"        # FEB4 CMP $04
    "B08A"        # FEB5 BCS $FE44      ; at personal limit
    "A002"        # FEB8 LDY #$02       ; find a free slot
    "B99600"      # FEBA LDA $0096,Y    ; .find
    "F004"        # FEBD BEQ $FEC3
    "88"          # FEBF DEY
    "10F8"        # FEC0 BPL $FEBA
    "60"          # FEC2 RTS            ; pool exhausted
    "8A"          # FEC3 TXA            ; .spawn: owner = me
    "990201"      # FEC4 STA $0102,Y
    "A502"        # FEC7 LDA $02
    "18"          # FEC9 CLC
    "6901"        # FECA ADC #$01
    "999600"      # FECC STA $0096,Y    ; state = facing+1
    "A502"        # FECF LDA $02
    "D008"        # FED1 BNE $FEDB
    "B57D"        # FED3 LDA $7D,X      ; facing left: X-4
    "18"          # FED5 CLC
    "69FC"        # FED6 ADC #$FC
    "4CDFFE"      # FED7 JMP $FEDF
    "B57D"        # FEDB LDA $7D,X      ; .right: X+5
    "18"          # FEDD CLC
    "6905"        # FEDE ADC #$05
    "999900"      # FEE0 STA $0099,Y    ; .stX
    "B57F"        # FEE3 LDA $7F,X
    "18"          # FEE5 CLC
    "6908"        # FEE6 ADC #$08       ; Y+8
    "999C00"      # FEE8 STA $009C,Y
    "A900"        # FEEB LDA #$00
    "999F00"      # FEED STA $009F,Y    ; reset counters
    "99A200"      # FEF0 STA $00A2,Y
    "A909"        # FEF3 LDA #$09
    "8D8001"      # FEF5 STA $0180      ; shot SFX
    "60"          # FEF8 RTS
)
assert len(NEW_SHOOT) == 0xFEF8 - 0xFE3D, f"length {len(NEW_SHOOT):#x}"


# NewCollision @ $FEF8 — tail of the enemy-vs-player check at $9582.
# Entered via JMP with carry = result of Mickey's box test at $95A5.
NEW_COLLISION = bytes.fromhex(
    "B004"        # FEF8 BCS $FEFE      ; Mickey missed -> try Minnie
    "204F96"      # FEFA JSR $964F      ; Mickey hit -> touch dispatch
    "60"          # FEFD RTS
    "ADFA07"      # FEFE LDA $07FA      ; Minnie kidnapped/absent? skip
    "D01E"        # FF01 BNE $FF21
    "A582"        # FF03 LDA $82        ; mirror Mickey's state<3 gate
    "C903"        # FF05 CMP #$03
    "B018"        # FF07 BCS $FF21
    "A57E"        # FF09 LDA $7E        ; Minnie X -> temp
    "850A"        # FF0B STA $0A
    "A580"        # FF0D LDA $80        ; Minnie Y -> temp
    "850B"        # FF0F STA $0B
    "A908"        # FF11 LDA #$08       ; same hitbox as Mickey
    "8502"        # FF13 STA $02
    "A90C"        # FF15 LDA #$0C
    "8503"        # FF17 STA $03
    "20E695"      # FF19 JSR $95E6      ; box check vs same enemy
    "B003"        # FF1C BCS $FF21
    "204F96"      # FF1E JSR $964F      ; hit -> same touch dispatch
    "60"          # FF21 RTS
)
assert len(NEW_COLLISION) == 0xFF22 - 0xFEF8


# MinnieWalk v10 @ $FF22 + MinnieJumpHold @ $FFC5.
# v0.16: jump SFX only when a jump actually starts (airborne check);
# Mickey anchor-skip now conditioned on him being AT the line ($7D>=$78)
# instead of merely holding right -- fixes his double speed when walking
# behind a Minnie-driven scroll.
MINNIE_SWIM = bytes.fromhex(
    "A558"    # FF22 LDA $58
    "855A"    # FF24 STA $5A
    "2980"    # FF26 AND #$80
    "D00D"    # FF28 BNE $FF37
    "A900"    # FF2A LDA #$00
    "8D0501"  # FF2C STA $0105
    "A901"    # FF2F LDA #$01
    "8D0601"  # FF31 STA $0106
    "4C50FF"  # FF34 JMP $FF50
    "A900"    # FF37 LDA #$00
    "8D0601"  # FF39 STA $0106
    "AD0501"  # FF3C LDA $0105
    "D00F"    # FF3F BNE $FF50
    "A534"    # FF41 LDA $34      ; airborne? no jump, NO SOUND
    "D00B"    # FF43 BNE $FF50
    "EE0501"  # FF45 INC $0105
    "20DFAD"  # FF48 JSR $ADDF
    "A907"    # FF4B LDA #$07
    "8D8001"  # FF4D STA $0180
    "A558"    # FF50 LDA $58      ; --- right ---
    "2901"    # FF52 AND #$01
    "F061"    # FF54 BEQ $FFB7
    "A52E"    # FF56 LDA $2E
    "C901"    # FF58 CMP #$01
    "F004"    # FF5A BEQ $FF60
    "C903"    # FF5C CMP #$03
    "D017"    # FF5E BNE $FF77
    "ADEE07"  # FF60 LDA $07EE
    "D009"    # FF63 BNE $FF6E
    "A528"    # FF65 LDA $28
    "C93E"    # FF67 CMP #$3E
    "900C"    # FF69 BCC $FF77
    "EEEE07"  # FF6B INC $07EE
    "A57E"    # FF6E LDA $7E      ; .endwalk
    "C9EC"    # FF70 CMP #$EC
    "B043"    # FF72 BCS $FFB7
    "4CB0FF"  # FF74 JMP $FFB0
    "A57E"    # FF77 LDA $7E      ; .norm
    "C978"    # FF79 CMP #$78
    "9033"    # FF7B BCC $FFB0
    "A901"    # FF7D LDA #$01     ; -- scroller mode --
    "8537"    # FF7F STA $37
    "8582"    # FF81 STA $82
    "852D"    # FF83 STA $2D
    "A559"    # FF85 LDA $59      ; anchor-skip requires BOTH:
    "2901"    # FF87 AND #$01     ; Mickey holding right...
    "F006"    # FF89 BEQ $FF91
    "A57D"    # FF8B LDA $7D      ; ...AND standing at the line
    "C978"    # FF8D CMP #$78
    "B01C"    # FF8F BCS $FFAD    ; genuine co-scroller -> no anchor
    "A57D"    # FF91 LDA $7D      ; .anchor
    "C908"    # FF93 CMP #$08     ; his left leash
    "B005"    # FF95 BCS $FF9C
    "A900"    # FF97 LDA #$00
    "852D"    # FF99 STA $2D
    "60"      # FF9B RTS
    "C67D"    # FF9C DEC $7D      ; anchor screen X
    "A56F"    # FF9E LDA $6F      ; + world counter
    "D009"    # FFA0 BNE $FFAB
    "A570"    # FFA2 LDA $70
    "38"      # FFA4 SEC
    "E901"    # FFA5 SBC #$01
    "2907"    # FFA7 AND #$07
    "8570"    # FFA9 STA $70
    "C66F"    # FFAB DEC $6F
    "E67E"    # FFAD INC $7E      ; pre-cancel her own anchor
    "60"      # FFAF RTS
    "A901"    # FFB0 LDA #$01     ; .dowalk
    "8537"    # FFB2 STA $37
    "4CCDAD"  # FFB4 JMP $ADCD
    "A558"    # FFB7 LDA $58      ; --- left ---
    "2902"    # FFB9 AND #$02
    "F00D"    # FFBB BEQ $FFCA
    "A57E"    # FFBD LDA $7E
    "C904"    # FFBF CMP #$04
    "9007"    # FFC1 BCC $FFCA
    "A901"    # FFC3 LDA #$01
    "8537"    # FFC5 STA $37
    "4CBBAD"  # FFC7 JMP $ADBB
    "60"      # FFCA RTS
    "AD0601"  # FFCB LDA $0106    ; MinnieJumpHold
    "F00A"    # FFCE BEQ $FFDA
    "A534"    # FFD0 LDA $34
    "C909"    # FFD2 CMP #$09
    "9004"    # FFD4 BCC $FFDA
    "A901"    # FFD6 LDA #$01
    "8500"    # FFD8 STA $00
    "60"      # FFDA RTS
)

MINNIE_SWIM = MINNIE_SWIM[:0xFFCB - 0xFF22]  # v33: JumpHold relocated into GateJump2
assert len(MINNIE_SWIM) == 0xFFCB - 0xFF22

# Section B in the dead vanilla shoot handler: door + object pickup for either character
DOOR_EITHER = bytes.fromhex(
    # DoorEither v4 @ 838B: each player's Up works only with their OWN proximity
    "A531"    # 838B LDA $31      ; both grounded (vanilla rule)
    "0534"    # 838D ORA $34
    "D035"    # 838F BNE $83C6
    "A559"    # 8391 LDA $59      ; Mickey's Up...
    "2908"    # 8393 AND #$08
    "F00C"    # 8395 BEQ $83A3
    "A57D"    # 8397 LDA $7D      ; ...with Mickey's proximity
    "38"      # 8399 SEC
    "E53C"    # 839A SBC $3C
    "20AB81"  # 839C JSR $81AB
    "C908"    # 839F CMP #$08
    "9012"    # 83A1 BCC $83B5    ; -> open
    "A55A"    # 83A3 LDA $5A      ; Minnie's Up...
    "2908"    # 83A5 AND #$08
    "F01D"    # 83A7 BEQ $83C6
    "A57E"    # 83A9 LDA $7E      ; ...with Minnie's proximity
    "38"      # 83AB SEC
    "E53C"    # 83AC SBC $3C
    "20AB81"  # 83AE JSR $81AB
    "C908"    # 83B1 CMP #$08
    "B011"    # 83B3 BCS $83C6
    "A53C"    # 83B5 LDA $3C      ; .open: snap Mickey to the door
    "857D"    # 83B7 STA $7D
    "A580"    # 83B9 LDA $80
    "857F"    # 83BB STA $7F
    "A53F"    # 83BD LDA $3F      ; door target
    "852F"    # 83BF STA $2F
    "A9F0"    # 83C1 LDA #$F0
    "8579"    # 83C3 STA $79      ; Mickey enters
    "60"      # 83C5 RTS
    "60"      # 83C6 RTS          ; .rts
    # NearObj @ 83C7
    "A57D"    # 83C7 LDA $7D
    "38"      # 83C9 SEC
    "E53C"    # 83CA SBC $3C
    "20AB81"  # 83CC JSR $81AB
    "C90A"    # 83CF CMP #$0A
    "B00C"    # 83D1 BCS $83DF
    "A57F"    # 83D3 LDA $7F
    "38"      # 83D5 SEC
    "E53D"    # 83D6 SBC $3D
    "20AB81"  # 83D8 JSR $81AB
    "C90A"    # 83DB CMP #$0A
    "9017"    # 83DD BCC $83F6
    "A57E"    # 83DF LDA $7E
    "38"      # 83E1 SEC
    "E53C"    # 83E2 SBC $3C
    "20AB81"  # 83E4 JSR $81AB
    "C90A"    # 83E7 CMP #$0A
    "B00A"    # 83E9 BCS $83F5
    "A580"    # 83EB LDA $80
    "38"      # 83ED SEC
    "E53D"    # 83EE SBC $3D
    "20AB81"  # 83F0 JSR $81AB
    "C90A"    # 83F3 CMP #$0A
    "60"      # 83F5 RTS
    "18"      # 83F6 CLC
    "60"      # 83F7 RTS
)



# v0.31 menu: MenuInput+Init live entirely in the reclaimed vanilla shoot
# handler ($838B-$843B); $DE54-$DE7F is left VANILLA because $DE63 (demo
# helper), $DE77 (demo level table) and $DE7C (LDA #$FF/STA $69 entry, JSR'd
# from $D7F6/$D8BB/$D8F4/$DB71/$DCF7 during level loads) are all live code --
# v0.30 overwrote $DE7C and crashed the game the moment Start loaded a level.
#
# NMI contract (vanilla): when $67 is armed, NMI does OAM DMA from $0300 and
# then CLEARS the whole shadow page to $F4. So the cursor sprite must be
# fully rebuilt (all 4 bytes) before every arm -- v0.30 only refreshed Y,
# which is why the cursor turned into tile $F4 at X=$F4 (far right).
MENU = bytes.fromhex(
    # --- MenuInput @ $83F8 (called from title wait loop each frame) ---
    "A557"      # 83F8 LDA $57       ; pad1 held
    "2908"      # 83FA AND #$08      ; Up
    "F004"      # 83FC BEQ $8402
    "A000"      # 83FE LDY #$00      ; -> ONE PLAYER
    "F008"      # 8400 BEQ $840A     ; (always)
    "A557"      # 8402 LDA $57
    "2904"      # 8404 AND #$04      ; Down
    "F014"      # 8406 BEQ $841C
    "A001"      # 8408 LDY #$01      ; -> TWO PLAYER
    "CCFF07"    # 840A CPY $07FF     ; changed?
    "F00D"      # 840D BEQ $841C     ; no -> don't re-arm (no flicker)
    "8CFF07"    # 840F STY $07FF
    "20DBFF"    # 8412 JSR $FFDB     ; DrawCursor (full 4-byte rebuild)
    "A901"      # 8415 LDA #$01
    "8567"      # 8417 STA $67       ; arm one OAM DMA
    "EAEAEA"    # 8419 NOP padding
    "A557"      # 841C LDA $57       ; tail: Start test (A/Z for caller)
    "2910"      # 841E AND #$10
    "60"        # 8420 RTS
    # --- Init @ $8421 (hooked from $DDC1, replaces JSR $DE80) ---
    "A900"      # 8421 LDA #$00
    "8DFF07"    # 8423 STA $07FF     ; default ONE PLAYER
    "20DBFF"    # 8426 JSR $FFDB     ; DrawCursor
    "4C80DE"    # 8429 JMP $DE80     ; vanilla arm + score draw
)
assert len(MENU) == 0x842C - 0x83F8  # v33: superseded by MENU_V33 in v40_gates (kept for reference)

# DrawCursor @ $FFDB (free space after MinnieJumpHold, before vectors)
DRAW_CURSOR = bytes.fromhex(
    "ADFF07"    # FFDB LDA $07FF
    "0A0A0A0A"  # FFDE ASL x4        ; 0 / $10
    "09A7"      # FFE2 ORA #$A7      ; Y = $A7/$B7: text rows 22/24 render 7px high (scroll $69=7), sprite delay 1 -> -8
    "8D0003"    # FFE4 STA $0300
    "A9EA"      # FFE7 LDA #$EA      ; diamond/star tile in title spr bank
    "8D0103"    # FFE9 STA $0301
    "A900"      # FFEC LDA #$00      ; sprite palette 0 (magenta/white)
    "8D0203"    # FFEE STA $0302
    "A950"      # FFF1 LDA #$50      ; X = col 10, one tile left of text
    "8D0303"    # FFF3 STA $0303
    "60"        # FFF6 RTS
)
assert len(DRAW_CURSOR) == 0xFFF7 - 0xFFDB

from v40_gates import V33_SITE_PATCHES, V33_BLOBS, V33_HOOK_PATCHES

PATCHES = [
    (0xDE4B, bytes.fromhex("A5"), bytes.fromhex("60"),
     "retire level-select cheat (start flow preserved)"),
    (0x931F, bytes.fromhex("0558"), bytes.fromhex("EAEA"),
     "Mickey input = pad 1 only (kept in both modes)"),
    (0x937B, bytes.fromhex("208B83"), bytes.fromhex("203DFE"),
     "hook caller 1 -> NewShoot"),
    (0x9435, bytes.fromhex("208B83"), bytes.fromhex("203DFE"),
     "hook caller 2 -> NewShoot"),
    (0xFF22, bytes.fromhex("FF"*len(MINNIE_SWIM)), MINNIE_SWIM,
     "MinnieSwim routine in free space (JumpHold relocated out)"),
    (0xB06F, bytes.fromhex("A5592908F015"), bytes.fromhex("4C8B83EAEAEA"),
     "door entry -> DoorEither (internally gated)"),
    (0x838B, bytes.fromhex("A5BCD00160A5BBF0"), None,
     "reclaim dead vanilla shoot handler (verify head only)"),
    (0xFE3D, bytes.fromhex("FF"*len(NEW_SHOOT)), NEW_SHOOT,
     "NewShoot + CharShoot in free space"),
] + list(V33_HOOK_PATCHES) + list(V33_SITE_PATCHES) \
  + [(a, None, blob, d) for (a, blob, d) in V33_BLOBS]


def _edit_title_seg2(rom):
    """Rewrite ONLY segment 2 (offset $80) of the title stream: replace the
    copyright block (screen rows 20-27) with centered ONE PLAYER / TWO PLAYER.
    Segment 1 (offset $40: logo + PRESS START + HI SCORE) untouched byte-for-byte.
    Letters = same ASCII tiles the copyright uses (proven to render); space=$46.
    Length-exact so nothing downstream shifts."""
    chr_base = 0x10 + 0x8000; b1 = chr_base + 0x2000
    ptr = rom[b1+0x1400] | (rom[b1+0x1401]<<8)
    src = b1 + ptr
    def dec(start, off):
        i=start; out=[]
        while True:
            b=rom[i]
            if b==0: i+=1; break
            if b&0x80: out.append((b-off)&0xFF); i+=1
            else:
                cnt=rom[i+1]; n=cnt if cnt else 256
                out.extend([((b|0x80)-off)&0xFF]*n); i+=2
        return out,i
    seg1,a1 = dec(src, 0x40)
    seg2,a2 = dec(a1, 0x80)
    assert len(seg1)==640 and len(seg2)==320, (len(seg1),len(seg2))
    seg2_len = a2 - a1                      # bytes incl. terminator
    SP=0x46
    flat = [SP]*320                          # blank all 10 rows
    def put(row_local, text):                # centered
        col = (32-len(text))//2
        for k,ch in enumerate(text):
            flat[row_local*32+col+k] = SP if ch==' ' else ord(ch)
    put(2, "ONE PLAYER")                     # screen row 22
    put(4, "TWO PLAYER")                     # screen row 24
    OFF=0x80
    out=bytearray(); j=0
    while j<len(flat):
        t=flat[j]; run=1
        while j+run<len(flat) and flat[j+run]==t and run<256: run+=1
        v=(t+OFF)&0xFF; assert v>=0x80, hex(t)
        if run>=2: out+=bytes([v&0x7F, run&0xFF]); j+=run
        else: out+=bytes([v]); j+=1
    out+=b'\x00'
    # length-exact pad by splitting runs
    while len(out) < seg2_len:
        k=0; done=False
        while k < len(out)-1:
            b=out[k]
            if b<0x80 and b!=0 and out[k+1]>2:
                cnt=out[k+1]; h=cnt//2
                out=out[:k]+bytes([b,h,b,cnt-h])+out[k+2:]; done=True; break
            k += 2 if (b<0x80 and b!=0) else 1
        if not done: break
    assert len(out)==seg2_len, (len(out), seg2_len)
    return a1, bytes(out)

def make_ips(diffs):
    out=[b"PATCH"]
    for off,new in diffs:
        out.append(struct.pack(">I",off)[1:]); out.append(struct.pack(">H",len(new))); out.append(new)
    out.append(b"EOF"); return b"".join(out)

def main():
    src = sys.argv[1] if len(sys.argv)>1 else "original.nes"
    rom = bytearray(open(src,"rb").read())
    diffs=[]
    _o,_b=_edit_title_seg2(rom); rom[_o:_o+len(_b)]=_b; diffs.append((_o,_b))
    # v39: star cursor -- copy the star projectile pattern (bank0 sprite tile
    # $02) over bank0 BG-table tile $2A.
    # v35 used $C1 and was WRONG: $C1 is 'A' in the dark sign font. Level-name
    # strings ($DD0C, plain ASCII) are printed by $DCFB as tile = char + $80,
    # so "THE OCEAN"/"THE CASTLE" render 'A' from $C1 -- the star leaked in.
    # $2A is verified unused by audit_tiles.py, which runs all five bank-0
    # screen loaders under a CNROM+PPU shim and records every tile actually
    # written to a nametable. Digits ($30-$39) and letters ($41-$5A) stay off
    # limits regardless, since dynamic text picks those at runtime.
    _chr = 0x10 + 0x8000
    _star = bytes(rom[_chr + 0x02*16 : _chr + 0x02*16 + 16])
    _dst = _chr + 0x1000 + 0x2A*16
    rom[_dst:_dst+16] = _star; diffs.append((_dst, _star))
    print("OK  CHR bank0 $1000 tile $2A <- star projectile pattern")
    print("OK  CHR title seg2 -> copyright removed, ONE/TWO PLAYER added")
    for addr, orig, repl, note in PATCHES:
        off = cpu_to_file(addr)
        if orig is not None and len(orig) > 0:
            cur = bytes(rom[off:off+len(orig)])
            if cur != orig:
                sys.exit(f"MISMATCH at ${addr:04X}: found {cur.hex().upper()}, expected {orig.hex().upper()}")
        if repl is None:
            print(f"OK  ${addr:04X}  {note} (verified)")
            continue
        rom[off:off+len(repl)] = repl
        diffs.append((off, repl))
        print(f"OK  ${addr:04X}  {note}")
    open("mousecapade_2p_v40.nes","wb").write(rom)
    open("mousecapade_2p_v40.ips","wb").write(make_ips(diffs))
    print("Wrote mousecapade_2p_v40.nes and mousecapade_2p_v40.ips")

if __name__=="__main__":
    main()
