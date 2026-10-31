; SkoolKit control file: Driller (ZX Spectrum, Incentive 1987, 48K retail
; tape), the redraw and the camera. See docs/research/zx-driller.md.
; Addresses are the original's, in hex. Names follow Castle Master II's
; annotated listing where the code is the same.
;
;   make zxdisasm    (build/zx/driller.skool, from build/zx/driller.z80)

; ----------------------------------------------------------------------------
; The camera
; ----------------------------------------------------------------------------

@ $8762 label=PlayerX
g $8762 The camera's position: x, y, z, 16-bit world units (64 to a cell)
D $8762 Y is up. An entrance sets them at #R$9D1C: the cell's centre in x and z, and the eye at 64*(ey+h-1)+32 on the probe, h = #R$8776.
W $8762,6,2
@ $8768 label=StepUnits
g $8768 The step in world units: #R$876A times the area's scale
W $8768,2
@ $876A label=Step
g $876A The step (1-250, from #R$88BE) and its index
B $876A,2,1
@ $876C label=Pitch
g $876C Pitch, yaw and roll, 5-degree units (0-71)
D $876C Positive pitch looks down; yaw 0 looks along +z, yaw 18 along +x.
B $876C,3,1
@ $876F label=Turn
g $876F The turn (5-degree units, from #R$88C9) and its index
B $876F,2,1
@ $8771 label=ExtensionMax
g $8771 The probe's vertical extension: the most levels, the level (1-4), and two more per-area values
D $8771 The panel shows the level less one. The area load (#R$BE18) multiplies each by the area's scale into #R$8775-#R$8778.
B $8771,4,1
@ $8775 label=ExtensionScaled
g $8775 The extension values times the area's scale; #R$8776 is the eye's height in cells, plus the floor's
B $8775,4,1
@ $8779 label=AreaScale
g $8779 The current area's scale (its header byte 5)
B $8779,1,1
@ $877A label=InJet
g $877A Non-zero in the jet
B $877A,1,1

; ----------------------------------------------------------------------------
; The view
; ----------------------------------------------------------------------------

@ $5CBC label=RenderBuffer
b $5CBC The view buffer: 26 bytes (208 pixels, bit 7 left) by 105 rows, top first
D $5CBC Projected y counts up from the bottom: the fill draws y into row 104-y. Rows 0-103 are copied to the screen (#R$9BF7); row 104 is drawn but never shown.
D $5CBC As in Castle Master II, the projection's scratch lives inside the buffer, which the draw overwrites afterwards: #R$6E25 compiles the transform's multiplies at its start, and the matrix and vertex lists are at #R$5E4C-#R$5F4C.
B $5CBC,400,26
@ $5E4C label=TempMatrix
N $5E4C One rotation (or the scaling diagonal), multiplied into #R$5E55 by #R$7896.
B $5E4C,9,3
@ $5E55 label=Matrix
N $5E55 The camera matrix: nine signed bytes, row-major, 1.0 = 64; rows are camera x, y, z.
B $5E55,9,3
@ $5E5E label=VertexFlags
B $5E5E,5,1
@ $5E63 label=VertsRelative
N $5E63 Vertices relative to the camera, 6 bytes each (x, y, z words).
B $5E63,60,6
@ $5E9F label=VertsCamera
N $5E9F Vertices in camera space, 6 bytes each (x, y, z words).
B $5E9F,60,6
B $5EDB,2187,26
@ $80B2 label=EndMasks
b $80B2 Pixel masks for the fill: the left n pixels of a byte (n = 1-7), then one pixel (bits 6-0)
B $80B2,14,7
@ $91EF label=DivSign
g $91EF The divide's sign and bit count (#R$91F1)
B $91EF,2,1
@ $CAA6 label=ProtectionState
b $CAA6 The protection's state, its input and its screen's text
@ $6EDB label=Identity
b $6EDB The identity matrix, 1.0 = 64
B $6EDB,9,3
@ $8862 label=AreaId
g $8862 The current area's id
B $8862,1,1
@ $8863 label=AreaObjects
g $8863 The current area's object count and object list
B $8863,1,1
W $8864,2
@ $88BE label=StepTable
b $88BE Step sizes: a count, then the steps in world units (times the area's scale)
B $88BE,9,9
@ $88C9 label=TurnTable
b $88C9 Turns: a count, then the turns in 5-degree units
B $88C9,7,7
@ $88D2 label=Scaling
b $88D2 The scaling diagonal (x, y, z), folded into the matrix last
B $88D2,3,3
@ $88D9 label=ViewCentre
b $88D9 The projection's centre (x, y): half the view's width and height
B $88D9,2,2
@ $88DB label=BufferRows
g $88DB The buffer's rows and bytes a row
W $88DB,4,2
@ $88E5 label=CullBounds
g $88E5 The coarse cull's box, in cells: x max, x min, y max, y min, z max, z min
B $88E5,6,2
@ $8920 label=GameFlags
g $8920 Flags: bit 2 of the first byte, re-project (moved or turned); bit 3 of the second, redraw
B $8920,2,1
@ $8918 label=NDrawn
g $8918 The objects in the draw list
B $8918,1,1
@ $8919 label=ScanTop
g $8919 The face being filled: its top and bottom rows (screen y, up)
W $8919,4,2
@ $8A83 label=MultiplyCode
g $8A83 Addresses of the nine compiled multiplies (#R$6E25), row-major
W $8A83,18,2
@ $8E78 label=SinCos
b $8E78 Sine and cosine, 72 pairs (sin, cos), signed bytes, 1.0 = 64
B $8E78,144,2

; ----------------------------------------------------------------------------
; The redraw
; ----------------------------------------------------------------------------

@ $6B12 label=Redraw
c $6B12 Redraw the view into #R$5CBC
D $6B12 Castle Master II's L83aa_redraw_whole_screen. Re-projects and sorts only if #R$8920 bit 2 is set; otherwise draws the last projection if the second flag byte's bit 3 is. The tape has JR $ here (an endless loop) until the protection (#R$CB7A) is passed, which makes it PUSH IX.
  $6B12 PUSH IX, once the protection is passed.
  $6B2A The coarse cull's box, the matrix and the compiled multiplies.
  $6B33 No objects to draw yet.
  $6B3D The area's objects, then the globals (the rig and the skanner).
  $6B5C Sort the objects to draw.
  $6B72 Draw them.
  $6B75 The redraw's end.
@ $6B7C label=ProjectObjects
c $6B7C Project A objects from IX, adding the drawable ones to the list at #R$8A26
D $6B7C Skips type 0 (entrances), invisible objects (bit 6) and objects outside the coarse cull's box (#R$88E5). Makes the box relative to the camera in world units, with the six which-side bits, then dispatches on the type.
@ $6C53 label=CullBox
c $6C53 The coarse cull's box, in cells, from the yaw and pitch quadrants and the camera's cell
@ $6E25 label=CompileMultiplies
c $6E25 Compile a shift-and-add multiply by each of the matrix's nine coefficients
D $6E25 Into ($8A97), the render buffer, with their addresses at #R$8A83. A zero coefficient's entry jumps straight to #R$7981 (no product). Each routine forms |m|*|d| in A,HL and ends at #R$795E.
@ $6EE4 label=BuildMatrix
c $6EE4 The camera matrix: S.Rroll.Rpitch.Ryaw, from the identity
D $6EE4 Each rotation (skipped when its angle is 0) goes into #R$5E4C and is multiplied in on the left by #R$7896, then the scaling diagonal #R$88D2.
@ $6FC2 label=ProjectCuboid
c $6FC2 Project a cuboid: its eight corners from the box relative to the camera
@ $70B7 label=ProjectPyramid
c $70B7 Project a pyramid (types 4-9)
@ $742B label=ProjectPolygon
c $742B Project a line or polygon (types 10-14)
@ $74B7 label=ProjectRectangle
c $74B7 Project a rectangle (type 3)
@ $7592 label=ProjectSensor
c $7592 Project a sensor (type 2)
@ $767E label=SortObjects
c $767E Sort the objects to draw (Castle Master II's L9c2d)
@ $7803 label=DrawObjects
c $7803 Draw the sorted objects into the buffer
@ $7896 label=MatrixMultiply
c $7896 #R$5E55 = #R$5E4C . #R$5E55, each sum rounded (v+32)>>6 to a byte
@ $7915 label=Transform
c $7915 Transform #R$8A7F vertices from #R$5E63 to #R$5E9F through the compiled multiplies
D $7915 Each product is the magnitude |m|*|d|>>6 with the sign applied after; each row's sum is 16-bit.
@ $795E label=ProductDone
@ $7981 label=ProductNext
@ $799E label=ClipEdge
c $799E Clip an edge against frustum plane (#R$5EDB): move the previous vertex to the crossing
@ $7C37 label=PlaneSide
c $7C37 Which side of frustum plane (#R$5EDB) the vertex at IX is: 0 inside, 1 outside, &FF on it
D $7C37 Planes 1-5: x+z, y+z, z-x, z-y, z. There is no near plane but z = 0.
@ $7C9D label=Project
c $7C9D Project #R$8A7F vertices from #R$5E9F to screen bytes at #R$8A6B
D $7C9D x = XC + trunc(XC*x/z), y = YC + trunc(YC*y/z), with (XC, YC) at #R$88D9; clamped to 0 or 2*XC (2*YC) outside the side planes; z = 0 gives the centre.
@ $7D46 label=ClassifyVertices
c $7D46 Transform an object's vertices and classify them against the frustum
@ $7D8C label=ClipFace
c $7D8C Clip a face's vertices against the five frustum planes in turn (#R$7C37, #R$799E)
@ $7EE5 label=Facing
c $7EE5 Which way the first three screen points at HL turn: A=0 anticlockwise (y up), 1 clockwise
@ $80C0 label=FillSpans
c $80C0 Fill a face's spans from the edge table at ($8A9F) with its pattern
D $80C0 From row #R$8919 (the top) down to #R$891B. Each row's span runs from its lower x to its higher x inclusive, at pixel column x-1, in the pattern byte for y AND 3, written opaquely through the masks at #R$80B2; the row's entry is cleared.
@ $81B6 label=ProjectFaces
c $81B6 Project an object's faces whose vertices are all inside the frustum, and add it to the draw list
D $81B6 IY: the face definitions (colour, point count, vertex indices). A face of colour 0 is skipped; #R$5E60 picks the facing rule (0 none, 1 drop clockwise faces, 2 the colour by the facing).
@ $828D label=ProjectFacesClipped
c $828D Project an object's faces, clipping each, and add it to the draw list
D $828D Marks a four-point face on the view's four corners as covering the whole view (#R$8A6A, and bit 7 of the object's face count).
@ $83FC label=ScanPolygon
c $83FC A face's edges into the edge table: one x a row for rows [y low, y high) of each edge
D $83FC Bresenham from each edge's lower end; a row keeps its first two distinct x values; a horizontal edge counts only on the top or bottom row and overwrites it. #R$8919 and #R$891B get the top and bottom rows.
@ $85FF label=ScanLine
c $85FF A two-point face (a line) into the edge table
@ $910E label=MulA_HL
c $910E A,HL = A * HL, signed, exact
@ $91F1 label=DivA_HL_DE
c $91F1 A,HL = A,HL / DE, signed, on the magnitudes (truncated toward zero); DE the remainder
@ $928C label=MulH_L
c $928C HL = H * L, signed bytes
@ $92D7 label=Div32
c $92D7 DE,HL = DE,HL / BC, signed, rounded on the magnitude
@ $9179 label=MulHL_DE
c $9179 DE,HL = HL * DE, signed

; ----------------------------------------------------------------------------
; Start-up and the main loop
; ----------------------------------------------------------------------------

@ $97A4 label=Start
c $97A4 The game's start: the loader jumps here
@ $9807 label=MainRedraw
@ $9825 label=MainLoop
c $9825 The main loop's top: input (#R$9990), events (#R$9B6E), then the redraw
D $9825 A pass: the input waits for keys or a minute of the clock and does each key's action; the events run the collided object's FCL and the conditions; then (at #R$9807) the redraw, the copy and the sensors (#R$9841) if something moved or changed, and the panel (#R$B72B). See docs/research/zx-logic.md.
  $9825 The input: the keys' actions.
  $9828 The events.
  $982B GameFlags bit 1: the game has ended; start again.
@ $9BF7 label=CopyBuffer
c $9BF7 Copy buffer rows 0-103 to the screen, one LDIR a row
D $9BF7 Then plays the sound left in #R$8A1F, and clears it.
@ $9D1C label=GoToEntrance
c $9D1C Put the camera at entrance #R$8911 of the current area
D $9D1C Loads the area (#R$BE18), then looks the entrance up by id (#R$A8BA: the globals, then the area's objects, any type). The cell's centre in x and z, the eye #R$8776-1 cells above the entrance's cell on the probe (the cell itself in the jet), and the entrance's pitch, yaw and roll. If there's no such object (entrance 0 is none), the camera has crossed the area's edge: x cell 126 becomes 1 and 0 becomes 125, or else z likewise, and nothing else changes.
  $9D3C No entrance: wrap the cell the last move left in #R$88B5 or #R$88B7.
@ $A364 label=MoveStep
c $A364 A step forward (A=3) or back (A=4)
D $A364 x += floor(step*sin(yaw)/64), z += floor(step*cos(yaw)/64), each negated after the floor for a step back. In the jet the step first splits by the pitch: y -= floor(step*sin(pitch)/64), and the horizontal step is floor(step*|cos(pitch)|/64). On the probe the move (#R$9F42) is made from the feet, #R$8776-1 cells below the eye, and the eye put back above wherever the feet end up.
  $A378 The jet: split the step by the pitch.
  $A437 The probe: down to the feet.
  $A452 Move; C bits 2 and 4 if the camera moved.
@ $BE18 label=LoadArea
c $BE18 Enter area #R$8862: its objects, its scale and the per-scale values
D $BE18 Resets the minute counters (#R$889D, #R$88AE), hides three globals, places the rig (#R$CD3B) and scales the step (#R$8768), the probe's height (#R$8776) and its limits (#R$8775-#R$8778) by the area's scale (#R$8779).
@ $CB7A label=Protection
c $CB7A The protection: a word from the manual, chosen by #R$8A1D from the table at #R$ABC1

; ----------------------------------------------------------------------------
; The player logic (docs/research/zx-logic.md; transcribed in tools/logic/)
; ----------------------------------------------------------------------------

; The input.
@ $9990 label=Input
c $9990 A pass's input: clear the pass's flags, wait for keys or a minute, do each key's action
D $9990 Clears #R$8920, #R$8A69, #R$8BF1, #R$8BF0, #R$8A64, #R$8A1F, #R$8A1E. Reads the keys (#R$943C) until one is held; a minute of the clock (#R$889D changed from #R$88AE) ends the pass at once with only the events due. Each key's action comes from the key table (#R$8FC8): the first part's third byte in shooting mode (#R$88AC). Then the actions in the keys' order: 1-$14 move (#R$A279), $15-$1E the crosshair and fire (#R$A95C), $28 and $2A the rigs (#R$BEFA), $29 the information screen (#R$C3DC).
  $99C0 Wait for a key or a minute.
  $99C8 The game is over: its end.
  $99CB A minute has ended: the events only.
  $99E4 Each key's action.
  $9A63 Do each action in turn.
@ $9AB7 label=GameEnd
c $9AB7 The game is over (#R$8BF2): its end, then a new game
@ $943C label=ReadKeys
c $943C Read up to five keys held, in the keyboard's order, as codes into #R$8FBD (#R$8FBC of them)
D $943C The half-rows from $FEFE to $7FFE, bit 0 first, through the code table at #R$9414; then the Kempston joystick if #R$8FC5 is 2. Carry set, A the first code, if any key is held. A set held since the last read is a repeat: it waits #R$8FC3 frames, then #R$8FC4 between repeats (both 0 in play).
@ $9404 label=KeyRows
g $9404 The half-rows as read, CPL AND $1F, less the keys taken
B $9404,8,8
@ $940C label=KeyRepeating
g $940C The held keys were held last time too; the last keys read and their count; the repeat delay copied
B $940C,8,8
@ $9414 label=KeyCodes
b $9414 A code for each key, five a half-row, from $FEFE's
B $9414,40,5
@ $8FBC label=KeyCount
g $8FBC The keys this pass: their count and codes; the interrupt's countdown; the repeat's delay and rate; the controls; the key table's lengths
B $8FBC,12,1
@ $8FC8 label=KeyTable
b $8FC8 Keys to actions: key, action, shooting mode's action ($8FC6 of them); then key, action ($8FC7 of them)
B $8FC8,36,3
B $8FEC,48,2
@ $998A label=Actions
g $998A The actions of this pass's keys, and the one being done
B $998A,6,6
@ $A95C label=CrosshairAction
c $A95C Actions $15-$1E: B ($15) shows or hides the crosshair, SPACE ($1E) toggles shooting mode, $17-$1A move the crosshair, 0 ($16) fires
D $A95C Fire draws the laser, finds the object under the crosshair (#R$B153) and sets #R$8BF1 so the events run its shot script.

; Moving.
@ $A279 label=Movement
c $A279 Actions 1-$14: rise, fall, step, turn, look, roll, turn round, the turn's and the step's sizes
D $A279 1 (R) rises: in the jet a step up; on the probe a level (#R$8779 cells) if the head's cells above are clear, to #R$8771. 2 (F) falls: in the jet a step down; on the probe a level, untested, to 1. 3 and 4 step (#R$A364). 5 and 6 (Q, W) turn by #R$876F, 7 and 8 (P, L) look up and down, 9 and $0A (N, M) roll; all mod 72. $0D (U) turns round, and in the jet turns the pitch round too. $0B and $0C (A, Z) and $11 and $12 (S, X) change the turn's and the step's sizes, then wait 7 frames. Exits at #R$A57C (the events due) or #R$A581, ORing C into #R$8920 and B into #R$8921.
  $A2B0 The probe rises: test the head's way up as the jet would.
  $A332 The probe falls: no test.
  $A46C The turns.
  $A4D6 Turn round.
  $A505 The turn's and the step's sizes.
  $A57C The events are due.
  $A581 The flags.
@ $A57C label=MovementDone
@ $A581 label=MovementFlags
@ $9F42 label=Move
c $9F42 Move the camera toward #R$88AF-#R$88B3, a cell boundary at a time; returns A=1 if it moved
D $9F42 The walk: of the axes with a boundary left to cross, the one crossed first (x, then z, then y, with the other two at its crossing point from #R$9179 and #R$92D7), and with it any axis crossed at the same point. Each crossing stops at the area's extent (#R$88DF), else goes to #R$9DCF. Stopped (1), the target is the crossing point a unit back into this cell; on a step up or a fall (2), the crossing point in x and z and the new y. Then #R$BCCB at each of the body's cells, and the target taken as the camera. With #R$88D0 = 0 (the sensors' test, #R$9841) it only walks.
  $9FCA The next crossing: x first?
  $A07E z first?
  $A107 y.
  $A158 The area's extent.
  $A1A9 Cross.
  $A1D8 Stopped.
  $A1F0 Stepped up or fell.
  $A220 Keep clear of faces, and move.
@ $A220 label=MoveDone
@ $9F33 label=MoveScratch
g $9F33 The move's target cells, its crossing point and its delta
B $9F33,3,3
W $9F36,12,6
@ $88AF label=Target
g $88AF The move's target (x, y, z words), and the walk's current cell (x, y, z)
W $88AF,6,2
B $88B5,3,3
@ $9DCF label=Cross
c $9DCF Cross into the next cell (the bits of A, as C in #R$9F42): 0 crossed, 1 stopped, 2 stepped up or fell
D $9DCF In the jet an object entered (#R$A597) stops it. On the probe, an object entered is climbed if there's a clear column #R$8776 cells high starting at most #R$8778 cells up, the cells above clear too; the target rises that far (sound 4). Across, the probe falls to whatever is below (sound 3), and a fall of more than #R$8777 cells ends the game (#R$8BF2 = 4, the view rolled 90 degrees and levelled). The object entered, and the one landed on, go to #R$8A69.
  $9E0A The step up: count clear cells up the column.
  $9E51 Too high: stopped.
  $9E5F Climbed.
  $9E8B Across.
  $9ECA The fall.
@ $9DC9 label=CrossScratch
g $9DC9 The step-up's starting cell, and a dummy for the test above
B $9DC9,2,1
@ $A597 label=Touch
c $A597 Does the crossing C from the current cell (#R$88B5) enter a visible object? A=1, its id at (IX)
D $A597 The area's objects, then the globals. An object is entered through a face: going up, the next cell is its first; going down, this cell is the one past its last; and on each other axis the cell is within it, or entered across it at the same time. A rectangle (type 3) or a line or polygon (10 on) returns at once; any other type is remembered (#R$A596) and the last of them returned. Entrances (type 0) aren't skipped: their angles are their size.
@ $A5C7 label=TouchScan
c $A5C7 B objects from IY
@ $A596 label=TouchRemembered
g $A596 #R$A597's last hit of a solid type
B $A596,1,1
@ $BCCB label=KeepClear
c $BCCB Keep the target #R$88D0 units from any face its cell's edges would cross into
D $BCCB An axis whose target is within #R$88D0 (10) of its cell's low or high edge marks a crossing that way; if those crossings together enter an object (#R$A597), the target moves back to #R$88D0 from each marked edge. The first object's id goes to #R$8A69. This is how the rectangles on an area's edge are found: the walk stops at the extent, and this finds the face beyond.
@ $BCCA label=KeepClearDummy
g $BCCA A dummy for #R$BCCB's hit once #R$8A69 is set
B $BCCA,1,1
@ $88D0 label=Margin
b $88D0 How near a face the camera stands; 0 makes #R$9F42 a test
B $88D0,2,1
@ $88DF label=AreaExtent
b $88DF The area's extent in cells: x max, x min, y max, y min, z max, z min
B $88DF,6,2

; Areas, entrances and the events.
@ $A8BA label=Lookup
c $A8BA The object with id #R$8916: A=0, the globals then this area's objects; else in area A. A=0 if found, IX at it
@ $CD3B label=PlaceRig
c $CD3B Show the rig's five global parts at the area's rig (#R$877B, #R$882C), or hide them
@ $877B label=RigPlaced
g $877B A rig in each of areas 1-18, and a second byte each
B $877B,36,18
@ $882C label=RigPositions
b $882C Each area's rig, in cells (x, y, z)
B $882C,54,3
@ $9B6E label=Events
c $9B6E A pass's events, if #R$8A64: the collided object's FCL, the global conditions, the area's
D $9B6E The object with id #R$8A69 runs its script (#R$B320); if it has none and the move was stopped (#R$8A1E), the bump's sound. Then each global condition (#R$8922) and each of the area's (#R$8868).
@ $B320 label=RunFCL
c $B320 Run A bytes of FCL from IX: the shot's instructions if #R$8BF1, else the others
D $B320 An instruction is an opcode (bit 7: a shot's) and operands, its length from #R$8939. A test that fails, and any opcode not handled (0 among them), ends the script. $12 is GOTO area, entrance (#R$9D1C), how Driller's areas connect.
  $B614 GOTO.
  $B635 SWAPJET: into the jet or out.
  $B6D0 REDRAW: the redraw, the copy, the sensors and the panel, there and then.
  $B6FA The next instruction.
@ $B31F label=FCLOpcode
g $B31F The instruction being run
B $B31F,1,1
@ $8939 label=FCLLengths
b $8939 Each FCL opcode's length, operands included
B $8939,48,16
@ $8929 label=ObjectHeader
b $8929 Each object type's header length: its FCL starts there
B $8929,16,16
@ $887B label=FCLBits
g $887B The FCL's 32 bits (bit 32, $887E bit 7, is in the jet), then its variables 1-32
D $887B Variable 30 (#R$889C) counts minutes; variable 31 (#R$889D) minutes in this area, which the input watches.
B $887B,4,4
B $887F,32,16
@ $88A0 label=Crosshair
g $88A0 The crosshair (x, y, shown), the interrupt's frames, the clock, shooting mode, the crosshair wanted, the minute the input saw
B $88A0,4,4
T $88A4,8
B $88AC,3,1
@ $8A64 label=EventsDue
g $8A64 The events are due this pass
B $8A64,1,1
@ $8A69 label=Collided
g $8A69 The object the move hit, or the shot hit
B $8A69,1,1
@ $8A1E label=Blocked
g $8A1E The move was stopped; a sound to play after the copy
B $8A1E,2,1
@ $8BF0 label=Wipe
g $8BF0 The copy wipes; the events are a shot's; why the game ended (1 shield, 2 time, 3 energy, 4 a fall)
B $8BF0,3,1
@ $8911 label=EntranceId
g $8911 The entrance #R$9D1C puts the camera at
B $8911,1,1
@ $8916 label=FoundId
g $8916 The id #R$A8BA looks up; the colour being filled
B $8916,2,1
@ $8875 label=Energy
g $8875 Energy (then the jet's and the probe's kept), shield (then the jet's and the probe's kept)
B $8875,6,1

; The interrupt.
@ $BAB1 label=InterruptInit
c $BAB1 IM 2, its table at $FE00, its handler at #R$BAE6
@ $BAE6 label=Interrupt
c $BAE6 The interrupt: frames (#R$8A1D, #R$8FC2), the clock a second a 50 frames, a minute's energy and #R$889D, and the sensors' shots
@ $BB27 label=InterruptMinute
