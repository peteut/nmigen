import argparse
import logging
import sys
import pathlib
from collections import OrderedDict
from edalize import get_edatool

from .back import rtlil, verilog, pysim
from .hdl.ir import Fragment
from .build.platform import get_eda_api

__all__ = ["main"]

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


def main_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    parser.add_argument(
        "--verbose", "-v", action="count", default=1)
    p_action = parser.add_subparsers(dest="action")

    p_generate = p_action.add_parser("generate",
        help="generate RTLIL or Verilog from the design")
    p_generate.add_argument("-t", "--type", dest="generate_type",
        metavar="LANGUAGE", choices=["il", "v"],
        default="v",
        help="generate LANGUAGE (il for RTLIL, v for Verilog; default: %(default)s)")
    p_generate.add_argument("generate_file",
        metavar="FILE", type=argparse.FileType("w"), nargs="?",
        help="write generated code to FILE")

    p_simulate = p_action.add_parser(
        "simulate", help="simulate the design")
    p_simulate.add_argument("-v", "--vcd-file",
        metavar="VCD-FILE", type=argparse.FileType("w"),
        help="write execution trace to VCD-FILE")
    p_simulate.add_argument("-w", "--gtkw-file",
        metavar="GTKW-FILE", type=argparse.FileType("w"),
        help="write GTKWave configuration to GTKW-FILE")
    p_simulate.add_argument("-p", "--period", dest="sync_period",
        metavar="TIME", type=float, default=1e-6,
        help="set 'sync' clock domain period to TIME (default: %(default)s)")
    p_simulate.add_argument("-c", "--clocks", dest="sync_clocks",
        metavar="COUNT", type=int, required=True,
        help="simulate for COUNT 'sync' clock periods")

    p_project = p_action.add_parser(
        "project", help="generate a Xilinx Vivado project")
    p_project.add_argument(
        "-work", metavar="WORKDIR",
        default="work", type=str, dest="work_root",
        help="set workdir to WORKDIR (default: %(default)s)")
    p_project.add_argument(
        "-name", metavar="PROJECT-NAME",
        help="project name set to PROJECT-NAME (default: %(default)s)",
        type=str, default="build", dest="project_name")
    p_project.add_argument(
        "--build", action="store_true", dest="project_build")

    return parser


def main_runner(parser, args, design, platform=None, name="top", ports=()):
    logger.setLevel(max(logging.ERROR - args.verbose * 10, logging.DEBUG))
    if args.action == "generate":
        fragment = Fragment.get(design, platform)
        generate_type = args.generate_type
        if generate_type is None and args.generate_file:
            if args.generate_file.name.endswith(".v"):
                generate_type = "v"
            if args.generate_file.name.endswith(".il"):
                generate_type = "il"
        if generate_type is None:
            parser.error("specify file type explicitly with -t")
        if generate_type == "il":
            output = rtlil.convert(fragment, name=name, ports=ports)
        if generate_type == "v":
            output = verilog.convert(fragment, name=name, ports=ports)
        if args.generate_file:
            args.generate_file.write(output)
        else:
            print(output)

    if args.action == "simulate":
        fragment = Fragment.get(design, platform)
        with pysim.Simulator(fragment,
                vcd_file=args.vcd_file,
                gtkw_file=args.gtkw_file,
                traces=ports) as sim:
            sim.add_clock(args.sync_period)
            sim.run_until(args.sync_period * args.sync_clocks, run_passive=True)

    if args.action == "project":
        work_path = pathlib.Path(args.work_root)
        work_path.mkdir(parents=True, exist_ok=True)
        hdl_path = work_path.joinpath(name + ".v")
        config_path = work_path.joinpath(name + platform.config_extension)
        ports_map = OrderedDict(zip([p.name for p in ports], ports))
        logger.info("%s ports:\n%s", name, "\n".join(ports_map.keys()))
        config_path.write_text(platform.config_writer(ports_map))
        logger.info("%s config:\n%s", name, platform.config_writer(ports_map))
        main_runner(parser, parser.parse_args(
            ["-v", "generate", str(hdl_path)]),
            design, platform, name, ports)
        eda_api = get_eda_api(
            platform, args.project_name, name, str(work_path),
            files=[str(f) for f in [hdl_path, config_path]])
        backend = get_edatool(platform.tool)(eda_api, str(work_path))
        backend.configure([])
        if args.project_build:
            backend.build()


def main(*args, **kwargs):
    parser = main_parser()
    main_runner(parser, parser.parse_args(), *args, **kwargs)
