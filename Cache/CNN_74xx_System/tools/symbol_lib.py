"""KiCad symbol library access for the 74-series CNN generator."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from kicad_sexpr import Pin, atoms, extract_block, find_pins, first, parse

KICAD_SYMBOL_DIR = os.environ.get(
    "KICAD10_SYMBOL_DIR", r"C:/Program Files/KiCad/10.0/share/kicad/symbols"
)


@dataclass
class SymbolDef:
    lib_id: str
    raw: str
    pins: List[Pin]
    name: str

    def renamed_raw(self, lib_nick: str) -> str:
        """Raw symbol block with the top-level name qualified by the library."""
        old = f'(symbol "{self.name}"'
        new = f'(symbol "{lib_nick}:{self.name}"'
        if not self.raw.startswith(old):
            raise ValueError(f"unexpected symbol block for {self.name}")
        return new + self.raw[len(old) :]

    def pin_by_number(self, number: str) -> Pin:
        for p in self.pins:
            if p.number == str(number):
                return p
        raise KeyError(f"{self.lib_id} has no pin {number}")

    def pin_by_name(self, name: str, unit: int = 1) -> Pin:
        for p in self.pins:
            if p.name == name and p.unit == unit:
                return p
        raise KeyError(f"{self.lib_id} has no pin named {name}")


class SymbolLibrary:
    def __init__(self, path: str):
        self.path = path
        with open(path, encoding="utf-8") as f:
            self.text = f.read()
        self._defs: Dict[str, SymbolDef] = {}

    def names(self) -> List[str]:
        root = parse(self.text)
        out = []
        for node in root:
            if isinstance(node, list) and node and node[0] == "symbol":
                out.append(node[1])
        return out

    def get(self, name: str) -> SymbolDef:
        if name in self._defs:
            return self._defs[name]
        raw = extract_block(self.text, f'(symbol "{name}"')
        if raw is None:
            raise KeyError(f"{name} not found in {self.path}")
        root = parse(raw)
        nodes = [n for n in root if isinstance(n, list) and n and n[0] == "symbol"]
        if not nodes:
            raise ValueError(f"could not parse symbol {name}")
        sym = nodes[0]

        # Derived symbols (``extends``) inherit graphics and pins.  KiCad
        # flattens them when saving a schematic, so do the same here.
        ext = first(sym, "extends")
        if ext is not None:
            base_name = atoms(ext)[0]
            base = self.get(base_name)
            flat = base.raw.replace(f'(symbol "{base_name}"', f'(symbol "{name}"', 1)
            flat = flat.replace(f'(symbol "{base_name}_', f'(symbol "{name}_')
            flat = flat.replace(
                f'(property "Value" "{base_name}"',
                f'(property "Value" "{name}"',
                1,
            )
            root = parse(flat)
            sym = [n for n in root if isinstance(n, list) and n and n[0] == "symbol"][0]
            pins = find_pins(sym)
            d = SymbolDef(lib_id=name, raw=flat, pins=pins, name=name)
            self._defs[name] = d
            return d

        pins = find_pins(sym)
        d = SymbolDef(lib_id=name, raw=raw, pins=pins, name=name)
        self._defs[name] = d
        return d


class SymbolRegistry:
    """Maps a schematic lib_id such as ``74xx:74LS161`` to its definition."""

    def __init__(self):
        self._libs: Dict[str, SymbolLibrary] = {}
        self._defs: Dict[str, SymbolDef] = {}

    def add_library(self, nick: str, path: str) -> None:
        self._libs[nick] = SymbolLibrary(path)

    def add_alias(self, nick: str, source_nick: str, name: str, alias: str) -> None:
        """Create a pin-compatible alias, e.g. 74LS161 -> 74HC161."""
        src = self._libs[source_nick].get(name)
        raw = src.raw
        # Rename the top level symbol and its default value text.
        raw = raw.replace(f'(symbol "{name}"', f'(symbol "{alias}"', 1)
        raw = raw.replace(f'(property "Value" "{name}"', f'(property "Value" "{alias}"', 1)
        raw = raw.replace(f'(symbol "{name}_', f'(symbol "{alias}_')
        root = parse(raw)
        sym = [n for n in root if isinstance(n, list) and n and n[0] == "symbol"][0]
        self._defs[f"{nick}:{alias}"] = SymbolDef(
            lib_id=f"{nick}:{alias}", raw=raw, pins=find_pins(sym), name=alias
        )

    def get(self, lib_id: str) -> SymbolDef:
        if lib_id in self._defs:
            return self._defs[lib_id]
        nick, name = lib_id.split(":", 1)
        d = self._libs[nick].get(name)
        q = SymbolDef(lib_id=lib_id, raw=d.raw, pins=d.pins, name=d.name)
        self._defs[lib_id] = q
        return q

    def raw_for_schematic(self, lib_id: str) -> str:
        nick, _ = lib_id.split(":", 1)
        d = self.get(lib_id)
        # Library symbols and aliases both start with an unqualified name.
        if d.raw.startswith(f'(symbol "{d.name}"'):
            return d.raw.replace(f'(symbol "{d.name}"', f'(symbol "{nick}:{d.name}"', 1)
        return d.raw
