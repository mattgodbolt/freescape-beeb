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
        """$B467: hiding a sensor stops it in the interrupt's list (which
        tools/logic/sensors.py's off does: this is the note of it)."""
        self._note("sensor_off", obj_id)

    def sensor_lines(self, s, x, y):
        """$BC0F: the interrupt's four lines (EOR) from a sensor's point (x,
        y, as the crosshair's) to the view's top and bottom by its centre."""
        self._note("sensor_lines", x, y)

    def border(self, s, colour):
        """OUT ($FE): the border's colour (the interrupt's flash of a shot)."""
        self._note("border", colour)

    # Shooting, the rigs and the rest.
    def laser(self, s):
        """$AA50-$AA8C: the laser's lines from the view's corners, twice."""
        self._note("laser")

    def shot(self, s):
        """$B153: the object under the crosshair, into Collided ($8A69); the
        renderer's projected faces decide it. The default hits nothing."""
        self._note("shot")

    def message(self, s, addr):
        """$93C4 then $BCA6: the 14-character message at addr shown, and
        highlighted, in the panel's message line (the rigs' messages; the
        wait after it is wait's)."""
        self._note("message", addr)

    def info(self, s):
        """$C3DC: I shows the information screen, and waits for a key."""
        self._note("info")

    def game_over(self, s):
        """$9AB7: GameOver ($8BF2) is set: the end of the game."""
        self._note("game_over", s.GameOver)

    def ended(self, s):
        """$9B34-$9B40: the end's redraw of area 127 ($6B12), the sensors'
        test ($9841), the panel ($B72B) and the message's highlight off."""
        self._note("ended")

    def started(self, s):
        """$97D3-$97EB: a game's start: the redraw, the panel, the clock's
        text, the control menu (not in the demo) and the sensors' test."""
        self._note("started")
