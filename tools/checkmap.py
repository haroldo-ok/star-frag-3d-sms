#!/usr/bin/env python3
"""Post-link sanity checks: code fits the fixed 32 KB, RAM stays below the
page-aligned buffers (0xD700), texture banks start at 0x8000, banks fit."""
import re, sys
txt = open(sys.argv[1]).read()
areas = {}
for m in re.finditer(r'^(\S+)\s+([0-9A-F]{8})\s+([0-9A-F]{8})\s+=\s+(\d+)\.\s+bytes', txt, re.M):
    areas[m.group(1)] = (int(m.group(2), 16), int(m.group(3), 16))
ok = True
def chk(cond, msg):
    global ok
    print(('ok   ' if cond else 'FAIL ') + msg)
    ok &= cond
code_end = max(a + s for n, (a, s) in areas.items() if n in ('_CODE', '_HOME', '_GSINIT', '_GSFINAL', '_INITIALIZER', '_LIT') )
chk(code_end <= 0x7FF0, 'fixed code/const end 0x%04X' % code_end)
data_end = max(a + s for n, (a, s) in areas.items() if n in ('_DATA', '_INITIALIZED', '_BSS', '_HEAP'))
chk(data_end <= 0xD000, 'RAM end 0x%04X (tables/buffers from 0xD000)' % data_end)
for n, (a, s) in sorted(areas.items()):
    if n.startswith('_BANK'):
        chk(s <= 16384, '%s %d bytes' % (n, s))
for b in ('_texbank0', '_texbank1'):
    m = re.search(r'([0-9A-F]{8})\s+%s\b' % b, txt)
    chk(m and (int(m.group(1), 16) & 0xFFFF) == 0x8000, '%s at 0x8000' % b)
sys.exit(0 if ok else 1)
