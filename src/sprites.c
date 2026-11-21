/* sprites.c - objects and opponents drawn with PRE-SCALED hardware sprites,
 * in two views at once.
 *
 * Every graphic exists in ROM at 8 sizes (8..48 px, made offline by
 * tools/gen.py).  Each frame every object is projected into each player's
 * view, the nearest pre-scaled size is picked, and the image is placed with
 * 8x16 hardware sprites.  Image tiles live in a VRAM cache shared by both
 * views, uploaded only when an image first appears.  Walls hide sprites per
 * 8 px column using the ray depth buffer; a piece is only shown when it fits
 * entirely inside its own 128 px window, so nothing leaks into the other view.
 *
 * The opponent is drawn from one of 8 rotations (Doom's rule: the angle from
 * the viewer, relative to where the opponent faces).
 */
#include <SMSlib.h>
#include "defs.h"

/* per object type: world height and lift (1/128 wall height) */
static const u8 type_height[] = { 40, 44, 40, 44, 44, 44, 44, 44, 44, 44,   /* items */
                                  26, 20, 30, 28,                           /* projectiles */
                                  84, 24, 24, 84 };                         /* effects */
static const u8 type_z[]      = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                  34, 14, 34, 30,
                                  12, 40, 36, 0 };
#define PLAYER_H 96

#define NCE 16
static u8 c_g[NCE], c_s[NCE], c_pair[NCE], c_np[NCE], c_last[NCE];
static u8 pair_own[CACHE_PAIRS];
static u8 upload_budget;

void sprites_init(void)
{
    u8 i;
    for (i = 0; i < NCE; i++) c_g[i] = 0xFF;
    for (i = 0; i < CACHE_PAIRS; i++) pair_own[i] = 0xFF;
    pl[0].cur_hand = pl[1].cur_hand = 0xFF;
}

void hand_upload(u8 p)
{
    Player *P = &pl[p];
    P->cur_hand = P->weapon;
    SMS_mapROMBank(MISC_BANK);
    SMS_loadTiles(hand_tiles + (u16)P->weapon * 512, 256 + SAT_WEAPON + p * 16, 512);
}

u8 find_run(u8 np)
{
    u8 i, run = 0;
    for (i = 0; i < CACHE_PAIRS; i++) {
        if (pair_own[i] == 0xFF) {
            run++;
            if (run == np) return i + 1 - np;
        } else run = 0;
    }
    return 0xFF;
}

void evict(u8 e)
{
    u8 i;
    for (i = 0; i < c_np[e]; i++) pair_own[c_pair[e] + i] = 0xFF;
    c_g[e] = 0xFF;
}

u8 evict_oldest(void)
{
    u8 e, best = 0xFF, age = 0;
    for (e = 0; e < NCE; e++) {
        if (c_g[e] != 0xFF && c_last[e] != frame_no) {
            u8 a = frame_no - c_last[e];
            if (a >= age) { age = a; best = e; }
        }
    }
    if (best == 0xFF) return 0;
    evict(best);
    return 1;
}

/* Returns the SAT tile of image (g,s) and leaves g's bank mapped.  *ps may be
   changed to a cached neighbour size when this frame's upload budget is spent. */
u8 cache_get(u8 g, u8 *ps)
{
    u8 e, s = *ps, np, pair, best = 0xFF, bd = 0xFF;
    const SprImg *img;
    SMS_mapROMBank(gfx_bank[g]);
    for (e = 0; e < NCE; e++) {
        if (c_g[e] == g) {
            u8 d;
            if (c_s[e] == s) { c_last[e] = frame_no; return SAT_CACHE + c_pair[e] * 2; }
            d = c_s[e] > s ? c_s[e] - s : s - c_s[e];
            if (d < bd) { bd = d; best = e; }
        }
    }
    img = &gfx_tab[g][s];
    np = img->npieces;
    if (np > upload_budget) {
        if (best != 0xFF) {
            *ps = c_s[best];
            c_last[best] = frame_no;
            return SAT_CACHE + c_pair[best] * 2;
        }
        return 0xFF;
    }
    for (;;) {
        pair = find_run(np);
        if (pair != 0xFF) break;
        if (!evict_oldest()) return 0xFF;
    }
    for (e = 0; e < NCE; e++)
        if (c_g[e] == 0xFF) break;
    if (e == NCE) {
        if (!evict_oldest()) return 0xFF;
        for (e = 0; e < NCE; e++)
            if (c_g[e] == 0xFF) break;
        pair = find_run(np);
        if (pair == 0xFF) return 0xFF;
    }
    c_g[e] = g; c_s[e] = s; c_pair[e] = pair; c_np[e] = np; c_last[e] = frame_no;
    for (np = 0; np < c_np[e]; np++) pair_own[pair + np] = e;
    SMS_VRAMmemcpy((256 + SAT_CACHE + pair * 2) * 32, img->data, c_np[e] * 64);
    upload_budget -= c_np[e];
    return SAT_CACHE + pair * 2;
}

