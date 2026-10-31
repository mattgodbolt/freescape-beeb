# Track D: the ZX oracle (docs/research/zx-driller.md).
#
#   make zx        Driller loaded and booted to the main loop, in play at
#                  the start (build/zx/driller.z80)
#   make zxdisasm  the annotated listing (build/zx/driller.skool), from
#                  disasm/*.ctl
#   make zxcheck   the original's arithmetic against tools/zx_arith.py's
#                  transcription
#
# Everything here reads Driller from originals/ and writes to build/zx/:
# nothing of the original is committed (decision 6).

ZXTAPE = originals/zx/Driller.tzx
ZXSNAP = build/zx/driller.z80

.PHONY: zx zxdisasm zxcheck
ALL    += $(ZXSNAP)
CHECKS += zxcheck

zx: $(ZXSNAP)
zxdisasm: build/zx/driller.skool

# The tape as a 48K loads it, the turbo loader simulated (SkoolKit's
# tap2sna.py), stopped where the tape ends.
build/zx/loaded.z80: $(ZXTAPE)
	@mkdir -p $(@D)
	$(PYTHON) -I .venv/bin/tap2sna.py -c machine=48 $< $@ > /dev/null

# Past the protection and the control menu to the main loop's top.
$(ZXSNAP): build/zx/loaded.z80 tools/zx.py
	$(PYTHON) -I tools/zx.py '>driller' build/zx/ --snap $< --boot > /dev/null

build/zx/driller.skool: $(ZXSNAP) $(wildcard disasm/*.ctl)
	rm -rf build/zx/ctl && mkdir -p build/zx/ctl
	cp disasm/*.ctl build/zx/ctl/
	$(PYTHON) -I .venv/bin/sna2skool.py -H -c build/zx/ctl $< > $@

zxcheck: $(ZXSNAP)
	$(PYTHON) -I tools/zx_arith.py --snap $(ZXSNAP)
