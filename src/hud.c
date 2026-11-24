/* hud.c - text and the two players' HUD halves */
#include <SMSlib.h>
#include "defs.h"

#define MSG_ROW 19      /* message; then shield/power, clock; radar at the right */

void print_at(u8 x, u8 y, const char *s)
{
    SMS_setNextTileatXY(x, y);
    while (*s) {
        u8 c = (u8)*s++;
        if (c < 32 || c > 90) c = 32;
        SMS_setTile((FONT_BASE + font_map[c - 32]) | TILE_PRIORITY);
    }
}

/* digits: number of characters; | 0x80: blank leading zeros */
void print_num(u8 x, u8 y, u16 v, u8 digits)
{
    char buf[7];
    u8 blank = digits & 0x80;
    u8 i;
    digits &= 0x7F;
    i = digits;
    buf[digits] = 0;
    while (i) {
        i--;
        if (blank && v == 0 && i != digits - 1) buf[i] = ' ';
        else buf[i] = '0' + (u8)(v % 10);
        v /= 10;
    }
    print_at(x, y, buf);
}

static void print_pad(u8 x, u8 y, const char *s, u8 w)
{
    char buf[17];
    u8 i = 0;
    while (s[i] && i < w) { buf[i] = s[i]; i++; }
    while (i < w) buf[i++] = ' ';
    buf[w] = 0;
    print_at(x, y, buf);
}

static void face_update(u8 p)
{
    Player *P = &pl[p];
    u8 f;
    if (P->dead) f = 7;
    else if (P->ouch) f = 5;
    else if (P->grin) f = 6;
    else if (P->health > 80) f = 0;
    else if (P->health > 60) f = 1;
    else if (P->health > 40) f = 2;
    else if (P->health > 20) f = 3;
    else f = 4;
    if (f != P->cur_face) {
        P->cur_face = f;
        SMS_mapROMBank(face_bank[P->skin]);
        SMS_loadTiles(face_data[P->skin] + (u16)f * 384, 256 + SAT_FACE + p * 12, 384);
    }
}

static void frags(u8 p)
{
    s8 f = pl[p].frags;
    u8 c = p * 16;
    print_at(c + 11, 0, f < 0 ? "-" : " ");
    print_num(c + 12, 0, f < 0 ? -f : f, 2);
}

static void msg_line(u8 p)
{
    Player *P = &pl[p];
    u8 c = p * 16 + 1;
    const char *s = "";
    switch (P->msg) {
    case MSG_FRAGGED:   s = p ? "FRAGGED P1!" : "FRAGGED P2!"; break;
    case MSG_FRAGGEDBY: s = p ? "FRAGGED BY P1" : "FRAGGED BY P2"; break;
    case MSG_SUICIDE:   s = "OOPS! SUICIDE"; break;
    case MSG_RESPAWN:   s = "RESPAWNED"; break;
    case MSG_POWER:     s = "OVERDRIVE!"; break;
    case MSG_SUDDEN:    s = "SUDDEN DEATH!"; break;
    case MSG_GOT:       print_at(c, MSG_ROW, "GOT "); print_pad(c + 4, MSG_ROW, weapon_names[P->weapon], 10); goto power;
    }
    if (P->dead > 45 && P->msg == MSG_NONE) s = "PRESS 1";
    print_pad(c, MSG_ROW, s, 14);
power:
    if (shield[p]) print_at(c, MSG_ROW + 1, "SHIELD  ");
    else if (P->power) {
        print_at(c, MSG_ROW + 1, "POWER ");
        print_num(c + 6, MSG_ROW + 1, P->power / 60, 2);
    } else print_at(c, MSG_ROW + 1, "        ");
}

/* ---------------------------------------------------------------- hit arrows
   Shown in the thin strips above (front) and below (back) the view; left and
   right hits light both ends of both strips. */
u8 arrow_shown[2];            /* (global for the playtests) */

