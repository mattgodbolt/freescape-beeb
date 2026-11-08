# Track I: Driller's player logic, transcribed and checked pass by pass
# against the original (docs/research/zx-logic.md).
#
#   make logic       the multiplies and divide against the original's own
#                    routines; every scenario in tests/logic/; and a fuzz of
#                    random walks from random entrances. Each pass runs on
#                    the original (tools/logic/oracle.py) and on the
#                    transcription (tools/logic/passes.py), and every
#                    variable must agree after it. Fails if any differs.
#   make logicfuzz   a longer fuzz: LOGICFUZZ walks from seed LOGICSEED; a
#                    failing walk is kept in tests/logic/ as a scenario
#
# build/logic/report.txt is the last full check's output.

# mk/zx.mk names the snapshot too, but is read after this file, and a
# rule's prerequisites expand as it's read.
ZXSNAP ?= build/zx/driller.z80
LOGICFUZZ ?= 1000
LOGICSEED ?= 100000
LOGIC_REPORT = build/logic/report.txt
LOGIC_DEPS = $(ZXSNAP) tools/zx.py $(wildcard tools/logic/*.py) $(wildcard tests/logic/*.txt) \
             $(DATA_JSON) $(wildcard tools/model/*.py)

.PHONY: logic logicfuzz
ALL    += $(LOGIC_REPORT)
CHECKS += logic

logic: $(LOGIC_REPORT)

$(LOGIC_REPORT): $(LOGIC_DEPS)
	@mkdir -p $(@D)
	$(PYTHON) -I tools/logic/check.py --snap $(ZXSNAP) --arith 2000 --fuzz 60 --passes 80 > $@ \
		|| { cat $@; rm -f $@; exit 1; }
	@cat $@

logicfuzz: $(ZXSNAP)
	$(PYTHON) -I tools/logic/check.py --snap $(ZXSNAP) --fuzz-only --fuzz $(LOGICFUZZ) \
		--seed $(LOGICSEED) --passes 120
