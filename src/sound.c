/* sound.c - tiny PSG driver, run from the frame interrupt, which also latches
 * both joypads.  Music on tone channels 0/1, sound effects on channel 2 + noise. */
#include <SMSlib.h>
#include "defs.h"

__sfr __at 0x7F PSGPort;
__sfr __at 0xDC IOPortA;
__sfr __at 0xDD IOPortB;

volatile u8 vbl_count;
volatile u8 pad_held[2], pad_press[2];
volatile u8 b2_tap[2];          /* button 2 tapped on its own (no left/right) */
static u8 pad_prev[2], b2_cnt[2], b2_dir[2];

static const u8 *mus_p[2], *mus_start[2];
static u8 mus_t[2], mus_el[2], mus_rest[2];
static u8 mus_loop, mus_on;
static const u8 mus_base[2] = { 3, 5 };
static volatile u8 sfx_id, sfx_t;

static void psg_tone(u8 ch, u16 per)
{
    PSGPort = 0x80 | (ch << 5) | (per & 0x0F);
    PSGPort = (per >> 4) & 0x3F;
}

static void psg_vol(u8 ch, u8 att)
{
    PSGPort = 0x90 | (ch << 5) | (att > 15 ? 15 : att);
}

void snd_init(void)
{
    u8 c;
    mus_on = 0;
    sfx_id = 0;
    for (c = 0; c < 4; c++) psg_vol(c, 15);
}

void music_play(const u8 *a, const u8 *b, u8 loop)
{
    __asm__("di");
    mus_start[0] = mus_p[0] = a;
    mus_start[1] = mus_p[1] = b;
    mus_t[0] = mus_t[1] = 1;
    mus_loop = loop;
    mus_on = 3;
    __asm__("ei");
}

void music_stop(void)
{
    mus_on = 0;
    psg_vol(0, 15);
    psg_vol(1, 15);
}

u8 music_busy(void) { return mus_on; }

void sfx(u8 id)
{
    /* explosions and deaths are not cut short by smaller sounds */
    if ((sfx_id == SFX_EXPLODE || sfx_id == SFX_DIE) && sfx_t < 10 && id != SFX_EXPLODE && id != SFX_DIE) return;
    sfx_id = id;
    sfx_t = 0;
}

static void music_step(u8 c)
{
    const u8 *p;
    if (!(mus_on & (1 << c))) return;
    if (--mus_t[c]) {
        mus_el[c]++;
        if (!mus_rest[c]) psg_vol(c, mus_base[c] + (mus_el[c] >> 3));
        return;
    }
    p = mus_p[c];
    if (p[1] & 0x40) {
        if (!mus_loop) { mus_on &= ~(1 << c); psg_vol(c, 15); return; }
        p = mus_start[c];
    }
    mus_t[c] = p[2];
    mus_el[c] = 0;
    if (p[1] & 0x80) {
        mus_rest[c] = 1;
        psg_vol(c, 15);
    } else {
        mus_rest[c] = 0;
        psg_tone(c, p[0] | ((u16)(p[1] & 3) << 8));
        psg_vol(c, mus_base[c]);
    }
    mus_p[c] = p + 3;
}

static const u16 arp[] = { 254, 214, 170, 127, 107, 85 };

static void sfx_step(void)
{
    u8 t = sfx_t, len;
    switch (sfx_id) {
    case 0: return;
    case SFX_BLASTER:
        len = 8;  psg_tone(2, 90 + t * 40); psg_vol(2, t); break;
    case SFX_RIFLE:
        len = 4;  PSGPort = 0xE4; psg_vol(3, 1 + t * 2); psg_tone(2, 400); psg_vol(2, 4 + t * 3); break;
    case SFX_PLASMA:
        len = 9;  psg_tone(2, 40 + ((t & 1) ? 30 : 0) + t * 12); psg_vol(2, t >> 1); break;
    case SFX_GREN:
        len = 8;  psg_tone(2, 500 - t * 20); psg_vol(2, 2 + t); PSGPort = 0xE5; psg_vol(3, 6 + t); break;
    case SFX_ROCKET:
        len = 16; PSGPort = 0xE6; psg_vol(3, 2 + (t >> 1)); psg_tone(2, 600 + t * 8); psg_vol(2, 6 + (t >> 1)); break;
    case SFX_FLAME:
        len = 5;  PSGPort = 0xE4; psg_vol(3, 5 + t * 2); break;
    case SFX_RAIL:
        len = 20; psg_tone(2, 30 + t * 6); psg_vol(2, t >> 1); PSGPort = 0xE4; psg_vol(3, 4 + (t >> 1)); break;
    case SFX_EXPLODE:
        len = 30; PSGPort = 0xE6 | (t > 6 ? 1 : 0); psg_vol(3, t >> 1); psg_tone(2, 900 + t * 4); psg_vol(2, 4 + (t >> 1)); break;
    case SFX_PICK:
        len = 12; psg_tone(2, arp[t >> 2]); psg_vol(2, 1 + (t & 3)); break;
    case SFX_WEAPON:
        len = 16; psg_tone(2, arp[(t >> 2) + 1] >> 1); psg_vol(2, 1 + (t & 3)); break;
    case SFX_POWER:
        len = 24; psg_tone(2, arp[(t >> 2) % 6] >> (t >> 4)); psg_vol(2, 1 + (t & 3)); break;
    case SFX_HURT:
        len = 12; psg_tone(2, 700 + t * 15); psg_vol(2, 3 + (t >> 1)); PSGPort = 0xE5; psg_vol(3, 4 + (t >> 1)); break;
    case SFX_DIE:
        len = 28; psg_tone(2, 300 + t * 20 + ((t & 2) ? 40 : 0)); psg_vol(2, t >> 1); PSGPort = 0xE6; psg_vol(3, 4 + (t >> 1)); break;
    case SFX_RESPAWN:
        len = 20; psg_tone(2, 200 - t * 8); psg_vol(2, 2 + (t >> 2)); break;
    case SFX_MENU:
        len = 4;  psg_tone(2, 180); psg_vol(2, 3 + t * 3); break;
    case SFX_BOUNCE:
        len = 4;  psg_tone(2, 350); psg_vol(2, 6 + t * 2); break;
    default: len = 0;
    }
    if (++sfx_t >= len) {
        sfx_id = 0;
        psg_vol(2, 15);
        psg_vol(3, 15);
    }
}

/* Latching in the interrupt means a quick press or tap is never lost, however
   slowly the 3D views are being drawn. */
static void pad_latch(u8 p, u8 k)
{
    pad_press[p] |= k & ~pad_prev[p];
    pad_held[p] = pad_prev[p] = k;
    if (k & 0x20) {
        if (b2_cnt[p] < 255) b2_cnt[p]++;
        if (k & 0x0C) b2_dir[p] = 1;
    } else {
        if (b2_cnt[p] && b2_cnt[p] < 24 && !b2_dir[p]) b2_tap[p] = 1;
        b2_cnt[p] = 0;
        b2_dir[p] = 0;
    }
}

/* frame interrupt: count frames, latch both pads, run the sound */
void snd_isr(void)
{
    u8 a = ~IOPortA, b = ~IOPortB, k;
    vbl_count++;
    pad_latch(0, a & 0x3F);
    pad_latch(1, ((a >> 6) & 3) | ((b & 0x0F) << 2));
    music_step(0);
    music_step(1);
    sfx_step();
}
