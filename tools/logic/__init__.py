"""Driller's player logic, transcribed from the ZX original, and its oracle.

docs/research/zx-logic.md describes what the original does; this package
does the same, pass for pass, on the original's variables:

    state.py     the variables by name, at the original's addresses
    arith.py     the multiplies and divide ($910E, $9179, $92D7, $928C)
    passes.py    a pass of the main loop ($9825): the input ($9990) and the
                 key reader ($943C), the crosshair ($A95C), the minute
    move.py      the movement actions ($A279), the step ($A364), the move
                 ($9F42), a crossing ($9DCF), the object test ($A597) and
                 keeping clear of faces ($BCCB)
    area.py      objects by id ($A8BA), the entrance ($9D1C), the area's
                 load ($BE18) and its rig ($CD3B)
    fcl.py       the events ($9B6E) and the FCL interpreter ($B320)
    hooks.py     the calls the logic leaves out (sound, the screen, the
                 renderer, the rigs), named by the original's addresses

    oracle.py    the original run pass by pass (tools/zx.py)
    scenario.py  the scenario format (tests/logic/*.txt)
    check.py     both sides compared after every pass, and the fuzzer

Run the scripts with -I: they read the snapshot made from the originals.
"""
