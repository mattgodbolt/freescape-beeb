# Track E: the Python model, the renderer's specification (docs/engine.md,
# docs/research/model.md).
#
#   make model        every entrance view: build/model/aAAA-eEEE.png, the
#                     work each took (build/model/counts.json), and the
#                     counts' summary
#   make model-check  the model's tests (tests/model), and its projected
#                     vertices against a floating-point reference
#                     (tools/model/floatref.py)
#   make model-zx     the model against the original's own entrance views
#                     (make zxviews): cameras, objects drawn, and pixels
#                     away from edges (tools/model/zxcompare.py); one of
#                     make check's once the ZX track's rules are here

MODEL_PY     = $(wildcard tools/model/*.py tools/model/standin/*.py)
MODEL_COUNTS = build/model/counts.json
MODEL_ZX     = build/zx/views/views.json

.PHONY: model model-check model-zx
ALL    += $(MODEL_COUNTS)
CHECKS += model-check
ifneq ($(wildcard mk/zx.mk),)
CHECKS += model-zx
endif

model: $(MODEL_COUNTS)
	$(PYTHON) -I tools/model/counts.py $(MODEL_COUNTS)

$(MODEL_COUNTS): $(DATA_JSON) $(MODEL_PY) src/defs.6502
	$(PYTHON) -I tools/model/render.py $(DATA_JSON) $(@D) > /dev/null

model-check: $(DATA_JSON)
	$(PYTHON) -I -m unittest discover -s tests/model -t .
	$(PYTHON) -I tools/model/floatref.py $(DATA_JSON)

model-zx: $(DATA_JSON) $(MODEL_ZX)
	$(PYTHON) -I tools/model/zxcompare.py $(DATA_JSON) $(dir $(MODEL_ZX))
