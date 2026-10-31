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
ASSERT raster_work_end <= &C000
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

build/raster/scenes.json: tools/rasterscenes.py $(RASTER_MODEL) src/defs.6502 | build/raster
	$(PYTHON) -I tools/rasterscenes.py $@

build/raster build/raster-alt:
	mkdir -p $@
