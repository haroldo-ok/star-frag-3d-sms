#!/bin/sh
# run a playtest on the project's smstest (has a player-2 pad) and convert screenshots to png
cd "$(dirname "$0")/.." || exit 1
[ -x tools/smstest/smstest ] || cc -O2 -w -o tools/smstest/smstest tools/smstest/smstest.c tools/smstest/z80.c
tools/smstest/smstest star_frag_3d.sms "$@"; r=$?
for f in shots/*.ppm; do [ -f "$f" ] && python3 -c "
from PIL import Image; Image.open('$f').resize((512,384),Image.NEAREST).save('${f%.ppm}.png')" && rm "$f"; done
exit $r
