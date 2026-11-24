#!/usr/bin/env python3
"""Star Frag 3D - asset & table generator.

Everything the ROM needs is produced here into ../gen:
  * sci-fi wall textures (vertically symmetric: only the top half is stored,
    the renderer mirrors it with the background V-flip bit),
  * ray tables for two 128 px views of 32 rays each,
  * player sprites converted from the "150 Doomguy Skins" WAD (8 rotations,
    pre-scaled to 8 sizes, quantised to the SMS palette) and their HUD faces,
  * items, projectiles, explosions and first-person weapons (drawn here),
  * font, HUD, title screen, arenas and music.

The skins WAD is read as data only.  Path: $SKINWAD or ../150skins.wad.
The Doom palette comes from Freedoom (tools/doompal.lmp, BSD licence).
"""
import math, os, sys, random
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wad import Wad, patch
from skinlib import load_pal, skin_index, find_frame, to_rgba
from maps import ARENAS

OUT = os.path.join(HERE, '..', 'gen')
SHOTS = os.path.join(HERE, '..', 'shots')
os.makedirs(OUT, exist_ok=True)
os.makedirs(SHOTS, exist_ok=True)
WADPATH = os.environ.get('SKINWAD', os.path.join(HERE, '..', '150skins.wad'))

# ------------------------------------------------------------------ palette
def smsc(r, g, b):
    return r | (g << 2) | (b << 4)

# 0,1: sky (BG palette) / floor (sprite palette) - per arena
BLACK, WHITE, LGREY, DGREY, RED, BROWN, TAN, YELLOW, GREEN, DKGREEN, BLUE = range(2, 13)
CYC_A, CYC_B, CYC_C = 13, 14, 15
FIXED = {BLACK: (0, 0, 0), WHITE: (3, 3, 3), LGREY: (2, 2, 2), DGREY: (1, 1, 1), RED: (3, 0, 0),
         BROWN: (2, 1, 0), TAN: (3, 2, 1), YELLOW: (3, 3, 0), GREEN: (1, 2, 0), DKGREEN: (0, 1, 0),
         BLUE: (0, 1, 2)}
# 6-step energy cycle for entries 13..15 (phases 0, 2, 4)
CYCLE = [(0, 3, 3), (0, 2, 3), (1, 1, 3), (2, 1, 3), (3, 1, 3), (2, 2, 3)]
DARK = {BLACK: BLACK, WHITE: LGREY, LGREY: DGREY, DGREY: BLACK, RED: BROWN, BROWN: DGREY, TAN: BROWN,
        YELLOW: TAN, GREEN: DKGREEN, DKGREEN: BLACK, BLUE: DGREY, CYC_A: CYC_A, CYC_B: CYC_B, CYC_C: CYC_C}
SPRITE_COLS = list(range(2, 13))       # colours the converted skins may use

def rgb8(c):
    return tuple(v * 85 for v in c)

def full_palette(level=0, which=0):
    _, sky, floor, _ = ARENAS[level]
    pal = [None] * 16
    for i in range(2):
        pal[i] = (sky if which == 0 else floor)[i]
    for k, v in FIXED.items():
        pal[k] = v
    pal[13], pal[14], pal[15] = CYCLE[0], CYCLE[2], CYCLE[4]
    return pal

# ------------------------------------------------------------------ helpers
def tile_bytes(px):
    out = []
    for row in px:
        for p in range(4):
            b = 0
            for x in range(8):
                if (row[x] >> p) & 1:
                    b |= 0x80 >> x
            out.append(b)
    return out

def c_array(name, data, typ='unsigned char', per=32, extra=''):
    s = '%sconst %s %s[%d] = {\n' % (extra, typ, name, len(data))
    for i in range(0, len(data), per):
        s += '  ' + ','.join(str(v) for v in data[i:i + per]) + ',\n'
    return s + '};\n'

def write(name, text):
    with open(os.path.join(OUT, name), 'w') as f:
        f.write(text)

def quantize(rgb, cols=SPRITE_COLS):
    r, g, b = rgb
    best, bd = cols[0], 1 << 30
    for i in cols:
        R, G, B = rgb8(FIXED[i])
        d = 3 * (R - r) ** 2 + 4 * (G - g) ** 2 + 2 * (B - b) ** 2
        if d < bd:
            bd, best = d, i
    return best

# ------------------------------------------------------------------ textures
TW, TH = 32, 16   # stored half texture (row 15 touches the horizon)

def blank(c):
    return [[c] * TW for _ in range(TH)]

def tex_tech():
    t = blank(LGREY)
    for y in range(TH):
        for x in range(TW):
            xx = x % 16
            c = LGREY
            if xx == 15: c = BLACK
            elif xx == 0: c = WHITE
            elif xx == 14: c = DGREY
            if y == 8: c = BLACK
            elif y == 9 and xx != 15: c = WHITE
            if y in (12, 13) and 2 <= xx <= 12: c = BLUE
            if y == 12 and xx in (4, 8): c = CYC_A
            if y == 13 and xx == 10: c = CYC_B
            if (xx, y) in ((2, 3), (12, 3), (2, 6), (12, 6)): c = DGREY
            t[y][x] = c
    for x in range(TW):
        t[0][x] = BLACK
        t[1][x] = DGREY
    return t

