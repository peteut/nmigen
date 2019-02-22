from abc import ABCMeta, abstractmethod
from itertools import filterfalse, chain, starmap, count, repeat
from operator import or_
from copy import copy
import pathlib
import types
from io import StringIO
from functools import reduce, partial
from typing import *  # noqa
from operator import methodcaller
from string import Template
from ..hdl.ast import Signal


__all__ = ["Constraint", "Pins", "IOStandard", "Drive", "Misc", "Subsignal",
           "Clock", "InputDelay", "Platform"]


split = methodcaller("split")


class Constraint(Hashable, metaclass=ABCMeta):
    @abstractmethod
    def __repr__(self) -> str:
        pass

    @abstractmethod
    def get_xdc(self, name: str) -> str:
        pass

    @property
    def _cls_name(self) -> str:
        return self.__class__.__name__

    def __hash__(self) -> int:
        return hash(repr(self))

    def __eq__(self, other):
        return hash(self) == hash(other)


def isconstraint(x: Any) -> bool:
    return isinstance(x, Constraint)


class Pins(Constraint, Sized):
    __slots__ = ("identifiers",)
    identifiers: List[str]

    def __init__(self, *identifiers: List[str]) -> None:
        self.identifiers = list(chain.from_iterable(map(split, identifiers)))

    def __repr__(self):
        return "{._cls_name}('{}')".format(self, " ".join(self.identifiers))

    def get_xdc(self, name):
        if len(self) == 1:
            return self.template.substitute(
                pin=self.identifiers[0], name=name)
        else:
            return "".join(
                starmap(lambda p, n: self.template.substitute(pin=p, name=n),
                        zip(self.identifiers,
                            map(partial("{}[{}]".format, name), count()))))

    def __len__(self):
        return len(self.identifiers)

    template = Template("set_property PACKAGE_PIN $pin [get_ports $name]\n")


class IOStandard(Constraint):
    __slots__ = ("name",)
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self):
        return "{0._cls_name}('{0.name}')".format(self)

    def get_xdc(self, name):
        return self.template.substitute(iostandard=self.name, name=name)

    template = Template(
        "set_property IOSTANDARD $iostandard [get_ports $name]\n")


class Drive(Constraint):
    __slots__ = ("strength",)
    strength: int

    def __init__(self, strength) -> None:
        self.strength = strength

    def __repr__(self):
        return "{0._cls_name}({0.strength})".format(self)

    def get_xdc(self, name):
        return self.template.substitute(drive=self.strength, name=name)

    template = Template(
        "set_property DRIVE $drive [get_ports $name]\n")


def isbool(x: Any) -> bool:
    return isinstance(x, bool)


class Misc(Constraint):
    __slots__ = ("misc",)
    misc: str

    def __init__(self, misc: Union[str, Tuple[str, Union[str, bool]]]) -> None:
        if isinstance(misc, str):
            self.misc = misc.strip()
        else:
            prop, value = misc
            self.misc = "{}={}".format(
                prop.strip().upper(), str(value).upper() if isbool(value) else
                value)

    def __repr__(self) -> str:
        return "{0._cls_name}({0.misc!r})".format(self)

    def get_xdc(self, name) -> str:
        return self.template.substitute(
            type="ports",
            misc=" ".join(self.misc.split("=")), name=name)

    def get_xdc_nets(self, name) -> str:
        return self.template.substitute(
            type="nets",
            misc=" ".join(self.misc.split("=")), name=name)

    template = Template("set_property $misc [get_$type $name]\n")


class Subsignal(Constraint):
    __slots__ = ("name", "constraints")
    name: str
    constraints: Set[Constraint]

    def __init__(self, name: str, *constraints: Iterable[Constraint]) -> None:
        self.name = name
        self.constraints = set(constraints)

    def __repr__(self) -> str:
        return "{0._cls_name}('{0.name}', {1})".format(
            self, ", ".join(map(repr, self.constraints)))

    def get_xdc(self, name):
        raise NotImplementedError


float_fmt = "{:.3f}".format


class Clock(Constraint):
    __slots__ = ("period", "waveform")
    period: float
    waveform: Tuple[float, float]

    def __init__(self, period: float,
                 waveform: Optional[Tuple[float, float]] = None) -> None:
        if waveform is None:
            waveform = (0., period / 2)
        self.period = period
        self.waveform = waveform

    def __repr__(self) -> str:
        return "{0._cls_name}({0.period!r}, {0.waveform!r})".format(self)

    def get_xdc(self, name) -> str:
        on_period, off_period = map(float_fmt, self.waveform)
        return self.template.substitute(
            name=name, period=float_fmt(self.period),
            off_period=off_period, on_period=on_period)

    template = Template("create_clock -name cd_$name -period $period "
                        "-waveform {$on_period $off_period} "
                        "[get_ports $name]\n")


