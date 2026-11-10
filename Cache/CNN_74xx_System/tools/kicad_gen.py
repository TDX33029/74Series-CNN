"""Programmatic KiCad 10 schematic builder for the 74-series CNN project.

The builder emits native ``.kicad_sch`` files: embedded symbol definitions,
real pin-level connections, global labels, power symbols and hierarchical
sheet symbols.  It deliberately uses label-based connectivity for wide
buses: every signal pin gets a short stub and a global label with the net
name.  This keeps generated sheets readable and lets KiCad's ERC/netlist
resolve connectivity across the hierarchy.
"""
from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from kicad_sexpr import Pin, atoms, children, first, fmt, parse, q, walk
from symbol_lib import KICAD_SYMBOL_DIR, SymbolRegistry


GRID = 1.27

# Part substitutions applied to the Value field only.  The symbol keeps its
# original pin-out, which is what the netlist cares about; the BOM and the
# JLC part number come from Value.
#   27C512  : OTP EPROM, out of production and expensive -> W27C512-45Z
#             (5 V, 64Kx8, DIP-28, electrically erasable, same read pin-out)
VALUE_OVERRIDE = {
    "Memory_EPROM:27C512": "W27C512",
}


def snap(v: float) -> float:
    """Snap a coordinate to the 50 mil connection grid."""
    return round(float(v) / GRID) * GRID


def uid() -> str:
    return str(uuid.uuid4())


def outward(pin: Pin) -> Tuple[int, int]:
    """Unit vector pointing away from the symbol body, in schematic coords."""
    return {
        0: (-1, 0),
        180: (1, 0),
        90: (0, 1),
        270: (0, -1),
    }[pin.rot]


def label_angle(pin: Pin) -> int:
    """Label rotation for the stub leaving *pin*.

    KiCad draws vertical labels with the text on the anchor side selected by
    the justification, not by 90 vs 270 alone:
      * 90 / justify left  -> text grows upwards from the anchor
      * 270 / justify right -> text grows downwards from the anchor
    A top-side pin (rot 270) therefore needs 90, a bottom-side pin (rot 90)
    needs 270.  The old mapping sent both labels back into the symbol body.
    """
    return {0: 180, 180: 0, 90: 270, 270: 90}[pin.rot]


# ---------------------------------------------------------------------------
# Library field (Reference/Value) placement
# ---------------------------------------------------------------------------
_FIELD_INFO: Dict[str, Dict[str, Tuple[float, float, int, bool]]] = {}
_SYMBOL_BBOX: Dict[str, Optional[Tuple[float, float, float, float]]] = {}


def _symbol_field_info(d) -> Dict[str, Tuple[float, float, int, bool]]:
    """Return {property name: (x, y, angle, hidden)} from a SymbolDef."""
    key = d.lib_id
    cached = _FIELD_INFO.get(key)
    if cached is not None:
        return cached
    info: Dict[str, Tuple[float, float, int, bool]] = {}
    root = parse(d.raw)[0]
    for p in children(root, "property"):
        a = atoms(p)
        at = first(p, "at")
        if len(a) < 2 or at is None:
            continue
        pat = atoms(at)
        px, py = float(pat[0]), float(pat[1])
        ang = int(float(pat[2])) if len(pat) > 2 else 0
        eff = first(p, "effects")
        hide = False
        if eff is not None:
            h = first(eff, "hide")
            if h is not None:
                ha = atoms(h)
                hide = (not ha) or (ha[0] == "yes")
        info[a[0]] = (px, py, ang, hide)
    _FIELD_INFO[key] = info
    return info


