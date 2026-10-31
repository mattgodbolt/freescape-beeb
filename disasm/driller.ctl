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
@ $9825 label=MainLoop
c $9825 The main loop's top: input (#R$9990), events (#R$9B6E), then the redraw
@ $9BF7 label=CopyBuffer
c $9BF7 Copy buffer rows 0-103 to the screen, one LDIR a row
@ $9D1C label=GoToEntrance
c $9D1C Put the camera at entrance #R$8911 of the current area
@ $A364 label=Step
c $A364 A step forward (A=3) or back (A=4)
@ $BE18 label=LoadArea
c $BE18 Enter area #R$8862: its objects, its scale and the per-scale values
@ $CB7A label=Protection
c $CB7A The protection: a word from the manual, chosen by #R$8A1D from the table at #R$ABC1