def tex_hazard():
    t = blank(DGREY)
    for y in range(TH):
        for x in range(TW):
            if 2 <= y <= 6:
                t[y][x] = YELLOW if ((x + y) // 3) % 2 else BLACK
            elif y == 7:
                t[y][x] = BLACK
            else:
                xx = x % 8
                t[y][x] = LGREY if xx == 0 else (BLACK if xx == 7 else DGREY)
                if xx == 3 and y in (10, 14): t[y][x] = LGREY
    for x in range(TW):
        t[0][x] = BLACK
        t[1][x] = LGREY
    return t

def tex_computer():
    t = blank(DGREY)
    rnd = random.Random(3)
    for y in range(TH):
        for x in range(TW):
            c = DGREY
            if 3 <= x <= 28 and 3 <= y <= 11:
                c = BLACK
                if 4 <= x <= 27 and 4 <= y <= 10 and y % 2 == 0 and rnd.random() < 0.55:
                    c = rnd.choice([CYC_A, CYC_B, CYC_C, GREEN])
            if x in (2, 29) and 2 <= y <= 12: c = LGREY
            if y in (2, 12) and 2 <= x <= 29: c = LGREY
            t[y][x] = c
    for i, x in enumerate((6, 10, 14, 18, 22, 26)):
        t[14][x] = [RED, YELLOW, GREEN, CYC_C, RED, GREEN][i]
        t[14][x + 1] = BLACK
    for x in range(TW):
        t[0][x] = BLACK
    return t

def tex_pipes():
    t = blank(BLACK)
    shade = [DKGREEN, GREEN, LGREY, GREEN, GREEN, DKGREEN, BLACK, DGREY]
    for y in range(TH):
        for x in range(TW):
            t[y][x] = shade[x % 8]
            if y in (4, 5):
                t[y][x] = LGREY if y == 4 else DGREY
            if y == 11 and x % 8 < 6:
                t[y][x] = YELLOW if x % 16 < 8 else RED
    for x in range(TW):
        t[0][x] = BLACK
    return t

def tex_force():
    t = blank(BLACK)
    seq = [CYC_A, CYC_A, CYC_B, CYC_B, CYC_C, CYC_C]
    for y in range(TH):
        for x in range(TW):
            t[y][x] = seq[((x + y * 2) // 2) % 6]
            if (x * 7 + y * 3) % 11 == 0: t[y][x] = WHITE
    for x in range(TW):
        t[0][x] = BLACK
        t[1][x] = DGREY
        t[2][x] = LGREY if x % 4 else BLACK
    return t

def tex_crate():
    t = blank(BROWN)
    for y in range(TH):
        for x in range(TW):
            xx = x % 16
            c = BROWN
            if xx in (0, 15) or y in (0, 1): c = BLACK if xx in (0, 15) or y == 0 else TAN
            elif xx in (1, 14) or y == 2: c = TAN
            else:
                # X brace (vertically symmetric about the horizon thanks to the mirror)
                d1 = abs((xx - 1) - (y - 2) * 6.5 / 13.0)
                d2 = abs((14 - xx) - (y - 2) * 6.5 / 13.0)
                if d1 < 1.1 or d2 < 1.1: c = TAN
                elif y in (6, 7) and 4 <= xx <= 11: c = YELLOW if (xx // 2) % 2 else BLACK
            t[y][x] = c
    return t

def tex_reactor():
    t = blank(DGREY)
    for y in range(TH):
        for x in range(TW):
            xx = x % 16
            c = DGREY
            if xx in (5, 10): c = BLACK
            elif 6 <= xx <= 9:
                c = [RED, YELLOW, WHITE, YELLOW][xx - 6] if y > 3 else RED
                if y % 4 == 0: c = CYC_C
            elif xx in (0, 15): c = BLACK
            elif xx in (1, 14): c = LGREY
            t[y][x] = c
    for x in range(TW):
        t[0][x] = BLACK
        t[1][x] = LGREY
        t[2][x] = BLACK
    return t

TEXTURES = [tex_tech(), tex_hazard(), tex_computer(), tex_pipes(), tex_force(), tex_crate(), tex_reactor()]
WALLCH = {'#': 1, 'H': 2, 'C': 3, 'P': 4, 'F': 5, 'X': 6, 'R': 7}

def variants():
    vs = []
    for t in TEXTURES:
        vs.append(t)
        vs.append([[DARK[c] for c in row] for row in t])
    return vs

# ------------------------------------------------------------------ view geometry
RAYS = 32              # per view (128 px / 4)
FOCAL = 120.0          # px: ~56 degree field of view in a 128 px window
HALF = 48
NK = 138
SKYPAGE, SHIFT = 0x90, 0x13

def k_to_hh(k):
    return k if k <= 48 else 48 + (k - 48) * 2

def hh_to_k(hh):
    if hh <= 48:
        return hh
    return min(NK - 1, 48 + (hh - 48 + 1) // 2)

def sky_index(y):
    if y < 18: return 0
    if y < 30: return 1 if (y % 2) else 0
    return 1

def rows_entry(k):
    hh = k_to_hh(k)
    out = []
    top = HALF - hh
    for y in range(HALF):
        if y < top:
            out.append(SKYPAGE + sky_index(y))
        else:
            v = int(((y + 0.5) - top) * 16.0 / hh) if hh else 0
            out.append(0x80 + max(0, min(15, v)))
    return out

def gen_texbanks():
    vs = variants()
    banks = []
    for g in range((len(vs) + 7) // 8):
        b = bytearray(16384)
        for s in range(8):
            v = g * 8 + s
            if v >= len(vs):
                break
            for p in range(16):
                for u in range(32):
                    c = vs[v][p][u]
                    b[p * 256 + s * 32 + u] = c
                    b[(p + SHIFT) * 256 + s * 32 + u] = c << 4
        for c in range(3):
            for i in range(256):
                b[(0x10 + c) * 256 + i] = c
                b[(0x10 + SHIFT + c) * 256 + i] = c << 4
        base = 0x26 * 256
        for k in range(NK):
            b[base + k * 48: base + k * 48 + 48] = bytes(rows_entry(k))
        banks.append(b)
    return banks

def gen_plane_lut():
    lut = []
    for p in range(4):
        for idx in range(256):
            l, r = idx >> 4, idx & 15
            lut.append((0xF0 if (l >> p) & 1 else 0) | (0x0F if (r >> p) & 1 else 0))
    return c_array('plane_lut', lut, 'unsigned char', 32)

def gen_tables():
    s = '#include "../src/defs.h"\n'
    sint = [int(round(math.sin(a * 2 * math.pi / 1024) * 256)) for a in range(1024)]
    rayoff, cosoff = [], []
    for i in range(RAYS):
        ang = math.atan(((i - 15.5) * 4) / FOCAL)
        rayoff.append(int(round(ang * 1024 / (2 * math.pi))))
        cosoff.append(min(255, int(round(math.cos(ang) * 256))))
    s += c_array('rayoff', rayoff, 'signed char', 16)
    s += c_array('cosoff', cosoff, 'unsigned char', 16)
    lut = []
    for p in range(4):
        for idx in range(256):
            l, r = idx >> 4, idx & 15
            lut.append((0xF0 if (l >> p) & 1 else 0) | (0x0F if (r >> p) & 1 else 0))
    return s

def gen_sky_tiles():
    sky = []
    for r in range(6):
        sky += tile_bytes([[sky_index(r * 8 + y)] * 8 for y in range(8)])
    return c_array('sky_tiles', sky, 'unsigned char', 32)

def gen_arrow_tiles():
    """hit-direction arrows on the HUD strip colours: left, right, up (front), down (back)"""
    shapes = {
        'L': ["...XX...", "..XX....", ".XXXXXX.", "XXXXXXX.", ".XXXXXX.", "..XX....", "...XX...", "........"],
        'U': ["...X....", "..XXX...", ".XXXXX..", "XXXXXXX.", "..XXX...", "..XXX...", "..XXX...", "........"],
    }
    def grid(rows):
        out = [[DGREY] * 8 for _ in range(8)]
        on = {(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == 'X'}
        for (x, y) in on:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if 0 <= x + dx < 8 and 0 <= y + dy < 8 and (x + dx, y + dy) not in on:
                        out[y + dy][x + dx] = BLACK
        for (x, y) in on:
            out[y][x] = RED if y in (0, 1, 2, 3) or x in (0, 1, 2, 3) else RED
        return out
    L = shapes['L']
    R = [r[::-1] for r in L]
    R = ["." + r[:-1] for r in R]          # keep the 7 px shape inside the tile
    U = shapes['U']
    D = U[:7][::-1] + ["........"]
    out = []
    for g in (L, R, U, D):
        out += tile_bytes(grid(g))
    return c_array('arrow_tiles', out)

RADAR = 24       # radar box, px (3 x 3 tiles)

def radar_base():
    img = [[BLACK] * RADAR for _ in range(RADAR)]
    for i in range(RADAR):
        img[0][i] = img[RADAR - 1][i] = img[i][0] = img[i][RADAR - 1] = LGREY
    for i in range(2, RADAR - 2, 2):
        img[12][i] = DKGREEN
        img[i][12] = DKGREEN
    # you: a small white arrow at the centre pointing up (forward)
    for (x, y) in ((12, 10), (11, 11), (12, 11), (13, 11), (12, 12), (12, 13)):
        img[y][x] = WHITE
    out = []
    for ty in range(3):
        for tx in range(3):
            out += tile_bytes([img[ty * 8 + y][tx * 8:tx * 8 + 8] for y in range(8)])
    return out

def gen_angbank():
    b = bytearray(16384)
    for a in range(1024):
        ang = a * 2 * math.pi / 1024
        c, sn = math.cos(ang), math.sin(ang)
        def dd(v):
            return 0x7FFF if abs(v) < 1e-6 else min(0x7FFF, int(round(256 / abs(v))))
        ddx, ddy = dd(c), dd(sn)
        ci = int(round(c * 256)); si = int(round(sn * 256))
        fl = (1 if ci < 0 else 0) | (2 if si < 0 else 0)
        b[a * 8:a * 8 + 8] = bytes([ddx & 255, ddx >> 8, ddy & 255, ddy >> 8,
                                    min(255, abs(ci)), min(255, abs(si)), fl, 0])
    for i in range(1536):
        hh = min(255, int(round((FOCAL / 2) * 256 / (i * 8 + 4))))
        b[0x2000 + i] = hh_to_k(hh)
        b[0x2600 + i] = hh                     # HHTAB: half wall height for perp>>3
    for a in range(1024):                      # SINTAB at 0xAC00: s16 sin * 256
        v = int(round(math.sin(a * 2 * math.pi / 1024) * 256)) & 0xFFFF
        b[0x2C00 + a * 2] = v & 255
        b[0x2C00 + a * 2 + 1] = v >> 8
    return b

def gen_unrolled_asm():
    a = ['; generated: unrolled column scalers (see tools/gen.py)',
         '\t.module scalers', '\t.area _CODE', '\t.globl dl_body', '\t.globl dr_body', 'dl_body:']
    for _ in range(HALF):
        a += ['\tld a,(bc)', '\tinc bc', '\tadd a,#0x%02X' % SHIFT, '\tld h,a', '\tld a,(hl)', '\tld (de),a', '\tinc e']
    a += ['\tret', 'dr_body:']
    for _ in range(HALF):
        a += ['\tld a,(bc)', '\tinc bc', '\tld h,a', '\tld a,(de)', '\tor (hl)', '\tld (de),a', '\tinc e']
    a += ['\tret', '']
    return '\n'.join(a)

# ------------------------------------------------------------------ vector art
T = 255   # transparent

class Art:
    """Shapes in normalised coords with black outlines, supersampled then
    reduced by majority vote (outlines protected)."""
    def __init__(self, w, h, ss=None, ow=1.0):
        self.w, self.h = w, h
        self.ss = ss or (8 if max(w, h) <= 16 else 4)
        self.img = Image.new('L', (w * self.ss, h * self.ss), T)
        self.d = ImageDraw.Draw(self.img)
        self.ow = max(1, int(round(ow * self.ss * (0.8 if max(w, h) < 20 else 1.0))))

    def P(self, x, y):
        return (x * self.w * self.ss, y * self.h * self.ss)

    def ell(self, cx, cy, rx, ry, col, ol=True):
        x0, y0 = self.P(cx - rx, cy - ry)
        x1, y1 = self.P(cx + rx, cy + ry)
        if ol:
            o = self.ow
            self.d.ellipse([x0 - o, y0 - o, x1 + o, y1 + o], fill=BLACK)
        if x1 - x0 >= 1 and y1 - y0 >= 1:
            self.d.ellipse([x0, y0, x1, y1], fill=col)

    def poly(self, pts, col, ol=True):
        pp = [self.P(x, y) for x, y in pts]
        if ol:
            self.d.polygon(pp, fill=BLACK, outline=BLACK, width=2 * self.ow)
        self.d.polygon(pp, fill=col)

    def rect(self, x0, y0, x1, y1, col, ol=True):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], col, ol)

    def line(self, pts, col, w=1.0):
        pp = [self.P(x, y) for x, y in pts]
        self.d.line(pp, fill=col, width=max(1, int(round(w * self.ss))), joint='curve')

    def star(self, cx, cy, r, col, n=5, inner=0.45, rot=-90, ol=True):
        pts = []
        for i in range(n * 2):
            a = math.radians(rot + i * 180 / n)
            rr = r if i % 2 == 0 else r * inner
            pts.append((cx + rr * math.cos(a) * (self.h / self.w), cy + rr * math.sin(a)))
        self.poly(pts, col, ol)

    def result(self):
        ss = self.ss
        src = self.img.load()
        out = [[T] * self.w for _ in range(self.h)]
        n = ss * ss
        for y in range(self.h):
            for x in range(self.w):
                cnt = {}
                for yy in range(ss):
                    for xx in range(ss):
                        c = src[x * ss + xx, y * ss + yy]
                        cnt[c] = cnt.get(c, 0) + 1
                if cnt.get(T, 0) * 2 > n:
                    continue
                if cnt.get(BLACK, 0) * 100 >= n * 34:
                    out[y][x] = BLACK
                    continue
                out[y][x] = max((k for k in cnt if k not in (T, BLACK)), key=lambda k: cnt[k], default=BLACK)
        return out

# --- items (drawn sitting on the floor)
def draw_medkit(a):
    a.rect(0.12, 0.5, 0.88, 0.95, WHITE)
    a.rect(0.12, 0.5, 0.88, 0.58, LGREY, ol=False)
    a.rect(0.42, 0.6, 0.58, 0.9, RED, ol=False)
    a.rect(0.3, 0.68, 0.7, 0.82, RED, ol=False)
    a.rect(0.38, 0.42, 0.62, 0.5, DGREY)

def draw_armor(a):
    a.poly([(0.18, 0.4), (0.38, 0.32), (0.5, 0.4), (0.62, 0.32), (0.82, 0.4), (0.78, 0.95),
            (0.22, 0.95)], GREEN)
    a.poly([(0.32, 0.5), (0.68, 0.5), (0.64, 0.86), (0.36, 0.86)], DKGREEN, ol=False)
    a.ell(0.5, 0.66, 0.08, 0.08, CYC_A, ol=False)
    a.line([(0.24, 0.44), (0.4, 0.38)], WHITE, 0.6)

def draw_ammo(a):
    a.rect(0.14, 0.55, 0.86, 0.95, DGREY)
    a.rect(0.14, 0.55, 0.86, 0.64, LGREY, ol=False)
    for i in range(4):
        x = 0.2 + i * 0.16
        a.rect(x, 0.68, x + 0.1, 0.9, YELLOW if i % 2 == 0 else TAN, ol=False)
    a.rect(0.28, 0.45, 0.42, 0.55, YELLOW)
    a.rect(0.58, 0.45, 0.72, 0.55, YELLOW)

def draw_gun(a, kind, y0=0.62, y1=0.88):
    """side view of a weapon lying on the floor (kind 1..6)"""
    m = (y0 + y1) / 2
    if kind == 1:      # pulse rifle
        a.rect(0.08, m - 0.06, 0.75, m + 0.06, LGREY)
        a.rect(0.75, m - 0.025, 0.95, m + 0.025, BLACK, ol=False)
        a.rect(0.3, m + 0.06, 0.4, y1 + 0.04, DGREY)
        a.rect(0.5, m - 0.03, 0.66, m + 0.02, BLUE, ol=False)
    elif kind == 2:    # plasma gun
        a.rect(0.1, m - 0.1, 0.7, m + 0.1, BLUE)
        for x in (0.25, 0.4, 0.55):
            a.rect(x, m - 0.1, x + 0.06, m + 0.1, CYC_A, ol=False)
        a.ell(0.78, m, 0.1, 0.08, CYC_B)
        a.rect(0.2, m + 0.1, 0.3, y1 + 0.05, DGREY)
    elif kind == 3:    # grenade launcher
        a.rect(0.1, m - 0.05, 0.85, m + 0.05, DGREY)
        a.ell(0.42, m, 0.16, 0.14, LGREY)
        a.ell(0.42, m, 0.06, 0.05, BLACK, ol=False)
        a.rect(0.78, m - 0.08, 0.92, m + 0.08, GREEN)
    elif kind == 4:    # rocket launcher
        a.rect(0.05, m - 0.1, 0.88, m + 0.1, DKGREEN)
        a.rect(0.05, m - 0.04, 0.88, m + 0.02, GREEN, ol=False)
        a.poly([(0.88, m - 0.07), (0.98, m), (0.88, m + 0.07)], RED)
        a.rect(0.35, m + 0.1, 0.45, y1 + 0.05, DGREY)
    elif kind == 5:    # flamer
        a.ell(0.3, m, 0.2, 0.14, RED)
        a.ell(0.25, m - 0.04, 0.06, 0.04, WHITE, ol=False)
        a.rect(0.48, m - 0.04, 0.9, m + 0.04, LGREY)
        a.ell(0.92, m, 0.04, 0.05, YELLOW)
    elif kind == 6:    # railgun
        a.rect(0.04, m - 0.05, 0.96, m + 0.05, LGREY)
        for x in (0.3, 0.45, 0.6, 0.75):
            a.ell(x, m, 0.03, 0.11, CYC_C)
        a.rect(0.1, m + 0.05, 0.2, y1 + 0.05, DGREY)

def draw_power(a):
    a.ell(0.5, 0.6, 0.3, 0.3, CYC_A)
    a.ell(0.5, 0.6, 0.2, 0.2, CYC_B, ol=False)
    a.ell(0.5, 0.6, 0.1, 0.1, WHITE, ol=False)
    a.star(0.5, 0.6, 0.16, YELLOW, n=4, inner=0.3, ol=False)

def draw_plasma(a):
    a.ell(0.5, 0.5, 0.36, 0.36, CYC_A)
    a.ell(0.5, 0.5, 0.24, 0.24, CYC_B, ol=False)
    a.ell(0.5, 0.5, 0.12, 0.12, WHITE, ol=False)

def draw_grenade(a):
    a.ell(0.5, 0.55, 0.3, 0.3, DGREY)
    a.ell(0.42, 0.45, 0.08, 0.06, LGREY, ol=False)
    a.ell(0.58, 0.62, 0.07, 0.07, RED, ol=False)

def draw_rocket(a):
    a.ell(0.5, 0.5, 0.4, 0.4, YELLOW)
    a.ell(0.5, 0.5, 0.3, 0.3, RED, ol=False)
    a.ell(0.5, 0.5, 0.2, 0.2, DGREY)
    a.ell(0.5, 0.5, 0.08, 0.08, LGREY, ol=False)

def draw_flame(a, f):
    r = 0.3 if f == 0 else 0.42
    a.ell(0.5, 0.55, r, r * 0.9, RED, ol=False)
    a.poly([(0.5 - r, 0.5), (0.5, 0.05 + (0.1 if f else 0.2)), (0.5 + r, 0.5)], RED, ol=False)
    a.ell(0.5, 0.6, r * 0.65, r * 0.6, YELLOW, ol=False)
    a.ell(0.5, 0.66, r * 0.3, r * 0.3, WHITE, ol=False)

def draw_explo(a, f):
    rnd = random.Random(5 + f)
    if f == 0:
        a.ell(0.5, 0.5, 0.46, 0.44, RED, ol=False)
        for _ in range(7):
            ang = rnd.random() * 6.28
            a.ell(0.5 + 0.3 * math.cos(ang), 0.5 + 0.3 * math.sin(ang), 0.15, 0.15, YELLOW, ol=False)
        a.ell(0.5, 0.5, 0.25, 0.24, YELLOW, ol=False)
        a.ell(0.5, 0.5, 0.13, 0.12, WHITE, ol=False)
    else:
        for _ in range(8):
            ang = rnd.random() * 6.28
            a.ell(0.5 + 0.28 * math.cos(ang), 0.5 + 0.28 * math.sin(ang), 0.17, 0.17, DGREY, ol=False)
        a.ell(0.5, 0.5, 0.3, 0.28, RED, ol=False)
        a.ell(0.5, 0.52, 0.14, 0.13, YELLOW, ol=False)

def draw_puff(a):
    a.star(0.5, 0.5, 0.4, YELLOW, n=6, inner=0.35, ol=False)
    a.ell(0.5, 0.5, 0.14, 0.14, WHITE, ol=False)

def draw_spark(a):
    a.ell(0.5, 0.5, 0.34, 0.34, CYC_C, ol=False)
    a.ell(0.5, 0.5, 0.22, 0.22, BLACK, ol=False)
    a.ell(0.5, 0.5, 0.1, 0.1, WHITE, ol=False)

def draw_tfog(a):
    for i in range(8):
        ang = i * math.pi / 4
        a.star(0.5 + 0.32 * math.cos(ang), 0.5 + 0.38 * math.sin(ang), 0.1, [CYC_A, CYC_B, CYC_C, WHITE][i % 4],
               n=4, inner=0.3, ol=False)
    a.ell(0.5, 0.5, 0.12, 0.16, WHITE, ol=False)

ITEM_GFX = [('medkit', draw_medkit), ('armor', draw_armor), ('ammo', draw_ammo)]
for k, nm in enumerate(('w_rifle', 'w_plasma', 'w_gren', 'w_rocket', 'w_flame', 'w_rail')):
    ITEM_GFX.append((nm, (lambda kk: (lambda a: draw_gun(a, kk)))(k + 1)))
ITEM_GFX += [('power', draw_power), ('plasma', draw_plasma), ('grenade', draw_grenade), ('rocket', draw_rocket),
             ('flame0', lambda a: draw_flame(a, 0)), ('flame1', lambda a: draw_flame(a, 1)),
             ('explo0', lambda a: draw_explo(a, 0)), ('explo1', lambda a: draw_explo(a, 1)),
             ('puff', draw_puff), ('spark', draw_spark), ('tfog', draw_tfog)]
SIZES = [8, 12, 16, 20, 24, 32, 40, 48]

# ------------------------------------------------------------------ skins
# (wad skin name, display name, face prefix)
SKINS = [('Base1', 'MARINE', 'BLM'), ('BaseFemale', 'RANGER', 'GAL'), ('Phobos', 'PHOBOS', 'PHB'),
         ('Cyborg', 'CYBORG', 'CYB'), ('Hazmat', 'HAZMAT', 'HLM'), ('Stealth', 'STEALTH', 'SHA')]
CREDITS = {'Base1': 'Doomkid', 'BaseFemale': 'Virtue', 'Phobos': 'Rottking', 'Cyborg': 'Cory Whittle',
           'Hazmat': 'Enjay/Scalliano', 'Stealth': '???'}
# per skin graphics: walk A rot 1..8, walk C rot 1..8, attack F1, pain G1, dying H0, dead N0
SKIN_FRAMES = [('A', r) for r in range(1, 9)] + [('C', r) for r in range(1, 9)] + \
              [('F', 1), ('G', 1), ('H', 0), ('N', 0)]
NSKINGFX = len(SKIN_FRAMES)

def skin_graphic(wd, sk, frame, rot, S, dpal):
    p, mir = find_frame(wd, sk, frame, rot)
    if p is None and rot:
        p, mir = find_frame(wd, sk, frame, 1)
    assert p is not None, (sk.get('name'), frame, rot)
    im, lo, to = to_rgba(p, dpal, mir)
    W, H = im.size
    sc = S / 56.0
    hw = int(math.ceil(max(lo * sc, (W - lo) * sc))) + 0
    hc = max(1, int(math.ceil(to * sc)))
    sw, sh = max(1, int(round(W * sc))), max(1, int(round(H * sc)))
    small = im.resize((sw, sh), Image.BOX)
    can = Image.new('RGBA', (2 * hw, hc), (0, 0, 0, 0))
    can.paste(small, (int(round(hw - lo * sc)), int(round(hc - to * sc))), small)
    out = [[T] * can.width for _ in range(can.height)]
    px = can.load()
    for y in range(can.height):
        for x in range(can.width):
            r, g, b, al = px[x, y]
            if al >= 110:
                out[y][x] = quantize((r * 255 // max(al, 1), g * 255 // max(al, 1), b * 255 // max(al, 1))
                                     if al < 255 else (r, g, b))
    return out

def face_tiles(wd, prefix, dpal):
    """8 faces (health levels 0..4, ouch, evil grin, dead) -> 3x4 BG tiles each"""
    data = []
    imgs = []
    for nm in ('ST01', 'ST11', 'ST21', 'ST31', 'ST41', 'OUCH0', 'EVL0', 'DEAD0'):
        lump = wd.get(prefix + nm)
        assert lump is not None, prefix + nm
        p = patch(lump)
        W, H, lo, to, pp = p
        img = [[BLUE] * 24 for _ in range(32)]
        ox, oy = (24 - W) // 2, max(0, 32 - H - 1)
        for y in range(H):
            for x in range(W):
                c = pp[y][x]
                if c is not None and 0 <= ox + x < 24 and 0 <= oy + y < 32:
                    img[oy + y][ox + x] = quantize(dpal[c])
        imgs.append(img)
        for ty in range(4):
            for tx in range(3):
                data += tile_bytes([img[ty * 8 + y][tx * 8:tx * 8 + 8] for y in range(8)])
    return data, imgs

# ------------------------------------------------------------------ sprite packing
def sprite_pieces(img):
    h = len(img); w = len(img[0])
    cols = (w + 7) // 8
    rows = (h + 15) // 16
    assert cols <= 15 and rows <= 15
    gw, gh = cols * 8, rows * 16
    ox, oy = (gw - w) // 2, gh - h
    grid = [[0] * gw for _ in range(gh)]
    for y in range(h):
        for x in range(w):
            c = img[y][x]
            if c != T:
                grid[oy + y][ox + x] = c
    pieces, data = [], []
    for r in range(rows):
        for c in range(cols):
            blk = [grid[r * 16 + yy][c * 8:(c + 1) * 8] for yy in range(16)]
            if any(any(v for v in row) for row in blk):
                pieces.append(c | (r << 4))
                data += tile_bytes(blk[:8]) + tile_bytes(blk[8:])
    return cols, rows, pieces, data

class Packer:
    """Fills 16 KB ROM banks with C arrays; an item never straddles banks."""
    def __init__(self, first, limit=16300):
        self.first, self.limit = first, limit
        self.banks = [[]]
        self.used = [0]

    def add(self, src, size):
        if self.used[-1] + size > self.limit:
            self.banks.append([])
            self.used.append(0)
        self.banks[-1].append(src)
        self.used[-1] += size
        return self.first + len(self.banks) - 1

def build_graphic(pk, gname, images):
    """images: 8 index images (one per size) -> one bank entry; returns bank"""
    src, size, entries = '', 0, []
    for si, img in enumerate(images):
        cols, rows, pieces, data = sprite_pieces(img)
        dn, pn = 'sd_%s_%d' % (gname, si), 'sp_%s_%d' % (gname, si)
        if not data:
            data = [0] * 64
            pieces = [0]
        src += c_array(dn, data, extra='static ')
        src += c_array(pn, pieces, extra='static ')
        entries.append('{%s,%d,%d,%d,%s}' % (dn, len(pieces), cols, rows, pn))
        size += len(data) + len(pieces) + 7
    src += 'const SprImg gt_%s[%d] = {%s};\n' % (gname, len(images), ','.join(entries))
    return pk.add(src, size)

# ------------------------------------------------------------------ first-person weapons
WEAPONS = ['BLASTER', 'PULSE', 'PLASMA', 'GRENADE', 'ROCKET', 'FLAMER', 'RAIL']

def draw_hand(a, kind, fire):
    """16x32: weapon held low, muzzle at the top centre"""
    r = 0.04 if fire else 0.0
    body = [BLUE, LGREY, BLUE, DGREY, DKGREEN, RED, LGREY][kind]
    trim = [CYC_A, BLUE, CYC_A, LGREY, GREEN, YELLOW, CYC_C][kind]
    w = [0.26, 0.24, 0.34, 0.36, 0.38, 0.3, 0.22][kind]
    top = [0.42, 0.22, 0.3, 0.38, 0.18, 0.34, 0.12][kind] + r
    a.rect(0.5 - w, top, 0.5 + w, 1.05, body)
    a.rect(0.5 - w * 0.35, top + 0.04, 0.5 + w * 0.35, 1.05, trim, ol=False)
    if kind == 1:
        a.rect(0.42, top - 0.12, 0.58, top + 0.02, BLACK, ol=False)
    if kind == 3:
        a.ell(0.5, top + 0.22, 0.4, 0.08, LGREY)
    if kind == 4:
        a.ell(0.5, top, w, 0.05, BLACK)
    if kind == 5:
        a.rect(0.44, top - 0.12, 0.56, top, LGREY)
    if kind == 6:
        for y in (0.3, 0.45, 0.6):
            a.rect(0.5 - w - 0.06, y + r, 0.5 + w + 0.06, y + 0.04 + r, CYC_C, ol=False)
    # glove
    a.ell(0.5, 0.92, 0.42, 0.12, TAN)
    a.line([(0.36, 0.84), (0.36, 0.98)], BROWN, 0.6)
    a.line([(0.64, 0.84), (0.64, 0.98)], BROWN, 0.6)
    if fire:
        fc = [CYC_B, YELLOW, CYC_A, YELLOW, YELLOW, RED, CYC_C][kind]
        a.ell(0.5, top - 0.1, 0.42, 0.1, fc)
        a.ell(0.5, top - 0.1, 0.2, 0.05, WHITE, ol=False)

def gen_hands():
    out = []
    for k in range(len(WEAPONS)):
        for fr in range(2):
            a = Art(16, 32, ss=6)
            draw_hand(a, k, fr)
            img = a.result()
            for c in range(2):
                for rr in range(2):
                    blk = [[(0 if img[rr * 16 + y][c * 8 + x] == T else img[rr * 16 + y][c * 8 + x])
                            for x in range(8)] for y in range(16)]
                    out += tile_bytes(blk[:8]) + tile_bytes(blk[8:])
    return out

# ------------------------------------------------------------------ font
GLYPHS = {
 '0': ["01110","10011","10101","10101","11001","10001","01110"],
 '1': ["00100","01100","00100","00100","00100","00100","01110"],
 '2': ["01110","10001","00001","00110","01000","10000","11111"],
 '3': ["11110","00001","00001","01110","00001","00001","11110"],
 '4': ["00010","00110","01010","10010","11111","00010","00010"],
 '5': ["11111","10000","11110","00001","00001","10001","01110"],
 '6': ["00110","01000","10000","11110","10001","10001","01110"],
 '7': ["11111","00001","00010","00100","01000","01000","01000"],
 '8': ["01110","10001","10001","01110","10001","10001","01110"],
 '9': ["01110","10001","10001","01111","00001","00010","01100"],
 'A': ["01110","10001","10001","11111","10001","10001","10001"],
 'B': ["11110","10001","10001","11110","10001","10001","11110"],
 'C': ["01110","10001","10000","10000","10000","10001","01110"],
 'D': ["11100","10010","10001","10001","10001","10010","11100"],
 'E': ["11111","10000","10000","11110","10000","10000","11111"],
 'F': ["11111","10000","10000","11110","10000","10000","10000"],
 'G': ["01110","10001","10000","10111","10001","10001","01111"],
 'H': ["10001","10001","10001","11111","10001","10001","10001"],
 'I': ["01110","00100","00100","00100","00100","00100","01110"],
 'J': ["00111","00010","00010","00010","00010","10010","01100"],
 'K': ["10001","10010","10100","11000","10100","10010","10001"],
 'L': ["10000","10000","10000","10000","10000","10000","11111"],
 'M': ["10001","11011","10101","10101","10001","10001","10001"],
 'N': ["10001","10001","11001","10101","10011","10001","10001"],
 'O': ["01110","10001","10001","10001","10001","10001","01110"],
 'P': ["11110","10001","10001","11110","10000","10000","10000"],
 'Q': ["01110","10001","10001","10001","10101","10010","01101"],
 'R': ["11110","10001","10001","11110","10100","10010","10001"],
 'S': ["01111","10000","10000","01110","00001","00001","11110"],
 'T': ["11111","00100","00100","00100","00100","00100","00100"],
 'U': ["10001","10001","10001","10001","10001","10001","01110"],
 'V': ["10001","10001","10001","10001","10001","01010","00100"],
 'W': ["10001","10001","10001","10101","10101","10101","01010"],
 'X': ["10001","10001","01010","00100","01010","10001","10001"],
 'Y': ["10001","10001","01010","00100","00100","00100","00100"],
 'Z': ["11111","00001","00010","00100","01000","10000","11111"],
 '!': ["00100","00100","00100","00100","00100","00000","00100"],
 '?': ["01110","10001","00001","00110","00100","00000","00100"],
 '.': ["00000","00000","00000","00000","00000","00000","00100"],
 ':': ["00000","00100","00000","00000","00000","00100","00000"],
 '-': ["00000","00000","00000","01110","00000","00000","00000"],
 "'": ["00100","00100","01000","00000","00000","00000","00000"],
 '/': ["00001","00010","00010","00100","01000","01000","10000"],
 '<': ["00010","00100","01000","10000","01000","00100","00010"],
 '>': ["01000","00100","00010","00001","00010","00100","01000"],
 '+': ["00000","00100","00100","11111","00100","00100","00000"],
}
FONT_CHARS = ' ' + ''.join(sorted(GLYPHS, key=lambda c: ord(c)))
assert len(FONT_CHARS) <= 48, len(FONT_CHARS)
HUD_BG = BLUE

def glyph_pixels(ch, fg, bg, ol=BLACK):
    g = GLYPHS.get(ch)
    px = [[bg] * 8 for _ in range(8)]
    if not g:
        return px
    on = {(x + 1, y) for y in range(7) for x in range(5) if g[y][x] == '1'}
    for (x, y) in on:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                xx, yy = x + dx, y + dy
                if 0 <= xx < 8 and 0 <= yy < 8 and (xx, yy) not in on:
                    px[yy][xx] = ol
    for (x, y) in on:
        px[y][x] = fg
    return px

def gen_font():
    data = []
    for ch in FONT_CHARS:
        data += tile_bytes(glyph_pixels(ch, WHITE, HUD_BG))
    cmap = [FONT_CHARS.index(chr(c)) if chr(c) in FONT_CHARS else 0 for c in range(32, 91)]
    return data, cmap

def draw_text_img(img, x, y, text, fg, ol=BLACK):
    for i, ch in enumerate(text):
        g = GLYPHS.get(ch)
        if not g:
            continue
        on = [(xx + 1, yy) for yy in range(7) for xx in range(5) if g[yy][xx] == '1']
        ox = x + i * 8
        for (gx, gy) in on:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    img.putpixel((ox + gx + dx, y + gy + dy), ol)
        for (gx, gy) in on:
            img.putpixel((ox + gx, y + gy), fg)

# ------------------------------------------------------------------ HUD frame
VIEW_TY = 2
FACE_TY = 15
# the bar between the two views: screen x -> colour (grey, black | black, grey)
DIVIDER = [(126, LGREY), (127, BLACK), (128, BLACK), (129, LGREY)]

def sky_edge_tiles():
    """sky tiles for view columns 15 and 16 with the divider painted in"""
    out = []
    for tc in (15, 16):
        for r in range(6):
            px = [[sky_index(r * 8 + y)] * 8 for y in range(8)]
            for x, c in DIVIDER:
                if x // 8 == tc:
                    for y in range(8):
                        px[y][x % 8] = c
            out += tile_bytes(px)
    return out

def gen_frame():
    img = Image.new('L', (256, 192), HUD_BG)
    d = ImageDraw.Draw(img)
    for y0 in (8, 112):
        d.rectangle([0, y0, 255, y0 + 7], fill=DGREY)
        d.rectangle([0, y0 + (7 if y0 == 8 else 0), 255, y0 + (7 if y0 == 8 else 0)], fill=BLACK)
        for x in range(4, 256, 16):
            yy = y0 + 3
            d.rectangle([x, yy, x + 1, yy + 1], fill=LGREY)
            d.point((x + 1, yy + 1), fill=BLACK)
        for x in range(10, 256, 16):
            d.rectangle([x, y0 + 2, x + 3, y0 + 4], fill=YELLOW if y0 == 8 else CYC_A)
    # divider between the two players' halves, full height (the renderer draws
    # the same bar through the 3D views: see DIVIDER below and out_column)
    for x, c in DIVIDER:
        d.rectangle([x, 0, x, 191], fill=c)
    px = img.load()
    tiles, index, tmap = [], {}, []
    for ty in range(24):
        for tx in range(32):
            inview = VIEW_TY <= ty < VIEW_TY + 12
            inface = FACE_TY <= ty < FACE_TY + 4 and (1 <= tx < 4 or 17 <= tx < 20)
            if inview or inface:
                tmap.append(0xFF)
                continue
            blk = tuple(tuple(px[tx * 8 + x, ty * 8 + y] for x in range(8)) for y in range(8))
            for row in blk:
                assert 0 not in row and 1 not in row
            if blk not in index:
                index[blk] = len(tiles)
                tiles.append(blk)
            tmap.append(index[blk])
    assert len(tiles) <= 20, len(tiles)
    return tiles, tmap, img

# ------------------------------------------------------------------ title screen
TITLE_PAL = [(0, 0, 0), (3, 3, 3), (3, 3, 0), (3, 1, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3), (1, 1, 2),
             (0, 0, 2), (0, 1, 3), (0, 2, 3), (1, 3, 3), (3, 3, 3), (1, 3, 3), (0, 2, 3), (0, 1, 3)]

def gen_title():
    W, H = 256, 192
    img = Image.new('L', (W, H), 0)
    px = img.load()
    rnd = random.Random(42)
    for i in range(140):
        x, y = rnd.randrange(W), rnd.randrange(H)
        px[x, y] = 4 + (i % 4)
        if i % 9 == 0 and 1 <= x < W - 1 and 1 <= y < H - 1:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                px[x + dx, y + dy] = 4 + ((i + 2) % 4)
    d = ImageDraw.Draw(img)
    d.fontmode = '1'
    fpath = '/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'
    big = ImageFont.truetype(fpath, 50)
    # planet
    d.ellipse([150, 100, 330, 280], fill=7)
    d.ellipse([160, 104, 330, 280], fill=8)
    # logo: metallic sheen bands (palette 8..15 rotate)
    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.fontmode = '1'
    for (txt, y) in (('STAR', 46), ('FRAG', 98)):
        md.text((128, y), txt, font=big, fill=255, anchor='mm', stroke_width=4, stroke_fill=128)
    m = mask.load()
    for y in range(H):
        for x in range(W):
            if m[x, y] == 128:
                px[x, y] = 0
            elif m[x, y] == 255:
                px[x, y] = 8 + ((x // 3 + y // 2) % 8) if 8 + ((x // 3 + y // 2) % 8) != 8 else 9
    # 3D badge
    d.ellipse([200, 108, 244, 148], fill=0)
    d.ellipse([202, 110, 242, 146], fill=3)
    d.text((222, 127), '3D', font=ImageFont.truetype(fpath, 20), fill=2, anchor='mm', stroke_width=1, stroke_fill=0)
    d.rectangle([20, 140, 180, 151], fill=0)
    draw_text_img(img, 22, 142, '2 PLAYER DEATHMATCH', 2, 0)
    d.rectangle([60, 160, 200, 175], fill=0)
    draw_text_img(img, 72, 164, 'PRESS BUTTON 1', 6, 0)
    draw_text_img(img, 52, 182, '2026 HOMEBREW - SMS', 5, 0)
    tiles, index, tm = [], {}, []
    for ty in range(24):
        for tx in range(32):
            blk = tuple(tuple(px[tx * 8 + x, ty * 8 + y] for x in range(8)) for y in range(8))
            if blk not in index:
                index[blk] = len(tiles)
                tiles.append(blk)
            tm.append(index[blk])
    assert len(tiles) <= 440, len(tiles)
    return tiles, tm, img

# ------------------------------------------------------------------ arenas
OBJCH = {'h': 0, 'a': 1, 'm': 2, 'r': 3, 'p': 4, 'g': 5, 'k': 6, 'f': 7, 'l': 8, 'o': 9}

def gen_levels():
    out = []
    for name, sky, floor, rows in ARENAS:
        assert len(rows) <= 22, (name, 'the bot navigation field covers 22 rows')
        cells = [1] * 1024
        objs, spawns = [], []
        for y, row in enumerate(rows):
            assert len(row) == 32, (name, y, len(row))
            for x, ch in enumerate(row):
                if ch in WALLCH:
                    cells[y * 32 + x] = WALLCH[ch]
                else:
                    assert ch == '.' or ch in OBJCH or ch.isdigit(), (name, ch)
                    cells[y * 32 + x] = 0
                    if ch.isdigit():
                        spawns.append((int(ch), x, y))
                    elif ch in OBJCH:
                        objs.append((OBJCH[ch], x, y))
        for x in range(32):
            assert cells[x] and cells[(len(rows) - 1) * 32 + x], (name, 'open border')
        for y in range(len(rows)):
            assert cells[y * 32] and cells[y * 32 + 31], (name, 'open border', y)
        spawns.sort()
        assert len(spawns) == 6, (name, spawns)
        start = (spawns[0][1], spawns[0][2])
        seen, stack = set(), [start]
        while stack:
            x, y = stack.pop()
            if (x, y) in seen or cells[y * 32 + x]:
                continue
            seen.add((x, y))
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        for (t, x, y) in objs:
            assert (x, y) in seen, (name, 'unreachable item', t, x, y)
        for (n, x, y) in spawns:
            assert (x, y) in seen, (name, 'unreachable spawn', n)
        out.append((name, cells, objs, [(x, y) for (_, x, y) in spawns]))
    return out

# ------------------------------------------------------------------ music
NOTE_NAMES = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}

def period(note):
    if note == 'R':
        return 0
    n, o = note[:-1], int(note[-1])
    midi = 12 * (o + 1) + NOTE_NAMES[n]
    f = 440.0 * 2 ** ((midi - 69) / 12.0)
    return max(1, min(1023, int(round(3579545 / (32 * f)))))

def song(text, unit):
    data = []
    for tok in text.split():
        nt, ln = tok.split(':')
        p = period(nt)
        data += [p & 0xFF, (p >> 8) | (0x80 if nt == 'R' else 0), int(ln) * unit]
    return data + [0, 0x40, 0]

SONGS = {
 'title': (
  "E4:2 B4:2 E5:2 D5:1 B4:1 A4:2 B4:2 G4:4 "
  "E4:2 B4:2 E5:2 F#5:1 G5:1 F#5:2 D5:2 B4:4 "
  "C5:2 E5:2 G5:2 F#5:1 E5:1 D5:2 B4:2 A4:4 "
  "G4:2 A4:2 B4:2 D5:2 E5:6 R:2",
  "E2:2 E3:2 E2:2 E3:2 C3:2 C3:2 D3:2 D3:2 E2:2 E3:2 E2:2 E3:2 B2:2 B2:2 D3:2 D3:2 "
  "C3:2 C3:2 C3:2 C3:2 D3:2 D3:2 D3:2 D3:2 E2:2 E3:2 B2:2 D3:2 E2:4 E3:4", 9),
 'game': (
  "A4:1 R:1 A4:1 C5:1 R:1 A4:1 D5:1 E5:1 R:2 E5:1 G5:1 E5:1 D5:1 C5:2 "
  "A4:1 R:1 A4:1 C5:1 R:1 A4:1 D5:1 E5:1 R:2 G5:1 F5:1 E5:1 D5:1 E5:2 "
  "F5:1 R:1 F5:1 E5:1 D5:1 C5:1 D5:2 R:1 E5:1 D5:1 C5:1 B4:1 G4:1 A4:2 "
  "C5:1 B4:1 A4:1 B4:1 C5:1 D5:1 E5:2 R:2 E4:1 G#4:1 B4:1 E5:1 A4:2",
  "A2:1 A2:1 A3:1 A2:1 A2:1 A3:1 G2:1 G3:1 A2:1 A2:1 A3:1 A2:1 C3:1 C3:1 D3:1 E3:1 "
  "A2:1 A2:1 A3:1 A2:1 A2:1 A3:1 G2:1 G3:1 A2:1 A2:1 A3:1 A2:1 E3:1 D3:1 C3:1 B2:1 "
  "F2:1 F2:1 F3:1 F2:1 F2:1 F3:1 G2:1 G3:1 C3:1 C3:1 C4:1 C3:1 G2:1 G2:1 G3:1 G2:1 "
  "F2:1 F2:1 F3:1 F2:1 G2:1 G2:1 G3:1 G2:1 E2:1 E2:1 E3:1 E2:1 E2:1 G#2:1 B2:1 E3:1", 7),
 'win': ("E5:1 G5:1 B5:1 E6:3 D6:1 E6:6 R:8", "E3:3 B3:3 E4:6 R:8", 6),
}

def gen_music():
    s = ''
    for k, (a, b, unit) in SONGS.items():
        s += c_array('mus_%s_a' % k, song(a, unit))
        s += c_array('mus_%s_b' % k, song(b, unit))
    return s

# ------------------------------------------------------------------ main
def main():
    write('tables.c', gen_tables())
    write('scalers.s', gen_unrolled_asm())
    banks = gen_texbanks()
    TEXBANK0 = 2
    for i, b in enumerate(banks):
        write('texbank%d.c' % i, c_array('texbank%d' % i, list(b), 'unsigned char', 64))
    ANG_BANK = TEXBANK0 + len(banks)
    write('angbank.c', c_array('angbank', list(gen_angbank()), 'unsigned char', 64))
    write('assets.inc', 'TEXBANK0 = %d\nANG_BANK = %d\nROWS_BASE = 0x%04X\n' % (TEXBANK0, ANG_BANK, 0x8000 + 0x26 * 256))
    MISC_BANK = ANG_BANK + 1
    TITLE_BANK = MISC_BANK + 1
    SPR_BANK = TITLE_BANK + 1

    # --- misc bank: arenas + first-person weapons
    lv = gen_levels()
    misc = '#include "../src/defs.h"\n'
    for i, (name, cells, objs, spawns) in enumerate(lv):
        misc += c_array('lvl%d_map' % i, cells, 'unsigned char', 32)
        flat = []
        for (t, x, y) in objs:
            flat += [t, x, y]
        misc += c_array('lvl%d_objs' % i, flat + [0xFF])
        misc += c_array('lvl%d_spawns' % i, [v for s in spawns for v in s])
    misc += 'const unsigned char * const lvl_maps[%d] = {%s};\n' % (len(lv), ','.join('lvl%d_map' % i for i in range(len(lv))))
    misc += 'const unsigned char * const lvl_objs[%d] = {%s};\n' % (len(lv), ','.join('lvl%d_objs' % i for i in range(len(lv))))
    misc += 'const unsigned char * const lvl_spawns[%d] = {%s};\n' % (len(lv), ','.join('lvl%d_spawns' % i for i in range(len(lv))))
    misc += c_array('hand_tiles', gen_hands())
    misc += gen_plane_lut()
    misc += gen_sky_tiles()
    misc += gen_arrow_tiles()
    misc += c_array('radar_tiles', radar_base())
    # screen-setup tiles live here too (loaded with the display off)
    ftiles, fmap, fimg = gen_frame()
    font, cmap = gen_font()
    misc += c_array('font_tiles', font)
    misc += c_array('frame_tiles', [b for t in ftiles for b in tile_bytes(t)])
    misc += c_array('sky_edge_tiles', sky_edge_tiles())
    misc += c_array('frame_map', fmap, 'unsigned char', 32)
    pal_bytes = []
    for L in range(len(ARENAS)):
        for which in range(2):
            pal_bytes += [smsc(*c) for c in full_palette(L, which)]
    misc += c_array('level_pals', pal_bytes)
    write('miscbank.c', misc)

    tt, tm, timg = gen_title()
    tb = '#include "../src/defs.h"\n'
    tb += c_array('title_tiles', [b for t in tt for b in tile_bytes(t)])
    tb += c_array('title_map', tm, 'unsigned short', 32)
    write('titlebank.c', tb)

    # --- sprites: procedural items/effects, then the skins
    pk = Packer(SPR_BANK)
    gnames, gbanks = [], []
    preview_rows = []
    for nm, fn in ITEM_GFX:
        imgs = []
        for S in SIZES:
            a = Art(S, S)
            fn(a)
            imgs.append(a.result())
        gbanks.append(build_graphic(pk, nm, imgs))
        gnames.append(nm)
        preview_rows.append(imgs[-1])
    dpal = load_pal(os.path.join(HERE, 'doompal.lmp'))
    wd = Wad(WADPATH)
    sks = {s.get('name'): s for s in skin_index(wd)}
    face_bank, face_names = [], []
    skin_previews = []
    for si, (wname, disp, fpre) in enumerate(SKINS):
        sk = sks[wname]
        for gi, (fr, rot) in enumerate(SKIN_FRAMES):
            imgs = [skin_graphic(wd, sk, fr, rot, S, dpal) for S in SIZES]
            nm = 's%d_%d' % (si, gi)
            gbanks.append(build_graphic(pk, nm, imgs))
            gnames.append(nm)
            if fr == 'A' or gi >= 16:
                skin_previews.append((si, gi, imgs[-1]))
        fdata, fimgs = face_tiles(wd, fpre, dpal)
        face_bank.append(pk.add(c_array('face_%d' % si, fdata), len(fdata)))
        face_names.append('face_%d' % si)
        skin_previews.append((si, 99, [r + [T] * 8 for r in fimgs[0]]))
    srcs = []
    for bi, arrs in enumerate(pk.banks):
        srcs.append('#include "../src/defs.h"\n' + '\n'.join(arrs))
    for i, src in enumerate(srcs):
        write('sprbank%d.c' % i, src)
    fx = '#include "../src/defs.h"\n'
    fx += ''.join('extern const SprImg gt_%s[%d];\n' % (n, len(SIZES)) for n in gnames)
    fx += ''.join('extern const unsigned char %s[];\n' % n for n in face_names)
    fx += c_array('gfx_bank', gbanks)
    fx += 'const SprImg * const gfx_tab[%d] = {%s};\n' % (len(gnames), ','.join('gt_%s' % n for n in gnames))
    fx += c_array('face_bank', face_bank)
    fx += 'const unsigned char * const face_data[%d] = {%s};\n' % (len(face_names), ','.join(face_names))
    write('sprites_tab.c', fx)

    # --- fixed-bank assets
    ftiles, fmap, fimg = gen_frame()
    # frame tiles past the first 10 go to 256+SAT_FRAME(56); the 12 divider sky tiles follow
    skyedge = 256 + 56 + max(0, len(ftiles) - 10)
    assert skyedge + 12 <= 256 + 69, 'divider sky tiles overlap the arrow/radar tiles'
    font, cmap = gen_font()
    fx = '#include "../src/defs.h"\n'
    fx += c_array('font_map', cmap)
    fx += gen_music()
    fx += c_array('cycle_cols', [smsc(*c) for c in CYCLE])
    fx += c_array('title_pal', [smsc(*c) for c in TITLE_PAL])
    fx += 'const char * const level_names[%d] = {%s};\n' % (len(lv), ''.join('"%s",' % n for (n, _, _, _) in lv))
    fx += 'const char * const skin_names[%d] = {%s};\n' % (len(SKINS), ''.join('"%s",' % d for (_, d, _) in SKINS))
    fx += 'const char * const weapon_names[%d] = {%s};\n' % (len(WEAPONS), ''.join('"%s",' % w for w in WEAPONS))
    write('assets_fixed.c', fx)

    h = '/* generated by tools/gen.py */\n#ifndef ASSETS_H\n#define ASSETS_H\n'
    h += '#define TITLE_BANK %d\n#define ANG_BANK %d\n#define TEXBANK0 %d\n#define MISC_BANK %d\n' % (
        TITLE_BANK, ANG_BANK, TEXBANK0, MISC_BANK)
    h += '#define NFRAME_TILES %d\n#define NTITLE_TILES %d\n#define NLEVELS %d\n#define NSIZES %d\n' % (
        len(ftiles), len(tt), len(lv), len(SIZES))
    h += '#define SKYEDGE_BASE %d\n' % skyedge
    with open(os.path.join(OUT, 'assets.inc'), 'a') as f:
        f.write('SKYEDGE_LO = %d\n' % (skyedge - 256))
    h += '#define NFONT %d\n#define NSKINS %d\n#define NSKINGFX %d\n#define NGRAPHICS %d\n' % (
        len(FONT_CHARS), len(SKINS), NSKINGFX, len(gnames))
    for i, (nm, _) in enumerate(ITEM_GFX):
        h += '#define G_%s %d\n' % (nm.upper(), i)
    h += '#define G_SKIN0 %d\n' % len(ITEM_GFX)
    h += 'static const unsigned char size_px[%d] = {%s};\n' % (len(SIZES), ','.join(map(str, SIZES)))
    h += '#endif\n'
    write('assets.h', h)
    nb = len(srcs)
    last = SPR_BANK + nb - 1
    romkb = 1 << max(7, (last + 1) * 16 - 1).bit_length()
    write('banks.mk', '\n'.join([
        'TEXBANKS = ' + ' '.join(str(TEXBANK0 + i) for i in range(len(banks))),
        'ANG_BANK = %d' % ANG_BANK, 'MISC_BANK = %d' % MISC_BANK, 'TITLE_BANK = %d' % TITLE_BANK,
        'SPRBANKS = ' + ' '.join(str(SPR_BANK + i) for i in range(nb)),
        'NSPRBANKS = %d' % nb, 'ROMKB = %d' % romkb]) + '\n')

    # --- previews
    pal1 = [rgb8(c) for c in full_palette(0, 1)]
    def colorize(rows, pal):
        im = Image.new('RGB', (len(rows[0]), len(rows)), (60, 60, 90))
        for y, r in enumerate(rows):
            for x, v in enumerate(r):
                if v != T and v < 16:
                    im.putpixel((x, y), pal[v])
        return im
    pv = Image.new('RGB', (64 * 10, 64 * (2 + len(SKINS) * 2)), (60, 60, 90))
    for i, img in enumerate(preview_rows):
        pv.paste(colorize(img, pal1), ((i % 10) * 64, (i // 10) * 64))
    row = {}
    for (si, gi, img) in skin_previews:
        k = row.get(si, 0)
        row[si] = k + 1
        pv.paste(colorize(img, pal1), ((k % 10) * 64, (2 + si * 2 + k // 10) * 64))
    pv.resize((pv.width * 2, pv.height * 2), Image.NEAREST).save(os.path.join(SHOTS, 'sprites_preview.png'))
    pal0 = [rgb8(c) for c in full_palette(0, 0)]
    def colorize_img(im, pal):
        o = Image.new('RGB', im.size)
        o.putdata([pal[v] if v < len(pal) else (255, 0, 255) for v in im.getdata()])
        return o
    colorize_img(fimg, pal0).resize((768, 576), Image.NEAREST).save(os.path.join(SHOTS, 'frame_preview.png'))
    colorize_img(timg, [rgb8(c) for c in TITLE_PAL]).resize((768, 576), Image.NEAREST).save(os.path.join(SHOTS, 'title_preview.png'))
    vs = variants()
    tp = Image.new('RGB', (34 * len(vs), 32))
    for i, t in enumerate(vs):
        full = t + t[::-1]
        for y in range(32):
            for x in range(32):
                tp.putpixel((i * 34 + x, y), rgb8(full_palette(0, 0)[full[y][x]]))
    tp.resize((tp.width * 3, 96), Image.NEAREST).save(os.path.join(SHOTS, 'textures_preview.png'))
    print('frame tiles', len(ftiles), 'title tiles', len(tt), 'tex banks', len(banks),
          'spr banks', nb, 'graphics', len(gnames), 'rom KB', romkb)

if __name__ == '__main__':
    main()
