# Track F: the maths, the transform's products and the projection
# (docs/engine.md, stages 3 and 5; docs/research/maths.md,
# docs/research/projection.md).
#
#   make maths    build the maths' check (tools/mathscheck.6502) and run
#                 it: src/maths.6502 and src/project.6502 against
#                 tools/model/maths.py, exactly, with their cycles, and
#                 every entrance view's projected vertices timed, each by
#                 project and shared by project_z and project_y
#                 (tools/mathscheck.mjs); one of make check's
#
#   .venv/bin/python -I tools/mkmaths.py --survey     the methods' errors
#   .venv/bin/python -I tools/mkmaths.py --flicker 2  what flickers in
#                 camera walks, 2 world units a frame (make data first)

MATHS_DIR     = build/maths
MATHS_GEN     = $(MATHS_DIR)/consts.6502 $(MATHS_DIR)/tables.6502
MATHS_BIN     = $(MATHS_DIR)/CODE
MATHS_SYMBOLS = $(MATHS_DIR)/symbols.json
MATHS_CASES   = $(MATHS_DIR)/cases.json
MATHS_VIEWS   = $(MATHS_DIR)/views.json
MATHS_SOURCES = tools/mathscheck.6502 src/defs.6502 src/maths.6502 src/project.6502

ALL    += $(MATHS_BIN)
CHECKS += maths

$(MATHS_GEN) &: tools/mkmaths.py tools/model/maths.py
	$(PYTHON) -I tools/mkmaths.py $(MATHS_DIR)

$(MATHS_BIN) $(MATHS_DIR)/HAZEL $(MATHS_SYMBOLS) &: $(MATHS_SOURCES) $(MATHS_GEN)
	$(ASM) --warn 2 -p $(MATHS_DIR) --symbols $(MATHS_SYMBOLS) tools/mathscheck.6502

$(MATHS_CASES): tools/mkmaths.py tools/model/maths.py
	$(PYTHON) -I tools/mkmaths.py $(MATHS_DIR) --cases $@

# The model's own projections, view by view (derived from the originals:
# built, never committed).
$(MATHS_VIEWS): tools/mkmaths.py $(DATA_JSON) $(wildcard tools/model/*.py)
	$(PYTHON) -I tools/mkmaths.py --views $(DATA_JSON) $@

.PHONY: maths
maths: $(MATHS_BIN) $(MATHS_CASES) $(MATHS_VIEWS)
	node tools/mathscheck.mjs $(MATHS_DIR)
