from abc import abstractproperty

from ..hdl.ast import *
from ..hdl.dsl import *
from ..hdl.ir import *
from ..hdl.cd import *
from ..build import *


__all__ = ["Xilinx7SeriesPlatform"]


class Xilinx7SeriesPlatform(TemplatedPlatform):
    """
    Required tools:
        * ``vivado``

    The environment is populated by running the script specified in the environment variable
    ``NMIGEN_Vivado_env``, if present.

    Available overrides:
        * ``script_after_read``: inserts commands after ``read_xdc`` in Tcl script.
        * ``script_after_synth``: inserts commands after ``synth_design`` in Tcl script.
        * ``script_after_place``: inserts commands after ``place_design`` in Tcl script.
        * ``script_after_route``: inserts commands after ``route_design`` in Tcl script.
        * ``script_before_bitstream``: inserts commands before ``write_bitstream`` in Tcl script.
        * ``script_after_bitstream``: inserts commands after ``write_bitstream`` in Tcl script.
        * ``add_constraints``: inserts commands in XDC file.
        * ``vivado_opts``: adds extra options for Vivado.
        * ``write_bitstream_opts``: add extra options for ``write_bitstream``.

    Build products:
        * ``{{name}}.log``: Vivado log.
        * ``{{name}}_timing_synth.rpt``: Vivado report.
        * ``{{name}}_utilization_hierarchical_synth.rpt``: Vivado report.
        * ``{{name}}_utilization_synth.rpt``: Vivado report.
        * ``{{name}}_utilization_hierarchical_place.rpt``: Vivado report.
        * ``{{name}}_utilization_place.rpt``: Vivado report.
        * ``{{name}}_io.rpt``: Vivado report.
        * ``{{name}}_control_sets.rpt``: Vivado report.
        * ``{{name}}_clock_utilization.rpt``:  Vivado report.
        * ``{{name}}_route_status.rpt``: Vivado report.
        * ``{{name}}_drc.rpt``: Vivado report.
        * ``{{name}}_timing.rpt``: Vivado report.
        * ``{{name}}_power.rpt``: Vivado report.
        * ``{{name}}_route.dcp``: Vivado design checkpoint.
        * ``{{name}}.bit``: binary bitstream.
    """

    toolchain = "Vivado"

    device  = abstractproperty()
    package = abstractproperty()
    speed   = abstractproperty()

    file_templates = {
        **TemplatedPlatform.build_script_templates,
        "{{name}}.v": r"""
            /* {{autogenerated}} */
            {{emit_design("verilog")}}
        """,
        "{{name}}.tcl": r"""
            # {{autogenerated}}
            create_project -force -name {{name}} -part {{platform.device}}{{platform.package}}-{{platform.speed}}
            {% for file in platform.iter_extra_files(".v", ".sv", ".vhd", ".vhdl") -%}
                add_files {{file}}
            {% endfor %}
            add_files {{name}}.v
            read_xdc {{name}}.xdc
            {% for file in platform.iter_extra_files(".xdc") -%}
                read_xdc {{file}}
            {% endfor %}
            {{get_override("script_after_read")|default("# (script_after_read placeholder)")}}
            synth_design -top {{name}} -part {{platform.device}}{{platform.package}}-{{platform.speed}}
            {{get_override("script_after_synth")|default("# (script_after_synth placeholder)")}}
            report_timing_summary -file {{name}}_timing_synth.rpt
            report_utilization -hierarchical -file {{name}}_utilization_hierachical_synth.rpt
            report_utilization -file {{name}}_utilization_synth.rpt
            opt_design
            place_design
            {{get_override("script_after_place")|default("# (script_after_place placeholder)")}}
            report_utilization -hierarchical -file {{name}}_utilization_hierarchical_place.rpt
            report_utilization -file {{name}}_utilization_place.rpt
            report_io -file {{name}}_io.rpt
            report_control_sets -verbose -file {{name}}_control_sets.rpt
            report_clock_utilization -file {{name}}_clock_utilization.rpt
            route_design
            {{get_override("script_after_route")|default("# (script_after_route placeholder)")}}
            phys_opt_design
            report_timing_summary -no_header -no_detailed_paths
            write_checkpoint -force {{name}}_route.dcp
            report_route_status -file {{name}}_route_status.rpt
            report_drc -file {{name}}_drc.rpt
            report_timing_summary -datasheet -max_paths 10 -file {{name}}_timing.rpt
            report_power -file {{name}}_power.rpt
            {{get_override("script_before_bitstream")|default("# (script_before_bitstream placeholder)")}}
            write_bitstream -force {{get_override("write_bitstream_opts")|join(" ")}} {{name}}.bit
            {{get_override("script_after_bitstream")|default("# (script_after_bitstream placeholder)")}}
            quit
        """,
        "{{name}}.xdc": r"""
            # {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                set_property PACKAGE_PIN {{pin_name}} [get_ports {{port_name}}]
                {% for attr_name, attr_value in attrs.items() -%}
                    set_property {{attr_name}} {{attr_value}} [get_ports {{port_name}}]
                {% endfor %}
            {% endfor %}
            {% for signal, frequency in platform.iter_clock_constraints() -%}
                create_clock -name {{signal.name}} -period {{1000000000/frequency}} [get_ports {{signal.name}}]
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """
    }
    command_templates = [
        r"""
        {{get_tool("vivado")}}
            {{verbose("-verbose")}}
            {{get_override("vivado_opts")|options}}
            -mode batch
            -log {{name}}.log
            -source {{name}}.tcl
        """
    ]

    def _get_xdr_buffer(self, m, pin, i_invert=None, o_invert=None):
        def get_dff(clk, d, q):
            # SDR I/O is performed by packing a flip-flop into the pad IOB.
            for bit in range(len(q)):
                _q = Signal()
                _q.attrs["IOB"] = "TRUE"
                # XXX: Vivado 2019.1 seems to make this flip-flop ineligible for IOB packing
                # unless we prevent it from being optimized.
                _q.attrs["DONT_TOUCH"] = "TRUE"
                m.submodules += Instance("FDCE",
                    i_C=clk,
                    i_CE=Const(1),
                    i_CLR=Const(0),
                    i_D=d[bit],
                    o_Q=_q
                )
                m.d.comb += q[bit].eq(_q)

        def get_iddr(clk, d, q1, q2):
            for bit in range(len(q1)):
                m.submodules += Instance("IDDR",
                    p_DDR_CLK_EDGE="SAME_EDGE_PIPELINED",
                    p_SRTYPE="ASYNC",
                    p_INIT_Q1=0, p_INIT_Q2=0,
                    i_C=clk,
                    i_CE=Const(1),
                    i_S=Const(0), i_R=Const(0),
                    i_D=d[bit],
                    o_Q1=q1[bit], o_Q2=q2[bit]
                )

        def get_oddr(clk, d1, d2, q):
            for bit in range(len(q)):
                m.submodules += Instance("ODDR",
                    p_DDR_CLK_EDGE="SAME_EDGE",
                    p_SRTYPE="ASYNC",
                    p_INIT=0,
                    i_C=clk,
                    i_CE=Const(1),
                    i_S=Const(0), i_R=Const(0),
                    i_D1=d1[bit], i_D2=d2[bit],
                    o_Q=q[bit]
                )

        def get_ixor(y, invert):
            if invert is None:
                return y
            else:
                a = Signal.like(y, name_suffix="_x{}".format(1 if invert else 0))
                for bit in range(len(y)):
                    m.submodules += Instance("LUT1",
                        p_INIT=0b01 if invert else 0b10,
                        i_I0=a[bit],
                        o_O=y[bit]
                    )
                return a

        def get_oxor(a, invert):
            if invert is None:
                return a
            else:
                y = Signal.like(a, name_suffix="_x{}".format(1 if invert else 0))
                for bit in range(len(a)):
                    m.submodules += Instance("LUT1",
                        p_INIT=0b01 if invert else 0b10,
                        i_I0=a[bit],
                        o_O=y[bit]
                    )
                return y

        if "i" in pin.dir:
            if pin.xdr < 2:
                pin_i  = get_ixor(pin.i, i_invert)
            elif pin.xdr == 2:
                pin_i0 = get_ixor(pin.i0, i_invert)
                pin_i1 = get_ixor(pin.i1, i_invert)
        if "o" in pin.dir:
            if pin.xdr < 2:
                pin_o  = get_oxor(pin.o, o_invert)
            elif pin.xdr == 2:
                pin_o0 = get_oxor(pin.o0, o_invert)
                pin_o1 = get_oxor(pin.o1, o_invert)

        i = o = t = None
        if "i" in pin.dir:
            i = Signal(pin.width, name="{}_xdr_i".format(pin.name))
        if "o" in pin.dir:
            o = Signal(pin.width, name="{}_xdr_o".format(pin.name))
        if pin.dir in ("oe", "io"):
            t = Signal(1,         name="{}_xdr_t".format(pin.name))

        if pin.xdr == 0:
            if "i" in pin.dir:
                i = pin_i
            if "o" in pin.dir:
                o = pin_o
            if pin.dir in ("oe", "io"):
                t = ~pin.oe
        elif pin.xdr == 1:
            if "i" in pin.dir:
                get_dff(pin.i_clk, i, pin_i)
            if "o" in pin.dir:
                get_dff(pin.o_clk, pin_o, o)
            if pin.dir in ("oe", "io"):
                get_dff(pin.o_clk, ~pin.oe, t)
        elif pin.xdr == 2:
            if "i" in pin.dir:
                get_iddr(pin.i_clk, i, pin_i0, pin_i1)
            if "o" in pin.dir:
                get_oddr(pin.o_clk, pin_o0, pin_o1, o)
            if pin.dir in ("oe", "io"):
                get_dff(pin.o_clk, ~pin.oe, t)
        else:
            assert False

        return (i, o, t)

    def get_input(self, pin, port, attrs, invert):
        self._check_feature("single-ended input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=True if invert else None)
        for bit in range(len(port)):
            m.submodules[pin.name] = Instance("IBUF",
                i_I=port[bit],
                o_O=i[bit]
            )
        return m

    def get_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=True if invert else None)
        for bit in range(len(port)):
            m.submodules[pin.name] = Instance("OBUF",
                i_I=o[bit],
                o_O=port[bit]
            )
        return m

    def get_tristate(self, pin, port, attrs, invert):
        self._check_feature("single-ended tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=True if invert else None)
        for bit in range(len(port)):
            m.submodules[pin.name] = Instance("OBUFT",
                i_T=t,
                i_I=o[bit],
                o_O=port[bit]
            )
        return m

    def get_input_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=True if invert else None,
                                               o_invert=True if invert else None)
        for bit in range(len(port)):
            m.submodules[pin.name] = Instance("IOBUF",
                i_T=t,
                i_I=o[bit],
                o_O=i[bit],
                io_IO=port[bit]
            )
        return m

    def get_diff_input(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=True if invert else None)
        for bit in range(len(p_port)):
            m.submodules[pin.name] = Instance("IBUFDS",
                i_I=p_port[bit], i_IB=n_port[bit],
                o_O=i[bit]
            )
        return m

    def get_diff_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=True if invert else None)
        for bit in range(len(p_port)):
            m.submodules[pin.name] = Instance("OBUFDS",
                i_I=o[bit],
                o_O=p_port[bit], o_OB=n_port[bit]
            )
        return m

    def get_diff_tristate(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=True if invert else None)
        for bit in range(len(p_port)):
            m.submodules[pin.name] = Instance("OBUFTDS",
                i_T=t,
                i_I=o[bit],
                o_O=p_port[bit], o_OB=n_port[bit]
            )
        return m

    def get_diff_input_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=True if invert else None,
                                               o_invert=True if invert else None)
        for bit in range(len(p_port)):
            m.submodules[pin.name] = Instance("IOBUFDS",
                i_T=t,
                i_I=o[bit],
                o_O=i[bit],
                io_IO=p_port[bit], io_IOB=n_port[bit]
            )
        return m

    def get_multi_reg(self, multireg):
        m = Module()
        dest_sync_ff = len(multireg._regs)
        if dest_sync_ff not in range(2, 11):
            raise ValueError(
                "allowed values for stages: [2, 10], got {}".format(dest_sync_ff))

        m.submodules += Instance(
            "xpm_cdc_array_single",
            p_DEST_SYNC_FF=dest_sync_ff,
            p_SRC_INPUT_REG=0,
            p_WIDTH=len(multireg.i),
            i_dest_clk=ClockSignal(multireg.odomain),
            o_dest_out=multireg.o,
            i_src_clk=Const(0),
            i_src_in=multireg.i)
        return m

    def get_pulse_sync(self, pulse_sync):
        m = Module()
        dest_sync_ff = pulse_sync.sync_stages
        if dest_sync_ff not in range(2, 11):
            raise ValueError(
                "allowed values for stages: [2, 10], got {}".format(dest_sync_ff))

        m.submodules += Instance(
            "xpm_cdc_pulse",
            p_DEST_SYNC_FF=dest_sync_ff,
            p_REG_OUTPUT=0,
            p_RST_USED=0,
            i_dest_clk=ClockSignal(pulse_sync.odomain),
            o_dest_pulse=pulse_sync.o,
            i_dest_rst=Const(0),
            i_src_clk=ClockSignal(pulse_sync.idomain),
            i_src_pulse=pulse_sync.i,
            i_src_rst=Const(0))
        return m
