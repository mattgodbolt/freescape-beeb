# Track X: Driller's panel below the view (src/panel.6502,
# docs/research/panel.md).
#
#   make panel-data  build/panel/: the panel's picture and tables
#                    (tools/mkpanel.py, from the ST's console and the ZX's
#                    data; tools/model/panel.py is the specification), with
#                    previews: picture.png, sample.png and sample4x.png
#   make panel-shots the live disc's panel in play, on an RGB monitor and
#                    through PAL (tools/pal.py): shots/panel_*.png
#
# The live discs' check (make live, tools/livecheck.mjs) holds the panel on
# the screen to the model after every pass.
#
# Everything here derives from the originals (decision 6): built, never
# committed.

PANEL_DIR  = build/panel
PANEL_GEN  = $(PANEL_DIR)/panel.6502 $(PANEL_DIR)/panel.json
# (mk/objects.mk's and mk/zx.mk's, read before or after this file)
AREAS_JSON ?= build/gen/areas.json
ZXSNAP     ?= build/zx/driller.z80

.PHONY: panel-data panel-shots
panel-data: $(PANEL_GEN)

$(PANEL_GEN) &: tools/mkpanel.py tools/model/panel.py tools/model/view.py tools/model/colours.py \
                src/defs.6502 tools/colour/sources.py tools/colour/images.py \
                tools/colour/database.py tools/colour/patterns.py tools/pal.py \
                tools/research/tap.py tools/logic/oracle.py originals/st/Driller.st \
                $(ZXSNAP) $(AREAS_JSON) $(DATA_JSON)
	$(PYTHON) -I tools/mkpanel.py $(PANEL_DIR) $(ZXSNAP) $(AREAS_JSON) $(DATA_JSON)
