"""The one switch between the model's stand-ins and the parts other tracks
own: tools/model/maths.py, raster.py, writer.py and colours.py.

SOURCE says, for each part, "real", "standin", or "auto" (the real module if
its file exists, else the stand-in). Everything else in the model goes
through the functions here, so swapping a part in touches only this file;
adapt the calls below if a real module's names differ.
"""
import importlib
import pathlib

SOURCE = {"maths": "auto", "raster": "auto", "writer": "auto", "colours": "auto"}

_HERE = pathlib.Path(__file__).resolve().parent


def _load(part):
    how = SOURCE[part]
    if how == "auto":
        how = "real" if (_HERE / (part + ".py")).exists() else "standin"
    name = "tools.model." + part if how == "real" else "tools.model.standin." + part
    return importlib.import_module(name), how


maths, _maths_how = _load("maths")
raster, _raster_how = _load("raster")
writer, _writer_how = _load("writer")
colours, _colours_how = _load("colours")
USING = {"maths": _maths_how, "raster": _raster_how, "writer": _writer_how, "colours": _colours_how}


def _agree():
    """The projection's constants are view.py's: a maths module that defines
    its own must define the same."""
    from tools.model import view
    for name in ("FX", "FY", "XC", "YC", "ZNEAR"):
        if hasattr(maths, name) and getattr(maths, name) != getattr(view, name):
            raise ImportError("maths.%s is %r, view.%s %r" % (name, getattr(maths, name),
                                                              name, getattr(view, name)))


_agree()


def project(X, Y, Z):
    """Camera space to view coordinates (maths.project)."""
    return maths.project(X, Y, Z)


def rasterise(faces, sky, ground, horizon=None, stats=None):
    """Faces nearest first to the lines' runs (raster.rasterise). stats, a
    dict, gets whatever counts the rasteriser keeps."""
    if stats is not None and _raster_how == "standin":
        return raster.rasterise(faces, sky, ground, horizon, stats)
    return raster.rasterise(faces, sky, ground, horizon)


def write(lines):
    """The lines' runs to the view's bytes (writer.write)."""
    return writer.write(lines)


def decode(view):
    """The view's bytes back to logical colours, a list of lines of pixels."""
    if hasattr(writer, "decode"):
        return writer.decode(view)
    from tools.model.standin import writer as standin_writer
    return standin_writer.decode(view)


def pattern(area, index):
    return colours.pattern(area, index)


def sky(area):
    return colours.sky(area)


def face_colours(area, object_id):
    """The object's colour nibbles in the version the colours follow, or None
    to keep the database's (the stand-in palette has no versions)."""
    if hasattr(colours, "face_colours"):
        return colours.face_colours(area, object_id)
    return None


def ground(area):
    return colours.ground(area)


def palette():
    """Logical colour to RGB for pictures: the colour study's if it gives
    one, else the BBC's default."""
    if hasattr(colours, "PALETTE"):
        return colours.PALETTE
    from tools.model.standin import colours as standin_colours
    return standin_colours.PALETTE
