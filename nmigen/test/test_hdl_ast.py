import warnings
from enum import Enum

from ..hdl.ast import *
from .tools import *


class UnsignedEnum(Enum):
    FOO = 1
    BAR = 2
    BAZ = 3


class SignedEnum(Enum):
    FOO = -1
    BAR =  0
    BAZ = +1


class StringEnum(Enum):
    FOO = "a"
    BAR = "b"


class ValueTestCase(FHDLTestCase):
    def test_wrap(self):
        self.assertIsInstance(Value.wrap(0), Const)
        self.assertIsInstance(Value.wrap(True), Const)
        c = Const(0)
        self.assertIs(Value.wrap(c), c)
        with self.assertRaises(TypeError,
                msg="Object ''str'' is not an nMigen value"):
            Value.wrap("str")

    def test_wrap_enum(self):
        e1 = Value.wrap(UnsignedEnum.FOO)
        self.assertIsInstance(e1, Const)
        self.assertEqual(e1.shape(), (2, False))
        e2 = Value.wrap(SignedEnum.FOO)
        self.assertIsInstance(e2, Const)
        self.assertEqual(e2.shape(), (2, True))

    def test_wrap_enum_wrong(self):
        with self.assertRaises(TypeError,
                msg="Only enumerations with integer values can be converted to nMigen values"):
            Value.wrap(StringEnum.FOO)

    def test_bool(self):
        with self.assertRaises(TypeError,
                msg="Attempted to convert nMigen value to boolean"):
            if Const(0):
                pass

    def test_len(self):
        self.assertEqual(len(Const(10)), 4)

    def test_getitem_int(self):
        s1 = Const(10)[0]
        self.assertIsInstance(s1, Slice)
        self.assertEqual(s1.start, 0)
        self.assertEqual(s1.end, 1)
        s2 = Const(10)[-1]
        self.assertIsInstance(s2, Slice)
        self.assertEqual(s2.start, 3)
        self.assertEqual(s2.end, 4)
        with self.assertRaises(IndexError,
                msg="Cannot index 5 bits into 4-bit value"):
            Const(10)[5]

    def test_getitem_slice(self):
        s1 = Const(10)[1:3]
        self.assertIsInstance(s1, Slice)
        self.assertEqual(s1.start, 1)
        self.assertEqual(s1.end, 3)
        s2 = Const(10)[1:-2]
        self.assertIsInstance(s2, Slice)
        self.assertEqual(s2.start, 1)
        self.assertEqual(s2.end, 2)
        s3 = Const(31)[::2]
        self.assertIsInstance(s3, Cat)
        self.assertIsInstance(s3.parts[0], Slice)
        self.assertEqual(s3.parts[0].start, 0)
        self.assertEqual(s3.parts[0].end, 1)
        self.assertIsInstance(s3.parts[1], Slice)
        self.assertEqual(s3.parts[1].start, 2)
        self.assertEqual(s3.parts[1].end, 3)
        self.assertIsInstance(s3.parts[2], Slice)
        self.assertEqual(s3.parts[2].start, 4)
        self.assertEqual(s3.parts[2].end, 5)

    def test_getitem_wrong(self):
        with self.assertRaises(TypeError,
                msg="Cannot index value with 'str'"):
            Const(31)["str"]


class ConstTestCase(FHDLTestCase):
    def test_shape(self):
        self.assertEqual(Const(0).shape(),   (1, False))
        self.assertEqual(Const(1).shape(),   (1, False))
        self.assertEqual(Const(10).shape(),  (4, False))
        self.assertEqual(Const(-10).shape(), (5, True))

        self.assertEqual(Const(1, 4).shape(),          (4, False))
        self.assertEqual(Const(1, (4, True)).shape(),  (4, True))
        self.assertEqual(Const(0, (0, False)).shape(), (0, False))

    def test_shape_bad(self):
        with self.assertRaises(TypeError,
                msg="Width must be a non-negative integer, not '-1'"):
            Const(1, -1)

    def test_normalization(self):
        self.assertEqual(Const(0b10110, (5, True)).value, -10)

    def test_value(self):
        self.assertEqual(Const(10).value, 10)

    def test_repr(self):
        self.assertEqual(repr(Const(10)),  "(const 4'd10)")
        self.assertEqual(repr(Const(-10)), "(const 5'sd-10)")

    def test_hash(self):
        with self.assertRaises(TypeError):
            hash(Const(0))