def _symbol_body_bbox(d) -> Optional[Tuple[float, float, float, float]]:
    """Bounding box of the symbol drawing primitives (library coordinates)."""
    key = d.lib_id
    if key in _SYMBOL_BBOX:
        return _SYMBOL_BBOX[key]
    xs: List[float] = []
    ys: List[float] = []

    def add(x: float, y: float) -> None:
        xs.append(x)
        ys.append(y)

    root = parse(d.raw)[0]
    for node in walk(root):
        if not isinstance(node, list) or not node:
            continue
        tag = node[0]
        if tag == "rectangle":
            st, en = first(node, "start"), first(node, "end")
            if st is not None and en is not None:
                sa, ea = atoms(st), atoms(en)
                add(float(sa[0]), float(sa[1]))
                add(float(ea[0]), float(ea[1]))
        elif tag in ("polyline", "bezier"):
            pts = first(node, "pts")
            if pts is not None:
                for xy in children(pts, "xy"):
                    a = atoms(xy)
                    add(float(a[0]), float(a[1]))
        elif tag == "circle":
            ce, rad = first(node, "center"), first(node, "radius")
            if ce is not None and rad is not None:
                ca, ra = atoms(ce), atoms(rad)
                cx, cy, r = float(ca[0]), float(ca[1]), float(ra[0])
                add(cx - r, cy - r)
                add(cx + r, cy + r)
        elif tag == "arc":
            for sub in ("start", "mid", "end"):
                pt = first(node, sub)
                if pt is not None:
                    a = atoms(pt)
                    add(float(a[0]), float(a[1]))
    bbox = (min(xs), min(ys), max(xs), max(ys)) if xs and ys else None
    _SYMBOL_BBOX[key] = bbox
    return bbox


@dataclass
class PlacedSymbol:
    lib_id: str
    ref: str
    value: str
    x: float
    y: float
    unit: int
    uuid: str
    pins: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    pin_objs: Dict[str, Pin] = field(default_factory=dict)