class InputDelay(Constraint):
    __slots__ = ("clock_name", "delay")
    clock_name: str
    delay: float

    def __init__(self, clk_name: str, delay: float) -> None:
        self.clock_name = clk_name
        self.delay = delay

    def __repr__(self) -> str:
        return "{0._cls_name}('{0.clock_name}', {1})".format(
            self, float_fmt(self.delay))

    def get_xdc(self, name) -> str:
        return self.template.substitute(
            clock_name=self.clock_name,
            delay=float_fmt(self.delay), name=name)

    template = Template("set_input_delay -clock cd_$clock_name $delay "
                        "[get_ports $name]\n")


class ConnectorProxy(NamedTuple):
    pins: Dict[Union[int, str], Union[Pins, "ConnectorProxy"]] = dict()

    @staticmethod
    def make(node: "ConnectorProxy", args: Tuple) -> "ConnectorProxy":
        ident, *rest = args
        pins = copy(node.pins)

        def wrap(x):
            if isinstance(x, Dict):
                return reduce(ConnectorProxy.make, x.items(), ConnectorProxy())
            else:
                return Pins(x)

        if isinstance(rest[0], Dict):
            pins[ident] = ConnectorProxy(
                dict(zip(rest[0].keys(), map(wrap, rest[0].values()))))
        elif len(rest) and isinstance(rest[0], str):
            pins[ident] = ConnectorProxy({0: Pins(rest[0])})
        else:
            pins[ident] = ConnectorProxy(dict(enumerate(map(Pins, rest[0]))))

        return ConnectorProxy(pins)

    def __dir__(self) -> List[str]:
        return list(self.pins.keys())

    def __iter__(self) -> Iterator:
        return iter(self.items.items())


def ispins(x: Any) -> bool:
    return isinstance(x, Pins)


def issubsignal(x: Any) -> bool:
    return isinstance(x, Subsignal)


def iterable(x: Any) -> bool:
    return isinstance(x, Iterable)


def ensure_iterable(x: Any) -> bool:
    return x if iterable(x) else [x]


class IOProxy(NamedTuple):
    items: Dict[Union[int, str], Union[Set, "IOProxy"]] = dict()

    @staticmethod
    def make(node: "IOProxy", args: Tuple) -> "IOProxy":
        ident, *rest = args
        name = ident if isinstance(ident, (int, str)) else \
            ident.name if isinstance(ident, Subsignal) else None
        items = copy(node.items)
        attrs = reduce(
            or_, map(set,
                     map(ensure_iterable, filterfalse(issubsignal, rest))), set())
        filtered_attrs = set(filterfalse(issubsignal, attrs))
        subsignals = list(filter(issubsignal, rest))
        if isinstance(len(rest) > 0 and rest[0], int):
            item = items.get(name)
            if item:
                item.items[rest[0]] = set(rest[1:])
            else:
                item = IOProxy.make(IOProxy(), rest)
                items[name] = item
        elif len(subsignals):
            items[name] = reduce(
                IOProxy.make,
                ((a, filtered_attrs) for a in subsignals), IOProxy())
        elif isinstance(name, int):
            items[name] = attrs
        elif isinstance(ident, Subsignal):
            items[name] = attrs | ident.constraints
        elif items.get(name) is None:
            items[name] = attrs
        return IOProxy(items)

    def __dir__(self) -> List[str]:
        return list(self.items.keys())

    def __iter__(self) -> Iterator:
        return iter(self.items.items())


class EdalizeApi(NamedTuple):
    files: List[Dict[str, str]]
    name: str
    toplevel: str
    parameters: Dict[str, Dict[str, str]] = {}
    tool_options: Dict[str, Any] = {}


class Port(Mapping):
    __slots__ = ("name", "io")
    name: str
    io: IOProxy

    def __init__(self, name: str, io: IOProxy) -> None:
        self.name = name
        self.io = io

    def _get(self, key) -> Union["Port", Signal]:
        name = key if self.name == "" else "_".join([self.name, str(key)])
        port = Port(name, self.io.items[key])
        if isinstance(port.io, set):
            pins = next(filter(ispins, port.io))
            sig = Signal(len(pins), name=name, attrs={
                repr(a): a for a in port.io})
            return sig
        return port

    def __getitem__(self, key) -> Union["Port", Signal]:
        return self._get(key)

    def __getattr__(self, key) -> Union["Port", Signal]:
        try:
            return self._get(key)
        except KeyError:
            return super().__getattr__(key)

    def __dir__(self) -> List[str]:
        return dir(self.io)

    def __len__(self) -> int:
        return len(dir(self))

    def __iter__(self) -> Iterator[Signal]:
        return chain.from_iterable(
            map(ensure_iterable, map(self.__getitem__, dir(self))))


