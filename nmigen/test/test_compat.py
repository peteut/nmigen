from ..hdl.ir import Fragment
from ..compat import *
from .tools import *


class CompatTestCase(FHDLTestCase):
    def test_fragment_get(self):
        m = Module()
        f = Fragment.get(m, platform=None)