class Schematic:
    def __init__(
        self,
        registry: SymbolRegistry,
        project: str,
        instance_path: str,
        title: str,
        paper: str = "A3",
        rev: str = "1.0",
        is_root: bool = False,
        sheet_uuid: Optional[str] = None,
        paper_w: Optional[float] = None,
        paper_h: Optional[float] = None,
    ):
        self.registry = registry
        self.project = project
        self.instance_path = instance_path
        self.title = title
        self.paper = paper
        self.paper_w = paper_w
        self.paper_h = paper_h
        self.rev = rev
        self.is_root = is_root
        # Supplying an existing UUID keeps incremental rebuilds byte-stable
        # for the child sheets' instance paths.
        self.uuid = sheet_uuid or uid()
        self.lib_symbols: Dict[str, str] = {}
        self.items: List[str] = []
        self.symbols: List[PlacedSymbol] = []
        self._ref_count = 0

    # ------------------------------------------------------------------ libs
    def _use_lib(self, lib_id: str) -> None:
        if lib_id in self.lib_symbols:
            return
        raw = self.registry.raw_for_schematic(lib_id)
        self.lib_symbols[lib_id] = raw

    # --------------------------------------------------------------- symbols
    def add_symbol(
        self,
        lib_id: str,
        ref: str,
        value: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        angle: float = 0.0,
        unit: int = 1,
        footprint: str = "",
        description: str = "",
    ) -> PlacedSymbol:
        if angle not in (0, 90, 180, 270):
            raise ValueError("angle must be 0/90/180/270")
        if angle != 0:
            raise NotImplementedError("rotation is not needed by the current generator")
        x, y = snap(x), snap(y)
        self._use_lib(lib_id)
        d = self.registry.get(lib_id)
        pins = [p for p in d.pins if p.unit == unit]
        # Pins directly on the top level are unit 1.
        if not pins:
            pins = [p for p in d.pins if p.unit == 1]
        if value is None:
            value = d.name
        value = VALUE_OVERRIDE.get(lib_id, value)
        placed = PlacedSymbol(
            lib_id=lib_id,
            ref=ref,
            value=value,
            x=x,
            y=y,
            unit=unit,
            uuid=uid(),
        )
        for p in pins:
            # Placement is rotation 0 with the symbol Y axis flipped.
            gx, gy = x + p.x, y - p.y
            placed.pins[p.number] = (gx, gy)
            placed.pin_objs[p.number] = p

        ys = [gy for _, gy in placed.pins.values()]
        top = min(ys) if ys else y - 10
        bottom = max(ys) if ys else y + 10
        ref_y = top - 2.54
        val_y = bottom + 2.54
        is_power = lib_id.startswith("power:")

        def field_pos(name: str, fallback: Tuple[float, float]) -> Tuple[float, float]:
            """Prefer the library field position; keep the pin-envelope fallback.

            The fallback is used for multi-unit gates (their library fields sit
            in the middle of the gate symbol) and for rotated fields.  Only
            fields that are outside the symbol drawing are adopted.
            """
            info = _symbol_field_info(d).get(name)
            if info is None:
                return fallback
            px, py, ang, hidden = info
            if hidden or ang % 360 != 0:
                return fallback
            bb = _symbol_body_bbox(d)
            if bb is not None:
                minx, miny, maxx, maxy = bb
                if minx + 1e-6 < px < maxx - 1e-6 and miny + 1e-6 < py < maxy - 1e-6:
                    return fallback
            return (x + px, y - py)

        ref_at = field_pos("Reference", (x, ref_y))
        val_at = field_pos("Value", (x, val_y))

        lines = [
            "\t(symbol",
            f'\t\t(lib_id {q(lib_id)})',
            f"\t\t(at {fmt(x)} {fmt(y)} 0)",
            f"\t\t(unit {unit})",
            "\t\t(exclude_from_sim no)",
            "\t\t(in_bom yes)",
            "\t\t(on_board yes)",
            "\t\t(dnp no)",
            f'\t\t(uuid "{placed.uuid}")',
        ]

        def prop(name: str, val: str, px: float, py: float, hide: bool = False) -> None:
            lines.extend(
                [
                    f"\t\t(property {q(name)} {q(val)}",
                    f"\t\t\t(at {fmt(px)} {fmt(py)} 0)",
                    "\t\t\t(effects",
                    "\t\t\t\t(font",
                    "\t\t\t\t\t(size 1.27 1.27)",
                    "\t\t\t\t)",
                ]
            )
            if hide:
                lines.append("\t\t\t\t(hide yes)")
            lines.extend(["\t\t\t)", "\t\t)"])

        prop("Reference", ref, ref_at[0], ref_at[1], hide=is_power)
        prop("Value", placed.value, val_at[0], val_at[1], hide=is_power)
        prop("Footprint", footprint, x, y, hide=True)
        prop("Datasheet", "", x, y, hide=True)
        prop("Description", description or self._description(lib_id), x, y, hide=True)
        for p in pins:
            lines.extend([f'\t\t(pin {q(p.number)}', f'\t\t\t(uuid "{uid()}")', "\t\t)"])
        lines.extend(
            [
                "\t\t(instances",
                f"\t\t\t(project {q(self.project)}",
                f"\t\t\t\t(path {q(self.instance_path)}",
                f"\t\t\t\t\t(reference {q(ref)})",
                f"\t\t\t\t\t(unit {unit})",
                "\t\t\t\t)",
                "\t\t\t)",
                "\t\t)",
                "\t)",
            ]
        )
        self.items.append("\n".join(lines) + "\n")
        self.symbols.append(placed)
        self._ref_count += 1
        return placed

    def _description(self, lib_id: str) -> str:
        d = self.registry.get(lib_id)
        # Try to pull the Description property from the raw symbol.
        for line in d.raw.splitlines():
            if '"Description"' in line:
                parts = line.strip().split('"')
                if len(parts) >= 4:
                    return parts[3]
        return d.name

    # ------------------------------------------------------------- primitives
    def add_wire(self, x1: float, y1: float, x2: float, y2: float) -> None:
        x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
        if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
            return
        self.items.append(
            "\t(wire\n"
            f"\t\t(pts\n\t\t\t(xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})\n\t\t)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f'\t\t(uuid "{uid()}")\n'
            "\t)\n"
        )

    def add_bus(self, x1: float, y1: float, x2: float, y2: float) -> None:
        x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
        self.items.append(
            "\t(bus\n"
            f"\t\t(pts\n\t\t\t(xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})\n\t\t)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f'\t\t(uuid "{uid()}")\n'
            "\t)\n"
        )

    def add_label(
        self,
        net: str,
        x: float,
        y: float,
        angle: int = 0,
        justify: str = "left",
    ) -> None:
        self.items.append(
            f"\t(label {q(net)}\n"
            f"\t\t(at {fmt(x)} {fmt(y)} {angle})\n"
            "\t\t(fields_autoplaced yes)\n"
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {justify})\n\t\t)\n"
            f'\t\t(uuid "{uid()}")\n'
            "\t)\n"
        )

    def add_global_label(
        self,
        net: str,
        x: float,
        y: float,
        angle: int = 0,
        shape: str = "bidirectional",
    ) -> None:
        justify = {0: "left", 90: "left", 180: "right", 270: "right"}[angle]
        x, y = snap(x), snap(y)
        self.items.append(
            f"\t(global_label {q(net)}\n"
            f"\t\t(shape {shape})\n"
            f"\t\t(at {fmt(x)} {fmt(y)} {angle})\n"
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {justify})\n\t\t)\n"
            f'\t\t(uuid "{uid()}")\n'
            "\t)\n"
        )

    def add_text(
        self,
        text: str,
        x: float,
        y: float,
        size: float = 1.27,
        justify: str = "left top",
        bold: bool = False,
    ) -> None:
        bold_s = "\n\t\t\t\t(bold yes)" if bold else ""
        self.items.append(
            f"\t(text {q(text)}\n"
            "\t\t(exclude_from_sim no)\n"
            f'\t\t(at {fmt(x)} {fmt(y)} 0)\n'
            "\t\t(effects\n"
            "\t\t\t(font\n"
            f"\t\t\t\t(size {fmt(size)} {fmt(size)}){bold_s}\n"
            "\t\t\t)\n"
            f"\t\t\t(justify {justify})\n"
            "\t\t)\n"
            f'\t\t(uuid "{uid()}")\n'
            "\t)\n"
        )

    def add_line(
        self, x1: float, y1: float, x2: float, y2: float, width: float = 0.15
    ) -> None:
        """Draw a schematic graphic line (KiCad polyline)."""
        self.items.append(
            "\t(polyline\n"
            f"\t\t(pts\n\t\t\t(xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})\n\t\t)\n"
            "\t\t(stroke\n"
            f"\t\t\t(width {fmt(width)})\n"
            "\t\t\t(type default)\n"
            "\t\t)\n"
            f'\t\t(uuid "{uid()}")\n'
            "\t)\n"
        )

    @staticmethod
    def _wrap_cell(text: str, width_mm: float, size: float, padding: float) -> List[str]:
        """Greedy wrap for a table cell; explicit newlines are preserved."""
        usable = max(1.0, width_mm - 2.0 * padding)
        max_chars = max(4, int(usable / (0.82 * max(size, 0.1))))
        out: List[str] = []
        for raw in str(text).split("\n"):
            if not raw:
                out.append("")
                continue
            while len(raw) > max_chars:
                cut = raw.rfind(" ", 0, max_chars + 1)
                if cut <= 0:
                    cut = raw.rfind(",", 0, max_chars + 1)
                if cut <= 0:
                    cut = raw.rfind("/", 0, max_chars + 1)
                if cut <= 0:
                    cut = max_chars
                out.append(raw[:cut].rstrip())
                raw = raw[cut:].lstrip(" ,/")
            out.append(raw)
        return out

    def add_table(
        self,
        x: float,
        y: float,
        widths: List[float],
        row_heights: List[float],
        rows: List[List[str]],
        font_size: float = 1.0,
        header_font_size: Optional[float] = None,
        header_rows: int = 1,
        padding: float = 1.0,
        outer_width: float = 0.3,
        inner_width: float = 0.15,
        header_bold: bool = True,
    ) -> float:
        """Draw a bordered table with KiCad polylines and text.

        ``row_heights`` are minimum heights; a row is grown when its wrapped
        text does not fit.  Returns the bottom Y coordinate so callers can
        stack additional tables without overlap.
        """
        if len(rows) != len(row_heights):
            raise ValueError("rows and row_heights must have the same length")
        if not widths:
            raise ValueError("table needs at least one column")
        for row in rows:
            if len(row) != len(widths):
                raise ValueError("every row must have one cell per column")
        header_font_size = header_font_size or font_size

        heights: List[float] = []
        wrapped: List[List[List[str]]] = []
        for i, (min_h, row) in enumerate(zip(row_heights, rows)):
            size = header_font_size if i < header_rows else font_size
            cells: List[List[str]] = []
            max_lines = 1
            for j, cell in enumerate(row):
                lines = self._wrap_cell(cell, widths[j], size, padding)
                cells.append(lines)
                max_lines = max(max_lines, len(lines))
            wrapped.append(cells)
            needed = 2.0 * padding + max_lines * size * 1.35
            heights.append(max(float(min_h), needed))

        total_w = sum(widths)
        total_h = sum(heights)
        xs = [x]
        for w in widths:
            xs.append(xs[-1] + w)
        ys = [y]
        for h in heights:
            ys.append(ys[-1] + h)

        # Outer frame and inner grid.
        for x1, y1, x2, y2 in (
            (xs[0], ys[0], xs[-1], ys[0]),
            (xs[-1], ys[0], xs[-1], ys[-1]),
            (xs[-1], ys[-1], xs[0], ys[-1]),
            (xs[0], ys[-1], xs[0], ys[0]),
        ):
            self.add_line(x1, y1, x2, y2, outer_width)
        for yy in ys[1:-1]:
            self.add_line(xs[0], yy, xs[-1], yy, inner_width)
        for xx in xs[1:-1]:
            self.add_line(xx, ys[0], xx, ys[-1], inner_width)

        # Cell text is added after the grid so it prints on top.
        for i, row_cells in enumerate(wrapped):
            size = header_font_size if i < header_rows else font_size
            bold = header_bold and i < header_rows
            for j, lines in enumerate(row_cells):
                self.add_text(
                    "\n".join(lines),
                    xs[j] + padding,
                    ys[i] + padding,
                    size=size,
                    justify="left top",
                    bold=bold,
                )
        return y + total_h

    def add_no_connect(self, x: float, y: float) -> None:
        x, y = snap(x), snap(y)
        self.items.append(f'\t(no_connect\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(uuid "{uid()}")\n\t)\n')

    def add_junction(self, x: float, y: float) -> None:
        x, y = snap(x), snap(y)
        self.items.append(
            f'\t(junction\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(diameter 0)\n'
            "\t\t(color 0 0 0 0)\n"
            f'\t\t(uuid "{uid()}")\n\t)\n'
        )

    def add_power(self, net: str, x: float, y: float, ref: str) -> PlacedSymbol:
        lib_id = "power:+5V" if net == "+5V" else "power:GND"
        d = self.registry.get(lib_id)
        return self.add_symbol(
            lib_id, ref, value=net, x=x, y=y, footprint="", description=f"Power {net}"
        )

    # ----------------------------------------------------------- convenience
    def stub_label(
        self,
        sym: PlacedSymbol,
        pin_number: str,
        net: str,
        length: float = 5.08,
        shape: str = "bidirectional",
        local: bool = False,
    ) -> None:
        if pin_number not in sym.pins:
            raise KeyError(f"{sym.ref} has no pin {pin_number}")
        p = sym.pin_objs[pin_number]
        gx, gy = sym.pins[pin_number]
        dx, dy = outward(p)
        ex, ey = gx + dx * length, gy + dy * length
        self.add_wire(gx, gy, ex, ey)
        angle = label_angle(p)
        if local:
            self.add_label(net, ex, ey, angle, "left" if angle in (0, 90) else "right")
        else:
            self.add_global_label(net, ex, ey, angle, shape)

    def stub_power(self, sym: PlacedSymbol, pin_number: str, net: str, ref: str) -> None:
        p = sym.pin_objs[pin_number]
        gx, gy = sym.pins[pin_number]
        dx, dy = outward(p)
        ex, ey = gx + dx * 5.08, gy + dy * 5.08
        self.add_wire(gx, gy, ex, ey)
        self.add_power(net, ex, ey, ref)

    def stub_nc(self, sym: PlacedSymbol, pin_number: str) -> None:
        gx, gy = sym.pins[pin_number]
        self.add_no_connect(gx, gy)

    # ------------------------------------------------------------------ emit
    def emit(self) -> str:
        out = [
            "(kicad_sch",
            "\t(version 20250610)",
            '\t(generator "eeschema")',
            '\t(generator_version "10.0")',
            f'\t(uuid "{self.uuid}")',
        ]
        if self.paper == "User" and self.paper_w and self.paper_h:
            out.append(f'\t(paper "User" {fmt(self.paper_w)} {fmt(self.paper_h)})')
        else:
            out.append(f'\t(paper {q(self.paper)})')
        out.extend([
            "\t(title_block",
            f"\t\t(title {q(self.title)})",
            '\t\t(date "2026-11-04")',
            f"\t\t(rev {q(self.rev)})",
            '\t\t(company "74Series-CNN Project")',
            "\t)",
            "\t(lib_symbols",
        ])
        for lib_id, raw in self.lib_symbols.items():
            indented = "\n".join("\t\t" + line if line else "" for line in raw.splitlines())
            out.append(indented)
        out.append("\t)")
        out.extend(self.items)
        if self.is_root:
            out.append("\t(sheet_instances")
            out.append('\t\t(path "/"')
            out.append('\t\t\t(page "1")')
            out.append("\t\t)")
            out.append("\t)")
        out.append("\t(embedded_fonts no)")
        out.append(")")
        return "\n".join(out) + "\n"

    def write(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.emit())