void set_proj_angle(u16 a)
{
    s16 ca = sintab[(a + 256) & 1023], sa = sintab[a & 1023];
    pj_ca = ca < 0 ? (ca < -255 ? 255 : -ca) : (ca > 255 ? 255 : ca);
    pj_sa = sa < 0 ? (sa < -255 ? 255 : -sa) : (sa > 255 ? 255 : sa);
    pj_cf = (ca < 0 ? 1 : 0) | (sa < 0 ? 2 : 0);
}

/* ------------------------------------------------------------ visibility lists */
#define NVIS 12
static u8 vis_g[2][NVIS], vis_lvl[2][NVIS], vis_bot[2][NVIS];
static s16 vis_cx[2][NVIS];
static u16 vis_depth[2][NVIS];
static u8 nvis[2];

/* project world point (x,y) into view v (projection angle already set) */
static u8 cv, ch, cz, cg;       /* consider(): view, height, lift, graphic */
void consider(void)
{
    s16 depth, lat, sxo;
    u8 hh, want, lvl, j, n, v = cv, h = ch, z = cz, g = cg;
    project_d();
    depth = pj_depth;
    if (depth < 64) return;
    lat = pj_lat;
    hh = hhtab[(u16)depth >> 3];
    sxo = (s16)mul8(hh, (u16)(lat < 0 ? -lat : lat)) * 2;
    if (sxo > 72) return;
    if (lat < 0) sxo = -sxo;
    want = (u8)(((u16)h * hh) >> 6 > 255 ? 255 : ((u16)h * hh) >> 6);
    if (want < 5) return;
    lvl = 0;
    while (lvl < NSIZES - 1 && size_px[lvl + 1] <= want + (want >> 3)) lvl++;
    n = nvis[v];
    if (n == NVIS) {
        if (vis_depth[v][NVIS - 1] <= (u16)depth) return;
        n = NVIS - 1;                 /* replace the farthest */
    } else nvis[v]++;
    for (j = n; j > 0 && vis_depth[v][j - 1] > (u16)depth; j--) {
        vis_g[v][j] = vis_g[v][j - 1];
        vis_lvl[v][j] = vis_lvl[v][j - 1];
        vis_bot[v][j] = vis_bot[v][j - 1];
        vis_cx[v][j] = vis_cx[v][j - 1];
        vis_depth[v][j] = vis_depth[v][j - 1];
    }
    {
        u16 b = HORIZON_Y + hh - (((u16)z * hh) >> 6);
        vis_bot[v][j] = b > 200 ? 200 : (u8)b;
    }
    vis_g[v][j] = g;
    vis_lvl[v][j] = lvl;
    vis_cx[v][j] = (s16)(v * 128 + 64) + sxo;
    vis_depth[v][j] = depth;
}

u8 obj_graphic(Obj *o)
{
    switch (o->type) {
    case OT_FLAME: return o->timer > 12 ? G_FLAME0 : G_FLAME1;
    case OT_EXPLO: return o->timer > 9 ? G_EXPLO0 : G_EXPLO1;
    default: return o->type;     /* graphics 0..17 follow the object types */
    }
}

u8 abs8(s16 v) { v = v < 0 ? -v : v; v >>= 4; return v > 255 ? 255 : (u8)v; }

/* which of the 8 Doom rotations of player o the viewer at (vx,vy) sees */
u8 rotation(Player *o, u16 vx, u16 vy)
{
    s16 f, r;
    u8 af, ar, s;
    set_proj_angle(o->a);
    pj_dx = vx - o->x; pj_dy = vy - o->y;
    project();
    f = pj_depth; r = pj_lat;        /* viewer in the opponent's frame: ahead, right */
    af = abs8(f); ar = abs8(r);
    if ((u16)ar * 106 < (u16)af * 44) s = f >= 0 ? 0 : 4;
    else if ((u16)af * 106 < (u16)ar * 44) s = r >= 0 ? 2 : 6;
    else if (f >= 0) s = r >= 0 ? 1 : 7;
    else s = r >= 0 ? 3 : 5;
    /* s: viewer angle clockwise from facing, in 45 degree steps -> Doom frame */
    return (8 - s) & 7;
}

