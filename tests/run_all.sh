#!/bin/sh
# build + run every playtest; non-zero exit on any failure
cd "$(dirname "$0")/.." || exit 1
make || exit 1
fail=0
for t in boot walkout fight weapons items bot flow pause gallery soak; do
  printf '%-8s ' $t
  tools/st.sh tests/$t.txt > /tmp/st_$t.log 2>&1 && echo PASS || { echo FAIL; fail=1; grep FAIL /tmp/st_$t.log | head -5; }
done
exit $fail
