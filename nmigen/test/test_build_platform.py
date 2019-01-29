import unittest
import functools
from ..build.platform import *
from ..build.platform import IOProxy

__all__ = ["ConstraintTestCase"]


class ConstraintTestCase(unittest.TestCase):
    def test_pins(self):
        self.assertIsInstance(Pins(""), Constraint)
        self.assertEqual(repr(Pins("1  2  3")), "Pins('1 2 3')")
        self.assertEqual(Pins("1 "), Pins(" 1 "))

    def test_iostandard(self):
        self.assertIsInstance(IOStandard("CMOS"), Constraint)
        self.assertEqual(repr(IOStandard("CMOS")), "IOStandard('CMOS')")
        self.assertEqual(IOStandard("CMOS"), IOStandard("CMOS"))

    def test_drive(self):
        self.assertIsInstance(Drive("high"), Constraint)
        self.assertEqual(repr(Drive("  high ")), "Drive('high')")
        self.assertEqual(Drive("high"), Drive(" high "))

    def test_misc(self):
        self.assertIsInstance(Misc("misc"), Constraint)
        self.assertEqual(repr(Misc("  misc ")), "Misc('misc')")
        self.assertEqual(Misc("misc"), Misc(" misc "))

    def test_subsignal(self):
        self.assertIsInstance(Subsignal("foo", Pins("1")), Constraint)
        self.assertEqual(repr(Subsignal("foo", Pins("  1 2 3 "))),
                         "Subsignal('foo', {!r})".format(Pins("1 2 3")))
        self.assertEqual(Subsignal("foo", Pins(" 1 2 3  ")),
                         Subsignal("foo", Pins("1 2 3")))


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


class PlatfromTestCase(unittest.TestCase):
    def test_get_vivado(self):
        plat = Platform.make("name", [])._asdict()
        plat["files"] += ["top.v"]
        backend = get_vivado(Platform(**plat))
        backend.configure([])
        self.assertTrue(get_vivado(Platform(**plat)))


class IOProxyTestCase(unittest.TestCase):
    def test_reduce_list(self):
        dut = functools.reduce(IOProxy.make, [
            ("io0", 0, Pins("1"), Misc("foo")),
            ("io0", 1, Pins("2")),
            ("io1", Pins("3")),
            ("io2",
             Subsignal("sub", Pins("4"), Misc("foobar")),
             Subsignal("sub2", Pins("5")),
             IOStandard("CMOS")),
        ], IOProxy())
        self.assertEqual(set([Pins("1"), Misc("foo")]), dut.items["io0"].items[0])
        self.assertEqual(set([Pins("2")]), dut.items["io0"].items[1])
        self.assertEqual(set([Pins("3")]), dut.items["io1"])
        self.assertEqual(
            set([Pins("4"), Misc("foobar"), IOStandard("CMOS")]),
            dut.items["io2"].items["sub"])
        self.assertEqual(
            set([Pins("5"), IOStandard("CMOS")]),
            dut.items["io2"].items["sub2"])
