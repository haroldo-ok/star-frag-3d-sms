# Star Frag 3D

A two-player split-screen first-person deathmatch for the **Sega Master System**, built on the
Splat Trooper 3D engine design (mirrored walls, pre-scaled hardware sprites, palette rotation).

`star_frag_3d.sms` is a 512 KB ROM with the standard Sega mapper. It needs no cartridge RAM and
no second-generation VDP features. It has only been run in the headless `smstest` emulator, not on
real hardware or other emulators.

## Playing

Two pads: player 1 on port A and player 2 on port B. Player 2 can also be the CPU, so one
person can play alone.

| pad | action |
|---|---|
| Up / Down | walk forward / back |
| Left / Right | turn |
| Button 2 + Left / Right | strafe |
| Button 2 tapped on its own | next weapon |
| Button 1 | fire (hold for auto-fire); respawn after being fragged |
| Pause (console) | pause |

**Match setup** (player 1's pad; Up/Down picks a line, Left/Right changes it, Button 1 starts):
- skin for player 1 and player 2
- whether player 2 is a human or the CPU (touching Left/Right on pad 2 makes player 2 human and
  picks its skin)
- arena
- frag limit: 5, 10, 15, 20 or 30

The two skins turn slowly on the setup screen, so you can see all 8 rotations. First to the frag
limit wins. Killing yourself (rockets, grenades) costs a frag.

### Arenas

| arena | look |
|---|---|
| Outpost Alpha | tech corridors, a computer room, crate stacks; deep-space blue |
| Reactor Core | a reactor ring in the middle; hot red haze |
| Cargo Bay | crate mazes around a computer room; teal |
| Force Dome | an open dome with force-field pillars; black sky, grey floor |

Each arena has 6 spawn points. You respawn at the one farthest from your opponent, facing the
longest open line.

### Weapons

| | weapon | type | notes |
|---|---|---|---|
| 1 | Blaster | hitscan | infinite ammo; everyone respawns with it |
| 2 | Pulse rifle | hitscan | fast, low damage |
| 3 | Plasma gun | projectile | fast glowing bolts |
| 4 | Grenade launcher | projectile | bounces off walls, rolls, fuse ~1.3 s, splash damage |
| 5 | Rocket launcher | projectile | explodes on impact, splash damage (also hurts you) |
| 6 | Flamer | projectile | short-range stream of flames |
| 7 | Railgun | hitscan | slow, 80 damage, leaves a trail of sparks |

Hitscan weapons have a little auto-aim around the centre of the view, which helps with a pad.

### Items

| item | effect | respawns |
|---|---|---|
| Medkit | +25 health (up to 100) | 10 s |
| Armor | +50 armor (up to 100); absorbs 2/3 of damage | 10 s |
| Ammo crate | ammo for every weapon you own | 10 s |
| Weapon | the weapon + ammo, and switches to it | 15 s |
| Overdrive | double damage for 20 s | 40 s |

## Player skins

Six skins from the **150 Doomguy Skins** pack (compiled by Doomkid) are converted at build time
by `tools/gen.py`. Each skin gets:
- 8 walking rotations in two frames (A and C)
- an attack frame (F1) and a pain frame (G1)
- dying (H) and dead (N) frames
- all of the above pre-scaled to 8 sizes
- 8 HUD faces: five health levels, ouch, evil grin and dead

Colours are quantised to the Master System palette.

| in game | pack skin | skin by | HUD face |
|---|---|---|---|
| MARINE | Base1 | Doomkid | Dark Complexion Marine (Doomkid) |
| RANGER | BaseFemale | Virtue | Female Marine (Lynn Forest, updated by Alice Jameson) |
| PHOBOS | Phobos | Rottking | Phobos variant (fct_skins_v8a.wad) |
| CYBORG | Cyborg | Cory Whittle | Cyborg Marine (RTC-3057 by Team Future) |
| HAZMAT | Hazmat | Enjay / Scalliano | Helmet Marine (Amuscaria / Eriance) |
| STEALTH | Stealth | ??? (as credited in the pack) | Shades Marine (brit11.wad) |

Face credits are matched from each skin's `face =` prefix to the pack's HUD-face credit list by
name, so treat them as a best match.

The opponent is drawn from the rotation Doom would pick: the angle from the viewer to the
opponent, compared with the way the opponent faces. `skins_gallery.png` shows each skin seen from
8 sides in the game's own view.

The Doom palette that the skins' pixels index into comes from Freedoom (`tools/doompal.lmp`,
BSD licence in `tools/doompal.COPYING`). The WAD contains no palette.

## How it works

- **Two views, one renderer.** The screen holds two 128 x 96 views side by side, 16 tile columns
  each. Rays 0-31 belong to player 1 and rays 32-63 to player 2, all 4 px wide. `cast_rays`
  casts the 32 rays from `ray_base` for one camera, and only when that player has moved or turned.
  `draw_view` draws the 16 columns from `dv_first`. The DDA, ray interpolation, unchanged-column
  skipping, generated scalers and paced VRAM upload are Splat Trooper's.

