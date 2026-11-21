/* Star Frag 3D - a 2-player split-screen deathmatch for the Sega Master System
 *
 * main.c: screens, menus, the frame loop, palette cycling.
 */
#include <SMSlib.h>
#include "defs.h"

SMS_EMBED_SEGA_ROM_HEADER(9999, 0);
SMS_EMBED_SDSC_HEADER_AUTO_DATE(1, 0, "Homebrew", "Star Frag 3D", "2-player split-screen deathmatch");

u8 frame_no;
u8 game_state;          /* 0 title, 1 menu, 2 playing, 3 results (for tests) */
u16 frames_drawn;
u8 menu_sel;
u8 opt_skin[2] = { 0, 3 };
u8 opt_cpu = 1;
void set_weapon(u8 p, u8 w);
u8 music_busy(void);

static u8 cyc_ph, cyc_last;

/* ------------------------------------------------------------ palette work */
static void set_cycle(void)
{
    u8 c0 = cycle_cols[cyc_ph];
    u8 c1 = cycle_cols[cyc_ph >= 4 ? cyc_ph - 4 : cyc_ph + 2];
    u8 c2 = cycle_cols[cyc_ph >= 2 ? cyc_ph - 2 : cyc_ph + 4];
    SMS_setBGPaletteColor(13, c0);
    SMS_setBGPaletteColor(14, c1);
    SMS_setBGPaletteColor(15, c2);
    SMS_setSpritePaletteColor(13, c0);
    SMS_setSpritePaletteColor(14, c1);
    SMS_setSpritePaletteColor(15, c2);
}

static void palette_fx(void)
{
    if ((u8)(vbl_count >> 3) != cyc_last) {
        cyc_last = vbl_count >> 3;
        if (++cyc_ph == 6) cyc_ph = 0;
        set_cycle();
    }
}

static void no_sprites(void)
{
    SMS_initSprites();
    SMS_finalizeSprites();
    SMS_copySpritestoSAT();
}

static void clear_press(void) { pad_press[0] = pad_press[1] = 0; }

/* ------------------------------------------------------------ title */
static void title_screen(void)
{
    u8 t = 0, ph = 0, i;
    game_state = 0;
    SMS_displayOff();
    SMS_setSpriteMode(SPRITEMODE_NORMAL);
    SMS_mapROMBank(TITLE_BANK);
    SMS_loadTiles(title_tiles, 0, NTITLE_TILES * 32);
    SMS_loadTileMap(0, 0, title_map, 32 * 24 * 2);
    SMS_loadBGPalette(title_pal);
    SMS_setBackdropColor(0);
    no_sprites();
    SMS_displayOn();
    music_play(mus_title_a, mus_title_b, 1);
    clear_press();
    for (;;) {
        SMS_waitForVBlank();
        t++;
        if ((t & 3) == 0) {
            ph = (ph + 1) & 7;
            /* logo sheen: rotate the 8 metal shades */
            for (i = 0; i < 7; i++)
                SMS_setBGPaletteColor(9 + i, title_pal[9 + ((i + ph) % 7)]);
        }
        if ((t & 7) == 0)          /* twinkling stars */
            for (i = 0; i < 4; i++)
                SMS_setBGPaletteColor(4 + i, title_pal[4 + ((i + (t >> 3)) & 3)]);
        SMS_setBGPaletteColor(6, (t & 32) ? 0x3F : 0x15);
        if (t > 30 && ((pad_press[0] | pad_press[1]) & (PORT_A_KEY_1 | PORT_A_KEY_2))) break;
        clear_press();
    }
    sfx(SFX_RESPAWN);
}

/* ------------------------------------------------------------ text screens */
static void text_screen(void)
{
    u16 i;
    SMS_displayOff();
    SMS_setSpriteMode(SPRITEMODE_TALL);
    SMS_loadTiles(font_tiles, FONT_BASE, NFONT * 32);
    SMS_loadTiles(frame_tiles, FRAME_BASE, (NFRAME_TILES > 10 ? 10 : NFRAME_TILES) * 32);
    if (NFRAME_TILES > 10)
        SMS_loadTiles(frame_tiles + 10 * 32, 256 + SAT_FRAME, (NFRAME_TILES - 10) * 32);
    SMS_loadBGPalette(&level_pals[0]);
    SMS_loadSpritePalette(&level_pals[16]);
    SMS_setBackdropColor(HUD_BG_COL);
    SMS_setNextTileatXY(0, 0);
    for (i = 0; i < 768; i++) {
        u8 y = i >> 5;
        u8 v = frame_map[(y == 1 || y == 22) ? (i & 31) + 32 : 0];
        SMS_setTile(v < 10 ? FRAME_BASE + v : 256 + SAT_FRAME + v - 10);
    }
    no_sprites();
    set_cycle();
}

static void center(u8 y, const char *s)
{
    u8 n = 0;
    while (s[n]) n++;
    print_at((32 - n) >> 1, y, s);
}

