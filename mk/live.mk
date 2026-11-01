# Track L: Driller live, the whole pipeline on the BBC every frame
# (src/live.6502, docs/research/live.md).
#
#   make live       build/live.ssd, and its check (tools/livecheck.mjs):
#                   booted on jsbeeb's full video, every entrance visited
#                   by SPACE, walks and turns at some, and the demo; every
#                   frame shown against the model's render of the frame's
#                   camera, byte for byte, with the fields a frame of the
#                   whole frame and of each half (build/live/check.json);
#                   one of make check's
#   make live-run   screenshots of the entrances LIVE_SHOTS names (their
#                   numbers from 0), on an RGB monitor and through PAL
#                   (tools/pal.py), into shots/
#
# The disc's data derive from the originals (make data, make colours, and
# the logic's database bank, build/logic6502's LOGIC), so they're built,
# never committed (decision 6).

LIVE_DIR     = build/live
LIVE_DISC    = build/live.ssd
LIVE_SYMBOLS = build/live.json
LIVE_GEN     = $(LIVE_DIR)/data.6502 $(LIVE_DIR)/live.json
LIVE_SOURCES = src/live.6502 src/text.6502 src/defs.6502 src/zp.6502 src/macros.6502 \
               src/screen.6502 src/irq.6502 src/input.6502 src/raster.6502 src/writer.6502 \
               src/area.6502 src/matrix.6502 src/transform.6502 src/objects.6502 src/clip.6502 \
               src/order.6502 src/maths.6502 src/project.6502
LIVE_SHOTS  ?= 0 18 26 40 57
# mk/maths.mk, mk/objects.mk and mk/logic6502.mk name these too, but are
# read after this file.
MATHS_GEN   ?= build/maths/consts.6502 build/maths/tables.6502
AREAS_GEN   ?= build/gen/areas.6502
AREAS_JSON  ?= build/gen/areas.json
MODEL_PY    ?= $(wildcard tools/model/*.py tools/model/standin/*.py)
L6_DIR      ?= build/logic6502

ALL    += $(LIVE_DISC)
CHECKS += live

$(LIVE_GEN) &: tools/mklive.py $(DATA_JSON) $(AREAS_JSON) $(MODEL_PY) $(COLOUR_MODEL)
	$(PYTHON) -I tools/mklive.py $(DATA_JSON) $(AREAS_JSON) $(LIVE_DIR)

$(LIVE_DISC) $(LIVE_SYMBOLS) &: $(LIVE_SOURCES) $(LIVE_GEN) $(AREAS_GEN) $(MATHS_GEN) $(L6_DIR)/LOGIC | build
	$(ASM) -D 'BUILD="$(FS_BUILD)"' -o $(LIVE_DISC) --title DRILLER --opt 3 --warn 2 \
	    --symbols $(LIVE_SYMBOLS) src/live.6502

.PHONY: live live-run
live: $(LIVE_DISC) $(LIVE_GEN)
	node tools/livecheck.mjs --disc $(LIVE_DISC) --live $(LIVE_DIR)/live.json --json $(LIVE_DIR)/check.json

LIVE_COMMA := ,
live-run: $(LIVE_DISC)
	node tools/play.mjs '=lv_want:0$(foreach v,$(LIVE_SHOTS),$(LIVE_COMMA)=lv_want:$(v)$(LIVE_COMMA)f160$(LIVE_COMMA)!view$(v))' \
	    shots/live_ --disc $(LIVE_DISC) --until live_loop
	for v in $(LIVE_SHOTS); do \
	    $(PYTHON) -I tools/pal.py --shrink 2 shots/live_view$$v.png shots/live_view$${v}_pal.png || exit 1; \
	done
