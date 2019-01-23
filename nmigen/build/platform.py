from abc import ABCMeta, abstractmethod
from typing import List
from operator import methodcaller

__all__ = ["Constraint", "Pins", "IOStandard", "Drive", "Misc", "Subsignal"]


class Constraint(metaclass=ABCMeta):
    @abstractmethod
    def __repr__(self) -> str:
        pass

    @property
    def _cls_name(self) -> str:
        return self.__class__.__name__

    def __hash__(self) -> int:
        return hash(repr(self))


split = methodcaller("split")


class Pins(Constraint):
    __slots__ = ("identifiers",)

    def __init__(self, *identifiers: List[str]) -> None:
        self.identifiers = list(map(split, identifiers))

    def __repr__(self):
        return "{._cls_name}('{}')".format(self, " ".join(*self.identifiers))


class IOStandard(Constraint):
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self):
        return "{0._cls_name}('{0.name}')".format(self)


class Drive(Constraint):
    __slots__ = ("strength",)

    def __init__(self, strength) -> None:
        self.strength = strength.strip()

    def __repr__(self):
        return "{0._cls_name}('{0.strength}')".format(self)


class Misc(Constraint):
    __slots__ = ("misc",)

    def __init__(self, misc: str) -> None:
        self.misc = misc.strip()

    def __repr__(self):
        return "{0._cls_name}({0.misc!r})".format(self)


class Subsignal(Constraint):
    __slots__ = ("name", "constraints")

    def __init__(self, name: str, *constraints: List[Constraint]):
        self.name = name
        self.constraints = list(constraints)

    def __repr__(self):
        return "{0._cls_name}('{0.name}', {1})".format(
            self, ", ".join(map(repr, self.constraints)))