static void strip_cell(u8 x, u8 y, u16 tile)
{
    SMS_setNextTileatXY(x, y);
    if (tile == 0xFFFF) {           /* restore the frame tile */
        u8 v;
        SMS_mapROMBank(MISC_BANK);
        v = frame_map[y * 32 + x];
        tile = v < 10 ? FRAME_BASE + v : 256 + SAT_FRAME + v - 10;
    }
    SMS_setTile(tile | TILE_PRIORITY);
}

static void arrow_draw(u8 p, u8 dir, u8 on)
{
    u8 c = p * 16;
    u16 t = on ? 256 + SAT_ARROW + dir - 1 : 0xFFFF;
    switch (dir) {
    case HIT_LEFT:  strip_cell(c + 1, 1, t);  strip_cell(c + 1, 14, t);  break;
    case HIT_RIGHT: strip_cell(c + 14, 1, t); strip_cell(c + 14, 14, t); break;
    case HIT_FRONT: strip_cell(c + 7, 1, t);  strip_cell(c + 8, 1, t);   break;
    case HIT_BACK:  strip_cell(c + 7, 14, t); strip_cell(c + 8, 14, t);  break;
    }
}

static void arrows(u8 p)
{
    u8 want = (hit_t[p] && !pl[p].dead) ? hit_dir[p] : 0;
    if (want == arrow_shown[p]) return;
    if (arrow_shown[p]) arrow_draw(p, arrow_shown[p], 0);
    if (want) arrow_draw(p, want, 1);
    arrow_shown[p] = want;
}

/* ---------------------------------------------------------------- radar
   3 x 3 tiles, turning with the player (forward is up), 1 px = 1/2 tile.
   An opponent out of range sits on the edge, so the dot always points at them. */
u8 dot_x[2], dot_y[2];       /* (global for the playtests) */
static u8 tbuf[32];

static void radar_tile(u8 p, u8 t, u8 nx, u8 ny)
{
    const u8 *src;
    u8 i, tx = (t % 3) * 8, ty = (t / 3) * 8;
    SMS_mapROMBank(MISC_BANK);
    src = radar_tiles + t * 32;
    for (i = 0; i < 32; i++) tbuf[i] = src[i];
    if (nx != 0xFF) {
        u8 x, y;
        for (y = ny; y < ny + 2; y++)
            for (x = nx; x < nx + 2; x++)
                if (x >= tx && x < tx + 8 && y >= ty && y < ty + 8) {
                    u8 *r = tbuf + (y - ty) * 4, b = 0x80 >> (x - tx);
                    r[0] &= ~b; r[1] |= b; r[2] |= b; r[3] &= ~b;     /* colour 6: red */
                }
    }
    SMS_loadTiles(tbuf, 256 + SAT_RADAR + p * 9 + t, 32);
}

static u16 dot_tiles(u8 x, u8 y)
{
    u16 m = 0;
    if (x == 0xFF) return 0;
    m |= 1 << ((y >> 3) * 3 + (x >> 3));
    m |= 1 << ((y >> 3) * 3 + ((x + 1) >> 3));
    m |= 1 << (((y + 1) >> 3) * 3 + (x >> 3));
    m |= 1 << (((y + 1) >> 3) * 3 + ((x + 1) >> 3));
    return m;
}

static void radar(u8 p)
{
    Player *P = &pl[p], *O = &pl[p ^ 1];
    u8 nx = 0xFF, ny = 0xFF, t;
    u16 m;
    if (!O->dead) {
        s16 dep, lat;
        SMS_mapROMBank(ANG_BANK);
        set_proj_angle(P->a);
        pj_dx = O->x - P->x; pj_dy = O->y - P->y;
        project();
        dep = pj_depth >> 7; lat = pj_lat >> 7;
        if (lat > 10) lat = 10;
        if (lat < -10) lat = -10;
        if (dep > 10) dep = 10;
        if (dep < -10) dep = -10;
        nx = (u8)(11 + lat); ny = (u8)(11 - dep);
    }
    if (nx == dot_x[p] && ny == dot_y[p]) return;
    m = dot_tiles(dot_x[p], dot_y[p]) | dot_tiles(nx, ny);
    for (t = 0; t < 9; t++)
        if (m & (1 << t)) radar_tile(p, t, nx, ny);
    dot_x[p] = nx; dot_y[p] = ny;
}

