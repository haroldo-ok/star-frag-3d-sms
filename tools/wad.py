"""Minimal Doom WAD reader (data only)."""
import struct
class Wad:
    def __init__(self, path):
        self.data = open(path, 'rb').read()
        ident, n, off = struct.unpack_from('<4sii', self.data, 0)
        self.lumps = []
        for i in range(n):
            o, s, name = struct.unpack_from('<ii8s', self.data, off + i * 16)
            self.lumps.append((name.rstrip(b'\0').decode('latin1').upper(), o, s))
    def get(self, name):
        for n, o, s in self.lumps:
            if n == name: return self.data[o:o + s]
        return None
    def all(self, name):
        return [self.data[o:o + s] for n, o, s in self.lumps if n == name]
def patch(data):
    """Doom picture -> (w, h, leftoff, topoff, pixels[h][w] (None = transparent))"""
    w, h, lo, to = struct.unpack_from('<HHhh', data, 0)
    cols = struct.unpack_from('<%dI' % w, data, 8)
    px = [[None] * w for _ in range(h)]
    for x, co in enumerate(cols):
        p = co; top = -1
        while data[p] != 0xFF:
            t = data[p]; n = data[p + 1]
            top = t if t > top else top + t      # tall-patch rule
            for i in range(n):
                y = top + i
                if 0 <= y < h: px[y][x] = data[p + 3 + i]
            p += n + 4
    return w, h, lo, to, px
