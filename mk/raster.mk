# The rasteriser and the writer (track G, docs/engine.md stages 8-10).
#
#   make raster   the 6502 (src/raster.6502, src/writer.6502) on every scene
#                 of tools/rasterscenes.py, its view's bytes against the
#                 model's (tools/model/raster.py, writer.py) exactly, with
#                 each scene's cycles (tools/rastercheck.mjs)
#
# The check build puts the code and the inputs in main RAM and the row runs
# and the span buffer in HAZEL; the engine's own build places the same
# sections where its memory map says.

RASTER_SRC   = src/defs.6502 src/raster.6502 src/writer.6502
RASTER_MODEL = tools/model/raster.py tools/model/writer.py

ALL    += build/raster/RCODE
CHECKS += raster

.PHONY: raster
raster: build/raster/RCODE build/raster/scenes.json
	node tools/rastercheck.mjs build/raster

define RASTER_CHECK_6502
\ The rasteriser's check build (mk/raster.mk, tools/rastercheck.mjs).
INCLUDE "../../src/defs.6502"
ZA_POOL &00..&8F

SECTION RasterCode, org = &1600, guard = &3000, filename = "RCODE", cmos = TRUE
.check_init
    ZA_ENTRY
    JMP raster_init
\ check_frame: raster_frame with check_acccon in ACCCON (HAZEL, and the
\ screen to draw), and the OS's ACCCON back after.
.check_frame
    ZA_ENTRY
    LDA acccon : PHA
    LDA check_acccon : STA acccon
    JSR raster_frame
    PLA : STA acccon
    RTS
.check_acccon
    EQUB ACCCON_Y
ENDSECTION
SECTION RasterIn, org = &0E00, guard = &1600, virtual = TRUE
ENDSECTION
SECTION RasterRuns, org = &C000, guard = &CD00, filename = "RRUNS", cmos = TRUE
ENDSECTION
SECTION RasterWork, org = &CD00, guard = &DF00, virtual = TRUE
ENDSECTION
SECTION RasterState, org = &DF00, guard = &E000, virtual = TRUE
ENDSECTION

INCLUDE "../../src/writer.6502"
INCLUDE "../../src/raster.6502"
endef
export RASTER_CHECK_6502

build/raster/check.6502: mk/raster.mk | build/raster
	printf '%s\n' "$$RASTER_CHECK_6502" > $@

build/raster/RCODE build/raster/RRUNS build/raster/symbols.json &: build/raster/check.6502 $(RASTER_SRC)
	$(ASM) --warn 2 -p build/raster --symbols build/raster/symbols.json $<

build/raster/scenes.json: tools/rasterscenes.py $(RASTER_MODEL) src/defs.6502 | build/raster
	$(PYTHON) -I tools/rasterscenes.py $@

build/raster:
	mkdir -p $@
