# Track K: the slideshow, Driller's entrance views drawn on the BBC by the
# 6502's rasteriser and writer from the model's inputs (src/slides.6502,
# tools/mkslides.py).
#
#   make slides       build/slides.ssd, and its checks: the loader's
#                     (tools/loadcheck.mjs, every part in place, the boot's
#                     times into build/slides/load.json), then tools/slidecheck.mjs:
#                     every view through jsbeeb's full video, each frame shown
#                     the model's bytes, the keys; with the fields a frame and
#                     raster_frame's cycles for each view
#                     (build/slides/check.json); one of make check's
#   make slides-run   screenshots of the views SLIDES_SHOTS names (their
#                     numbers from 0), on an RGB monitor and through PAL
#                     (tools/pal.py), into shots/
#
# The views' data derive from the originals (make data, make colours), so
# they're built, never committed (decision 6).

SLIDES_DIR     = build/slides
SLIDES_DISC    = build/slides.ssd
SLIDES_SYMBOLS = build/slides.json
SLIDES_VIEWS   = $(SLIDES_DIR)/views.json
SLIDES_SOURCES = src/slides.6502 src/text.6502 src/defs.6502 src/zp.6502 \
                 src/macros.6502 src/screen.6502 src/irq.6502 src/input.6502 \
                 src/raster.6502 src/writer.6502
SLIDES_SHOTS  ?= 0 7 18 26 40 57

ALL    += $(SLIDES_DISC)
CHECKS += slides

# The banks' files (S<bank>) come with slides.6502, which includes them.
$(SLIDES_DIR)/slides.6502 $(SLIDES_VIEWS) &: tools/mkslides.py $(DATA_JSON) $(MODEL_PY) \
        $(COLOUR_MODEL) src/defs.6502 src/raster.6502
	$(PYTHON) -I tools/mkslides.py $(DATA_JSON) $(SLIDES_DIR)

# Two passes, as the live discs' (mk/live.mk): the parts into
# $(SLIDES_DIR)/parts/ and their description, then the loader packs them.
# (mk/live.mk's, read before this file)
LOADER_SOURCES ?= src/loader.6502 src/zx02.6502
$(SLIDES_SYMBOLS) $(SLIDES_DIR)/parts.6502 &: $(SLIDES_SOURCES) $(SLIDES_DIR)/slides.6502 | build
	@mkdir -p $(SLIDES_DIR)/parts
	$(ASM) -D 'BUILD="$(FS_BUILD)"' -p $(SLIDES_DIR)/parts -log1 $(SLIDES_DIR)/parts.6502 --warn 2 \
	    --symbols $(SLIDES_SYMBOLS) src/slides.6502

$(SLIDES_DISC) $(SLIDES_DISC:.ssd=-loader.json) &: $(LOADER_SOURCES) $(SLIDES_DIR)/parts.6502
	$(ASM) -D 'LD_BUILD="../$(SLIDES_DIR)/"' -o $(SLIDES_DISC) --title DRILLER --opt 2 --warn 2 \
	    --symbols $(SLIDES_DISC:.ssd=-loader.json) src/loader.6502

.PHONY: slides slides-run
slides: $(SLIDES_DISC) $(SLIDES_VIEWS)
	node tools/loadcheck.mjs --disc $(SLIDES_DISC) --until slides_loop --json $(SLIDES_DIR)/load.json
	node tools/slidecheck.mjs --disc $(SLIDES_DISC) --views $(SLIDES_VIEWS) --json $(SLIDES_DIR)/check.json

SLIDES_COMMA := ,
slides-run: $(SLIDES_DISC)
	node tools/play.mjs '=slide_hold:0$(foreach v,$(SLIDES_SHOTS),$(SLIDES_COMMA)=slide_want:$(v)$(SLIDES_COMMA)f80$(SLIDES_COMMA)!view$(v))' \
	    shots/slides_ --disc $(SLIDES_DISC) --until slides_loop
	for v in $(SLIDES_SHOTS); do \
	    $(PYTHON) -I tools/pal.py --shrink 2 shots/slides_view$$v.png shots/slides_view$${v}_pal.png || exit 1; \
	done