/* ---------------------------------------------------------------- match clock */
static u16 clock_sec = 0xFFFF;

static void clock_draw(void)
{
    u16 sec;
    u8 p;
    char buf[10];
    if (!time_limit) return;
    sec = (time_left + 59) / 60;
    if (sec == clock_sec) return;
    clock_sec = sec;
    buf[0] = 'T'; buf[1] = 'I'; buf[2] = 'M'; buf[3] = 'E'; buf[4] = ' ';
    buf[5] = '0' + sec / 60; buf[6] = ':';
    buf[7] = '0' + (sec % 60) / 10; buf[8] = '0' + sec % 10; buf[9] = 0;
    for (p = 0; p < 2; p++) print_at(p * 16 + 1, MSG_ROW + 2, buf);
}

/* one player's dirty fields; at most one tile upload per call */
static void hud_player(u8 p)
{
    Player *P = &pl[p];
    u8 d = P->dirty, c = p * 16 + 5;
    if (P->ouch && P->cur_face != 5) d |= D_FACE;
    if (P->dead > 45 && P->dead < 52) d |= D_MSG;
    if (!d) return;
    P->dirty = 0;
    if (d & D_HEALTH) print_num(c + 7, 15, P->health, 0x83);
    if (d & D_ARMOR) print_num(c + 7, 16, P->armor, 0x83);
    if (d & D_WEAPON) {
        print_pad(c, 17, weapon_names[P->weapon], 10);
        if (P->weapon == W_BLASTER) print_at(c + 7, 18, "---");
        else print_num(c + 7, 18, P->ammo[P->weapon], 3);
    }
    if (d & D_FRAGS) frags(p);
    if (d & D_MSG) msg_line(p);
    if (P->cur_hand != P->weapon) { hand_upload(p); P->dirty |= d & D_FACE; return; }
    if (d & D_FACE) face_update(p);
}

void hud_draw(void)
{
    static u8 turn;
    turn ^= 1;
    hud_player(turn);
    hud_player(turn ^ 1);
    arrows(0);
    arrows(1);
    radar(turn);            /* one radar per frame, alternating */
    clock_draw();
}

void hud_full(void)
{
    u8 p, x, y;
    clock_sec = 0xFFFF;
    for (p = 0; p < 2; p++) {
        Player *P = &pl[p];
        u8 c = p * 16;
        print_at(c + 1, 0, p ? "P2" : "P1");
        print_pad(c + 4, 0, skin_names[P->skin], 7);
        print_at(c + 5, 15, "HEALTH");
        print_at(c + 5, 16, "ARMOR");
        print_at(c + 5, 18, "AMMO");
        for (y = 0; y < 3; y++) {
            SMS_setNextTileatXY(c + 12, MSG_ROW + 1 + y);
            for (x = 0; x < 3; x++)
                SMS_setTile((256 + SAT_RADAR + p * 9 + y * 3 + x) | TILE_PRIORITY);
        }
        for (x = 0; x < 9; x++) radar_tile(p, x, 0xFF, 0xFF);
        dot_x[p] = dot_y[p] = 0xFF;
        if (arrow_shown[p]) arrow_draw(p, arrow_shown[p], 0);
        arrow_shown[p] = 0;
        for (y = 0; y < 4; y++) {
            SMS_setNextTileatXY(c + 1, 15 + y);
            for (x = 0; x < 3; x++)
                SMS_setTile((256 + SAT_FACE + p * 12 + y * 3 + x) | TILE_PRIORITY);
        }
        P->cur_face = 0xFF;
        P->dirty = D_ALL;
        face_update(p);
        hand_upload(p);
        P->dirty = D_ALL;
        hud_player(p);
    }
}