class Connector(Mapping):
    __slots__ = ("name", "connector")
    name: str
    connector: ConnectorProxy

    def __init__(self, name: str, connector: ConnectorProxy) -> None:
        self.name = name
        self.connector = connector

    def _get(self, key) -> Union["Connector", Signal]:
        name = key if self.name == "" else "_".join([self.name, str(key)])
        if ispins(self.connector.pins[key]):
            pins = self.connector.pins[key]
            return Signal(len(pins), name=name, attrs={repr(pins): pins})

        connector = Connector(name, self.connector.pins[key])
        return connector

    def __getitem__(self, key) -> Union["Connector", Signal]:
        return self._get(key)

    def __getattr__(self, key) -> Union["Connector", Signal]:
        try:
            return self[key]
        except KeyError:
            return super().__getattr__(key)

    def __dir__(self):
        return dir(self.connector)

    def __len__(self) -> int:
        return len(dir(self))

    def __iter__(self) -> Iterator[Signal]:
        return chain.from_iterable(
            map(ensure_iterable, map(self.__getitem__, dir(self))))


def compose_xdc_from_signal(name: str, signal: Signal):
    constraints = list(filter(isconstraint, signal.attrs.values()))
    if len(constraints) == 0:
        return ""

    with StringIO() as buf:
        buf.write("# {}\n".format(signal.name))
        [buf.write(s) for s in starmap(
            lambda n, c: c.get_xdc(n), zip(repeat(name), constraints))]
        return buf.getvalue()


ConnectorDecl = Tuple[str, Union[str, Mapping]]


_techmap = {
    "get_tristate", "get_multi_reg", "get_reset_sync",
    "get_differential_input", "get_differential_output",
    "get_ddr_input", "get_ddr_output"}


class Platform(types.SimpleNamespace):
    _io: IOProxy
    _connector: ConnectorProxy
    name: str
    tool: str
    tool_options: Dict[str, Any] = {}
    files: List[pathlib.Path] = []
    commands: List[str] = []

    @staticmethod
    def make(name: str, io: Iterable[Tuple], tool: str,
             connector: Iterable[ConnectorDecl] = [], **kwargs) -> "Platform":
        io_proxy = reduce(IOProxy.make, io, IOProxy())
        connector_proxy = reduce(ConnectorProxy.make, connector, ConnectorProxy())
        kwargs = copy(kwargs)
        kwargs.update(
            name=name, _io=io_proxy, tool=tool, _connector=connector_proxy)
        techmap = kwargs.pop("techmap", {})
        for method in _techmap & set(techmap):
            kwargs[method] = techmap[method]

        kwargs.update(_tool_supportmap[tool])
        return Platform(**kwargs)

    @property
    def port(self) -> Port:
        return Port("", self._io)

    @property
    def connector(self) -> Connector:
        return Connector("", self._connector)


def get_filetype(name: str):
    if name.endswith(".v"):
        return "verilogSource"
    elif name.endswith(".vhd") or name.endswith(".vhdl"):
        return "vhdlSource"
    elif name.endswith(".xdc"):
        return "xdc"
    else:
        raise ValueError("unkown file extension `.{}`".format(name.split(".")[-1]))


def get_eda_api(platform: Platform, name: str, toplevel: str, work_root: str,
                files: Iterable[str] = [], **kwargs) -> Dict:
    tool_options = copy(platform.tool_options)
    tool_options.update(kwargs.get("tool_options", {}))
    work_path = pathlib.Path(work_root)
    work_path.mkdir(parents=True, exist_ok=True)
    # copy platform.files to work
    for f in platform.files:
        new_path = work_path.joinpath(f.name)
        data = f.read_text()
        new_path.write_text(data)

    return EdalizeApi(
        files=[{"name": str(f.relative_to(work_root)),
                "file_type": get_filetype(f.name)} for f in chain(
                    [work_path.joinpath(f.name) for f in platform.files],
                    [pathlib.Path(f) for f in files])],
        name=name, toplevel=toplevel, tool_options=tool_options)._asdict()


def xdc_writer(port_map: Mapping[str, Signal]) -> str:
    def filter_contraints(k, v):
        return zip(repeat(k), filter(isconstraint, v.attrs.values()))

    with StringIO() as buf:
        constraints = chain.from_iterable(
            starmap(filter_contraints, port_map.items()))
        [buf.write(v.get_xdc(k)) for k, v in constraints]
        return buf.getvalue()


_tool_supportmap = {
    "vivado": {"config_writer": xdc_writer, "config_extension": ".xdc"}}