static void opt_line(u8 row, const char *label, const char *val, u8 sel)
{
    char buf[16];
    u8 i = 0;
    print_at(2, row, sel ? ">" : " ");
    print_at(4, row, label);
    buf[0] = '<';
    while (val[i] && i < 13) { buf[i + 1] = val[i]; i++; }
    while (i < 13) buf[++i] = ' ';
    buf[14] = '>';
    buf[15] = 0;
    print_at(15, row, buf);
}

static const char * const cpu_names[] = { "HUMAN", "CPU" };
static const u8 limits[] = { 5, 10, 15, 20, 30 };
static u8 lim_idx = 1;

static void menu_draw(void)
{
    char num[3];
    num[0] = '0' + limits[lim_idx] / 10; num[1] = '0' + limits[lim_idx] % 10; num[2] = 0;
    opt_line(5, "PLAYER 1", skin_names[opt_skin[0]], menu_sel == 0);
    opt_line(7, "PLAYER 2", skin_names[opt_skin[1]], menu_sel == 1);
    opt_line(9, "PLAYER 2 IS", cpu_names[opt_cpu], menu_sel == 2);
    opt_line(11, "ARENA", level_names[level], menu_sel == 3);
    opt_line(13, "FRAG LIMIT", num, menu_sel == 4);
    print_at(2, 15, menu_sel == 5 ? ">" : " ");
    print_at(4, 15, "START MATCH");
}

static void menu_screen(void)
{
    u8 t = 0, k, dirty = 1;
    game_state = 1;
    text_screen();
    sprites_init();
    center(3, "STAR FRAG 3D - MATCH SETUP");
    center(18, "UP/DOWN PICK");
    center(19, "L/R CHANGE");
    center(20, "1 START");
    print_at(5, 23, "P1");
    print_at(25, 23, "P2");
    SMS_displayOn();
    if (!music_busy()) music_play(mus_title_a, mus_title_b, 1);
    clear_press();
    for (;;) {
        u8 rot = (t >> 4) & 7;
        if (dirty) { menu_draw(); dirty = 0; }
        SMS_initSprites();
        menu_sprite(48, 182, G_SKIN0 + opt_skin[0] * NSKINGFX + rot);
        menu_sprite(208, 182, G_SKIN0 + opt_skin[1] * NSKINGFX + ((8 - rot) & 7));
        SMS_finalizeSprites();
        SMS_waitForVBlank();
        SMS_copySpritestoSAT();
        frame_no++;
        t++;
        if ((t & 7) == 0) { if (++cyc_ph == 6) cyc_ph = 0; set_cycle(); }
        k = pad_press[0];
        if (k & PORT_A_KEY_UP) { menu_sel = menu_sel ? menu_sel - 1 : 5; dirty = 1; }
        if (k & PORT_A_KEY_DOWN) { menu_sel = menu_sel == 5 ? 0 : menu_sel + 1; dirty = 1; }
        if (k & (PORT_A_KEY_LEFT | PORT_A_KEY_RIGHT)) {
            u8 r = (k & PORT_A_KEY_RIGHT) ? 1 : 0;
            switch (menu_sel) {
            case 0: case 1: opt_skin[menu_sel] = r ? (opt_skin[menu_sel] + 1) % NSKINS
                                                   : (opt_skin[menu_sel] + NSKINS - 1) % NSKINS; break;
            case 2: opt_cpu ^= 1; break;
            case 3: level = r ? (level + 1) % NLEVELS : (level + NLEVELS - 1) % NLEVELS; break;
            case 4: lim_idx = r ? (lim_idx + 1) % 5 : (lim_idx + 4) % 5; break;
            }
            dirty = 1;
        }
        if (pad_press[1] & (PORT_A_KEY_LEFT | PORT_A_KEY_RIGHT)) {
            opt_skin[1] = (pad_press[1] & PORT_A_KEY_RIGHT) ? (opt_skin[1] + 1) % NSKINS
                                                             : (opt_skin[1] + NSKINS - 1) % NSKINS;
            opt_cpu = 0;
            dirty = 1;
        }
        if (dirty) sfx(SFX_MENU);
        if (k & PORT_A_KEY_1) {
            if (menu_sel == 5) break;
            menu_sel++;
            dirty = 1;
        }
        clear_press();
    }
    frag_limit = limits[lim_idx];
    music_stop();
    sfx(SFX_RESPAWN);
}

/* ------------------------------------------------------------ playing */
static void cast_both(u8 force)
{
    u8 p;
    for (p = 0; p < 2; p++) {
        Player *P = &pl[p];
        if (force || !P->cvalid || P->x != P->cx || P->y != P->cy || P->a != P->ca) {
            P->cx = P->x; P->cy = P->y; P->ca = P->a; P->cvalid = 1;
            px = P->x; py = P->y; pa = P->a;
            ray_base = p * VRAYS;
            cast_rays();
        }
    }
}

static void draw_both(void)
{
    dv_first = 0;
    draw_view();
    dv_first = 16;
    draw_view();
}

