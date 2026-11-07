# Track S: Driller's sounds on the SN76489 (src/sound.6502,
# docs/research/sound.md).
#
#   make sound      the sounds' scripts (tools/mksound.py: each of the
#                   original's 21 beeper sounds run on the ZX snapshot,
#                   measured a field at a time and fitted with segments,
#                   into build/sound/), then tools/soundcheck.mjs: the live
#                   disc booted on jsbeeb, every sound asked for alone and
#                   in a queue, each tick's writes to the chip against the
#                   driver's model (tools/model/sound.py), write for write.
#                   One of make check's. (tools/livecheck.mjs holds the
#                   logic's asks to the transcription's, and the chip's
#                   writes over its run to the model, too.)
#
# Everything is made from the ZX snapshot into build/sound/ (decision 6).

SOUND_DIR  = build/sound
SOUND_GEN  = $(SOUND_DIR)/sound.6502 $(SOUND_DIR)/sound.json
# (mk/zx.mk's, read after this file)
ZXSNAP    ?= build/zx/driller.z80
LIVE_DISC ?= build/live.ssd

.PHONY: sound
CHECKS += sound

$(SOUND_GEN) &: tools/mksound.py tools/model/sound.py tools/zx.py $(ZXSNAP)
	@mkdir -p $(SOUND_DIR)
	$(PYTHON) -I tools/mksound.py $(ZXSNAP) $(SOUND_DIR)

sound: $(SOUND_GEN) $(LIVE_DISC)
	node tools/soundcheck.mjs --disc $(LIVE_DISC) --sound $(SOUND_DIR)/sound.json --log $(SOUND_DIR)/check.json