class OperatorTestCase(FHDLTestCase):
    def test_bool(self):
        v = Const(0, 4).bool()
        self.assertEqual(repr(v), "(b (const 4'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_invert(self):
        v = ~Const(0, 4)
        self.assertEqual(repr(v), "(~ (const 4'd0))")
        self.assertEqual(v.shape(), (4, False))

    def test_neg(self):
        v1 = -Const(0, (4, False))
        self.assertEqual(repr(v1), "(- (const 4'd0))")
        self.assertEqual(v1.shape(), (5, True))
        v2 = -Const(0, (4, True))
        self.assertEqual(repr(v2), "(- (const 4'sd0))")
        self.assertEqual(v2.shape(), (4, True))

    def test_add(self):
        v1 = Const(0, (4, False)) + Const(0, (6, False))
        self.assertEqual(repr(v1), "(+ (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (7, False))
        v2 = Const(0, (4, True)) + Const(0, (6, True))
        self.assertEqual(v2.shape(), (7, True))
        v3 = Const(0, (4, True)) + Const(0, (4, False))
        self.assertEqual(v3.shape(), (6, True))
        v4 = Const(0, (4, False)) + Const(0, (4, True))
        self.assertEqual(v4.shape(), (6, True))
        v5 = 10 + Const(0, 4)
        self.assertEqual(v5.shape(), (5, False))

    def test_sub(self):
        v1 = Const(0, (4, False)) - Const(0, (6, False))
        self.assertEqual(repr(v1), "(- (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (7, False))
        v2 = Const(0, (4, True)) - Const(0, (6, True))
        self.assertEqual(v2.shape(), (7, True))
        v3 = Const(0, (4, True)) - Const(0, (4, False))
        self.assertEqual(v3.shape(), (6, True))
        v4 = Const(0, (4, False)) - Const(0, (4, True))
        self.assertEqual(v4.shape(), (6, True))
        v5 = 10 - Const(0, 4)
        self.assertEqual(v5.shape(), (5, False))

    def test_mul(self):
        v1 = Const(0, (4, False)) * Const(0, (6, False))
        self.assertEqual(repr(v1), "(* (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (10, False))
        v2 = Const(0, (4, True)) * Const(0, (6, True))
        self.assertEqual(v2.shape(), (10, True))
        v3 = Const(0, (4, True)) * Const(0, (4, False))
        self.assertEqual(v3.shape(), (8, True))
        v5 = 10 * Const(0, 4)
        self.assertEqual(v5.shape(), (8, False))

    def test_and(self):
        v1 = Const(0, (4, False)) & Const(0, (6, False))
        self.assertEqual(repr(v1), "(& (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (6, False))
        v2 = Const(0, (4, True)) & Const(0, (6, True))
        self.assertEqual(v2.shape(), (6, True))
        v3 = Const(0, (4, True)) & Const(0, (4, False))
        self.assertEqual(v3.shape(), (5, True))
        v4 = Const(0, (4, False)) & Const(0, (4, True))
        self.assertEqual(v4.shape(), (5, True))
        v5 = 10 & Const(0, 4)
        self.assertEqual(v5.shape(), (4, False))

    def test_or(self):
        v1 = Const(0, (4, False)) | Const(0, (6, False))
        self.assertEqual(repr(v1), "(| (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (6, False))
        v2 = Const(0, (4, True)) | Const(0, (6, True))
        self.assertEqual(v2.shape(), (6, True))
        v3 = Const(0, (4, True)) | Const(0, (4, False))
        self.assertEqual(v3.shape(), (5, True))
        v4 = Const(0, (4, False)) | Const(0, (4, True))
        self.assertEqual(v4.shape(), (5, True))
        v5 = 10 | Const(0, 4)
        self.assertEqual(v5.shape(), (4, False))

    def test_xor(self):
        v1 = Const(0, (4, False)) ^ Const(0, (6, False))
        self.assertEqual(repr(v1), "(^ (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (6, False))
        v2 = Const(0, (4, True)) ^ Const(0, (6, True))
        self.assertEqual(v2.shape(), (6, True))
        v3 = Const(0, (4, True)) ^ Const(0, (4, False))
        self.assertEqual(v3.shape(), (5, True))
        v4 = Const(0, (4, False)) ^ Const(0, (4, True))
        self.assertEqual(v4.shape(), (5, True))
        v5 = 10 ^ Const(0, 4)
        self.assertEqual(v5.shape(), (4, False))

    def test_shl(self):
        v1 = Const(1, 4) << Const(4)
        self.assertEqual(repr(v1), "(<< (const 4'd1) (const 3'd4))")
        self.assertEqual(v1.shape(), (11, False))
        v2 = Const(1, 4) << Const(-3)
        self.assertEqual(v2.shape(), (7, False))

    def test_shr(self):
        v1 = Const(1, 4) >> Const(4)
        self.assertEqual(repr(v1), "(>> (const 4'd1) (const 3'd4))")
        self.assertEqual(v1.shape(), (4, False))
        v2 = Const(1, 4) >> Const(-3)
        self.assertEqual(v2.shape(), (8, False))

    def test_lt(self):
        v = Const(0, 4) < Const(0, 6)
        self.assertEqual(repr(v), "(< (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_le(self):
        v = Const(0, 4) <= Const(0, 6)
        self.assertEqual(repr(v), "(<= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_gt(self):
        v = Const(0, 4) > Const(0, 6)
        self.assertEqual(repr(v), "(> (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_ge(self):
        v = Const(0, 4) >= Const(0, 6)
        self.assertEqual(repr(v), "(>= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_eq(self):
        v = Const(0, 4) == Const(0, 6)
        self.assertEqual(repr(v), "(== (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_ne(self):
        v = Const(0, 4) != Const(0, 6)
        self.assertEqual(repr(v), "(!= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_mux(self):
        s  = Const(0)
        v1 = Mux(s, Const(0, (4, False)), Const(0, (6, False)))
        self.assertEqual(repr(v1), "(m (const 1'd0) (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (6, False))
        v2 = Mux(s, Const(0, (4, True)), Const(0, (6, True)))
        self.assertEqual(v2.shape(), (6, True))
        v3 = Mux(s, Const(0, (4, True)), Const(0, (4, False)))
        self.assertEqual(v3.shape(), (5, True))
        v4 = Mux(s, Const(0, (4, False)), Const(0, (4, True)))
        self.assertEqual(v4.shape(), (5, True))

    def test_mux_wide(self):
        s = Const(0b100)
        v = Mux(s, Const(0, (4, False)), Const(0, (6, False)))
        self.assertEqual(repr(v), "(m (b (const 3'd4)) (const 4'd0) (const 6'd0))")

    def test_bool(self):
        v = Const(0).bool()
        self.assertEqual(repr(v), "(b (const 1'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_any(self):
        v = Const(0b101).any()
        self.assertEqual(repr(v), "(r| (const 3'd5))")

    def test_all(self):
        v = Const(0b101).all()
        self.assertEqual(repr(v), "(r& (const 3'd5))")

    def test_xor(self):
        v = Const(0b101).xor()
        self.assertEqual(repr(v), "(r^ (const 3'd5))")

    def test_matches(self):
        s = Signal(4)
        self.assertRepr(s.matches(), "(const 1'd0)")
        self.assertRepr(s.matches(1), """
        (== (sig s) (const 1'd1))
        """)
        self.assertRepr(s.matches(0, 1), """
        (r| (cat (== (sig s) (const 1'd0)) (== (sig s) (const 1'd1))))
        """)
        self.assertRepr(s.matches("10--"), """
        (== (& (sig s) (const 4'd12)) (const 4'd8))
        """)

    def test_matches_enum(self):
        s = Signal.enum(SignedEnum)
        self.assertRepr(s.matches(SignedEnum.FOO), """
        (== (& (sig s) (const 2'd3)) (const 2'd3))
        """)

    def test_matches_width_wrong(self):
        s = Signal(4)
        with self.assertRaises(SyntaxError,
                msg="Match pattern '--' must have the same width as match value (which is 4)"):
            s.matches("--")
        with self.assertWarns(SyntaxWarning,
                msg="Match pattern '10110' is wider than match value (which has width 4); "
                    "comparison will never be true"):
            s.matches(0b10110)

    def test_matches_bits_wrong(self):
        s = Signal(4)
        with self.assertRaises(SyntaxError,
                msg="Match pattern 'abc' must consist of 0, 1, and - (don't care) bits"):
            s.matches("abc")

    def test_matches_pattern_wrong(self):
        s = Signal(4)
        with self.assertRaises(SyntaxError,
                msg="Match pattern must be an integer, a string, or an enumeration, not 1.0"):
            s.matches(1.0)

    def test_hash(self):
        with self.assertRaises(TypeError):
            hash(Const(0) + Const(0))


class SliceTestCase(FHDLTestCase):
    def test_shape(self):
        s1 = Const(10)[2]
        self.assertEqual(s1.shape(), (1, False))
        s2 = Const(-10)[0:2]
        self.assertEqual(s2.shape(), (2, False))

    def test_start_end_negative(self):
        c  = Const(0, 8)
        s1 = Slice(c, 0, -1)
        self.assertEqual((s1.start, s1.end), (0, 7))
        s1 = Slice(c, -4, -1)
        self.assertEqual((s1.start, s1.end), (4, 7))

    def test_start_end_wrong(self):
        with self.assertRaises(TypeError,
                msg="Slice start must be an integer, not ''x''"):
            Slice(0, "x", 1)
        with self.assertRaises(TypeError,
                msg="Slice end must be an integer, not ''x''"):
            Slice(0, 1, "x")

    def test_start_end_out_of_range(self):
        c = Const(0, 8)
        with self.assertRaises(IndexError,
                msg="Cannot start slice 10 bits into 8-bit value"):
            Slice(c, 10, 12)
        with self.assertRaises(IndexError,
                msg="Cannot end slice 12 bits into 8-bit value"):
            Slice(c, 0, 12)
        with self.assertRaises(IndexError,
                msg="Slice start 4 must be less than slice end 2"):
            Slice(c, 4, 2)

    def test_repr(self):
        s1 = Const(10)[2]
        self.assertEqual(repr(s1), "(slice (const 4'd10) 2:3)")


class BitSelectTestCase(FHDLTestCase):
    def setUp(self):
        self.c = Const(0, 8)
        self.s = Signal.range(self.c.width)

    def test_shape(self):
        s1 = self.c.bit_select(self.s, 2)
        self.assertEqual(s1.shape(), (2, False))
        s2 = self.c.bit_select(self.s, 0)
        self.assertEqual(s2.shape(), (0, False))

    def test_stride(self):
        s1 = self.c.bit_select(self.s, 2)
        self.assertEqual(s1.stride, 1)

    def test_width_bad(self):
        with self.assertRaises(TypeError):
            self.c.bit_select(self.s, -1)

    def test_repr(self):
        s = self.c.bit_select(self.s, 2)
        self.assertEqual(repr(s), "(part (const 8'd0) (sig s) 2 1)")


class WordSelectTestCase(FHDLTestCase):
    def setUp(self):
        self.c = Const(0, 8)
        self.s = Signal.range(self.c.width)

    def test_shape(self):
        s1 = self.c.word_select(self.s, 2)
        self.assertEqual(s1.shape(), (2, False))

    def test_stride(self):
        s1 = self.c.word_select(self.s, 2)
        self.assertEqual(s1.stride, 2)

    def test_width_bad(self):
        with self.assertRaises(TypeError):
            self.c.word_select(self.s, 0)
        with self.assertRaises(TypeError):
            self.c.word_select(self.s, -1)

    def test_repr(self):
        s = self.c.word_select(self.s, 2)
        self.assertEqual(repr(s), "(part (const 8'd0) (sig s) 2 2)")


class CatTestCase(FHDLTestCase):
    def test_shape(self):
        c0 = Cat()
        self.assertEqual(c0.shape(), (0, False))
        c1 = Cat(Const(10))
        self.assertEqual(c1.shape(), (4, False))
        c2 = Cat(Const(10), Const(1))
        self.assertEqual(c2.shape(), (5, False))
        c3 = Cat(Const(10), Const(1), Const(0))
        self.assertEqual(c3.shape(), (6, False))

    def test_repr(self):
        c1 = Cat(Const(10), Const(1))
        self.assertEqual(repr(c1), "(cat (const 4'd10) (const 1'd1))")


class ReplTestCase(FHDLTestCase):
    def test_shape(self):
        s1 = Repl(Const(10), 3)
        self.assertEqual(s1.shape(), (12, False))
        s2 = Repl(Const(10), 0)
        self.assertEqual(s2.shape(), (0, False))

    def test_count_wrong(self):
        with self.assertRaises(TypeError):
            Repl(Const(10), -1)
        with self.assertRaises(TypeError):
            Repl(Const(10), "str")

    def test_repr(self):
        s = Repl(Const(10), 3)
        self.assertEqual(repr(s), "(repl (const 4'd10) 3)")


class ArrayTestCase(FHDLTestCase):
    def test_acts_like_array(self):
        a = Array([1,2,3])
        self.assertSequenceEqual(a, [1,2,3])
        self.assertEqual(a[1], 2)
        a[1] = 4
        self.assertSequenceEqual(a, [1,4,3])
        del a[1]
        self.assertSequenceEqual(a, [1,3])
        a.insert(1, 2)
        self.assertSequenceEqual(a, [1,2,3])

    def test_becomes_immutable(self):
        a = Array([1,2,3])
        s1 = Signal.range(len(a))
        s2 = Signal.range(len(a))
        v1 = a[s1]
        v2 = a[s2]
        with self.assertRaisesRegex(ValueError,
                regex=r"^Array can no longer be mutated after it was indexed with a value at "):
            a[1] = 2
        with self.assertRaisesRegex(ValueError,
                regex=r"^Array can no longer be mutated after it was indexed with a value at "):
            del a[1]
        with self.assertRaisesRegex(ValueError,
                regex=r"^Array can no longer be mutated after it was indexed with a value at "):
            a.insert(1, 2)

    def test_repr(self):
        a = Array([1,2,3])
        self.assertEqual(repr(a), "(array mutable [1, 2, 3])")
        s = Signal.range(len(a))
        v = a[s]
        self.assertEqual(repr(a), "(array [1, 2, 3])")


class ArrayProxyTestCase(FHDLTestCase):
    def test_index_shape(self):
        m = Array(Array(x * y for y in range(1, 4)) for x in range(1, 4))
        a = Signal.range(3)
        b = Signal.range(3)
        v = m[a][b]
        self.assertEqual(v.shape(), (4, False))

    def test_attr_shape(self):
        from collections import namedtuple
        pair = namedtuple("pair", ("p", "n"))
        a = Array(pair(i, -i) for i in range(10))
        s = Signal.range(len(a))
        v = a[s]
        self.assertEqual(v.p.shape(), (4, False))
        self.assertEqual(v.n.shape(), (6, True))

    def test_repr(self):
        a = Array([1, 2, 3])
        s = Signal.range(3)
        v = a[s]
        self.assertEqual(repr(v), "(proxy (array [1, 2, 3]) (sig s))")


class SignalTestCase(FHDLTestCase):
    def test_shape(self):
        s1 = Signal()
        self.assertEqual(s1.shape(), (1, False))
        s2 = Signal(2)
        self.assertEqual(s2.shape(), (2, False))
        s3 = Signal((2, False))
        self.assertEqual(s3.shape(), (2, False))
        s4 = Signal((2, True))
        self.assertEqual(s4.shape(), (2, True))
        s5 = Signal(0)
        self.assertEqual(s5.shape(), (0, False))
        s6 = Signal.range(16)
        self.assertEqual(s6.shape(), (4, False))
        s7 = Signal.range(4, 16)
        self.assertEqual(s7.shape(), (4, False))
        s8 = Signal.range(-4, 16)
        self.assertEqual(s8.shape(), (5, True))
        s9 = Signal.range(-20, 16)
        self.assertEqual(s9.shape(), (6, True))
        s10 = Signal.range(0)
        self.assertEqual(s10.shape(), (1, False))
        s11 = Signal.range(1)
        self.assertEqual(s11.shape(), (1, False))
        # deprecated
        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore", category=DeprecationWarning)
            d6 = Signal(max=16)
            self.assertEqual(d6.shape(), (4, False))
            d7 = Signal(min=4, max=16)
            self.assertEqual(d7.shape(), (4, False))
            d8 = Signal(min=-4, max=16)
            self.assertEqual(d8.shape(), (5, True))
            d9 = Signal(min=-20, max=16)
            self.assertEqual(d9.shape(), (6, True))
            d10 = Signal(max=1)
            self.assertEqual(d10.shape(), (0, False))

    def test_shape_bad(self):
        with self.assertRaises(TypeError,
                msg="Width must be a non-negative integer, not '-10'"):
            Signal(-10)

    def test_min_max_deprecated(self):
        with self.assertWarns(DeprecationWarning,
                msg="instead of `Signal(min=0, max=10)`, use `Signal.range(0, 10)`"):
            Signal(max=10)
        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore", category=DeprecationWarning)
            with self.assertRaises(ValueError,
                    msg="Lower bound 10 should be less or equal to higher bound 4"):
                Signal(min=10, max=4)
            with self.assertRaises(ValueError,
                    msg="Only one of bits/signedness or bounds may be specified"):
                Signal(2, min=10)

    def test_name(self):
        s1 = Signal()
        self.assertEqual(s1.name, "s1")
        s2 = Signal(name="sig")
        self.assertEqual(s2.name, "sig")

    def test_reset(self):
        s1 = Signal(4, reset=0b111, reset_less=True)
        self.assertEqual(s1.reset, 0b111)
        self.assertEqual(s1.reset_less, True)

    def test_reset_narrow(self):
        with self.assertWarns(SyntaxWarning,
                msg="Reset value 8 requires 4 bits to represent, but the signal only has 3 bits"):
            Signal(3, reset=8)
        with self.assertWarns(SyntaxWarning,
                msg="Reset value 4 requires 4 bits to represent, but the signal only has 3 bits"):
            Signal((3, True), reset=4)
        with self.assertWarns(SyntaxWarning,
                msg="Reset value -5 requires 4 bits to represent, but the signal only has 3 bits"):
            Signal((3, True), reset=-5)

    def test_attrs(self):
        s1 = Signal()
        self.assertEqual(s1.attrs, {})
        s2 = Signal(attrs={"no_retiming": True})
        self.assertEqual(s2.attrs, {"no_retiming": True})

    def test_repr(self):
        s1 = Signal()
        self.assertEqual(repr(s1), "(sig s1)")

    def test_like(self):
        s1 = Signal.like(Signal(4))
        self.assertEqual(s1.shape(), (4, False))
        s2 = Signal.like(Signal.range(-15, 1))
        self.assertEqual(s2.shape(), (5, True))
        s3 = Signal.like(Signal(4, reset=0b111, reset_less=True))
        self.assertEqual(s3.reset, 0b111)
        self.assertEqual(s3.reset_less, True)
        s4 = Signal.like(Signal(attrs={"no_retiming": True}))
        self.assertEqual(s4.attrs, {"no_retiming": True})
        s5 = Signal.like(Signal(decoder=str))
        self.assertEqual(s5.decoder, str)
        s6 = Signal.like(10)
        self.assertEqual(s6.shape(), (4, False))
        s7 = [Signal.like(Signal(4))][0]
        self.assertEqual(s7.name, "$like")
        s8 = Signal.like(s1, name_suffix="_ff")
        self.assertEqual(s8.name, "s1_ff")

    def test_decoder(self):
        class Color(Enum):
            RED  = 1
            BLUE = 2
        s = Signal(decoder=Color)
        self.assertEqual(s.decoder(1), "RED/1")
        self.assertEqual(s.decoder(3), "3")

    def test_enum(self):
        s1 = Signal.enum(UnsignedEnum)
        self.assertEqual(s1.shape(), (2, False))
        s2 = Signal.enum(SignedEnum)
        self.assertEqual(s2.shape(), (2, True))
        self.assertEqual(s2.decoder(SignedEnum.FOO), "FOO/-1")


class ClockSignalTestCase(FHDLTestCase):
    def test_domain(self):
        s1 = ClockSignal()
        self.assertEqual(s1.domain, "sync")
        s2 = ClockSignal("pix")
        self.assertEqual(s2.domain, "pix")

        with self.assertRaises(TypeError,
                msg="Clock domain name must be a string, not '1'"):
            ClockSignal(1)

    def test_shape(self):
        self.assertEqual(ClockSignal().shape(), (1, False))

    def test_repr(self):
        s1 = ClockSignal()
        self.assertEqual(repr(s1), "(clk sync)")

    def test_wrong_name_comb(self):
        with self.assertRaises(ValueError,
                msg="Domain 'comb' does not have a clock"):
            ClockSignal("comb")


class ResetSignalTestCase(FHDLTestCase):
    def test_domain(self):
        s1 = ResetSignal()
        self.assertEqual(s1.domain, "sync")
        s2 = ResetSignal("pix")
        self.assertEqual(s2.domain, "pix")

        with self.assertRaises(TypeError,
                msg="Clock domain name must be a string, not '1'"):
            ResetSignal(1)

    def test_shape(self):
        self.assertEqual(ResetSignal().shape(), (1, False))

    def test_repr(self):
        s1 = ResetSignal()
        self.assertEqual(repr(s1), "(rst sync)")

    def test_wrong_name_comb(self):
        with self.assertRaises(ValueError,
                msg="Domain 'comb' does not have a reset"):
            ResetSignal("comb")


class MockUserValue(UserValue):
    def __init__(self, lowered):
        super().__init__()
        self.lower_count = 0
        self.lowered     = lowered

    def lower(self):
        self.lower_count += 1
        return self.lowered


class UserValueTestCase(FHDLTestCase):
    def test_shape(self):
        uv = MockUserValue(1)
        self.assertEqual(uv.shape(), (1, False))
        uv.lowered = 2
        self.assertEqual(uv.shape(), (1, False))
        self.assertEqual(uv.lower_count, 1)


class SampleTestCase(FHDLTestCase):
    def test_const(self):
        s = Sample(1, 1, "sync")
        self.assertEqual(s.shape(), (1, False))

    def test_signal(self):
        s1 = Sample(Signal(2), 1, "sync")
        self.assertEqual(s1.shape(), (2, False))
        s2 = Sample(ClockSignal(), 1, "sync")
        s3 = Sample(ResetSignal(), 1, "sync")

    def test_wrong_value_operator(self):
        with self.assertRaises(TypeError,
                "Sampled value must be a signal or a constant, not "
                "(+ (sig $signal) (const 1'd1))"):
            Sample(Signal() + 1, 1, "sync")

    def test_wrong_clocks_neg(self):
        with self.assertRaises(ValueError,
                "Cannot sample a value 1 cycles in the future"):
            Sample(Signal(), -1, "sync")

    def test_wrong_domain(self):
        with self.assertRaises(TypeError,
                "Domain name must be a string or None, not 0"):
            Sample(Signal(), 1, 0)


class InitialTestCase(FHDLTestCase):
    def test_initial(self):
        i = Initial()
        self.assertEqual(i.shape(), (1, False))
