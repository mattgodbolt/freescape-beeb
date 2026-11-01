# Track L, then P: Driller live, its own logic and the whole pipeline on
# the BBC every frame (src/live.6502, docs/research/live.md).
#
#   make live       build/live.ssd (Driller's logic moves the camera) and
#                   build/live-free.ssd (the free camera, -D
#                   FREE_CAMERA=TRUE), and their checks: the loader's
#                   (tools/loadcheck.mjs: every part in its place, and the
#                   boot's times, into <dir>/load.json), then tools/livecheck.mjs,
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
#
# Each disc is built in two passes: src/live.6502 writes each of its parts
# as a file into <dir>/parts/ (baron -p) and PRINTs where each goes into
# <dir>/parts.6502; then the loader (src/loader.6502) packs them into the
# disc's two files, !BOOT and DRILLER. tools/loadcheck.mjs boots each disc
# and holds every part in memory to its file, and times the boot.

LIVE_DIR     = build/live
LIVE_FREE_DIR = build/live-free
LIVE_DISC    = build/live.ssd
LIVE_FREE    = build/live-free.ssd
LIVE_SYMBOLS = build/live.json
LOADER_SOURCES = src/loader.6502 src/zx02.6502 src/defs.6502
LIVE_GEN     = $(LIVE_DIR)/data.6502 $(LIVE_DIR)/live.json
LIVE_TRACE   = $(LIVE_DIR)/trace.json
LIVE_SOURCES = src/live.6502 src/panel.6502 src/defs.6502 src/zp.6502 src/macros.6502 \
               src/screen.6502 src/irq.6502 src/input.6502 src/raster.6502 src/writer.6502 \
               src/area.6502 src/matrix.6502 src/transform.6502 src/objects.6502 src/clip.6502 \
               src/order.6502 src/maths.6502 src/project.6502 $(wildcard src/logic/*.6502)
LIVE_SHOTS  ?= 0 18 26 40 57
# (every scenario of tests/logic/ but keys, whose E the disc doesn't read)
LIVE_SCENARIOS ?= walls climb fall fall-high doors edge rise fcl jet ticks minutes steps turns corner crosshair \
                  fuzz-23 fuzz-28 fuzz-30 fuzz-34 fuzz-47 fuzz-109 fuzz-1239 fuzz-1244
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

# The first pass: the parts and their description, and the symbols.
$(LIVE_SYMBOLS) $(LIVE_DIR)/parts.6502 &: $(LIVE_SOURCES) $(LIVE_GEN) $(AREAS_GEN) $(MATHS_GEN) $(LIVE_L6) $(PANEL_GEN) | build
	@mkdir -p $(LIVE_DIR)/parts
	$(ASM) -D 'BUILD="$(FS_BUILD)"' -p $(LIVE_DIR)/parts -log1 $(LIVE_DIR)/parts.6502 --warn 2 \
	    --symbols $(LIVE_SYMBOLS) src/live.6502

$(LIVE_FREE:.ssd=.json) $(LIVE_FREE_DIR)/parts.6502 &: $(LIVE_SOURCES) $(LIVE_GEN) $(AREAS_GEN) $(MATHS_GEN) $(LIVE_L6) $(PANEL_GEN) | build
	@mkdir -p $(LIVE_FREE_DIR)/parts
	$(ASM) -D 'BUILD="$(FS_BUILD)"' -D FREE_CAMERA=TRUE -p $(LIVE_FREE_DIR)/parts -log1 $(LIVE_FREE_DIR)/parts.6502 \
	    --warn 2 --symbols $(LIVE_FREE:.ssd=.json) src/live.6502

# The second: the disc, the loader's symbols beside it.
$(LIVE_DISC) $(LIVE_DISC:.ssd=-loader.json) &: $(LOADER_SOURCES) $(LIVE_DIR)/parts.6502
	$(ASM) -D 'LD_BUILD="../$(LIVE_DIR)/"' -o $(LIVE_DISC) --title DRILLER --opt 2 --warn 2 \
	    --symbols $(LIVE_DISC:.ssd=-loader.json) src/loader.6502

$(LIVE_FREE) $(LIVE_FREE:.ssd=-loader.json) &: $(LOADER_SOURCES) $(LIVE_FREE_DIR)/parts.6502
	$(ASM) -D 'LD_BUILD="../$(LIVE_FREE_DIR)/"' -o $(LIVE_FREE) --title DRILLER --opt 2 --warn 2 \
	    --symbols $(LIVE_FREE:.ssd=-loader.json) src/loader.6502

# The scenarios' passes, as the transcription takes them, with the
# segments its moves walked (tools/mklive.py --trace).
$(LIVE_TRACE): tools/mklive.py tools/logictrace.py $(wildcard tools/logic/*.py) $(ZXSNAP) \
               $(foreach s,$(LIVE_SCENARIOS),tests/logic/$(s).txt)
	@mkdir -p $(LIVE_DIR)
	$(PYTHON) -I tools/mklive.py --trace $(ZXSNAP) $@ $(foreach s,$(LIVE_SCENARIOS),tests/logic/$(s).txt)

.PHONY: live live-run
live: $(LIVE_DISC) $(LIVE_FREE) $(LIVE_GEN) $(LIVE_TRACE)
	node tools/loadcheck.mjs --disc $(LIVE_DISC) --json $(LIVE_DIR)/load.json
	node tools/loadcheck.mjs --disc $(LIVE_FREE) --json $(LIVE_FREE_DIR)/load.json
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
