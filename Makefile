# FREESCAPE for the BBC Master
#
#   make venv     the Python tools' environment (.venv, by uv: SkoolKit,
#                 Pillow, NumPy, py65)
#   make fetch    the originals into originals/ (never committed)
#   make          everything the tracks build ($(ALL))
#   make check    every track's checks ($(CHECKS)); read its exit status,
#                 never pipe it into tail
#   make clean    remove build/
#
# Each track adds its own rules, and appends to ALL and CHECKS, in its own
# mk/*.mk, so that tracks working at once don't share a file.

# local.mk (not committed) can set BARON.
-include local.mk
BARON   ?= $(firstword $(wildcard ../baron/build/src/baron) baron)
# Baron, failing on a warning too.
ASM      = BARON=$(BARON) tools/asm.sh
PYTHON  ?= .venv/bin/python

# A failed step leaves no half-made target behind.
.DELETE_ON_ERROR:

ALL    :=
CHECKS :=

.PHONY: all check venv fetch clean
all:

include $(sort $(wildcard mk/*.mk))

all: $(ALL)
check: $(CHECKS)

venv:
	uv sync

fetch:
	tools/fetch.sh

clean:
	rm -rf build

build:
	mkdir -p build
