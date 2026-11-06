# The rasteriser and the writer (track G, docs/engine.md stages 8-10).
#
#   make raster   the 6502 (src/raster.6502, src/writer.6502) on every scene
#                 of tools/rasterscenes.py, its view's bytes against the
#                 model's (tools/model/raster.py, writer.py) exactly, with
#                 each scene's cycles (tools/rastercheck.mjs); both builds,
#                 the engine's (build/raster) and the other way, the span
#                 buffer's or the painter's (build/raster-alt), for comparison
#
# The check build lays the sections out as decision 20 does: the code, the
# row runs and the work in a sideways bank (RASTER_BANK), the inputs and
# what lasts in main RAM; the harness's stubs page the bank in.

RASTER_SRC   = src/defs.6502 src/raster.6502 src/writer.6502
RASTER_MODEL = tools/model/raster.py tools/model/writer.py

ALL    += build/raster/RCODE
CHECKS += raster

.PHONY: raster
raster: build/raster/RCODE build/raster-alt/RCODE build/raster/scenes.json
	node tools/rastercheck.mjs build/raster
	$(RASTER_DRILLER)
	node tools/rastercheck.mjs build/raster-alt --scenes build/raster/scenes.json
	$(RASTER_DRILLER_ALT)

# Driller's own entrance views, once the whole-view model is in the tree:
# derived from the originals (make data), so built, never committed.
ifneq ($(wildcard tools/model/render.py),)
RASTER_DRILLER = node tools/rastercheck.mjs build/raster --scenes build/raster/driller.json
RASTER_DRILLER_ALT = node tools/rastercheck.mjs build/raster-alt --scenes build/raster/driller.json
raster: build/raster/driller.json
build/raster/driller.json: build/data/driller.json $(COLOUR_MODEL) tools/rasterscenes.py build/raster/limits $(wildcard tools/model/*.py) | build/raster
	$(PYTHON) -I tools/rasterscenes.py --driller $< $@
endif

define RASTER_CHECK_6502
\ The rasteriser's check build (mk/raster.mk, tools/rastercheck.mjs).
INCLUDE "../../src/defs.6502"
ZA_POOL &00..&8F
RASTER_BANK = 4
\ The line heads and the row runs' scratch bytes out of the bank, as the
\ live disc has them, in RasterState's page after its state.
RASTER_HEAD = &1780
RASTER_SCRATCH = RASTER_HEAD + VIEW_H

\ The stubs the harness calls: each pages in the bank and the screen
\ check_acccon names, and puts ACCCON back after.
SECTION RasterCheck, org = &0E00, guard = &0F00, filename = "RCHECK", cmos = TRUE
.check_init
    ZA_ENTRY
    JSR paged : JSR raster_init : JMP unpaged
.check_forget
    ZA_ENTRY
    JSR paged : JSR raster_forget : JMP unpaged
.check_frame
    ZA_ENTRY
    JSR paged : JSR raster_frame : JMP unpaged
.paged
    LDA acccon : STA check_was
    LDA check_acccon : STA acccon
    LDA #RASTER_BANK : STA romsel
    RTS
.unpaged
    LDA check_was : STA acccon
    RTS
.check_acccon
    EQUB 0
.check_was
    EQUB 0
ENDSECTION
SECTION RasterIn, org = &0F00, guard = &1700, virtual = TRUE
ENDSECTION
SECTION RasterState, org = &1700, guard = &1800, virtual = TRUE
ENDSECTION
SECTION RasterEnds, org = &1800, guard = &1C00, virtual = TRUE
ENDSECTION
\ The bank's sections one after another, as the slideshow has them.
SECTION RasterRuns, org = &8000, guard = &C000, filename = "RRUNS", cmos = TRUE
ENDSECTION
SECTION RasterCode, org = raster_runs_end, guard = &C000, filename = "RCODE", cmos = TRUE
ENDSECTION
SECTION RasterWork, org = raster_code_end, guard = &C000, virtual = TRUE
ENDSECTION

INCLUDE "../../src/raster.6502"
INCLUDE "../../src/writer.6502"
SECTION RasterRuns
.raster_runs_end
ENDSECTION
SECTION RasterCode
.raster_code_end
ENDSECTION
SECTION RasterWork
.raster_work_end
ENDSECTION
SECTION RasterState
.raster_state_end
ENDSECTION
ASSERT raster_work_end <= &C000 AND raster_state_end <= RASTER_HEAD
endef
export RASTER_CHECK_6502

build/raster/check.6502: mk/raster.mk | build/raster
	printf '%s\n' "$$RASTER_CHECK_6502" > $@

build/raster/RCODE build/raster/RRUNS build/raster/RCHECK build/raster/symbols.json &: build/raster/check.6502 $(RASTER_SRC)
	$(ASM) --warn 2 -p build/raster --symbols build/raster/symbols.json $<

# The other way: the same check build with RASTER_OTHER_WAY defined, which
# turns raster.6502's RASTER_PAINTER the other way from its default.
build/raster-alt/check.6502: mk/raster.mk | build/raster-alt
	{ printf 'RASTER_OTHER_WAY = TRUE\n'; printf '%s\n' "$$RASTER_CHECK_6502"; } > $@

build/raster-alt/RCODE build/raster-alt/RRUNS build/raster-alt/RCHECK build/raster-alt/symbols.json &: build/raster-alt/check.6502 $(RASTER_SRC)
	$(ASM) --warn 2 -p build/raster-alt --symbols build/raster-alt/symbols.json $<

build/raster/scenes.json: tools/rasterscenes.py $(RASTER_MODEL) src/defs.6502 build/raster/limits | build/raster
	$(PYTHON) -I tools/rasterscenes.py $@

# The 6502's limits that the scenes' views depend on (tools/rasterscenes.py
# reads them from src/raster.6502), rewritten only when they change, so an
# edit to the code doesn't remake every scene.
build/raster/limits: src/raster.6502 | build/raster
	sed -n -E 's/^\s*(POOL_NODES|POOL_HELD|RS_PATTERNS|RS_HMAX)\s*=\s*([0-9]+).*/\1 = \2/p' $< > $@.new
	cmp -s $@.new $@ || mv $@.new $@
	rm -f $@.new

build/raster build/raster-alt:
	mkdir -p $@

# The column fill, priced (docs/research/colfill.md):
#
#   make colfill  the column fill's model (tools/model/colfill.py) against the
#                 row fill's on every scene and Driller view, byte for byte,
#                 with its counts; its kernels (src/colfill-kernels.6502)
#                 timed in headless jsbeeb, and the column fill priced from
#                 them against the row fill's measured cycles, view by view
#                 (tools/colfillprice.mjs)
CHECKS += colfill

COLFILL_SCENES = build/raster/scenes.json $(if $(RASTER_DRILLER),build/raster/driller.json)

.PHONY: colfill
colfill: build/colfill/counts.json build/colfill/CKERN build/colfill/rows-driller.json
	node tools/colfillprice.mjs build/colfill --rows build/colfill/rows-driller.json

build/colfill/counts.json: tools/model/colfill.py $(RASTER_MODEL) $(COLFILL_SCENES) | build/colfill
	$(PYTHON) -I tools/model/colfill.py --counts $@ $(COLFILL_SCENES)

build/colfill/check.6502: mk/raster.mk | build/colfill
	printf 'INCLUDE "../../src/colfill-kernels.6502"\n' > $@

build/colfill/CKERN build/colfill/symbols.json &: build/colfill/check.6502 src/colfill-kernels.6502 src/defs.6502
	$(ASM) --warn 2 -p build/colfill --symbols build/colfill/symbols.json $<

# The row fill's own cycles on Driller's views, for the comparison.
build/colfill/rows-driller.json: build/raster/RCODE build/raster/driller.json | build/colfill
	node tools/rastercheck.mjs build/raster --scenes build/raster/driller.json --json $@

#   make colfill-live  the same on the live discs' frames: the cameras of
#                 make live's records (build/live/check*.json, every
#                 COLFILL_EVERY-th frame of the logic's run and every frame of
#                 the free camera's), rendered by the model, each drawn fresh
#                 by the row fill and priced for the column fill. Not one of
#                 make check's: it needs make live's records, and takes a
#                 while.
COLFILL_EVERY ?= 5
COLFILL_LIVE  = build/colfill/live.json

.PHONY: colfill-live
colfill-live: build/colfill/counts-live.json build/colfill/CKERN build/colfill/rows-live.json
	node tools/colfillprice.mjs build/colfill --rows build/colfill/rows-live.json --counts build/colfill/counts-live.json

$(COLFILL_LIVE): tools/rasterscenes.py build/live/check.json build/live/check-free.json build/live/live.json \
                 build/raster/limits $(wildcard tools/model/*.py) | build/colfill
	$(PYTHON) -I tools/rasterscenes.py --cameras build/data/driller.json build/live/live.json $@ \
	    build/live/check.json:$(COLFILL_EVERY) build/live/check-free.json

build/colfill/counts-live.json: tools/model/colfill.py $(RASTER_MODEL) $(COLFILL_LIVE)
	$(PYTHON) -I tools/model/colfill.py --counts $@ $(COLFILL_LIVE)

build/colfill/rows-live.json: build/raster/RCODE $(COLFILL_LIVE)
	node tools/rastercheck.mjs build/raster --scenes $(COLFILL_LIVE) --json $@

build/colfill:
	mkdir -p $@
