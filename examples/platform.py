from nmigen import Signal, Module
from nmigen.cli import main


class Adder:
    def __init__(self, width):
        a, b, o = Signal(width), Signal(width), Signal(width)
        [setattr(self, k, v) for k, v in locals().items()]

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.a + self.b)
        return m


class Subtractor:
    def __init__(self, width):
        a, b, o = Signal(width), Signal(width), Signal(width)
        [setattr(self, k, v) for k, v in locals().items()]

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.a - self.b)
        return m


class ALU:
    def __init__(self, width):
        op, a, b, o = Signal(), Signal(width), Signal(width), Signal(width)
        add, sub = Adder(width), Subtractor(width)
        [setattr(self, k, v) for k, v in locals().items()]

    def elaborate(self, platform):
        m = Module()
        m.submodules.add = self.add
        m.submodules.sub = self.sub
        m.d.comb += [
            self.add.a.eq(self.a),
            self.sub.a.eq(self.a),
            self.add.b.eq(self.b),
            self.sub.b.eq(self.b),
        ]
        with m.If(self.op):
            m.d.comb += self.o.eq(self.sub.o)
        with m.Else():
            m.d.comb += self.o.eq(self.add.o)
        return m


if __name__ == "__main__":
    import types
    from nmigen.build import Platform, Pins

    # platform declaration
    cfg = {
        "name": "alu_example",
        "tool": "vivado",
        "io": [
            ("op", 0, Pins("1")),
            ("a", 0, Pins(" ".join(map(str, range(10, 17))))),
            ("b", 0, Pins(" ".join(map(str, range(20, 27))))),
            ("o", 0, Pins(" ".join(map(str, range(30, 37)))))],
    }
    platform = Platform.make(**cfg)

    # lookup ports
    op, a, b, o = platform.port.op[0], platform.port.a[0], \
        platform.port.b[0], platform.port.o[0]

    def elaborate(platform):
        m = Module()
        m.submodules.alu = alu = ALU(16)
        # wire top level ports
        m.d.comb += [
            alu.op.eq(op),
            alu.a.eq(a),
            alu.b.eq(b),
            o.eq(alu.o)]
        return m

    top = types.SimpleNamespace(elaborate=elaborate)

    main(top, ports=[op, a, b, o], platform=platform)
