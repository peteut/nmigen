import argparse
import logging
import sys
import io
import os
from os import path
from edalize import get_edatool

from .back import rtlil, verilog, pysim
from .hdl.ir import Fragment
from .build.platform import Platform, get_eda_api

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
    p_project.add_argument("-work",
        metavar="WORKDIR",
        default="work", type=str, dest="work_root",
        help="set workdir to WORKDIR (default: %(default)s)")
    p_project.add_argument("-name",
        metavar="PROJECT-NAME",
        help="project name set to PROJECT-NAME (default: %(default)s)",
        type=str, default="build", dest="project_name")

    return parser


def fragment_info(fragment: Fragment) -> str:
    join_sigs = "\n".join
    format_sigs = lambda it: join_sigs(map(
        "  name: {0.name:<20} nbits: {0.nbits:<3} signed: {0.signed}".format,
        it))

    with io.StringIO() as output:
        output.write("converted Fragment\n")
        write_if_any = lambda fn, fmt_fn: len(tuple(fn())) and output.write(
            fmt_fn(format_sigs(fn())))
        write_if_any(lambda: fragment.iter_ports("i"), "inputs:\n{}\n".format)
        write_if_any(lambda: fragment.iter_ports("o"), "outputs:\n{}\n".format)
        write_if_any(lambda: fragment.iter_ports("io"), "inouts:\n{}\n".format)
        write_if_any(fragment.iter_signals, "signals:\n{}\n".format)
        return output.getvalue()


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
        logger.info(fragment_info(fragment.prepare(ports=ports)))

    if args.action == "simulate":
        fragment = Fragment.get(design, platform)
        with pysim.Simulator(fragment,
                vcd_file=args.vcd_file,
                gtkw_file=args.gtkw_file,
                traces=ports) as sim:
            sim.add_clock(args.sync_period)
            sim.run_until(args.sync_period * args.sync_clocks, run_passive=True)

    if args.action == "project":
        # build it first
        os.makedirs(args.work_root, exist_ok=True)
        filename = "{}.v".format(name)
        main_runner(parser, parser.parse_args(
            ["-v", "generate", path.join(args.work_root, filename)]),
            design, platform, name, ports)
        eda_api = get_eda_api(
            platform, args.project_name, name, args.work_root,
            files=[path.join(args.work_root, filename)])
        backend = get_edatool(platform.tool)(eda_api, args.work_root)
        backend.configure([])
        backend.build()


def main(*args, **kwargs):
    parser = main_parser()
    main_runner(parser, parser.parse_args(), *args, **kwargs)