class RootSchematic(Schematic):
    """Root sheet with hierarchical sheet symbols (global-label interconnects)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("is_root", True)
        super().__init__(*args, **kwargs)
        self.subsheets: List[dict] = []

    def add_sheet(
        self,
        name: str,
        filename: str,
        x: float,
        y: float,
        w: float,
        h: float,
        page: int,
        sheet_uuid: Optional[str] = None,
    ) -> str:
        su = sheet_uuid or uid()
        self.subsheets.append(
            {"name": name, "file": filename, "x": x, "y": y, "w": w, "h": h, "uuid": su, "page": page}
        )
        self.items.append(
            "\t(sheet\n"
            f"\t\t(at {fmt(x)} {fmt(y)})\n"
            f"\t\t(size {fmt(w)} {fmt(h)})\n"
            "\t\t(exclude_from_sim no)\n"
            "\t\t(in_bom yes)\n"
            "\t\t(on_board yes)\n"
            "\t\t(dnp no)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type solid)\n\t\t)\n"
            "\t\t(fill\n\t\t\t(color 0 0 0 0.0000)\n\t\t)\n"
            f'\t\t(uuid "{su}")\n'
            f'\t\t(property "Sheetname" {q(name)}\n'
            f"\t\t\t(at {fmt(x)} {fmt(y - 1.27)} 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.524 1.524)\n\t\t\t\t)\n"
            "\t\t\t\t(justify left bottom)\n\t\t\t)\n\t\t)\n"
            f'\t\t(property "Sheetfile" {q(filename)}\n'
            f"\t\t\t(at {fmt(x)} {fmt(y + h + 1.27)} 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.524 1.524)\n\t\t\t\t)\n"
            "\t\t\t\t(justify left top)\n\t\t\t)\n\t\t)\n"
            "\t\t(instances\n"
            f"\t\t\t(project {q(self.project)}\n"
            f"\t\t\t\t(path {q(self.instance_path)}\n"
            f'\t\t\t\t\t(page "{page}")\n'
            "\t\t\t\t)\n\t\t\t)\n\t\t)\n"
            "\t)\n"
        )
        return su


def write_project(project_path: str, name: str) -> None:
    pro = {
        "board": {},
        "schematic": {},
        "meta": {"filename": name + ".kicad_pro", "version": 1},
    }
    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")


def write_sym_lib_table(path: str) -> None:
    libs = [
        ("74xx", "${KICAD10_SYMBOL_DIR}/74xx.kicad_sym"),
        ("Memory_RAM", "${KICAD10_SYMBOL_DIR}/Memory_RAM.kicad_sym"),
        ("Memory_EPROM", "${KICAD10_SYMBOL_DIR}/Memory_EPROM.kicad_sym"),
        ("Memory_EEPROM", "${KICAD10_SYMBOL_DIR}/Memory_EEPROM.kicad_sym"),
        ("Device", "${KICAD10_SYMBOL_DIR}/Device.kicad_sym"),
        ("power", "${KICAD10_SYMBOL_DIR}/power.kicad_sym"),
        ("Connector", "${KICAD10_SYMBOL_DIR}/Connector.kicad_sym"),
        ("Connector_Generic", "${KICAD10_SYMBOL_DIR}/Connector_Generic.kicad_sym"),
        ("CNN_Blocks", "${KIPRJMOD}/symbols/CNN_Blocks.kicad_sym"),
    ]
    lines = ["(sym_lib_table", "\t(version 7)"]
    for name, uri in libs:
        lines.append(
            f'\t(lib (name {q(name)})(type "KiCad")(uri {q(uri)})(options "")(descr ""))'
        )
    lines.append(")")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def default_registry() -> SymbolRegistry:
    reg = SymbolRegistry()
    reg.add_library("74xx", KICAD_SYMBOL_DIR + "/74xx.kicad_sym")
    reg.add_library("Memory_RAM", KICAD_SYMBOL_DIR + "/Memory_RAM.kicad_sym")
    reg.add_library("Memory_EPROM", KICAD_SYMBOL_DIR + "/Memory_EPROM.kicad_sym")
    reg.add_library("Memory_EEPROM", KICAD_SYMBOL_DIR + "/Memory_EEPROM.kicad_sym")
    reg.add_library("Device", KICAD_SYMBOL_DIR + "/Device.kicad_sym")
    reg.add_library("power", KICAD_SYMBOL_DIR + "/power.kicad_sym")
    reg.add_library("Connector", KICAD_SYMBOL_DIR + "/Connector.kicad_sym")
    reg.add_library("Connector_Generic",
                    KICAD_SYMBOL_DIR + "/Connector_Generic.kicad_sym")

    # Pin-compatible 74HC aliases for symbols missing from the KiCad library.
    reg.add_alias("74xx", "74xx", "74LS161", "74HC161")
    reg.add_alias("74xx", "74xx", "74LS283", "74HC283")
    reg.add_alias("74xx", "74xx", "74LS157", "74HC157")
    reg.add_alias("74xx", "74xx", "74LS08", "74HC08")
    reg.add_alias("74xx", "74xx", "74LS32", "74HC32")
    reg.add_alias("74xx", "74xx", "74HCT541", "74HC541")
    reg.add_alias("74xx", "74xx", "74HCT574", "74HC574")
    return reg


FOOTPRINTS = {
    "74HC00": "Package_DIP:DIP-14_W7.62mm",
    "74HC02": "Package_DIP:DIP-14_W7.62mm",
    "74HC04": "Package_DIP:DIP-14_W7.62mm",
    "74HC08": "Package_DIP:DIP-14_W7.62mm",
    "74HC32": "Package_DIP:DIP-14_W7.62mm",
    "74HC74": "Package_DIP:DIP-14_W7.62mm",
    "74HC86": "Package_DIP:DIP-14_W7.62mm",
    "74HC138": "Package_DIP:DIP-16_W7.62mm",
    "74HC157": "Package_DIP:DIP-16_W7.62mm",
    "74HC161": "Package_DIP:DIP-16_W7.62mm",
    "74HC283": "Package_DIP:DIP-16_W7.62mm",
    "74HC85": "Package_DIP:DIP-16_W7.62mm",
    "74HC688": "Package_DIP:DIP-20_W7.62mm",
    "74HC245": "Package_DIP:DIP-20_W7.62mm",
    "74HCT273": "Package_DIP:DIP-20_W7.62mm",
    "74HC238": "Package_DIP:DIP-16_W7.62mm",
    "74HCT238": "Package_DIP:DIP-16_W7.62mm",
    "74HC688": "Package_DIP:DIP-20_W7.62mm",
    "74HCT374": "Package_DIP:DIP-20_W7.62mm",
    "74HCT541": "Package_DIP:DIP-20_W7.62mm",
    "74HCT574": "Package_DIP:DIP-20_W7.62mm",
    "27C512": "Package_DIP:DIP-28_W15.24mm",
    "28C256": "Package_DIP:DIP-28_W15.24mm",
    "HY6264AxP": "Package_DIP:DIP-28_W15.24mm",
    "C": "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
}


def footprint_for(lib_id: str) -> str:
    name = lib_id.split(":", 1)[1]
    return FOOTPRINTS.get(name, "")
