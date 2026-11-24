/* render.c - set-up for the two mirrored-half views.
 *
 * Name-table layout (each view 16 x 12 tiles, views side by side at row 2):
 *   top row r (0..5) of column tc -> tile VIEW_BASE + tc*6 + r   (BG palette: sky)
 *   bottom row 11-r                -> same tile | FLIP_Y | SPRITE_PALETTE (floor)
 * A cell that is pure sky points at SKY_BASE + r instead (its mirror shows the
 * floor gradient) and costs no tile upload.
 */
#include <SMSlib.h>
#include "defs.h"

u16 zbuf[NRAYS];
u16 px, py, pa;
extern u8 sig[NRAYS * 4];
extern u8 nt_state[32 * 6];
void ray_init(void);
void qsq_init(void);

void render_invalidate(void)
{
    u16 i;
    for (i = 0; i < NRAYS * 4; i++)
        sig[i] = 0xFF;
    for (i = 0; i < 32 * 6; i++)
        nt_state[i] = 0xFF;
}

void render_init(void)
{
    u8 *d = LUT;
    const u8 *s = plane_lut;
    u16 n;
    SMS_mapROMBank(MISC_BANK);
    for (n = 0; n < 1024; n++)
        *d++ = *s++;
    ray_init();
    qsq_init();
    SMS_mapROMBank(MISC_BANK);
    SMS_loadTiles(sky_tiles, SKY_BASE, 192);
    render_invalidate();
}
