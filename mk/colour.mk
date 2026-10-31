# The colour study (decision 8; docs/research/colour.md).
#
#   make colours        build/colour/: each version's colours, the BBC's
#                       patterns as a table for each display (bbc-rgb.json,
#                       bbc-pal.json, bbc-both.json, which
#                       tools/model/colours.py reads), the study's figures
#                       (study.md) and the swatches, on an RGB monitor and
#                       through PAL
#   make colour-check   the patterns' checks
#
# tools/pal.py is jsbeeb's PAL TV in NumPy: python -I tools/pal.py IN.png
# OUT.png shows a jsbeeb screenshot through it. tools/colour/pal-glcheck.py
# checks it against jsbeeb's own shader; it needs a jsbeeb checkout and
# Chrome, so it isn't one of the checks here.
#
# Every input but the scripts is a fetched original (make fetch).

COLOUR       = build/colour
COLOUR_ORIG  = originals/zx/Driller.tzx originals/dos/DISK01.IMA \
               originals/cpc/Driller.dsk originals/st/Driller.st \
               originals/amiga/Driller.adf
COLOUR_VERS  = dos cpc st amiga
COLOUR_FOR   = rgb pal both
# The model's tables, one for each display.
COLOUR_MODEL = $(foreach d,$(COLOUR_FOR),$(COLOUR)/bbc-$(d).json)
# Every version's, to compare.
COLOUR_TABLES = $(foreach v,$(COLOUR_VERS),$(foreach d,$(COLOUR_FOR),\
                  $(COLOUR)/bbc-$(v)-$(d).json))
# Swatches of a table: the model's for each display, and two others.
COLOUR_SWATCHES = $(COLOUR_FOR) dos-both cpc-both

.PHONY: colours colour-check
colours: $(COLOUR_MODEL) $(COLOUR)/study.md \
         $(foreach s,$(COLOUR_SWATCHES),$(COLOUR)/swatches/$(s)/sheet.png)
ALL    += colours
CHECKS += colour-check

$(COLOUR)/sources.json: tools/colour/sources.py tools/colour/database.py \
                        tools/colour/images.py tools/research/tap.py \
                        $(COLOUR_ORIG)
	mkdir -p $(COLOUR)
	$(PYTHON) -I tools/colour/sources.py $@

$(COLOUR_MODEL) $(COLOUR)/study.json $(COLOUR_TABLES) &: \
        $(COLOUR)/sources.json tools/colour/design.py \
        tools/colour/patterns.py tools/pal.py
	$(PYTHON) -I tools/colour/design.py $< $(COLOUR)

$(COLOUR)/study.md: tools/colour/report.py $(COLOUR)/sources.json \
                    $(COLOUR)/study.json $(COLOUR_MODEL)
	$(PYTHON) -I $< $(COLOUR)/sources.json $(COLOUR)/study.json $@

# Each table's swatches: an image an area, and the sheet of them all.
$(COLOUR)/swatches/%/sheet.png: $(COLOUR)/bbc-%.json $(COLOUR)/sources.json \
                                tools/colour/swatches.py \
                                tools/colour/patterns.py tools/pal.py
	$(PYTHON) -I tools/colour/swatches.py $(COLOUR)/sources.json $< $(@D)

colour-check: $(COLOUR_MODEL) tools/colour/check.py tools/model/colours.py \
              tools/colour/design.py tools/colour/patterns.py
	$(PYTHON) -I tools/colour/check.py $(COLOUR)/sources.json $(COLOUR)
