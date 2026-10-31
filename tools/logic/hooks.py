"""Where the pass calls code the logic leaves out, by the original's address.

The transcription calls these at the points the original calls its own
routines. The defaults do nothing (or say nothing was drawn or hit); the
oracle (tools/logic/oracle.py) gives them what the original's renderer
left, where the logic reads it back.
"""


class Hooks:
    def __init__(self):
        self.log = []   # (name, args) of every call, for tracing

    def _note(self, name, *args):
        self.log.append((name, args))

    # Sound and waiting.
    def sound(self, s, n):
        """$9574: play sound n (the beeper; waits while it plays)."""
        self._note("sound", n)

    def wait(self, s, frames):
        """Wait while the interrupt counts Countdown ($8FC2) down from
        frames: the step and turn size keys (7), the crosshair keys (9) and
        the FCL's DELAY."""
        self._note("wait", frames)

    # The screen.
    def key_lights(self, s, which):
        """$99AE and $9A64: the panel's key lights, in the attributes at
        ($8BF3)."""
        self._note("key_lights", which)

    def panel(self, s):
        """$B72B: redraw the panel's figures (SPACE calls it)."""
        self._note("panel")

    def crosshair(self, s):
        """$AAA0: draw or erase the crosshair (EOR) at CrossX, CrossY."""
        self._note("crosshair")

    def screen_colours(self, s):
        """$A77A after its first lines: the view's attributes from
        ScreenColours, and the sensors' flash counters."""
        self._note("screen_colours")

    def redraw(self, s):
        """FCL REDRAW: the redraw ($6B12), the copy and the sensors
        ($9841) and the panel ($B72B), there and then."""
        self._note("redraw")

    def undraw(self, s, obj_id):
        """FCL TOGVIS, INVIS or DESTROY hiding an object: $B492 takes it
        out of the last redraw's draw list, if it's there. True if it was
        (GameFlags2 bit 3 then asks for a redraw from the list)."""
        self._note("undraw", obj_id)
        return False

    def sensor_off(self, s, obj_id):
        """$B467: hiding a sensor stops it in the interrupt's list."""
        self._note("sensor_off", obj_id)

    # Shooting, the rigs and the rest.
    def laser(self, s):
        """$AA50-$AA8C: the laser's lines from the view's corners, twice."""
        self._note("laser")

    def shot(self, s):
        """$B153: the object under the crosshair, into Collided ($8A69); the
        renderer's projected faces decide it. The default hits nothing."""
        self._note("shot")

    def rig(self, s, action):
        """$BEFA: D drills (action $28) and C collects (action $2A) a rig."""
        self._note("rig", action)

    def info(self, s):
        """$C3DC: I shows the information screen, and waits for a key."""
        self._note("info")

    def game_over(self, s):
        """$9AB7: GameOver ($8BF2) is set: the end of the game."""
        self._note("game_over", s.GameOver)
