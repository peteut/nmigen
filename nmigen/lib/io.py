import types
from .. import *
from ..hdl.rec import *


__all__ = ["pin_layout", "Pin",
           "DifferentialInput", "DifferentialOutput", "DDRInput", "DDROutput"]


def pin_layout(width, dir, xdr=1):
    """
    Layout of the platform interface of a pin or several pins, which may be used inside
    user-defined records.

    See :class:`Pin` for details.
    """
    if not isinstance(width, int) or width < 1:
        raise TypeError("Width must be a positive integer, not '{!r}'"
                        .format(width))
    if dir not in ("i", "o", "io"):
        raise TypeError("Direction must be one of \"i\", \"o\" or \"io\", not '{!r}'"""
                        .format(dir))
    if not isinstance(xdr, int) or xdr < 1:
        raise TypeError("Gearing ratio must be a positive integer, not '{!r}'"
                        .format(xdr))

    fields = []
    if dir in ("i", "io"):
        if xdr == 1:
            fields.append(("i", width))
        else:
            for n in range(xdr):
                fields.append(("i{}".format(n), width))
    if dir in ("o", "io"):
        if xdr == 1:
            fields.append(("o", width))
        else:
            for n in range(xdr):
                fields.append(("o{}".format(n), width))
    if dir == "io":
        fields.append(("oe", 1))
    return Layout(fields)


class Pin(Record):
    """
    An interface to an I/O buffer or a group of them that provides uniform access to input, output,
    or tristate buffers that may include a 1:n gearbox. (A 1:2 gearbox is typically called "DDR".)

    A :class:`Pin` is identical to a :class:`Record` that uses the corresponding :meth:`pin_layout`
    except that it allos accessing the parameters like ``width`` as attributes. It is legal to use
    a plain :class:`Record` anywhere a :class:`Pin` is used, provided that these attributes are
    not necessary.

    Parameters
    ----------
    width : int
        Width of the ``i``/``iN`` and ``o``/``oN`` signals.
    dir : ``"i"``, ``"o"``, ``"io"``
        Direction of the buffers. If ``"i"`` is specified, only the ``i``/``iN`` signals are
        present. If ``"o"`` is specified, only the ``o``/``oN`` signals are present. If ``"io"``
        is specified, both the ``i``/``iN`` and ``o``/``oN`` signals are present, and an ``oe``
        signal is present.
    xdr : int
        Gearbox ratio. If equal to 1, the I/O buffer is SDR, and only ``i``/``o`` signals are
        present. If greater than 1, the I/O buffer includes a gearbox, and ``iN``/``oN`` signals
        are present instead, where ``N in range(0, N)``. For example, if ``xdr=2``, the I/O buffer
        is DDR; the signal ``i0`` reflects the value at the rising edge, and the signal ``i1``
        reflects the value at the falling edge.

    Attributes
    ----------
    i : Signal, out
        I/O buffer input, without gearing. Present if ``dir="i"`` or ``dir="io"``, and ``xdr`` is
        equal to 1.
    i0, i1, ... : Signal, out
        I/O buffer inputs, with gearing. Present if ``dir="i"`` or ``dir="io"``, and ``xdr`` is
        greater than 1.
    o : Signal, in
        I/O buffer output, without gearing. Present if ``dir="o"`` or ``dir="io"``, and ``xdr`` is
        greater than 1.
    o0, o1, ... : Signal, in
        I/O buffer outputs, with gearing. Present if ``dir="o"`` or ``dir="io"``, and ``xdr`` is
        greater than 1.
    oe : Signal, in
        I/O buffer output enable. Present if ``dir="io"``. Buffers generally cannot change
        direction more than once per cycle, so at most one output enable signal is present.
    """
    def __init__(self, width, dir, xdr=1):
        self.width = width
        self.dir   = dir
        self.xdr   = xdr

        super().__init__(pin_layout(self.width, self.dir, self.xdr))
        f = m.elaborate(platform)
        f.flatten = True
        return f


class DifferentialInput(types.SimpleNamespace):
    def __init__(self, shape=None, min=None, max=None, name=None):
        i_p = Signal(shape, min=min, max=max, name=name and name + "_i_p")
        i_n = Signal(shape, min=min, max=max, name=name and name + "_i_n")
        o = Signal(shape, min=min, max=max, name=name and name + "_o")
        super().__init__(**locals())

    def __len__(self):
        return len(self.i_p)

    def elaborate(self, platform):
        try:
            return platform.get_differential_input(self)
        except AttributeError:
            raise NotImplementedError("{} not implemented by {!r}".format(
                self.__class__.__name__, platform))


class DifferentialOutput(types.SimpleNamespace):
    def __init__(self, shape=None, min=None, max=None, name=None):
        o_p = Signal(shape, min=min, max=max, name=name and name + "_o_p")
        o_n = Signal(shape, min=min, max=max, name=name and name + "_o_n")
        i = Signal(shape, min=min, max=max, name=name and name + "_i")
        super().__init__(**locals())

    def __len__(self):
        return len(self.i)

    def elaborate(self, platform):
        try:
            return platform.get_differential_output(self)
        except AttributeError:
            raise NotImplementedError("{} not implemented by {!r}".format(
                self.__class__.__name__, platform))


class DDRInput(types.SimpleNamespace):
    def __init__(self, shape=None, min=None, max=None, name=None,
                 domain="sync"):
        i = Signal(shape, min=min, max=max, name=name and name + "_i")
        o1 = Signal(shape, min=min, max=max, name=name and name + "_o1")
        o2 = Signal(shape, min=min, max=max, name=name and name + "_o2")
        domain = domain
        super().__init__(**locals())

    def __len__(self):
        return len(self.i)

    def elaborate(self, platform):
        try:
            return platform.get_ddr_input(self)
        except AttributeError:
            raise NotImplementedError("{} not implemented by {!r}".format(
                self.__class__.__name__, platform))


class DDROutput(types.SimpleNamespace):
    def __init__(self, shape=None, min=None, max=None, name=None,
                 domain="sync"):
        i1 = Signal(shape, min=min, max=max, name=name and name + "_i1")
        i2 = Signal(shape, min=min, max=max, name=name and name + "_i2")
        o = Signal(shape, min=min, max=max, name=name and name + "_o")
        domain = domain
        super().__init__(**locals())

    def __len__(self):
        return len(self.i1)

    def elaborate(self, platform):
        try:
            return platform.get_ddr_output(self)
        except AttributeError:
            raise NotImplementedError("{} not implemented by {!r}".format(
                self.__class__.__name__, platform))
