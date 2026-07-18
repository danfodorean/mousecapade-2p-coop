# Mickey Mousecapade — Two-Player Co-op

A ROM hack for Mickey Mousecapade (NES, 1987) that adds genuine simultaneous
two-player co-op. Player 2 controls Minnie.

**[Download the latest patch →](../../releases/latest)**

Mickey Mousecapade is built around two characters but only ever had room for one
player: Minnie follows Mickey under CPU control, and controller 2 does nothing.
This hack hands her to a second player — her own movement, jumping, swimming,
doors, item pickups, and her own star shots.

## Features

- Simultaneous two-player co-op; Minnie is fully player-controlled
- Title-screen mode select (ONE PLAYER / TWO PLAYER) with a star cursor and menu SFX
- Faithful one-player mode — every change is gated on the selected mode, so 1P
  keeps the original follow AI, owl kidnapping, and behaviour
- Each character shoots with their own B button in two-player
- Exactly one background tile differs from the original ROM (the cursor star)
- Mapper 3 / CNROM, no expansion hardware — runs on real hardware
- The patching hashes in the README are for the base ROM, so they stay correct as-is.

## Patching

Apply the `.bps` to an unmodified USA ROM **with** the 16-byte iNES header:

| | |
|---|---|
| No-Intro | `Mickey Mousecapade (USA).nes` |
| Size     | 65,552 bytes (65,536 + 16-byte header) |
| CRC32    | `1D961110` |
| MD5      | `D634A9B11B464BC2A6C452BAF5A57F3E` |
| SHA-1    | `C37AA6ACFCD64EB51E93E77881BABC8C06779BEE` |

Use [Flips](https://www.romhacking.net/utilities/1040/), beat, or
[Rom Patcher JS](https://www.romhacking.net/patch/). The BPS verifies the ROM's
checksum and refuses the wrong file. An `.ips` is included for legacy patchers
only — it has no checksum, and applied to a *headerless* ROM it will silently
produce a broken game.

No ROM is distributed here. Supply your own.

## How it's built

The hack is assembled by a Python toolchain rather than a hex editor:

| File | Purpose |
|---|---|
| `build_patch_v41.py` | Applies site patches + code blobs, emits the ROM and IPS |
| `v41_gates.py`       | 6502 gate routines, hook table, free-space map |
| `test_gates_v41.py`  | 27 unit tests for the mode gates |
| `nes_fast.py`        | Headless 6502 harness (exec-compiled opcode handlers) |
| `audit_tiles.py`     | CNROM+PPU shim; runs the real screen loaders and records every tile written to a nametable |
| `make_bps.py`        | BPS patch creation + verification |

Every mode-dependent change is a *gate*: a small routine that reads the mode
byte at `$07FF` and either runs the vanilla code path or the two-player one.
That is what keeps ONE PLAYER byte-faithful to the original game.

## Credits

Hack, disassembly and tooling by **SideofClouds**.
Mickey Mousecapade © 1987 Hudson Soft / Capcom.
