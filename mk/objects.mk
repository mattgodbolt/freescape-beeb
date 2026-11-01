# Track H: the object pipeline in 6502 (docs/engine.md stages 1-7,
# docs/research/objects.md).
#
#   make objects   the working copy's model (tools/mkareas.py, into
#                  build/gen/), the check build (build/objects/), and the
#                  checks: every area's working copy and the globals', as
#                  area_init and area_enter build them from Driller's
#                  database in the logic's bank (build/logic6502's LOGIC),
#                  against mkareas.py's, byte for byte, with their cycles
#                  (tools/areacheck.mjs); then every entrance view and the
#                  extra cameras through the 6502, headless, each stage's
#                  output against the model's exactly, with each stage's
#                  cycles (tools/objectcheck.mjs, on tools/objectcases.py's
#                  cases); and both again on the build that takes what's
#                  hidden from the logic's flags (OBJ_LOGIC,
#                  build/objects-logic/), the views there the entrances and
#                  their walks; one of make check's
#
# The check build puts the code, the tables and the working memory in main
# RAM and HAZEL, the logic's database bank and the conversion's in sideways
# RAM, as the engine's build places the same sections where its memory map
# says.

AREAS_GEN   = build/gen/areas.6502
AREAS_JSON  = build/gen/areas.json
OBJ_DIR     = build/objects
OBJ_LOGIC_DIR = build/objects-logic
OBJ_DB      = $(L6_DIR)/LOGIC
OBJ_SRC     = src/defs.6502 src/area.6502 src/matrix.6502 src/objects.6502 \
              src/order.6502 src/transform.6502 src/clip.6502
