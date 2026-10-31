# Track H: the object pipeline in 6502 (docs/engine.md stages 1-7,
# docs/research/objects.md).
#
#   make objects   the area records (tools/mkareas.py, into build/gen/),
#                  the check build (build/objects/), and the check: every
#                  entrance view and the extra cameras through the 6502,
#                  headless, each stage's output against the model's
#                  exactly, with each stage's cycles (tools/objectcheck.mjs,
#                  on tools/objectcases.py's cases); one of make check's
#
# The check build puts the code, the tables and the working memory in main
# RAM and the records in sideways RAM banks, as the engine's build will
# place the same sections where its memory map says.

AREAS_GEN   = build/gen/areas.6502
AREAS_JSON  = build/gen/areas.json
OBJ_DIR     = build/objects
OBJ_SRC     = src/defs.6502 src/area.6502 src/matrix.6502 src/objects.6502 \
              src/order.6502 src/transform.6502 src/clip.6502
OBJ_MODEL   = $(wildcard tools/model/*.py tools/model/standin/*.py)
OBJ_CASES   = $(OBJ_DIR)/cases.json

ALL    += $(OBJ_DIR)/OCODE $(OBJ_CASES)
CHECKS += objects

.PHONY: objects
objects: $(OBJ_DIR)/OCODE $(OBJ_CASES)
	node tools/objectcheck.mjs $(OBJ_DIR)

# The faces' colours are the model's (render.recolour), from make colours.
$(AREAS_GEN) $(AREAS_JSON) &: tools/mkareas.py $(DATA_JSON) $(OBJ_MODEL) $(COLOUR_MODEL) src/defs.6502
	@mkdir -p $(@D)
	$(PYTHON) -I tools/mkareas.py $(DATA_JSON) $(AREAS_GEN) $(AREAS_JSON)

define OBJECTS_CHECK_6502
\ The object pipeline's check build (mk/objects.mk, tools/objectcheck.mjs).
\ The code, the records' working copy and the work in main RAM; the maths'
\ tables, the transform's cache and the output in HAZEL, which the check's
\ entries page in.
INCLUDE "../../src/defs.6502"
INCLUDE "../maths/consts.6502"
ZA_POOL &10..&8F

SECTION ObjCode, org = &0E00, guard = &4F00, filename = "OCODE", cmos = TRUE
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
ENDSECTION
\ area_enter pages the records' banks, so its code is never in one.
SECTION AreaCode, org = &4F00, guard = &5000, filename = "OAREA", cmos = TRUE
ENDSECTION
SECTION ObjConst, org = &5000, guard = &5C00, filename = "OCONST"
ENDSECTION
SECTION ObjArea, org = &5C00, guard = &6600, virtual = TRUE
ENDSECTION
SECTION ObjWork, org = &6600, guard = &7400, virtual = TRUE
ENDSECTION
SECTION ObjMaths, org = &C000, guard = &D300, filename = "OMATHS"
INCLUDE "../maths/tables.6502"
ENDSECTION
SECTION ObjCache, org = &D300, guard = &DC00, virtual = TRUE
ENDSECTION
SECTION ObjOut, org = &7400, guard = &7C00, virtual = TRUE
ENDSECTION

INCLUDE "../gen/areas.6502"
INCLUDE "../../src/area.6502"
INCLUDE "../../src/matrix.6502"
INCLUDE "../../src/transform.6502"
INCLUDE "../../src/objects.6502"
INCLUDE "../../src/clip.6502"
INCLUDE "../../src/order.6502"
endef
export OBJECTS_CHECK_6502

$(OBJ_DIR)/check.6502: mk/objects.mk
	@mkdir -p $(@D)
	printf '%s\n' "$$OBJECTS_CHECK_6502" > $@

$(OBJ_DIR)/OCODE $(OBJ_DIR)/OAREA $(OBJ_DIR)/symbols.json &: $(OBJ_DIR)/check.6502 $(OBJ_SRC) $(AREAS_GEN) \
                                             src/maths.6502 src/project.6502 $(MATHS_GEN)
	$(ASM) --warn 2 -p $(OBJ_DIR) --symbols $(OBJ_DIR)/symbols.json $<

$(OBJ_CASES): tools/objectcases.py $(AREAS_JSON) $(DATA_JSON) $(OBJ_MODEL) $(COLOUR_MODEL)
	$(PYTHON) -I tools/objectcases.py $(DATA_JSON) $(AREAS_JSON) $@

# make objects-nocache: the same check with the transform's cache off (every
# object's corner and edges made afresh every frame), to measure what the
# cache saves on the entrance views (each a turn) and their walks (each a
# step). Not one of make check's.
OBJ_NC_DIR = build/objects-nocache

.PHONY: objects-nocache
objects-nocache: $(OBJ_NC_DIR)/OCODE $(OBJ_CASES)
	cp $(OBJ_CASES) $(OBJ_NC_DIR)/cases.json
	node tools/objectcheck.mjs $(OBJ_NC_DIR) --entrance

$(OBJ_NC_DIR)/OCODE &: $(OBJ_DIR)/check.6502 $(OBJ_SRC) $(AREAS_GEN) src/maths.6502 src/project.6502 $(MATHS_GEN)
	@mkdir -p $(@D)
	cp $(OBJ_DIR)/check.6502 $(OBJ_NC_DIR)/check.6502
	$(ASM) --warn 2 -D OBJ_NOCACHE=TRUE -p $(OBJ_NC_DIR) --symbols $(OBJ_NC_DIR)/symbols.json $(OBJ_NC_DIR)/check.6502
