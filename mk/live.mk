# Track L, then P: Driller live, its own logic and the whole pipeline on
# the BBC every frame (src/live.6502, docs/research/live.md).
#
#   make live       build/live.ssd (Driller's logic moves the camera) and
#                   build/live-free.ssd (the free camera, -D
#                   FREE_CAMERA=TRUE), and their checks (tools/livecheck.mjs),
#                   on jsbeeb's full video: on the first, the scenarios of
#                   tests/logic/ LIVE_SCENARIOS names, a run of the keys they
#                   don't press and a tour of every entrance by the FCL's
#                   GOTO, by the keys, each pass's logic against tools/logic/, and
#                   every frame shown against the model's render of its
#                   camera, byte for byte, the frames between passes on the
#                   segments the moves walked; on the second, every entrance
#                   by SPACE, walks and turns, and the demo. Fields a frame
#                   into build/live/check.json and check-free.json. One of
#                   make check's
#   make live-run   screenshots of the entrances LIVE_SHOTS names (their
#                   numbers from 0) on the free camera's disc, on an RGB
#                   monitor and through PAL (tools/pal.py), into shots/
#
# The discs' data derive from the originals (make data, make colours, the
# logic's data, build/logic6502/), so they're built, never committed
# (decision 6).

LIVE_DIR     = build/live
LIVE_DISC    = build/live.ssd
LIVE_FREE    = build/live-free.ssd
LIVE_SYMBOLS = build/live.json
LIVE_GEN     = $(LIVE_DIR)/data.6502 $(LIVE_DIR)/live.json
LIVE_TRACE   = $(LIVE_DIR)/trace.json
LIVE_SOURCES = src/live.6502 src/panel.6502 src/defs.6502 src/zp.6502 src/macros.6502 \
               src/screen.6502 src/irq.6502 src/input.6502 src/raster.6502 src/writer.6502 \
               src/area.6502 src/matrix.6502 src/transform.6502 src/objects.6502 src/clip.6502 \
               src/order.6502 src/maths.6502 src/project.6502 $(wildcard src/logic/*.6502)
LIVE_SHOTS  ?= 0 18 26 40 57
LIVE_SCENARIOS ?= walls climb fall fall-high doors edge rise
# mk/maths.mk, mk/objects.mk and mk/logic6502.mk name these too, but are
# read after this file.
MATHS_GEN   ?= build/maths/consts.6502 build/maths/tables.6502
AREAS_GEN   ?= build/gen/areas.6502
AREAS_JSON  ?= build/gen/areas.json
MODEL_PY    ?= $(wildcard tools/model/*.py tools/model/standin/*.py)
L6_DIR      ?= build/logic6502
ZXSNAP      ?= build/zx/driller.z80
LIVE_L6     = $(L6_DIR)/data.6502 $(L6_DIR)/db.bin
# (mk/panel.mk's: the panel's data)
PANEL_GEN   ?= build/panel/panel.6502 build/panel/panel.json

ALL    += $(LIVE_DISC) $(LIVE_FREE)
CHECKS += live

$(LIVE_GEN) &: tools/mklive.py $(DATA_JSON) $(AREAS_JSON) $(MODEL_PY) $(COLOUR_MODEL)
	$(PYTHON) -I tools/mklive.py $(DATA_JSON) $(AREAS_JSON) $(LIVE_DIR)

$(LIVE_DISC) $(LIVE_SYMBOLS) &: $(LIVE_SOURCES) $(LIVE_GEN) $(AREAS_GEN) $(MATHS_GEN) $(LIVE_L6) $(PANEL_GEN) | build
	$(ASM) -D 'BUILD="$(FS_BUILD)"' -o $(LIVE_DISC) --title DRILLER --opt 3 --warn 2 \
	    --symbols $(LIVE_SYMBOLS) src/live.6502

$(LIVE_FREE) $(LIVE_FREE:.ssd=.json) &: $(LIVE_SOURCES) $(LIVE_GEN) $(AREAS_GEN) $(MATHS_GEN) $(LIVE_L6) $(PANEL_GEN) | build
	$(ASM) -D 'BUILD="$(FS_BUILD)"' -D FREE_CAMERA=TRUE -o $(LIVE_FREE) --title DRILLER --opt 3 --warn 2 \
	    --symbols $(LIVE_FREE:.ssd=.json) src/live.6502

# The scenarios' passes, as the transcription takes them, with the
# segments its moves walked (tools/mklive.py --trace).
$(LIVE_TRACE): tools/mklive.py tools/logictrace.py $(wildcard tools/logic/*.py) $(ZXSNAP) \
               $(foreach s,$(LIVE_SCENARIOS),tests/logic/$(s).txt)
	@mkdir -p $(LIVE_DIR)
	$(PYTHON) -I tools/mklive.py --trace $(ZXSNAP) $@ $(foreach s,$(LIVE_SCENARIOS),tests/logic/$(s).txt)

.PHONY: live live-run
live: $(LIVE_DISC) $(LIVE_FREE) $(LIVE_GEN) $(LIVE_TRACE)
	node tools/livecheck.mjs --disc $(LIVE_DISC) --live $(LIVE_DIR)/live.json --trace $(LIVE_TRACE) \
	    --json $(LIVE_DIR)/check.json
	node tools/livecheck.mjs --free --disc $(LIVE_FREE) --live $(LIVE_DIR)/live.json \
	    --json $(LIVE_DIR)/check-free.json

LIVE_COMMA := ,
live-run: $(LIVE_FREE)
	node tools/play.mjs '=lv_want:0$(foreach v,$(LIVE_SHOTS),$(LIVE_COMMA)=lv_want:$(v)$(LIVE_COMMA)f160$(LIVE_COMMA)!view$(v))' \
	    shots/live_ --disc $(LIVE_FREE) --until live_loop
	for v in $(LIVE_SHOTS); do \
	    $(PYTHON) -I tools/pal.py --shrink 2 shots/live_view$$v.png shots/live_view$${v}_pal.png || exit 1; \
	done