OBJ_MODEL   = $(wildcard tools/model/*.py tools/model/standin/*.py)
OBJ_CASES   = $(OBJ_DIR)/cases.json

ALL    += $(OBJ_DIR)/OCODE $(OBJ_LOGIC_DIR)/OCODE $(OBJ_CASES)
CHECKS += objects

.PHONY: objects
objects: $(OBJ_DIR)/OCODE $(OBJ_LOGIC_DIR)/OCODE $(OBJ_CASES) $(OBJ_DB) $(AREAS_JSON)
	node tools/areacheck.mjs $(OBJ_DIR) --areas $(AREAS_JSON) --db $(OBJ_DB)
	node tools/areacheck.mjs $(OBJ_LOGIC_DIR) --areas $(AREAS_JSON) --db $(OBJ_DB)
	node tools/objectcheck.mjs $(OBJ_DIR) --db $(OBJ_DB)
	node tools/objectcheck.mjs $(OBJ_LOGIC_DIR) --db $(OBJ_DB) --cases $(OBJ_CASES) \
	    --areas $(AREAS_JSON) --entrance

# The faces' colours are the model's (render.recolour), from make colours;
# the globals' records are the tape's.
$(AREAS_GEN) $(AREAS_JSON) &: tools/mkareas.py tools/freescape.py $(DATA_JSON) $(DATA_TAPE) \
                              $(OBJ_MODEL) $(COLOUR_MODEL) src/defs.6502
	@mkdir -p $(@D)
	$(PYTHON) -I tools/mkareas.py $(DATA_JSON) $(DATA_TAPE) $(AREAS_GEN) $(AREAS_JSON)

define OBJECTS_CHECK_6502
\ The object pipeline's check build (mk/objects.mk, tools/objectcheck.mjs,
\ tools/areacheck.mjs). The code, the working copy and the work in main
\ RAM, the output in the OS's pages (nothing of the OS runs once the
\ harness's stub has turned interrupts off); the maths' tables, the
\ transform's cache and f64 table in HAZEL, which the check's entries page
\ in; the logic's database bank (the harness loads build/logic6502's LOGIC)
\ and the conversion's in sideways RAM. ObjCode holds the maths' code (the
\ harness lets the pipeline write only its own sections) as well as what
\ the live disc puts in its bank, so it has room for both to be full
\ (src/defs.6502's OBJ_CODE_ORG to &C000, ASSERTed below), and ObjMore for
\ the live disc's less the maths'.
INCLUDE "../../src/defs.6502"
INCLUDE "../maths/consts.6502"
ZA_POOL &10..&8F
AREA_DB_BANK   = 4              ; src/logic/vars.6502's LOGIC_BANK (tools/areacheck.mjs checks)
AREA_CONV_BANK = 5

SECTION ObjCode, org = &0E00, guard = CHECK_CODE_GUARD, filename = "OCODE", cmos = TRUE
INCLUDE "../../src/maths.6502"
INCLUDE "../../src/project.6502"
\ The check's entry points, each called from the harness's stub.
MACRO HAZEL_IN
    LDA acccon : PHA
    ORA #ACCCON_Y : STA acccon
ENDMACRO
MACRO HAZEL_OUT
    PLA : STA acccon
ENDMACRO
.check_init
    ZA_ENTRY
    JMP area_init
.check_enter
    ZA_ENTRY
    LDA check_area
    JMP area_enter
.check_matrix
    ZA_ENTRY
    JMP matrix_build
.check_pass
    ZA_ENTRY
    HAZEL_IN
    JSR matrix_update
    JSR transform_setup
    JSR camera_setup
    JSR object_pass
    HAZEL_OUT
    RTS
.check_frame
    ZA_ENTRY
    HAZEL_IN
    JSR objects_frame
    HAZEL_OUT
    RTS
\ check_cut: the 2D clip's crossing (clip_cut) from fp, fq, po and qo at
\ cut_args (the harness's), r after them.
.check_cut
    ZA_ENTRY
    HAZEL_IN
    LDA cut_args : STA clip_cut.fp
    LDA cut_args+1 : STA clip_cut.fp+1
    LDA cut_args+2 : STA clip_cut.fq
    LDA cut_args+3 : STA clip_cut.fq+1
    LDA cut_args+4 : STA clip_cut.po
    LDA cut_args+5 : STA clip_cut.po+1
    LDA cut_args+6 : STA clip_cut.qo
    LDA cut_args+7 : STA clip_cut.qo+1
    JSR clip_cut
    LDA clip_cut.r : STA cut_args+8
    LDA clip_cut.r+1 : STA cut_args+9
    HAZEL_OUT
    RTS
.cut_args
    SKIP 10
\ check_shared: never called by the check; it reaches the projection's
\ shared-coordinate entries, as a caller would, after project.
.check_shared
    ZA_ENTRY
    HAZEL_IN
    JSR shared_in : JSR project
    JSR shared_in : JSR project_z
    JSR shared_in : JSR project_y
    HAZEL_OUT
    RTS
.shared_in
    ZA_DISCARD proj_v
    STZ proj_v : STZ proj_v+1 : STZ proj_v+2 : STZ proj_v+3 : STZ proj_v+4
    STZ proj_v+5 : STZ proj_v+6 : STZ proj_v+7 : STZ proj_v+8
    RTS
.check_area
    EQUB 0
.check_entries_end
ENDSECTION
\ (the rest of ObjCode, the pipeline's, as much as the live disc's bank holds)
CHECK_CODE_GUARD = &5900
ASSERT CHECK_CODE_GUARD - check_entries_end >= &C000 - OBJ_CODE_ORG
\ area_init and area_enter page the banks, so their code is never in one.
SECTION AreaCode, org = CHECK_CODE_GUARD, guard = &5980, filename = "OAREA", cmos = TRUE
ENDSECTION
\ (the OS's pages above ObjOut: nothing of the OS runs while the check calls)
SECTION ObjConst, org = &0A00, guard = &0E00, filename = "OCONST"
ENDSECTION
SECTION ObjArea, org = &5980, guard = &6600, virtual = TRUE
ENDSECTION
SECTION ObjWork, org = &6600, guard = &7000, virtual = TRUE
ENDSECTION
SECTION ObjMaths, org = &C000, guard = &D300, filename = "OMATHS"
INCLUDE "../maths/tables.6502"
ENDSECTION
SECTION ObjCache, org = &D300, guard = &DC00, virtual = TRUE
ENDSECTION
SECTION ObjTables, org = &DC00, guard = &E000, filename = "OTABLES"
ENDSECTION
SECTION ObjOut, org = &0400, guard = &0A00, virtual = TRUE
ENDSECTION
SECTION ObjMemo, org = &7000, guard = &7680, virtual = TRUE
ENDSECTION
\ ObjMore: the pipeline's code outside its bank (the live disc's main RAM).
SECTION ObjMore, org = &7680, guard = &8000, filename = "OMORE", cmos = TRUE
ENDSECTION
SECTION AreaConv, org = &8000, guard = &C000, filename = "ACONV", cmos = TRUE
ENDSECTION

INCLUDE "../gen/areas.6502"
INCLUDE "../../src/area.6502"
INCLUDE "../../src/matrix.6502"
INCLUDE "../../src/transform.6502"
INCLUDE "../../src/objects.6502"
INCLUDE "../../src/clip.6502"
INCLUDE "../../src/order.6502"
IF DEFINED(OBJ_LOGIC)
\ The logic's flags for the objects of its index, as logic_go_shown leaves
\ them (src/logic/vars.6502's): tools/objectcheck.mjs writes them.
SECTION ObjWork
.ix_flags   SKIP IX_MOST
ENDSECTION
ENDIF
ASSERT LO(fq0) = 0
endef
export OBJECTS_CHECK_6502

$(OBJ_DIR)/check.6502: mk/objects.mk
	@mkdir -p $(@D)
	printf '%s\n' "$$OBJECTS_CHECK_6502" > $@

$(OBJ_DIR)/OCODE $(OBJ_DIR)/OAREA $(OBJ_DIR)/symbols.json &: $(OBJ_DIR)/check.6502 $(OBJ_SRC) $(AREAS_GEN) \
                                             src/maths.6502 src/project.6502 $(MATHS_GEN)
	$(ASM) --warn 2 -p $(OBJ_DIR) --symbols $(OBJ_DIR)/symbols.json $<

# The same, with what's hidden from the logic's flags (src/area.6502's
# OBJ_LOGIC).
$(OBJ_LOGIC_DIR)/OCODE &: $(OBJ_DIR)/check.6502 $(OBJ_SRC) $(AREAS_GEN) src/maths.6502 src/project.6502 $(MATHS_GEN)
	@mkdir -p $(@D)
	cp $(OBJ_DIR)/check.6502 $(OBJ_LOGIC_DIR)/check.6502
	$(ASM) --warn 2 -D OBJ_LOGIC=TRUE -p $(OBJ_LOGIC_DIR) --symbols $(OBJ_LOGIC_DIR)/symbols.json \
	    $(OBJ_LOGIC_DIR)/check.6502

$(OBJ_CASES): tools/objectcases.py $(AREAS_JSON) $(DATA_JSON) $(OBJ_MODEL) $(COLOUR_MODEL)
	$(PYTHON) -I tools/objectcases.py $(DATA_JSON) $(AREAS_JSON) $@

# make objects-nocache: the same check with the transform's cache off (every
# object's corner and edges made afresh every frame), to measure what the
# cache saves on the entrance views (each a turn) and their walks (each a
# step). Not one of make check's.
OBJ_NC_DIR = build/objects-nocache

.PHONY: objects-nocache
objects-nocache: $(OBJ_NC_DIR)/OCODE $(OBJ_CASES) $(OBJ_DB)
	node tools/objectcheck.mjs $(OBJ_NC_DIR) --db $(OBJ_DB) --cases $(OBJ_CASES) --entrance

$(OBJ_NC_DIR)/OCODE &: $(OBJ_DIR)/check.6502 $(OBJ_SRC) $(AREAS_GEN) src/maths.6502 src/project.6502 $(MATHS_GEN)
	@mkdir -p $(@D)
	cp $(OBJ_DIR)/check.6502 $(OBJ_NC_DIR)/check.6502
	$(ASM) --warn 2 -D OBJ_NOCACHE=TRUE -p $(OBJ_NC_DIR) --symbols $(OBJ_NC_DIR)/symbols.json $(OBJ_NC_DIR)/check.6502
