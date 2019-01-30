import os
import subprocess

from . import rtlil


__all__ = ["convert"]


class YosysError(Exception):
    pass


def convert(*args, **kwargs):
    with_meta = kwargs.get("with_meta", False)
    try:
        popen = subprocess.Popen([os.getenv("YOSYS", "yosys"), "-q", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8")
    except FileNotFoundError as e:
        if os.getenv("YOSYS"):
            raise YosysError("Could not find Yosys in {} as specified via the YOSYS environment "
                             "variable".format(os.getenv("YOSYS"))) from e
        else:
            raise YosysError("Could not find Yosys in PATH. Place `yosys` in PATH or specify "
                             "path explicitly via the YOSYS environment variable") from e
    if with_meta is True:
        il_text, module_name, port_map = rtlil.convert(*args, **kwargs)
    else:
        il_text = rtlil.convert(*args, **kwargs)

    verilog_text, error = popen.communicate("""
# Convert nMigen's RTLIL to readable Verilog.
read_ilang <<rtlil
{}
rtlil
proc_init
proc_arst
proc_dff
proc_clean
memory_collect
write_verilog -norename
""".format(il_text))
    if popen.returncode:
        raise YosysError(error.strip())
    else:
        if with_meta is True:
            return verilog_text, module_name, port_map
        else:
            return verilog_text
