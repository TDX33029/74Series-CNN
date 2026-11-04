"""Minimal S-expression reader/writer helpers for KiCad files.

Only the subset needed by the schematic generator is implemented.  The
reader keeps the original token text so callers can either inspect the
tree or extract a symbol block verbatim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional


_TOKEN_RE = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text)


def parse(text: str) -> List[list]:
    """Parse a KiCad S-expression into nested lists.

    Atoms and quoted strings are both returned as plain ``str``.  This is
    sufficient for symbol inspection; raw text extraction is used when a
    block has to be re-emitted byte-for-byte.
    """
    stack: List[list] = [[]]
    for tok in tokenize(text):
        if tok == "(":
            node: list = []
            stack[-1].append(node)
            stack.append(node)
        elif tok == ")":
            if len(stack) == 1:
                raise ValueError("unbalanced ')'")
            stack.pop()
        elif tok.startswith('"'):
            body = tok[1:-1]
            body = body.replace('\\"', '"').replace("\\\\", "\\")
            stack[-1].append(body)
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced '('")
    return stack[0]


def children(node: list, name: str) -> List[list]:
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name]


def first(node: list, name: str) -> Optional[list]:
    for c in node[1:]:
        if isinstance(c, list) and c and c[0] == name:
            return c
    return None


def atoms(node: list) -> List[str]:
    return [c for c in node[1:] if not isinstance(c, list)]


def walk(node: list) -> Iterable[list]:
    yield node
    for c in node[1:]:
        if isinstance(c, list):
            yield from walk(c)


def extract_block(text: str, start_pattern: str) -> Optional[str]:
    """Return the parenthesis-balanced block beginning at *start_pattern*."""
    i = text.find(start_pattern)
    if i < 0:
        return None
    depth = 0
    j = i
    in_string = False
    escape = False
    while j < len(text):
        ch = text[j]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[i : j + 1]
        j += 1
    return None


def q(value: str) -> str:
    """Quote a string for KiCad output (newlines/tabs escaped)."""
    s = str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return '"' + s + '"'


def fmt(value: float) -> str:
    """Format a coordinate without scientific notation or trailing zeros."""
    if isinstance(value, int):
        return str(value)
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s


@dataclass
class Pin:
    number: str
    name: str
    x: float
    y: float
    rot: int
    length: float
    unit: int
    etype: str
    bodystyle: int = 1

    @property
    def is_power(self) -> bool:
        return self.etype == "power_in" or self.etype == "power_out"

    @property
    def side(self) -> str:
        """Side of the symbol body the pin is attached to."""
        return {0: "right", 90: "top", 180: "left", 270: "bottom"}.get(
            self.rot, "right"
        )


def find_pins(symbol_node: list) -> List[Pin]:
    """Collect pins from a parsed symbol node (body style 1 only)."""
    pins: List[Pin] = []

    def visit(node: list, unit: int, bodystyle: int) -> None:
        for child in node[1:]:
            if not isinstance(child, list) or not child:
                continue
            if child[0] == "symbol":
                sub_name = child[1] if len(child) > 1 and isinstance(child[1], str) else ""
                m = re.search(r"_(\d+)_(\d+)$", sub_name)
                sub_unit = int(m.group(1)) if m else unit
                sub_style = int(m.group(2)) if m else bodystyle
                visit(child, sub_unit, sub_style)
            elif child[0] == "pin":
                # Body style 0 is common to all styles; style 1 is the
                # normal (IEEE) drawing.  Style 2 is the De Morgan
                # alternative and must not be duplicated.
                if bodystyle not in (0, 1):
                    continue
                at = first(child, "at")
                length = first(child, "length")
                name = first(child, "name")
                number = first(child, "number")
                if not (at and length and name and number):
                    continue
                etype = child[1] if len(child) > 1 and isinstance(child[1], str) else ""
                pins.append(
                    Pin(
                        number=atoms(number)[0] if atoms(number) else "",
                        name=atoms(name)[0] if atoms(name) else "",
                        x=float(at[1]),
                        y=float(at[2]),
                        rot=int(at[3]),
                        length=float(length[1]),
                        unit=unit,
                        etype=etype,
                        bodystyle=bodystyle,
                    )
                )

    visit(symbol_node, 1, 1)
    return pins


def rotate(x: float, y: float, rot: int) -> tuple[float, float]:
    """Rotate a symbol-local point counter-clockwise in schematic space."""
    if rot == 0:
        return x, y
    if rot == 90:
        return y, -x
    if rot == 180:
        return -x, -y
    if rot == 270:
        return -y, x
    raise ValueError(f"unsupported rotation {rot}")