- **Mirrored walls.** Wall textures are symmetric top to bottom, so only the top 6 tile rows of
  each view are built and uploaded. The bottom 6 rows use the same tiles with the background V-flip
  bit and the sprite palette. That palette has floor colours where the BG palette has sky colours,
  so the mirrored sky becomes the floor.

- **Pre-scaled hardware sprites.** Every opponent frame, item, projectile and effect exists in ROM
  at 8 sizes (8 to 48 px), so 140 graphics take 25 banks. Each frame every object is projected into
  both views and the nearest size is shown with 8x16 sprites from a VRAM cache shared by both
  views. Walls hide sprites per 8 px column using each view's depth buffer. A piece is only shown
  if it lies entirely inside its own window, so nothing leaks into the other player's view.

- **Palette rotation.** Entries 13-15 cycle through an energy-blue/violet sequence. This animates:
  - force fields, computer screens and panel lights
  - the reactor glow and HUD lights
  - plasma bolts, rail sparks and the overdrive orb

  The title screen rotates 7 shades across the logo for a metallic sheen and twinkles the stars.

- **Game time is independent of frame rate.** The frame interrupt counts VBlanks, latches both
  pads and runs the music and sound. The game advances by the ticks that have passed, capped at 12
  per drawn frame. Quick presses and Button 2 taps are latched in the interrupt, so none are lost
  at low frame rates.

- **CPU opponent.** The bot steers with a breadth-first distance field toward you, kept in the
  free RAM page under the ray caster (arenas are at most 32 x 22 cells). In sight, it turns to aim,
  fires, keeps its distance and strafes. It picks its best weapon that has ammo, and it plays by the
  same movement and firing rules as a player.

### Frame rate

Measured in `smstest` with NTSC 60 Hz timing:

| situation | frames per second |
|---|---|
| both players standing still | 15 |
| one player walking | 11 |
| one player turning | 7.4 |
| both players turning | 5.2 |
| both walking, turning and firing | 5.0 |

Turning is the slowest case because every column of that view changes and has to be uploaded.
Two views mean twice the columns of Splat Trooper's single view. The speed of the game itself
does not change.

### Limitations

- Hardware sprites are at most 48 px tall, so an opponent closer than about 2 tiles stops growing.
- The VDP shows at most 8 sprites per scanline, and both views share those lines. Pieces past
  the limit drop out, most often when an explosion, an opponent and both weapons overlap. The two
  views take turns going first each frame, so it flickers rather than always hiding one view.
- Palette effects are global, so there is no per-player screen flash. Hits show on the HUD face.

## Building

You need SDCC 4.2 or later, devkitSMS (SMSlib, `ihx2sms`), python3 with Pillow, and the skins
WAD. Put `150skins.wad` in the project folder, or set `SKINWAD=/path/to/150skins.wad`. The
converted data is already in `gen/`, so `make` only reads the WAD if `tools/gen.py` or
`tools/maps.py` changes.

    make                 # gen/ (if needed) + star_frag_3d.sms
    tests/run_all.sh     # build + every playtest

`tools/gen.py` checks every arena when it builds:
- all spawns and items can be reached from spawn 1
- the border is solid
- the arena fits the bot's 22-row navigation field

`tools/checkmap.py` checks the link:
- code fits the fixed 32 KB
- RAM ends below the page-aligned tables at 0xD000
- the texture banks start at 0x8000

## Project layout

| path | what it is |
|---|---|
| `src/main.c` | title, match setup, results screens, the frame loop, palette cycling, pause |
| `src/game.c` | deathmatch rules: movement, weapons, projectiles, splash damage, items, frags, respawn |
| `src/bot.c` | the CPU opponent and its breadth-first navigation field |
| `src/sprites.c` | projecting objects into both views, opponent rotation, the shared VRAM sprite cache, hand weapons |
| `src/hud.c` | text output and the two HUD halves (faces, stats, messages) |
| `src/sound.c` | PSG music and sound effects; frame interrupt that also latches both pads and Button 2 taps |
| `src/render.c` | view set-up, invalidation |
| `src/ray.s` | ray casting and view composition for two views (Z80) |
| `src/asm.s` | hot paths: multiply, column scalers, VRAM column upload, projection (Z80) |
| `src/defs.h` | shared types, screen and tile layout, object and weapon enums |
| `tools/gen.py` | generates everything in `gen/`: textures, tables, skins, faces, items, font, HUD, title, arenas, music |
| `tools/maps.py` | the four arenas as text maps, with their sky and floor colours |
| `tools/wad.py`, `tools/skinlib.py` | read the skins WAD (data only) and pick frames and rotations |
| `tools/doompal.lmp` | the Doom palette, from Freedoom |
| `tools/checkmap.py` | link-map checks run by `make` |
| `tools/smstest/` | headless test emulator with a second joypad (built automatically by `tools/st.sh`) |
| `tools/st.sh` | runs one playtest and turns its screenshots into PNGs in `shots/` |
| `tests/` | playtest scripts and `run_all.sh` |
| `gen/` | generated sources (already converted, so the WAD is only needed to regenerate) |
| `montage.png`, `skins_gallery.png` | screenshots from the test emulator |

