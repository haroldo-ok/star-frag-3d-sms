# Star Frag 3D - Sega Master System
DK      ?= $(HOME)/.devkitsms
CC      = sdcc
AS      = sdasz80
CFLAGS  = -mz80 -I$(DK)/include -Isrc --peep-file $(DK)/include/peep-rules.txt --opt-code-size --max-allocs-per-node 25000
OUT     = build
ROM     = star_frag_3d.sms
export PATH := $(DK)/bin:$(PATH)

GEN_STAMP = gen/assets.h
-include gen/banks.mk

FIXED_C = src/main.c src/render.c src/sprites.c src/game.c src/bot.c src/hud.c src/sound.c \
          gen/tables.c gen/assets_fixed.c gen/sprites_tab.c
ASM     = src/asm.s src/ray.s gen/scalers.s

FIXED_REL = $(patsubst %.c,$(OUT)/%.rel,$(notdir $(FIXED_C))) $(patsubst %.s,$(OUT)/%.rel,$(notdir $(ASM)))

# banked data: texbank0.c -> BANK2 ...
SPRIDX  = $(shell i=0; while [ $$i -lt $(NSPRBANKS) ]; do echo $$i; i=$$((i+1)); done)
BANKSRC = $(foreach i,0 1,gen/texbank$(i).c) gen/angbank.c gen/miscbank.c gen/titlebank.c $(foreach i,$(SPRIDX),gen/sprbank$(i).c)
BANKNUM = $(TEXBANKS) $(ANG_BANK) $(MISC_BANK) $(TITLE_BANK) $(SPRBANKS)
BANK_REL = $(patsubst %.c,$(OUT)/%.rel,$(notdir $(BANKSRC)))
BANK_LOCS = $(foreach b,$(BANKNUM),-Wl-b_BANK$(b)=0x$(shell printf '%x' $(b))8000)

all: $(ROM)

$(GEN_STAMP): tools/gen.py tools/maps.py
	python3 -I tools/gen.py

$(OUT):
	mkdir -p $(OUT)

vpath %.c src gen
vpath %.s src gen

$(OUT)/%.rel: %.c src/defs.h $(GEN_STAMP) | $(OUT)
	$(CC) $(CFLAGS) -c -o $@ $<

$(OUT)/%.rel: %.s gen/assets.inc | $(OUT)
	$(AS) -plosgff -o $@ $<

# bank sources: compile into their own const segment
define BANKRULE
$(OUT)/$(notdir $(1:.c=.rel)): $(1) $(GEN_STAMP) | $(OUT)
	$(CC) -mz80 -I$(DK)/include -Isrc --constseg BANK$(2) -c -o $$@ $$<
endef
pairs = $(join $(BANKSRC),$(addprefix :,$(BANKNUM)))
$(foreach p,$(pairs),$(eval $(call BANKRULE,$(word 1,$(subst :, ,$(p))),$(word 2,$(subst :, ,$(p))))))

$(OUT)/crt0_sms.rel: | $(OUT)
	cp $(DK)/lib/crt0_sms.rel $@; touch $(OUT)/crt0_sms.lst

$(OUT)/game.ihx: $(OUT)/crt0_sms.rel $(FIXED_REL) $(BANK_REL)
	$(CC) -mz80 --no-std-crt0 -Wl-u --data-loc 0xC000 $(BANK_LOCS) -o $@ \
	  build/crt0_sms.rel $(FIXED_REL) $(DK)/lib/SMSlib.lib $(DK)/lib/PSGlib.lib $(BANK_REL)

$(ROM): $(OUT)/game.ihx
	ihx2sms $< $@
	python3 -c "import sys;d=open('$@','rb').read();open('$@','wb').write(d+b'\\xff'*($(ROMKB)*1024-len(d)))"
	python3 tools/checkmap.py $(OUT)/game.map

clean:
	rm -rf $(OUT) $(ROM)

.PHONY: all clean
