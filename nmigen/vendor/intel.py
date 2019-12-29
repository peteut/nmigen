from abc import abstractproperty

from ..hdl import *
from ..build import *


__all__ = ["IntelPlatform"]


class IntelPlatform(TemplatedPlatform):
    """
    Required tools:
        * ``quartus_map``
        * ``quartus_fit``
        * ``quartus_asm``
        * ``quartus_sta``

    The environment is populated by running the script specified in the environment variable
    ``NMIGEN_ENV_Quartus``, if present.

    Available overrides:
        * ``nproc``: sets the number of cores used by all tools.
        * ``quartus_map_opts``: adds extra options for ``quartus_map``.
        * ``quartus_fit_opts``: adds extra options for ``quartus_fit``.
        * ``quartus_asm_opts``: adds extra options for ``quartus_asm``.
        * ``quartus_sta_opts``: adds extra options for ``quartus_sta``.

    Build products:
        * ``*.rpt``: toolchain reports.
        * ``{{name}}.sof``: bitstream as SRAM object file.
        * ``{{name}}.rbf``: bitstream as raw binary file.
    """

    toolchain = "Quartus"

    device  = abstractproperty()
    package = abstractproperty()
    speed   = abstractproperty()
    suffix  = ""

    quartus_suppressed_warnings = [
        10264,  # All case item expressions in this case statement are onehot
        10270,  # Incomplete Verilog case statement has no default case item
        10335,  # Unrecognized synthesis attribute
        10763,  # Verilog case statement has overlapping case item expressions with non-constant or don't care bits
        10935,  # Verilog casex/casez overlaps with a previous casex/vasez item expression
        12125,  # Using design file which is not specified as a design file for the current project, but contains definitions used in project
        18236,  # Number of processors not specified in QSF
        292013, # Feature is only available with a valid subscription license
    ]

    required_tools = [
        "quartus_map",
        "quartus_fit",
        "quartus_asm",
        "quartus_sta",
    ]

    file_templates = {
        **TemplatedPlatform.build_script_templates,
        "build_{{name}}.sh": r"""
            # {{autogenerated}}
            if [ -n "${{platform._toolchain_env_var}}" ]; then
                QUARTUS_ROOTDIR=$(dirname $(dirname "${{platform._toolchain_env_var}}"))
                # Quartus' qenv.sh does not work with `set -e`.
                . "${{platform._toolchain_env_var}}"
            fi
            set -e{{verbose("x")}}
            {{emit_commands("sh")}}
        """,
        # Quartus doesn't like constructs like (* keep = 32'd1 *), even though they mean the same
        # thing as (* keep = 1 *); use -decimal to work around that.
        "{{name}}.v": r"""
            /* {{autogenerated}} */
            {{emit_verilog(["-decimal"])}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog(["-decimal"])}}
        """,
        "{{name}}.qsf": r"""
            # {{autogenerated}}
            {% if get_override("nproc") -%}
                set_global_assignment -name NUM_PARALLEL_PROCESSORS {{get_override("nproc")}}
            {% endif %}

            {% for file in platform.iter_extra_files(".v") -%}
                set_global_assignment -name VERILOG_FILE "{{file}}"
            {% endfor %}
            {% for file in platform.iter_extra_files(".sv") -%}
                set_global_assignment -name SYSTEMVERILOG_FILE "{{file}}"
            {% endfor %}
            {% for file in platform.iter_extra_files(".vhd", ".vhdl") -%}
                set_global_assignment -name VHDL_FILE "{{file}}"
            {% endfor %}
            set_global_assignment -name VERILOG_FILE {{name}}.v
            set_global_assignment -name TOP_LEVEL_ENTITY {{name}}

            set_global_assignment -name DEVICE {{platform.device}}{{platform.package}}{{platform.speed}}{{platform.suffix}}
            {% for port_name, pin_name, extras in platform.iter_port_constraints_bits() -%}
                set_location_assignment -to "{{port_name}}" PIN_{{pin_name}}
                {% for key, value in extras.items() -%}
                    set_instance_assignment -to "{{port_name}}" -name {{key}} "{{value}}"
                {% endfor %}
            {% endfor %}

            set_global_assignment -name GENERATE_RBF_FILE ON
        """,
        "{{name}}.sdc": r"""
            {% for signal, frequency in platform.iter_clock_constraints() -%}
                create_clock -period {{1000000000/frequency}} [get_nets {{signal|hierarchy("|")}}]
            {% endfor %}
        """,
        "{{name}}.srf": r"""
            {% for warning in platform.quartus_suppressed_warnings %}
            { "" "" "" "{{name}}.v" {  } {  } 0 {{warning}} "" 0 0 "Design Software" 0 -1 0 ""}
            {% endfor %}
        """,      
    }
    command_templates = [
        r"""
        {{invoke_tool("quartus_map")}}
            {{get_override("quartus_map_opts")|options}}
            --rev={{name}} {{name}}
        """,
        r"""
        {{invoke_tool("quartus_fit")}}
            {{get_override("quartus_fit_opts")|options}}
            --rev={{name}} {{name}}
        """,
        r"""
        {{invoke_tool("quartus_asm")}}
            {{get_override("quartus_asm_opts")|options}}
            --rev={{name}} {{name}}
        """,
        r"""
        {{invoke_tool("quartus_sta")}}
            {{get_override("quartus_sta_opts")|options}}
            --rev={{name}} {{name}}
        """,
    ]

    def add_clock_constraint(self, clock, frequency):
        super().add_clock_constraint(clock, frequency)
        # Make sure the net constrained in the SDC file is kept through synthesis; it is redundant
        # after Quartus flattens the hierarchy and will be eliminated if not explicitly kept.
        clock.attrs["keep"] = 1

    # The altiobuf_* and altddio_* primitives are explained in the following Intel documents:
    # * https://www.intel.com/content/dam/www/programmable/us/en/pdfs/literature/ug/ug_altiobuf.pdf
    # * https://www.intel.com/content/dam/www/programmable/us/en/pdfs/literature/ug/ug_altddio.pdf
    # See also errata mentioned in: https://www.intel.com/content/www/us/en/programmable/support/support-resources/knowledge-base/solutions/rd11192012_735.html.

    @staticmethod
    def _get_ireg(m, pin, invert):
        def get_ineg(i):
            if invert:
                i_neg = Signal.like(i, name_suffix="_neg")
                m.d.comb += i.eq(~i_neg)
                return i_neg
            else:
                return i

        if pin.xdr == 0:
            return get_ineg(pin.i)
        elif pin.xdr == 1:
            i_sdr = Signal(pin.width, name="{}_i_sdr")
            m.submodules += Instance("$dff",
                p_CLK_POLARITY=1,
                p_WIDTH=pin.width,
                i_CLK=pin.i_clk,
                i_D=i_sdr,
                o_Q=get_ineg(pin.i),
            )
            return i_sdr
        elif pin.xdr == 2:
            i_ddr = Signal(pin.width, name="{}_i_ddr".format(pin.name))
            m.submodules["{}_i_ddr".format(pin.name)] = Instance("altddio_in",
                p_width=pin.width,
                i_datain=i_ddr,
                i_inclock=pin.i_clk,
                o_dataout_h=get_ineg(pin.i0),
                o_dataout_l=get_ineg(pin.i1),
            )
            return i_ddr
        assert False

    @staticmethod
    def _get_oreg(m, pin, invert):
        def get_oneg(o):
            if invert:
                o_neg = Signal.like(o, name_suffix="_neg")
                m.d.comb += o_neg.eq(~o)
                return o_neg
            else:
                return o

        if pin.xdr == 0:
            return get_oneg(pin.o)
        elif pin.xdr == 1:
            o_sdr = Signal(pin.width, name="{}_o_sdr".format(pin.name))
            m.submodules += Instance("$dff",
                p_CLK_POLARITY=1,
                p_WIDTH=pin.width,
                i_CLK=pin.o_clk,
                i_D=get_oneg(pin.o),
                o_Q=o_sdr,
            )
            return o_sdr
        elif pin.xdr == 2:
            o_ddr = Signal(pin.width, name="{}_o_ddr".format(pin.name))
            m.submodules["{}_o_ddr".format(pin.name)] = Instance("altddio_out",
                p_width=pin.width,
                o_dataout=o_ddr,
                i_outclock=pin.o_clk,
                i_datain_h=get_oneg(pin.o0),
                i_datain_l=get_oneg(pin.o1),
            )
            return o_ddr
        assert False

    @staticmethod
    def _get_oereg(m, pin):
        if pin.xdr == 0:
            return pin.oe
        elif pin.xdr in (1, 2):
            oe_reg = Signal(pin.width, name="{}_oe_reg".format(pin.name))
            oe_reg.attrs["useioff"] = "1"
            m.submodules += Instance("$dff",
                p_CLK_POLARITY=1,
                p_WIDTH=pin.width,
                i_CLK=pin.o_clk,
                i_D=pin.oe,
                o_Q=oe_reg,
            )
            return oe_reg
        assert False

    def get_input(self, pin, port, attrs, invert):
        self._check_feature("single-ended input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_in",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="FALSE",
            i_datain=port,
            o_dataout=self._get_ireg(m, pin, invert)
        )
        return m

    def get_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_out",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="FALSE",
            p_use_oe="FALSE",
            i_datain=self._get_oreg(m, pin, invert),
            o_dataout=port,
        )
        return m

    def get_tristate(self, pin, port, attrs, invert):
        self._check_feature("single-ended tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_out",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="FALSE",
            p_use_oe="TRUE",
            i_datain=self._get_oreg(m, pin, invert),
            o_dataout=port,
            i_oe=pin.oe,
        )
        return m

    def get_input_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_bidir",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="FALSE",
            i_datain=self._get_oreg(m, pin, invert),
            io_dataio=port,
            o_dataout=self._get_ireg(m, pin, invert),
            i_oe=self._get_oereg(m, pin),
        )
        return m

    def get_diff_input(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            p_port.attrs["useioff"] = 1
            n_port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_in",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="TRUE",
            i_datain=p_port,
            i_datain_b=n_port,
            o_dataout=self._get_ireg(m, pin, invert)
        )
        return m

    def get_diff_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            p_port.attrs["useioff"] = 1
            n_port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_out",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="TRUE",
            p_use_oe="FALSE",
            i_datain=self._get_oreg(m, pin, invert),
            o_dataout=p_port,
            o_dataout_b=n_port,
        )
        return m

    def get_diff_tristate(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            p_port.attrs["useioff"] = 1
            n_port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_out",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="TRUE",
            p_use_oe="TRUE",
            i_datain=self._get_oreg(m, pin, invert),
            o_dataout=p_port,
            o_dataout_b=n_port,
            i_oe=self._get_oereg(m, pin),
        )
        return m

    def get_diff_input_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            p_port.attrs["useioff"] = 1
            n_port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_bidir",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="TRUE",
            i_datain=self._get_oreg(m, pin, invert),
            io_dataio=p_port,
            io_dataio_b=n_port,
            o_dataout=self._get_ireg(m, pin, invert),
            i_oe=self._get_oereg(m, pin),
        )
        return m

    # The altera_std_synchronizer{,_bundle} megafunctions embed SDC constraints that mark false
    # paths, so use them instead of our default implementation.

    def get_ff_sync(self, ff_sync):
        return Instance("altera_std_synchronizer_bundle",
            p_width=len(ff_sync.i),
            p_depth=ff_sync._stages,
            i_clk=ClockSignal(ff_sync._o_domain),
            i_reset_n=Const(1),
            i_din=ff_sync.i,
            o_dout=ff_sync.o,
        )

    def get_reset_sync(self, reset_sync):
        m = Module()
        rst_n = Signal()
        m.submodules += Instance("altera_std_synchronizer",
            p_depth=reset_sync._stages,
            i_clk=ClockSignal(reset_sync._domain),
            i_reset_n=~reset_sync.arst,
            i_din=Const(1),
            o_dout=rst_n,
        )
        m.d.comb += ResetSignal(reset_sync._domain).eq(~rst_n)
        return m
