/* bot.c - a simple CPU opponent.  It produces pad bits, so it moves, turns and
 * fires under exactly the same rules as a human player. */
#include <SMSlib.h>
#include "defs.h"

#define K_UP 1
#define K_DOWN 2
#define K_LEFT 4
#define K_RIGHT 8
#define K_1 16
#define K_2 32

u8 rand8(void);
u8 los(u16 x0, u16 y0, u16 x1, u16 y1);
u16 approx_dist(s16 dx, s16 dy);
void select_best_weapon(u8 p);

static u16 last_x, last_y;
static u8 stuck_t, turn_t, turn_dir, strafe_t, think, vis, react;

/* Navigation: a breadth-first distance field toward the target cell, in the
 * free RAM page under the ray caster (arenas are at most 32 x 22 cells). */
#define DIST ((u8 *)0xD400)
#define NAVCELLS 704
static u16 bfs_q[256];
static u16 bfs_target = 0xFFFF;
static u8 bfs_age;

static void bfs(u16 t)
{
    u16 i;
    u8 head = 0, tail = 0;
    u8 *D = DIST;
    for (i = 0; i < NAVCELLS; i++) D[i] = 0xFF;
    bfs_target = t;
    bfs_age = 0;
    if (map[t]) return;
    D[t] = 0;
    bfs_q[tail++] = t;
    while (head != tail) {
        u16 c = bfs_q[head++];
        u8 d = D[c] + 1;
        if (d == 0xFF) d = 0xFE;
        /* the arena border is always wall, so floor cells never sit on the edge */
        if (!map[c - 1] && D[c - 1] == 0xFF) { D[c - 1] = d; bfs_q[tail++] = c - 1; }
        if (!map[c + 1] && D[c + 1] == 0xFF) { D[c + 1] = d; bfs_q[tail++] = c + 1; }
        if (c >= 32 && !map[c - 32] && D[c - 32] == 0xFF) { D[c - 32] = d; bfs_q[tail++] = c - 32; }
        if (c + 32 < NAVCELLS && !map[c + 32] && D[c + 32] == 0xFF) { D[c + 32] = d; bfs_q[tail++] = c + 32; }
    }
}

static u16 cell_of(u16 x, u16 y) { return ((y >> 8) << 5) | (x >> 8); }

/* the centre of the neighbouring cell that is one step closer to the target */
static void next_step(Player *P, u16 *gx, u16 *gy)
{
    u16 c = cell_of(P->x, P->y), best = c;
    u8 bd = DIST[c];
    if (DIST[c - 1] < bd) { bd = DIST[c - 1]; best = c - 1; }
    if (DIST[c + 1] < bd) { bd = DIST[c + 1]; best = c + 1; }
    if (DIST[c - 32] < bd) { bd = DIST[c - 32]; best = c - 32; }
    if (DIST[c + 32] < bd) { bd = DIST[c + 32]; best = c + 32; }
    *gx = ((best & 31) << 8) | 0x80;
    *gy = ((best >> 5) << 8) | 0x80;
}

/* keys that turn p toward world point (x,y); sets *ahead when roughly facing it */
static u8 steer(Player *P, u16 x, u16 y, u8 *ahead)
{
    s16 depth, lat;
    set_proj_angle(P->a);
    pj_dx = x - P->x; pj_dy = y - P->y;
    project();
    depth = pj_depth; lat = pj_lat;
    *ahead = depth > 0 && (lat < 0 ? -lat : lat) < 0x30 + (depth >> 3);
    if (depth <= 0) return lat >= 0 ? K_RIGHT : K_LEFT;
    if (lat > (depth >> 4) + 8) return K_RIGHT;
    if (lat < -(depth >> 4) - 8) return K_LEFT;
    return 0;
}

u8 bot_keys(u8 p)
{
    Player *P = &pl[p], *O = &pl[p ^ 1];
    u8 keys = 0, ahead;
    u16 d, gx, gy;
    if (P->dead) { bfs_target = 0xFFFF; return (P->dead > 70 && (P->dead & 8)) ? K_1 : 0; }
    if (bfs_age < 255) bfs_age++;
    if (++think >= 4) {
        think = 0;
        vis = !O->dead && los(P->x, P->y, O->x, O->y);
        select_best_weapon(p);
    }
    d = approx_dist((s16)(O->x - P->x), (s16)(O->y - P->y));
    if (vis) {
        keys = steer(P, O->x, O->y, &ahead);
        if (react < 20) react++;
        if (ahead && react > 12) keys |= K_1;
        if (d > 0x380) keys |= K_UP;
        else if (d < 0x180 && P->weapon != W_FLAME) keys |= K_DOWN;
        else if (P->weapon == W_FLAME) keys |= K_UP;
        if (++strafe_t > 90) strafe_t = 0;
        if (ahead && strafe_t > 50) keys = (keys & ~(K_LEFT | K_RIGHT)) | K_2 | (strafe_t > 70 ? K_LEFT : K_RIGHT);
    } else {
        react = 0;
        /* hunt: follow the distance field toward the opponent (or its last
           position while it is dead) */
        u16 t = cell_of(O->x, O->y);
        if (t >= NAVCELLS) t = bfs_target;
        if (bfs_target == 0xFFFF || (t != bfs_target && bfs_age > 20)) bfs(t);
        next_step(P, &gx, &gy);
        keys = steer(P, gx, gy, &ahead);
        if (ahead || !(keys & (K_LEFT | K_RIGHT))) keys |= K_UP;
        if (turn_t) {
            /* unstick: back off while turning */
            turn_t--;
            keys = (keys & ~(K_LEFT | K_RIGHT | K_UP)) | turn_dir | K_DOWN;
        }
    }
    /* stuck against a wall: turn away for a while */
    if ((keys & K_UP) && approx_dist((s16)(P->x - last_x), (s16)(P->y - last_y)) < 2) {
        if (++stuck_t > 6) {
            stuck_t = 0;
            turn_t = 12 + (rand8() & 31);
            turn_dir = (rand8() & 1) ? K_LEFT : K_RIGHT;
        }
    } else stuck_t = 0;
    last_x = P->x; last_y = P->y;
    return keys;
}
