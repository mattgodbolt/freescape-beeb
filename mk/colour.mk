# The colour study (decision 8; docs/research/colour.md).
#
#   make colours        build/colour/: each version's colours, the BBC's
#                       patterns (bbc.json, which tools/model/colours.py
#                       reads), the study's figures (study.md) and the
#                       swatches, on an RGB monitor and through PAL
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
# Swatches: a version and the display its patterns were chosen for.
COLOUR_SWATCHES = st-both st-pal st-rgb dos-both cpc-both
COLOUR_TABLES   = $(foreach v,$(COLOUR_VERS),$(foreach d,$(COLOUR_FOR),\
                    $(COLOUR)/bbc-$(v)-$(d).json))

.PHONY: colours colour-check
colours: $(COLOUR)/bbc.json $(COLOUR)/study.md \
         $(foreach s,$(COLOUR_SWATCHES),$(COLOUR)/swatches/$(s)/sheet.png)
ALL    += colours
CHECKS += colour-check

$(COLOUR)/sources.json: tools/colour/sources.py tools/colour/database.py \
                        tools/colour/images.py tools/research/tap.py \
                        $(COLOUR_ORIG)
	mkdir -p $(COLOUR)
	$(PYTHON) -I tools/colour/sources.py $@

$(COLOUR)/bbc.json $(COLOUR)/study.json $(COLOUR_TABLES) &: \
        $(COLOUR)/sources.json tools/colour/design.py \
        tools/colour/patterns.py tools/pal.py
	$(PYTHON) -I tools/colour/design.py $< $(COLOUR)

$(COLOUR)/study.md: tools/colour/report.py $(COLOUR)/sources.json \
                    $(COLOUR)/study.json
	$(PYTHON) -I $< $(COLOUR)/sources.json $(COLOUR)/study.json $@

# Each table's swatches: an image an area, and the sheet of them all.
$(COLOUR)/swatches/%/sheet.png: $(COLOUR)/bbc-%.json $(COLOUR)/sources.json \
                                tools/colour/swatches.py \
                                tools/colour/patterns.py tools/pal.py
	$(PYTHON) -I tools/colour/swatches.py $(COLOUR)/sources.json $< $(@D)

colour-check: $(COLOUR)/bbc.json tools/colour/check.py tools/model/colours.py
	$(PYTHON) -I tools/colour/check.py $(COLOUR)/sources.json $(COLOUR)/bbc.json
