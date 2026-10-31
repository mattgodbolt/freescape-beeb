# Track E: Driller's database as JSON (tools/freescape.py,
# docs/research/model.md).
#
#   make data    build/data/driller.json from the ZX tape, checked: the
#                block's md5 against ScummVM's detection entry; every
#                area's objects end where its conditions start; the counts
#                BRIEF.md measured; the sine table; the start's step, turn
#                and entrance
#
# The tape is read with python -I and nothing of it is committed
# (decision 6).

DATA_TAPE = originals/zx/Driller.tzx
DATA_JSON = build/data/driller.json

.PHONY: data data-check
ALL    += $(DATA_JSON)
CHECKS += data-check

data: data-check

$(DATA_JSON): tools/freescape.py $(DATA_TAPE)
	@mkdir -p $(@D)
	$(PYTHON) -I tools/freescape.py $(DATA_TAPE) $@

data-check: $(DATA_JSON)
	$(PYTHON) -I tools/freescape.py --check $(DATA_JSON)
