from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from itertools import filterfalse, chain, starmap, count, repeat
from operator import or_
from copy import copy
import os
from io import StringIO
from functools import reduce, partial
from typing import *  # noqa
from operator import methodcaller
from string import Template
from ..hdl.ast import Signal


__all__ = ["Constraint", "Pins", "IOStandard", "Drive", "Misc", "Subsignal",
           "Connector", "Platform"]


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
            print(self.identifiers)
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

    def __repr__(self):
        return "{0._cls_name}({0.misc!r})".format(self)

    def get_xdc(self, name):
        return self.template.substitute(
            misc=" ".join(self.misc.split("=")), name=name)

    template = Template("set_property $misc [get_ports $name]\n")


class Subsignal(Constraint):
    __slots__ = ("name", "constraints")
    name: str
    constraints: Set[Constraint]

    def __init__(self, name: str, *constraints: Iterable[Constraint]):
        self.name = name
        self.constraints = set(constraints)

    def __repr__(self):
        return "{0._cls_name}('{0.name}', {1})".format(
            self, ", ".join(map(repr, self.constraints)))

    def get_xdc(self, name):
        raise NotImplementedError


connector_decl = Union[Tuple[str, str], Dict[str, str]]


class Connector(NamedTuple):
    name: str
    pins: Dict[Union[int, str], Pins]

    @staticmethod
    def make(definition: connector_decl) -> "Connector":
        name, pins = definition
        return Connector(
            name=name, pins={k: Pins(v) for k, v in pins.items()}
            if isinstance(pins, Dict) else {0: Pins(pins)}
            if isinstance(pins, str) else {
                k: Pins(v) for k, v in enumerate(pins)})


def ispins(x):
    return isinstance(x, Pins)


def issubsignal(x):
    return isinstance(x, Subsignal)


def ensure_iterable(x):
    return x if isinstance(x, Iterable) else [x]


class IOProxy(NamedTuple):
    items: Dict[Union[int, str], NamedTuple] = dict()

    @staticmethod
    def make(node: "IOProxy", args: Tuple) -> "IOProxy":
        ident, *rest = args
        name = ident if isinstance(ident, (int, str)) else \
            ident.name if isinstance(ident, Subsignal) else None
        items = copy(node.items)
        attrs = reduce(
            or_, map(set,
                     map(ensure_iterable, filterfalse(issubsignal, rest))))
        filtered_attrs = set(filterfalse(issubsignal, attrs))
        subsignals = list(filter(issubsignal, rest))
        if len(subsignals):
            items[name] = reduce(
                IOProxy.make,
                ((a, filtered_attrs) for a in subsignals), IOProxy())
        if isinstance(len(rest) > 0 and rest[0], int):
            item = items.get(name)
            if item:
                item.items[rest[0]] = set(rest[1:])
            else:
                item = IOProxy.make(IOProxy(), rest)
                items[name] = item
        elif isinstance(name, int):
            items[name] = attrs
        elif isinstance(ident, Subsignal):
            items[name] = attrs | ident.constraints
        elif items.get(name) is None:
            items[name] = attrs
        return IOProxy(items)


class EdalizeApi(NamedTuple):
    files: List[Dict[str, str]]
    name: str
    toplevel: str
    parameters: Dict[str, Dict[str, str]] = {}
    tool_options: Dict[str, Any] = {}


class Port:
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

    def __getitem__(self, key):
        return self._get(key)

    def __getattr__(self, key):
        try:
            return self._get(key)
        except KeyError:
            return super().__getattr__(key)


def compose_xdc_from_signal(name: str, signal: Signal):
    constraints = list(filter(isconstraint, signal.attrs.values()))
    if len(constraints) == 0:
        return ""

    with StringIO() as buf:
        buf.write("# {}\n".format(signal.name))
        [buf.write(s) for s in starmap(
            lambda n, c: c.get_xdc(n), zip(repeat(name), constraints))]
        return buf.getvalue()



class Platform(NamedTuple):
    io: IOProxy
    connector: Set[Connector]
    name: str
    tool: str
    tool_options: Dict[str, Any] = {}
    files: List[str] = []

    @staticmethod
    def make(name: str, io: Iterable[Tuple], tool: str,
             connector: Iterable[Connector] = [], **kwargs) -> "Platform":
        io_proxy = reduce(IOProxy.make, io, IOProxy())
        return Platform(
            name=name, tool=tool, io=io_proxy, connector=set(connector), **kwargs)

    @property
    def port(self) -> Port:
        return Port("", self.io)


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
    return EdalizeApi(
        files=[{"name": os.path.relpath(f, work_root),
                "file_type": get_filetype(f)} for f in chain(
                    platform.files, files)],
        name=name, toplevel=toplevel, tool_options=tool_options)._asdict()
