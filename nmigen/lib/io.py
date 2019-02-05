import types
from .. import *


__all__ = ["TSTriple", "Tristate", "DifferentialInput", "DifferentialOutput",
           "DDRInput", "DDROutput"]


class TSTriple:
    def __init__(self, shape=None, min=None, max=None, reset_o=0, reset_oe=0, reset_i=0,
                 name=None):
        self.o  = Signal(shape, min=min, max=max, reset=reset_o,
                         name=None if name is None else name + "_o")
        self.oe = Signal(reset=reset_oe,
                         name=None if name is None else name + "_oe")
        self.i  = Signal(shape, min=min, max=max, reset=reset_i,
                         name=None if name is None else name + "_i")

    def __len__(self):
        return len(self.o)

    def elaborate(self, platform):
        return Fragment()

    def get_tristate(self, io):
        return Tristate(self, io)


class Tristate:
    def __init__(self, triple, io):
        self.triple = triple
        self.io     = io

    def elaborate(self, platform):
        if hasattr(platform, "get_tristate"):
            return platform.get_tristate(self.triple, self.io)

        m = Module()
        m.d.comb += self.triple.i.eq(self.io)
        m.submodules += Instance("$tribuf",
            p_WIDTH=len(self.io),
            i_EN=self.triple.oe,
            i_A=self.triple.o,
            o_Y=self.io,
        )

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