## ROM, VRAM and RAM maps

**ROM** (16 KB banks, Sega mapper):

| bank | contents |
|---|---|
| 0-1 | code, tables, font, HUD tiles, music, palettes (fixed, ends at 0x7B74) |
| 2-3 | wall textures (7 textures x light/dark side) and the row tables for column scaling |
| 4 | ray-angle records, distance-to-wall-height tables, the sine table |
| 5 | arenas, first-person weapon tiles, bit-plane lookup table |
| 6 | title screen |
| 7-31 | pre-scaled sprites (140 graphics x 8 sizes) and HUD faces |

**VRAM tiles:**

| tiles | use |
|---|---|
| 0-46 | font (47 glyphs) |
| 48-53 | sky gradient (mirrored, these are also the floor) |
| 54-61 | HUD frame (8 tiles) |
| 64-255 | the two views: 32 columns x 6 tiles (top half only; the bottom half is mirrored) |
| 256-271 / 272-287 | player 1 / player 2 hand weapon, 2 frames each |
| 288-311 | the two HUD faces (3 x 4 tiles each) |
| 332-447 | sprite cache, 58 tile pairs shared by both views |

**RAM:** game variables end at 0xCF13. 0xD000-0xD3FF holds squaring tables for the ray caster,
0xD400-0xD6BF the bot's 32 x 22 navigation field, 0xD6C0 the DDA code, 0xD700 the column buffer,
0xD800-0xDBFF the bit-plane lookup table, with the stack at the top.

## Changing skins and arenas

- **Skins:** edit `SKINS` in `tools/gen.py`. Each entry is the skin's name in the WAD, the name
  shown in the game (up to 7 characters), and the 3-letter prefix of its HUD faces in the WAD.
  Every skin costs about 4 ROM banks, and the ROM is full at six. To add one, either drop another
  or enlarge the ROM past 512 KB.
- **Arenas:** edit `tools/maps.py`. Rows are 32 characters, at most 22 rows. Walls are `#` tech,
  `H` hazard, `C` computer, `P` pipes, `F` force field, `X` crate, `R` reactor. Spawns are `1`-`6`
  (all six required). Items are `h` medkit, `a` armor, `m` ammo, `o` overdrive. Weapons are
  `r` pulse rifle, `p` plasma, `g` grenades, `k` rockets, `f` flamer, `l` railgun. The generator
  refuses an arena with an open border or anything unreachable.

Then run `make` (with the WAD present) and `tests/run_all.sh`.

## Tests

`tools/smstest/` is the devkitSMS skill's headless emulator with one addition: a **second
joypad**. Port 0xDC bits 6-7 and port 0xDD bits 0-3 are wired up, and scripts use `p2up`,
`p2down`, `p2left`, `p2right`, `p21` and `p22`.

| test | what it checks |
|---|---|
| boot | title, menu, match start, both views drawn |
| walkout | controller only: P1 leaves its spawn and walks |
| fight | blaster damage; rocket kill; frag counted; respawn |
| weapons | P2's pad picks a skin and moves/turns P2; all 7 weapons fire and use ammo; Button 2 tap cycles weapons |
| items | medkit, armor, weapon pickup and auto-switch, item respawn, overdrive |
| bot | the CPU opponent finds and frags an idle player |
| flow | all 4 arenas load; a real frag-limit win; results; back to the menu |
| pause | console pause freezes play; the PSG is written |
| gallery | every skin seen from 8 sides (screenshots) |
| soak | 2400 frames of P1 on the controller vs the CPU |

The soak test also checks VRAM write pacing during active display and the stack depth.
`tests/showcase.txt` only makes the screenshots in `montage.png`.

**Not verified:** real hardware, and other emulators.

## Credits

- Engine design (mirrored half-height walls, pre-scaled sprites, palette rotation, generated
  column scalers): Splat Trooper 3D, https://github.com/haroldo-ok/splat-trooper-3d-sms, itself
  derived from Wolf 3D for the Sega Master System.
- Player skins and HUD faces: the **150 Doomguy Skins** pack compiled by Doomkid
  (https://www.doomworld.com/forum/topic/102669-150-doomguy-skins-new-download/). The individual
  authors are listed under "Player skins".
- Doom palette: Freedoom (BSD licence, `tools/doompal.COPYING`).
- Toolchain: SDCC and devkitSMS (SMSlib, PSGlib, ihx2sms) by sverx and contributors.
- Test emulator: the devkitSMS skill's `smstest`, using superzazu's MIT Z80 core (see
  `tools/smstest/ATTRIBUTION.md`).
- Textures, items, weapons, font, HUD, title, arenas and music are drawn or composed by
  `tools/gen.py`.
