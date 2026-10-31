# The rasteriser and the writer (track G, docs/engine.md stages 8-10).
#
#   make raster   the 6502 (src/raster.6502, src/writer.6502) on every scene
#                 of tools/rasterscenes.py, its view's bytes against the
#                 model's (tools/model/raster.py, writer.py) exactly, with
#                 each scene's cycles (tools/rastercheck.mjs)
#
# The check build lays the sections out as decision 20 does: the code, the
# row runs and the work in a sideways bank (RASTER_BANK), the inputs and
# what lasts in main RAM; the harness's stubs page the bank in.

RASTER_SRC   = src/defs.6502 src/raster.6502 src/writer.6502
RASTER_MODEL = tools/model/raster.py tools/model/writer.py

ALL    += build/raster/RCODE
CHECKS += raster

.PHONY: raster
raster: build/raster/RCODE build/raster/scenes.json
	node tools/rastercheck.mjs build/raster
	$(RASTER_DRILLER)

# Driller's own entrance views, once the whole-view model is in the tree:
# derived from the originals (make data), so built, never committed.
ifneq ($(wildcard tools/model/render.py),)
RASTER_DRILLER = node tools/rastercheck.mjs build/raster --scenes build/raster/driller.json
raster: build/raster/driller.json
build/raster/driller.json: build/data/driller.json $(COLOUR_MODEL) tools/rasterscenes.py $(wildcard tools/model/*.py) | build/raster
	$(PYTHON) -I tools/rasterscenes.py --driller $< $@
endif

define RASTER_CHECK_6502
\ The rasteriser's check build (mk/raster.mk, tools/rastercheck.mjs).
INCLUDE "../../src/defs.6502"
ZA_POOL &00..&8F
RASTER_BANK = 4

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
SECTION RasterState, org = &1700, guard = &1900, virtual = TRUE
ENDSECTION
SECTION RasterRuns, org = &8000, guard = &8D00, filename = "RRUNS", cmos = TRUE
ENDSECTION
SECTION RasterCode, org = &8D00, guard = &A700, filename = "RCODE", cmos = TRUE
ENDSECTION
SECTION RasterWork, org = &A700, guard = &C000, virtual = TRUE
ENDSECTION

INCLUDE "../../src/raster.6502"
INCLUDE "../../src/writer.6502"
endef
export RASTER_CHECK_6502

build/raster/check.6502: mk/raster.mk | build/raster
	printf '%s\n' "$$RASTER_CHECK_6502" > $@

build/raster/RCODE build/raster/RRUNS build/raster/RCHECK build/raster/symbols.json &: build/raster/check.6502 $(RASTER_SRC)
	$(ASM) --warn 2 -p build/raster --symbols build/raster/symbols.json $<

build/raster/scenes.json: tools/rasterscenes.py $(RASTER_MODEL) src/defs.6502 | build/raster
	$(PYTHON) -I tools/rasterscenes.py $@

build/raster:
	mkdir -p $@