static void game_screen(void)
{
    u16 i;
    SMS_displayOff();
    SMS_setSpriteMode(SPRITEMODE_TALL);
    SMS_loadTiles(font_tiles, FONT_BASE, NFONT * 32);
    SMS_loadTiles(frame_tiles, FRAME_BASE, (NFRAME_TILES > 10 ? 10 : NFRAME_TILES) * 32);
    if (NFRAME_TILES > 10)
        SMS_loadTiles(frame_tiles + 10 * 32, 256 + SAT_FRAME, (NFRAME_TILES - 10) * 32);
    render_init();
    SMS_setNextTileatXY(0, 0);
    for (i = 0; i < 768; i++) {
        u8 v = frame_map[i];
        u16 t;
        if (v == 0xFF) t = SKY_BASE;
        else t = (v < 10 ? FRAME_BASE + v : 256 + SAT_FRAME + v - 10) | TILE_PRIORITY;
        SMS_setTile(t);
    }
    SMS_loadBGPalette(&level_pals[level * 32]);
    SMS_loadSpritePalette(&level_pals[level * 32 + 16]);
    SMS_setBackdropColor(HUD_BG_COL);
    set_cycle();
    sprites_init();
    hud_full();
    cast_both(1);
    build_sprites();
    draw_both();
    SMS_copySpritestoSAT();
    game_state = 2;
    SMS_displayOn();
}

static void do_pause(void)
{
    print_at(13, 1, "PAUSED");
    music_stop();
    SMS_resetPauseRequest();
    while (!SMS_queryPauseRequested()) SMS_waitForVBlank();
    SMS_resetPauseRequest();
    hud_full();
    {
        /* restore the strip under the text */
        u8 x;
        SMS_setNextTileatXY(13, 1);
        for (x = 13; x < 19; x++) {
            u8 v = frame_map[32 + x];
            SMS_setTile((v < 10 ? FRAME_BASE + v : 256 + SAT_FRAME + v - 10) | TILE_PRIORITY);
        }
    }
    music_play(mus_game_a, mus_game_b, 1);
}

static void play_match(void)
{
    u8 last, n, end_t = 0;
    level_load(level);
    pl[0].skin = opt_skin[0];
    pl[1].skin = opt_skin[1];
    pl[0].cpu = 0;
    pl[1].cpu = opt_cpu;
    match_new();
    game_screen();
    music_play(mus_game_a, mus_game_b, 1);
    last = vbl_count;
    for (;;) {
        n = vbl_count - last;
        last += n;
        if (n > 12) n = 12;     /* game time keeps pace down to 5 fps */
        if (n) game_tick(n);
        if (game_result) {
            end_t += n;
            if (end_t > 100) break;
        }
        cast_both(0);
        build_sprites();
        draw_both();
        SMS_waitForVBlank();
        SMS_copySpritestoSAT();
        palette_fx();
        hud_draw();
        frame_no++;
        frames_drawn++;
        if (SMS_queryPauseRequested()) { do_pause(); last = vbl_count; }
    }
    music_stop();
}

static void results_screen(void)
{
    u8 w = game_result - 1, t;
    game_state = 3;
    text_screen();
    sprites_init();
    center(3, "MATCH OVER");
    center(5, w ? "PLAYER 2 WINS!" : "PLAYER 1 WINS!");
    center(7, level_names[level]);
    print_at(4, 10, "P1");
    print_at(7, 10, skin_names[pl[0].skin]);
    print_num(18, 10, pl[0].frags < 0 ? 0 : pl[0].frags, 2);
    print_at(4, 12, "P2");
    print_at(7, 12, skin_names[pl[1].skin]);
    print_num(18, 12, pl[1].frags < 0 ? 0 : pl[1].frags, 2);
    print_at(21, 10, "FRAGS");
    print_at(21, 12, "FRAGS");
    center(14, "PRESS BUTTON 1");
    SMS_displayOn();
    music_play(mus_win_a, mus_win_b, 0);
    clear_press();
    for (t = 0; ; t++) {
        u8 rot = (t >> 3) & 7;
        SMS_initSprites();
        /* the winner celebrates (attack pose), the loser lies down */
        menu_sprite(128, 182, G_SKIN0 + pl[w].skin * NSKINGFX + ((t & 16) ? 16 : rot));
        SMS_finalizeSprites();
        SMS_waitForVBlank();
        SMS_copySpritestoSAT();
        frame_no++;
        if ((t & 7) == 0) { if (++cyc_ph == 6) cyc_ph = 0; set_cycle(); }
        if (t > 60 && ((pad_press[0] | pad_press[1]) & PORT_A_KEY_1)) break;
        if (t == 255) t = 61;
        clear_press();
    }
}

void main(void)
{
    snd_init();
    SMS_setFrameInterruptHandler(snd_isr);
    title_screen();
    for (;;) {
        menu_screen();
        play_match();
        results_screen();
    }
}
