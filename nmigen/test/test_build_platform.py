import unittest
import functools
from collections.abc import Iterable
from operator import attrgetter
from ..build.platform import Pins, Constraint, IOStandard, Drive, Misc, \
    Subsignal, ConnectorProxy, Platform

    # noqa
from ..build.platform import IOProxy, Port, compose_xdc_from_signal
from ..hdl.ast import Signal
from ..lib.io import TSTriple

__all__ = ["ConstraintTestCase"]


class ConstraintTestCase(unittest.TestCase):
    def test_pins_init(self):
        self.assertIsInstance(Pins(""), Constraint)
        self.assertEqual(repr(Pins("1  2  3")), "Pins('1 2 3')")
        self.assertEqual(Pins("1 "), Pins(" 1 "))

    def test_pins_xdc(self):
        self.assertEqual("""\
set_property PACKAGE_PIN B26 [get_ports CLK]
""", Pins("B26").get_xdc("CLK"))
        self.assertEqual("""\
set_property PACKAGE_PIN B26 [get_ports CLKS[0]]
set_property PACKAGE_PIN B28 [get_ports CLKS[1]]
""", Pins("B26 B28").get_xdc("CLKS"))

    def test_iostandard(self):
        self.assertIsInstance(IOStandard("CMOS"), Constraint)
        self.assertEqual(repr(IOStandard("CMOS")), "IOStandard('CMOS')")
        self.assertEqual(IOStandard("CMOS"), IOStandard("CMOS"))

    def test_iostandard_xdc(self):
        self.assertEqual("""\
set_property IOSTANDARD LVCMOS12 [get_ports STATUS]
""", IOStandard("LVCMOS12").get_xdc("STATUS"))

    def test_drive(self):
        self.assertIsInstance(Drive(1), Constraint)
        self.assertEqual(repr(Drive(1)), "Drive(1)")

    def test_drive_xdc(self):
        self.assertEqual("""\
set_property DRIVE 2 [get_ports STATUS]
""", Drive(2).get_xdc("STATUS"))

    def test_misc(self):
        self.assertIsInstance(Misc("misc"), Constraint)
        self.assertEqual(repr(Misc("  misc ")), "Misc('misc')")
        self.assertEqual(Misc("misc"), Misc(" misc "))
        self.assertEqual(repr(Misc(("IOB", True))), "Misc('IOB=TRUE')")

    def test_misc_xdc(self):
        self.assertEqual("""\
set_property MISC value [get_ports STATUS]
""", Misc("MISC=value").get_xdc("STATUS"))

    def test_subsignal(self):
        self.assertIsInstance(Subsignal("foo", Pins("1")), Constraint)
        self.assertEqual(repr(Subsignal("foo", Pins("  1 2 3 "))),
                         "Subsignal('foo', {!r})".format(Pins("1 2 3")))
        self.assertEqual(Subsignal("foo", Pins(" 1 2 3  ")),
                         Subsignal("foo", Pins("1 2 3")))

    def test_subsignal_xdc(self):
        with self.assertRaises(NotImplementedError):
            Subsignal("foo").get_xdc("FOO")

_connector = [
    ("com", "1 2 3"),
    ("com1", [("1 2 3"), ("4 5 6")]),
    ("deep", {"a": "1", "b": "2"})]


class ConnectorProxyTestCase(unittest.TestCase):
    dut = functools.reduce(ConnectorProxy.make, _connector, ConnectorProxy())

    def test_make(self):
        dut = self.dut
        self.assertIsInstance(dut, ConnectorProxy)
        self.assertIsInstance(dut.pins["deep"], ConnectorProxy)

    def test_dir(self):
        dut = self.dut
        self.assertEqual(dir(dut), "com  com1 deep".split())

    def test_getitem(self):
        dut = self.dut
        self.assertEqual(dut.pins["com"].pins[0], Pins("1 2 3"))
        self.assertEqual(dut.pins["com1"].pins[1], Pins("4 5 6"))

    def test_recursive(self):
        dut = self.dut
        self.assertEqual(dut.pins["deep"].pins["a"], Pins("1"))


_io = [
    ("io0", 0, Pins("1"), Misc("foo")),
    ("io0", 1, Pins("2")),
    ("io1", Pins("3")),
    ("io2",
     Subsignal("sub", Pins("4"), Misc("foobar")),
     Subsignal("sub2", Pins("5")),
     IOStandard("CMOS")),
    ("io3", 0,
     Subsignal("sub", Pins("6"), Misc("foobar")),
     Subsignal("sub2", Pins("7")),
     IOStandard("CMOS"))]


