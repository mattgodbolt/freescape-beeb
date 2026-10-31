# Track J: Driller's player logic in 6502 (src/logic/;
# docs/research/logic6502.md).
#
#   make logic6502      build the logic (tools/logiccheck.6502: the
#                       workspace LOGICW, the banks LOGIC and LOGICC, and
#                       the harness's entries CHECK) and check it pass by
#                       pass against tools/logic/ with decision 18's fix
#                       on: every scenario in tests/logic/ and a fuzz of
#                       random walks, every variable and the database after
#                       every step, the arithmetic on its own, and the
#                       cycles of each pass (tools/logiccheck.mjs); one of
#                       make check's
#   make logic6502fuzz  a longer fuzz: L6FUZZ walks of 120 passes from seed
#                       L6SEED
#
# Everything is made from the fetched tape and the ZX snapshot into
# build/logic6502/ (decision 6).

# mk/zx.mk names these too, but is read after this file, and a rule's
# prerequisites expand as it's read.
ZXSNAP  ?= build/zx/driller.z80
L6_TAPE  = originals/zx/Driller.tzx
L6_DIR   = build/logic6502
L6_DATA  = $(L6_DIR)/data.6502 $(L6_DIR)/db.bin $(L6_DIR)/layout.json
L6_BIN   = $(L6_DIR)/CHECK $(L6_DIR)/LOGIC $(L6_DIR)/LOGICC $(L6_DIR)/LOGICW
L6_SYMS  = $(L6_DIR)/symbols.json
L6_TRACE = $(L6_DIR)/trace.json
L6_SOURCES = tools/logiccheck.6502 src/defs.6502 src/zp.6502 src/input.6502 $(wildcard src/logic/*.6502)
L6_PY    = tools/logictrace.py tools/mklogicdata.py tools/freescape.py $(wildcard tools/logic/*.py)
L6FUZZ  ?= 1000
L6SEED  ?= 100000

.PHONY: logic6502 logic6502fuzz
ALL    += $(L6_BIN)
CHECKS += logic6502

$(L6_DATA) &: tools/mklogicdata.py tools/freescape.py tools/logic/state.py $(ZXSNAP) $(L6_TAPE)
	@mkdir -p $(L6_DIR)
	$(PYTHON) -I tools/mklogicdata.py $(ZXSNAP) $(L6_TAPE) $(L6_DIR)

$(L6_BIN) $(L6_SYMS) &: $(L6_SOURCES) $(L6_DATA)
	$(ASM) --warn 2 -p $(L6_DIR) --symbols $(L6_SYMS) tools/logiccheck.6502

$(L6_TRACE): $(L6_PY) $(ZXSNAP) $(wildcard tests/logic/*.txt)
	@mkdir -p $(L6_DIR)
	$(PYTHON) -I tools/logictrace.py --snap $(ZXSNAP) --out $@ --fuzz 60 --seed 1 --passes 80 --arith 3000

logic6502: $(L6_BIN) $(L6_TRACE) tools/logiccheck.mjs tools/run6502.mjs
	node tools/logiccheck.mjs $(L6_DIR) $(L6_TRACE)

logic6502fuzz: $(L6_BIN) $(L6_PY) $(ZXSNAP)
	$(PYTHON) -I tools/logictrace.py --snap $(ZXSNAP) --out $(L6_DIR)/fuzz.json --no-scenarios \
		--fuzz $(L6FUZZ) --seed $(L6SEED) --passes 120
	node tools/logiccheck.mjs $(L6_DIR) $(L6_DIR)/fuzz.json
