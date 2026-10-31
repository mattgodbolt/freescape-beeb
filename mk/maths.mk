# Track F: the maths, the transform's products and the projection
# (docs/engine.md, stages 3 and 5; docs/research/maths.md).
#
#   make maths    build the maths' check (tools/mathscheck.6502) and run
#                 it: src/maths.6502 and src/project.6502 against
#                 tools/model/maths.py, exactly, with their cycles
#                 (tools/mathscheck.mjs); one of make check's

MATHS_DIR     = build/maths
MATHS_GEN     = $(MATHS_DIR)/consts.6502 $(MATHS_DIR)/tables.6502
MATHS_BIN     = $(MATHS_DIR)/CODE
MATHS_SYMBOLS = $(MATHS_DIR)/symbols.json
MATHS_CASES   = $(MATHS_DIR)/cases.json
MATHS_SOURCES = tools/mathscheck.6502 src/defs.6502 src/maths.6502 src/project.6502

ALL    += $(MATHS_BIN)
CHECKS += maths

$(MATHS_GEN) &: tools/mkmaths.py tools/model/maths.py
	$(PYTHON) -I tools/mkmaths.py $(MATHS_DIR)

$(MATHS_BIN) $(MATHS_DIR)/HAZEL $(MATHS_SYMBOLS) &: $(MATHS_SOURCES) $(MATHS_GEN)
	$(ASM) --warn 2 -p $(MATHS_DIR) --symbols $(MATHS_SYMBOLS) tools/mathscheck.6502

$(MATHS_CASES): tools/mkmaths.py tools/model/maths.py
	$(PYTHON) -I tools/mkmaths.py $(MATHS_DIR) --cases $@

.PHONY: maths
maths: $(MATHS_BIN) $(MATHS_CASES)
	node tools/mathscheck.mjs $(MATHS_DIR)
