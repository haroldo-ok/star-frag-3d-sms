"""Doom skin -> SMS sprite conversion helpers (reads the WAD as data)."""
import re, sys
from PIL import Image
from wad import Wad, patch

def load_pal(path):
    d = open(path, 'rb').read()
    return [tuple(d[i * 3:i * 3 + 3]) for i in range(256)]

def skin_index(w):
    names = [n for n, o, s in w.lumps]
    starts = [i for i, n in enumerate(names) if n == 'S_SKIN'] + [len(names)]
    out = []
    for k in range(len(starts) - 1):
        n, o, s = w.lumps[starts[k]]
        d = {}
        for line in w.data[o:o + s].decode('latin1').splitlines():
            m = re.match(r'\s*(\w+)\s*=\s*"?([^"\r\n]*)"?', line)
            if m:
                d[m.group(1).lower()] = m.group(2).strip()
        d['lumps'] = {w.lumps[i][0]: (w.lumps[i][1], w.lumps[i][2]) for i in range(starts[k] + 1, starts[k + 1])}
        out.append(d)
    return out

def find_frame(w, sk, frame, rot):
    """returns (patch, mirrored) for frame letter + rotation 1..8 (0 = any)"""
    for name, (o, s) in sk['lumps'].items():
        if len(name) < 6:
            continue
        pre = name[:4]
        # name: PPPPFR[FR]
        if name[4] == frame and (name[5] == str(rot) or name[5] == '0'):
            return patch(w.data[o:o + s]), False
        if len(name) == 8 and name[6] == frame and name[7] == str(rot):
            return patch(w.data[o:o + s]), True
    return None, False

def find_lump(w, sk, prefix_len_name):
    for name, (o, s) in sk['lumps'].items():
        if name == prefix_len_name:
            return w.data[o:o + s]
    return None

def to_rgba(p, pal, mirror=False):
    W, H, lo, to, px = p
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for y in range(H):
        for x in range(W):
            c = px[y][x]
            if c is not None:
                im.putpixel((W - 1 - x if mirror else x, y), pal[c] + (255,))
    if mirror:
        lo = W - 1 - lo
    return im, lo, to
