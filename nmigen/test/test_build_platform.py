import unittest
import functools
from ..build.platform import *
from ..build.platform import IOProxy, Port
from ..hdl.ast import Signal

__all__ = ["ConstraintTestCase"]


class ConstraintTestCase(unittest.TestCase):
    def test_pins(self):
        self.assertIsInstance(Pins(""), Constraint)
        self.assertEqual(repr(Pins("1  2  3")), "Pins('1 2 3')")
        self.assertEqual(Pins("1 "), Pins(" 1 "))

    def test_pins_xdc(self):
        self.assertEqual(
"""set_property PACKAGE_PIN B26 [get_ports CLK]
""",
            Pins("B26").get_xdc("CLK"))
        self.assertEqual(
"""set_property PACKAGE_PIN B26 [get_ports CLKS[0]]
set_property PACKAGE_PIN B28 [get_ports CLKS[1]]
""",
            Pins("B26 B28").get_xdc("CLKS"))

    def test_iostandard(self):
        self.assertIsInstance(IOStandard("CMOS"), Constraint)
        self.assertEqual(repr(IOStandard("CMOS")), "IOStandard('CMOS')")
        self.assertEqual(IOStandard("CMOS"), IOStandard("CMOS"))

    def test_iostandard_xdc(self):
        self.assertEqual(
"""set_property IOSTANDARD LVCMOS12 [get_ports STATUS]
""",
            IOStandard("LVCMOS12").get_xdc("STATUS"))

    def test_drive(self):
        self.assertIsInstance(Drive(1), Constraint)
        self.assertEqual(repr(Drive(1)), "Drive(1)")

    def test_drive_xdc(self):
        self.assertEqual(
"""set_property DRIVE 2 [get_ports STATUS]
""",
            Drive(2).get_xdc("STATUS"))

    def test_misc(self):
        self.assertIsInstance(Misc("misc"), Constraint)
        self.assertEqual(repr(Misc("  misc ")), "Misc('misc')")
        self.assertEqual(Misc("misc"), Misc(" misc "))
        self.assertEqual(repr(Misc(("IOB", True))), "Misc('IOB=TRUE')")

    def test_misc_xdc(self):
        self.assertEqual(
"""set_property MISC value [get_ports STATUS]
""",
            Misc("MISC=value").get_xdc("STATUS"))

    def test_subsignal(self):
        self.assertIsInstance(Subsignal("foo", Pins("1")), Constraint)
        self.assertEqual(repr(Subsignal("foo", Pins("  1 2 3 "))),
                         "Subsignal('foo', {!r})".format(Pins("1 2 3")))
        self.assertEqual(Subsignal("foo", Pins(" 1 2 3  ")),
                         Subsignal("foo", Pins("1 2 3")))

    def test_subsignal_xdc(self):
        with self.assertRaises(NotImplementedError):
            Subsignal("foo").get_xdc("FOO")


class ConnectorTestCase(unittest.TestCase):
    def test_make(self):
        self.assertIsInstance(Connector.make(("x", "1 2 3")), Connector)
        self.assertIsInstance(Connector.make(("x", [("1 2 3"), ("3 4 5")])),
                              Connector)
        self.assertIsInstance(Connector.make(("x", {"Pin1": "1"})), Connector)

    def test_getitem(self):
        self.assertEqual(
            Connector.make(("x", "1 2 3")).pins[0], Pins("1 2 3"))
        self.assertEqual(
            Connector.make(("x", [("1 2 3"), ("4 5 6")])).pins[1],
            Pins("4 5 6"))
        self.assertEqual(
            Connector.make(("x", {"Pin1": "1"})).pins["Pin1"], Pins("1"))


_io = [
    ("io0", 0, Pins("1"), Misc("foo")),
    ("io0", 1, Pins("2")),
    ("io1", Pins("3")),
    ("io2",
     Subsignal("sub", Pins("4"), Misc("foobar")),
     Subsignal("sub2", Pins("5")),
     IOStandard("CMOS"))]


class IOProxyTestCase(unittest.TestCase):
    def test_reduce_list(self):
        dut = functools.reduce(IOProxy.make, _io, IOProxy())
        self.assertEqual(set([Pins("1"), Misc("foo")]), dut.items["io0"].items[0])
        self.assertEqual(set([Pins("2")]), dut.items["io0"].items[1])
        self.assertEqual(set([Pins("3")]), dut.items["io1"])
        self.assertEqual(
            set([Pins("4"), Misc("foobar"), IOStandard("CMOS")]),
            dut.items["io2"].items["sub"])
        self.assertEqual(
            set([Pins("5"), IOStandard("CMOS")]),
            dut.items["io2"].items["sub2"])


class PlatfromTestCase(unittest.TestCase):
    def test_get_vivado(self):
        plat = Platform.make("name", _io)._asdict()
        plat["files"] += ["top.v"]
        backend = get_vivado(Platform(**plat))
        backend.configure([])
        self.assertTrue(get_vivado(Platform(**plat)))

    def test_port(self):
        plat = Platform.make("name", _io)
        self.assertIsInstance(plat.port, Port)
        self.assertEqual(plat.port.name, "")
        self.assertEqual(plat.port.io0.name, "io0")
        self.assertIsInstance(plat.port.io0[0], Signal)
        self.assertEqual(plat.port.io0[0].name, "io0_0")
        self.assertEqual(len(plat.port.io0[0]), 1)
