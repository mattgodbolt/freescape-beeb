# Track A: the screen, the frame loop and the BBC-side harness
# (docs/engine.md, section 1).
#
#   make build/freescape.ssd   the disc: !BOOT runs FS (src/main.6502),
#                 which flips as the beam leaves the view
#   make build/freescape-vsync.ssd   the same, flipping at the vertical
#                 sync (-D VSYNC_FLIP=TRUE)
#   make run      boot the disc in jsbeeb, screenshot to shots/run.png
#   make frames   both discs' frame loops checked on jsbeeb's full video,
#                 and their pace (tools/frames.mjs); one of make check's

FS_DISC    = build/freescape.ssd
FS_SYMBOLS = build/freescape.json
FS_VSYNC   = build/freescape-vsync.ssd
FS_VSYNC_SYMBOLS = build/freescape-vsync.json
FS_SOURCES = src/main.6502 src/defs.6502 src/zp.6502 src/macros.6502 \
             src/screen.6502 src/irq.6502 src/input.6502

# Stamped into !BOOT, so a disc says what it is: UTC build time and the
# commit, with + if the tree had changes.
FS_BUILD := $(shell date -u '+%Y-%m-%d %H:%M UTC') $(shell git rev-parse --short HEAD 2>/dev/null || echo NOGIT)$(shell git diff --quiet HEAD -- . 2>/dev/null || echo +)

ALL    += $(FS_DISC) $(FS_VSYNC)
CHECKS += frames

$(FS_DISC) $(FS_SYMBOLS) &: $(FS_SOURCES) | build
	$(ASM) -D 'BUILD="$(FS_BUILD)"' -o $(FS_DISC) --title FREESCAPE --opt 3 --warn 2 \
	    --symbols $(FS_SYMBOLS) src/main.6502

$(FS_VSYNC) $(FS_VSYNC_SYMBOLS) &: $(FS_SOURCES) | build
	$(ASM) -D 'BUILD="$(FS_BUILD) VSYNC"' -D VSYNC_FLIP=TRUE -o $(FS_VSYNC) --title FREESCAPE --opt 3 \
	    --warn 2 --symbols $(FS_VSYNC_SYMBOLS) src/main.6502

.PHONY: run frames
run: $(FS_DISC)
	node tools/play.mjs 'f25,!run' shots/ --disc $(FS_DISC) --until main_loop

frames: $(FS_DISC) $(FS_VSYNC)
	node tools/frames.mjs --disc $(FS_DISC)
	node tools/frames.mjs --disc $(FS_VSYNC)
