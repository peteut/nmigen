from ..build.platform import *
import unittest

__all__ = ["ConstraintTestCase"]


class ConstraintTestCase(unittest.TestCase):
    def test_pins(self):
        self.assertIsInstance(Pins(""), Constraint)
        self.assertEqual(repr(Pins("1  2  3")), "Pins('1 2 3')")
        self.assertEqual(hash(Pins("1 ")), hash(Pins(" 1 ")))

    def test_iostandard(self):
        self.assertIsInstance(IOStandard("CMOS"), Constraint)
        self.assertEqual(repr(IOStandard("CMOS")), "IOStandard('CMOS')")
        self.assertEqual(hash(IOStandard("CMOS")), hash(IOStandard("CMOS")))

    def test_drive(self):
        self.assertIsInstance(Drive("high"), Constraint)
        self.assertEqual(repr(Drive("  high ")), "Drive('high')")
        self.assertEqual(hash(Drive("high")), hash(Drive(" high ")))

    def test_misc(self):
        self.assertIsInstance(Misc("misc"), Constraint)
        self.assertEqual(repr(Misc("  misc ")), "Misc('misc')")
        self.assertEqual(hash(Misc("misc")), hash(Misc(" misc ")))

    def test_subsignal(self):
        self.assertIsInstance(Subsignal("foo", Pins("1")), Constraint)
        self.assertEqual(repr(Subsignal("foo", Pins("  1 2 3 "))),
                         "Subsignal('foo', {!r})".format(Pins("1 2 3")))
        self.assertEqual(hash(Subsignal("foo",  Pins(" 1 2 3  "))),
                         hash(Subsignal("foo", Pins("1 2 3"))))


class ConnectorTestCase(unittest.TestCase):
    def test_make(self):
        self.assertIsInstance(Connector.make(("x", "1 2 3")), Connector)
        self.assertIsInstance(Connector.make(("x", [("1 2 3"), ("3 4 5")])),
                              Connector)
        self.assertIsInstance(Connector.make(("x", {"Pin1": "1"})), Connector)

    def test_getitem(self):
        self.assertEqual(
            hash(Connector.make(("x", "1 2 3")).pins[0]), hash(Pins("1 2 3")))
        self.assertEqual(
            hash(Connector.make(("x", [("1 2 3"), ("4 5 6")])).pins[1]),
            hash(Pins("4 5 6")))
        self.assertEqual(
            hash(Connector.make(("x", {"Pin1": "1"})).pins["Pin1"]),
            hash(Pins("1")))
