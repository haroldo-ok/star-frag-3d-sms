/* Star Frag 3D - shared definitions */
#ifndef DEFS_H
#define DEFS_H

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;
typedef signed long s32;

/* one pre-scaled image; lives in a ROM bank next to its data */
typedef struct {
    const u8 *data;
    u8 npieces, cols, rows;
    const u8 *pieces;
} SprImg;

/* ---- fixed RAM areas (page aligned, used by the asm) ---- */
#define COLBUF   ((u8 *)0xD700)    /* 48 bytes: one tile column, packed L|R pixel pairs */
#define LUT      ((u8 *)0xD800)    /* 4 x 256: pixel pair -> bitplane byte */

/* ---- screen layout: two 128 px views side by side ---- */
#define VIEW_TY   2                /* tile row of the top of both views */
#define VIEW_TW   16               /* tile columns per view */
#define NRAYS     64               /* 32 per view, 4 px each */
#define VRAYS     32
#define HORIZON_Y 64               /* screen y of the horizon */
#define VIEW_BOT  112
#define HUD_BG_COL 12

/* ---- BG tile allocation ---- */
#define FONT_BASE  0               /* NFONT glyphs */
#define SKY_BASE   48              /* 6 sky tiles */
#define FRAME_BASE 54              /* 10 frame tiles here, the rest at 256 + SAT_FRAME */
#define VIEW_BASE  64              /* 32 columns x 6 rows (tc*6 + r) */
/* sprite area: SAT tile n == BG tile 256+n */
#define SAT_WEAPON  0              /* player*16 + frame*8 */
#define SAT_FACE    32             /* player*12 */
#define SAT_FRAME   56
#define SAT_CACHE   76
#define CACHE_PAIRS 58

/* ---- objects ---- */
enum { OT_MEDKIT, OT_ARMOR, OT_AMMO, OT_W_RIFLE, OT_W_PLASMA, OT_W_GREN, OT_W_ROCKET,
       OT_W_FLAME, OT_W_RAIL, OT_POWER,                         /* items 0..9 */
       OT_PLASMA, OT_GRENADE, OT_ROCKET, OT_FLAME,               /* projectiles 10..13 */
       OT_EXPLO, OT_PUFF, OT_SPARK, OT_TFOG,                     /* effects 14..17 */
       OT_NONE = 0xFF };
#define OT_LAST_ITEM OT_POWER
#define OT_LAST_PROJ OT_FLAME

enum { W_BLASTER, W_RIFLE, W_PLASMA, W_GREN, W_ROCKET, W_FLAME, W_RAIL, NWEAPONS };

typedef struct {
    u16 x, y;          /* 8.8 tiles */
    u8 type;
    u8 state;          /* items: 0 present, 1 waiting to respawn */
    u8 owner;          /* projectiles: player index */
    u8 dmg;
    u16 timer;
    s16 vx, vy;
    u8 anim;
} Obj;

#define MAXOBJ 40

typedef struct {
    u16 x, y, a;
    u8 health, armor, weapon, owned;
    u8 ammo[NWEAPONS];
    s8 frags;
    u8 cool, wframe, bob;
    u8 ouch, grin;
    u8 dead;            /* 0 alive, else ticks since death (saturates) */
    u16 power;          /* overdrive ticks left */
    u8 anim, attack_t, pain_t;
    u8 skin;
    u8 keys, prev;      /* pad state this tick */
    u8 spare[2];        /* keeps field offsets stable for the playtests */
    u8 dirty;           /* HUD bits */
    u8 msg, msg_t;
    u16 cx, cy, ca;     /* camera the view was last cast from */
    u8 cvalid;
    u8 cur_face, cur_hand;
    u8 cpu;             /* 1: driven by the bot */
} Player;

/* HUD dirty bits */
#define D_HEALTH 1
#define D_ARMOR  2
#define D_WEAPON 4
#define D_FACE   8
#define D_FRAGS  16
#define D_MSG    32
#define D_ALL    63

/* messages */
enum { MSG_NONE, MSG_FRAGGED, MSG_FRAGGEDBY, MSG_SUICIDE, MSG_RESPAWN, MSG_POWER, MSG_GOT };

/* ---- globals ---- */
extern u16 px, py, pa;              /* camera for cast_rays */
extern u8 ray_base, dv_first;
extern u8 map[1024];
extern Obj objs[MAXOBJ];
extern Player pl[2];
extern u16 zbuf[NRAYS];
extern u8 frame_no;
extern volatile u8 vbl_count;
extern volatile u8 pad_held[2], pad_press[2], b2_tap[2];

/* render.c / ray.s */
void render_init(void);
void render_invalidate(void);
void cast_rays(void);
void draw_view(void);

/* asm */
u16 mul8(u8 a, u16 b);
extern s16 pj_dx, pj_dy, pj_depth, pj_lat;
extern u8 pj_ca, pj_sa, pj_cf;
void project(void);
void project_d(void);   /* early-out when depth < 64 */
void set_proj_angle(u16 a);

/* sprites.c */
void sprites_init(void);
void build_sprites(void);
void menu_sprite(u8 x, u8 y, u8 g);
void hand_upload(u8 p);

/* game.c */
void match_new(void);
void level_load(u8 lvl);
void game_tick(u8 n);
extern u8 level, frag_limit, game_result;
extern u8 shake;

/* bot.c */
u8 bot_keys(u8 p);

/* hud.c */
void print_at(u8 x, u8 y, const char *s);
void print_num(u8 x, u8 y, u16 v, u8 digits);
void hud_draw(void);
void hud_full(void);

/* sound.c */
void snd_init(void);
void snd_isr(void);
void music_play(const u8 *a, const u8 *b, u8 loop);
void music_stop(void);
void sfx(u8 id);
enum { SFX_BLASTER = 1, SFX_RIFLE, SFX_PLASMA, SFX_GREN, SFX_ROCKET, SFX_FLAME, SFX_RAIL,
       SFX_EXPLODE, SFX_PICK, SFX_WEAPON, SFX_HURT, SFX_DIE, SFX_RESPAWN, SFX_POWER, SFX_MENU,
       SFX_BOUNCE, SFX_PUFF };

/* generated tables / assets */
#include "../gen/assets.h"
/* in ANG_BANK: map it before use (game_tick and build_sprites do) */
#define sintab ((const s16 *)0xAC00)
#define hhtab  ((const u8 *)0xA600)
extern const signed char rayoff[VRAYS];
extern const unsigned char cosoff[VRAYS];
extern const unsigned char plane_lut[1024];
extern const unsigned char sky_tiles[192];
extern const unsigned char gfx_bank[];
extern const SprImg * const gfx_tab[];
extern const unsigned char face_bank[];
extern const unsigned char * const face_data[];
extern const unsigned char font_tiles[];
extern const unsigned char font_map[];
extern const unsigned char frame_tiles[];
extern const unsigned char frame_map[768];
extern const unsigned char level_pals[];
extern const unsigned char cycle_cols[6];
extern const unsigned char title_pal[16];
extern const char * const level_names[];
extern const char * const skin_names[];
extern const char * const weapon_names[];
extern const unsigned char mus_title_a[], mus_title_b[], mus_game_a[], mus_game_b[];
extern const unsigned char mus_win_a[], mus_win_b[];
/* banked (MISC_BANK / TITLE_BANK) */
extern const unsigned char * const lvl_maps[];
extern const unsigned char * const lvl_objs[];
extern const unsigned char * const lvl_spawns[];
extern const unsigned char hand_tiles[];
extern const unsigned char title_tiles[];
extern const unsigned short title_map[];

#endif