class IOProxyTestCase(unittest.TestCase):
    dut = functools.reduce(IOProxy.make, _io, IOProxy())

    def test_reduce_list(self):
        dut = self.dut
        self.assertEqual(
            set([Pins("1"), Misc("foo")]), dut.items["io0"].items[0])
        self.assertEqual(set([Pins("2")]), dut.items["io0"].items[1])
        self.assertEqual(set([Pins("3")]), dut.items["io1"])
        self.assertEqual(
            set([Pins("4"), Misc("foobar"), IOStandard("CMOS")]),
            dut.items["io2"].items["sub"])
        self.assertEqual(
            set([Pins("5"), IOStandard("CMOS")]),
            dut.items["io2"].items["sub2"])
        self.assertEqual(
            set([Pins("7"), IOStandard("CMOS")]),
            dut.items["io3"].items[0].items["sub2"])

    def test_dir(self):
        dut = self.dut
        self.assertEqual(dir(dut), "io0 io1 io2 io3".split())

    def test_itearable(self):
        dut = self.dut
        self.assertIsInstance(dut, Iterable)
        self.assertEqual(
            list(iter(dut)), [
                ("io0", IOProxy(items={
                    0: {Pins("1"), Misc("foo")},
                    1: {Pins("2")}})),
                ("io1", {Pins("3")}),
                ("io2", IOProxy(
                    items={
                        "sub": {
                            Pins("4"), IOStandard("CMOS"), Misc("foobar")},
                        "sub2": {IOStandard("CMOS"), Pins("5")}})),
                ("io3",
                 IOProxy(items={
                     0: IOProxy(
                         items={
                             "sub": {
                                 Pins("6"), IOStandard("CMOS"), Misc("foobar")},
                             "sub2": {IOStandard("CMOS"), Pins("7")}})}))])


class PlatfromTestCase(unittest.TestCase):
    def get_tristate_raise(triple: TSTriple, io: Signal):
        raise NotImplementedError

    dut = Platform.make(
        "name", _io, "vivado", _connector,
        techmap={"get_tristate": get_tristate_raise})

    def test_port_getattr(self):
        dut = self.dut.port
        self.assertIsInstance(dut, Port)
        self.assertEqual(dut.name, "")
        self.assertEqual(dut.io0.name, "io0")
        self.assertIsInstance(dut.io0[0], Signal)
        self.assertEqual(dut.io0[0].name, "io0_0")
        self.assertEqual(len(dut.io0[0]), 1)

    def test_port_dir(self):
        dut = self.dut.port
        self.assertEqual(dir(dut), "io0 io1 io2 io3".split())

    def test_port_len(self):
        dut = self.dut.port
        self.assertEqual(4, len(dut))

    def test_port_iter(self):
        dut = self.dut.port
        self.assertEqual(
            "io0_0 io0_1 io1 io2_sub io2_sub2 io3_0_sub io3_0_sub2".split(),
            list(map(attrgetter("name"), dut)))

    def test_connector_len(self):
        dut = self.dut.connector
        self.assertEqual(3, len(dut))

    def test_connector_iter(self):
        dut = self.dut.connector
        self.assertEqual(
            "com_0 com1_0 com1_1 deep_a deep_b".split(),
            list(map(attrgetter("name"), dut)))

    def test_get_tristate(self):
        dut = self.dut
        triple, io_sig = TSTriple(), Signal()
        tristate = triple.get_tristate(io_sig)
        with self.assertRaises(NotImplementedError):
            tristate.elaborate(dut)


class ComposeXdcFromSignalTestCase(unittest.TestCase):
    def test_without_attrs(self):
        self.assertEqual(
            compose_xdc_from_signal("foo", Signal(0, name="foo")), "")

    def test_one_attr(self):
        self.assertEqual(
            compose_xdc_from_signal(
                "foo", Signal(0, name="foo_name", attrs={
                    "misc": Misc(("IOB", True))})),
            """\
# foo_name
set_property IOB TRUE [get_ports foo]
""")

    def test_multiple_attr(self):
        self.assertEqual(
            compose_xdc_from_signal(
                "foo", Signal(0, name="foo_name", attrs={
                    "misc": Misc(("IOB", True)),
                    "iostandard": IOStandard("LVCMOS12")})), """\
# foo_name
set_property IOB TRUE [get_ports foo]
set_property IOSTANDARD LVCMOS12 [get_ports foo]
""")