u8 player_graphic(Player *o, u8 rot)
{
    u8 base = G_SKIN0 + o->skin * NSKINGFX;
    if (o->dead) return base + (o->dead < 18 ? 18 : 19);
    if (rot == 0 && o->attack_t) return base + 16;
    if (o->pain_t && (rot == 0 || rot == 1 || rot == 7)) return base + 17;
    return base + rot + (((o->anim >> 3) & 1) ? 8 : 0);
}

void build_view(u8 v)
{
    Player *V = &pl[v], *O = &pl[v ^ 1];
    u8 k;
    Obj *o;
    nvis[v] = 0;
    px = V->x; py = V->y;
    /* the opponent */
    {
        u8 rot = rotation(O, V->x, V->y);
        set_proj_angle(V->a);
        cv = v; ch = PLAYER_H; cz = 0; cg = player_graphic(O, rot);
        pj_dx = O->x - px; pj_dy = O->y - py;
        consider();
    }
    for (k = 0, o = objs; k < MAXOBJ; k++, o++) {
        u8 t = o->type;
        s16 d;
        if (t == OT_NONE || o->state) continue;
        /* small things vanish (< 5 px) beyond ~7 tiles; explosions are big */
        d = o->x - px;
        if (d > 0x0700 || d < -0x0700) { if (t != OT_EXPLO && t != OT_TFOG) continue; if (d > 0x0C00 || d < -0x0C00) continue; }
        pj_dx = d;
        d = o->y - py;
        if (d > 0x0700 || d < -0x0700) { if (t != OT_EXPLO && t != OT_TFOG) continue; if (d > 0x0C00 || d < -0x0C00) continue; }
        pj_dy = d;
        ch = type_height[t]; cz = type_z[t]; cg = obj_graphic(o);
        consider();
    }
}

void emit_view(u8 v)
{
    u8 i, n, lo_ray = v * VRAYS, hi_ray = v * VRAYS + VRAYS - 1;
    s16 x0 = v * 128;
    for (i = 0; i < nvis[v]; i++) {
        u8 lvl = vis_lvl[v][i], g = vis_g[v][i], t;
        const SprImg *img;
        const u8 *pc;
        s16 left, top;
        u16 depth = vis_depth[v][i];
        t = cache_get(g, &lvl);
        if (t == 0xFF) continue;
        img = &gfx_tab[g][lvl];
        left = vis_cx[v][i] - img->cols * 4;
        top = (s16)vis_bot[v][i] - img->rows * 16;
        pc = img->pieces;
        for (n = 0; n < img->npieces; n++, t += 2) {
            u8 c = pc[n];
            s16 x = left + (c & 15) * 8;
            s16 y = top + (c >> 4) * 16;
            s16 ri;
            if (x < x0 || x > x0 + 120) continue;
            if (y >= VIEW_BOT || y < VIEW_TY * 8 - 15) continue;
            ri = (x + 4) >> 2;
            if (ri < lo_ray) ri = lo_ray;
            if (ri > hi_ray) ri = hi_ray;
            if (zbuf[ri] < depth) continue;
            SMS_addSprite((u8)x, (u8)y, t);
        }
    }
}

void build_sprites(void)
{
    u8 p, first;
    upload_budget = 40;
    SMS_mapROMBank(ANG_BANK);
    build_view(0);
    build_view(1);
    SMS_initSprites();
    /* weapons in hand first: they are on top */
    for (p = 0; p < 2; p++) {
        Player *P = &pl[p];
        u8 c, r, x, y, t;
        if (P->dead || P->cur_hand != P->weapon) continue;
        x = p * 128 + 66 + (P->wframe ? 1 : 0);
        y = VIEW_BOT - 32 + P->bob + (P->wframe ? 3 : 0);
        t = SAT_WEAPON + p * 16 + P->wframe * 8;
        for (c = 0; c < 2; c++)
            for (r = 0; r < 2; r++, t += 2)
                SMS_addSprite(x + c * 8, y + r * 16, t);
    }
    /* the two views take turns going first, so 8-per-line drop-outs flicker
       between them instead of always hiding the same view */
    first = frame_no & 1;
    emit_view(first);
    emit_view(first ^ 1);
    SMS_finalizeSprites();
}

/* menu: graphic g at its largest size, bottom-centred at (x, y) */
void menu_sprite(u8 x, u8 y, u8 g)
{
    u8 lvl = NSIZES - 1, t, n;
    const SprImg *img;
    const u8 *pc;
    upload_budget = 40;
    t = cache_get(g, &lvl);
    if (t == 0xFF) return;
    img = &gfx_tab[g][lvl];
    pc = img->pieces;
    for (n = 0; n < img->npieces; n++, t += 2) {
        u8 c = pc[n];
        SMS_addSprite(x - img->cols * 4 + (c & 15) * 8, y - img->rows * 16 + (c >> 4) * 16, t);
    }
}
