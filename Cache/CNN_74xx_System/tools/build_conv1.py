"""Build S07_Conv1.kicad_sch (CONV1 engine) and shared engine helpers.

Run from the tools directory:
    python build_conv1.py

The same helper class is imported by build_conv2.py and build_fc.py.  The
schematics are documentation-grade functional schematics: every real IC pin
is wired (stub + net label), tied to a power rail, or explicitly marked NC.
The CONV1 requantization core is a separate gate-level sheet
(S13_Requant_C1.kicad_sch); its interface nets are global labels on this
sheet.  S08/S09 still contain the Requant_Block macro and must be copied from
S13 by the follow-on integration step.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import default_registry, footprint_for, outward, Schematic, uid
from kicad_sexpr import q

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"
BLOCK_LIB = os.path.join(PROJECT_DIR, "symbols", "CNN_Blocks.kicad_sym")

L0 = "GND"        # logic 0 is the global ground net
L1 = "+5V"        # logic 1 is the global 5 V net


# ---------------------------------------------------------------------------
# Custom functional block library
# ---------------------------------------------------------------------------
def _pin(num: int, name: str, x: float, y: float, rot: int, etype: str) -> str:
    return (
        f'\t\t\t(pin {etype} line\n'
        f'\t\t\t\t(at {x:.2f} {y:.2f} {rot})\n'
        f'\t\t\t\t(length 5.08)\n'
        f'\t\t\t\t(name {q(name)}\n'
        f'\t\t\t\t\t(effects (font (size 1.27 1.27)))\n'
        f'\t\t\t\t)\n'
        f'\t\t\t\t(number {q(str(num))}\n'
        f'\t\t\t\t\t(effects (font (size 1.27 1.27)))\n'
        f'\t\t\t\t)\n'
        f'\t\t\t)'
    )


def _block_symbol(name: str, pins: List[Tuple[int, str, float, float, int, str]],
                  body: Tuple[float, float, float, float], desc: str,
                  ref_pos: Tuple[float, float],
                  val_pos: Tuple[float, float]) -> str:
    """Build a functional block symbol.

    *body* is ``(x_min, x_max, y_min, y_max)`` in library coordinates.  The
    caller is responsible for making the body edges meet the side-pin line
    ends and for keeping the top/bottom pin connection points 5.08 mm outside
    the body; ``_assert_block_geometry`` enforces both.
    """
    x_min, x_max, y_min, y_max = body
    lines = [
        f'\t(symbol {q(name)}',
        "\t\t(pin_names",
        "\t\t\t(offset 1.016)",
        "\t\t)",
        "\t\t(exclude_from_sim no)",
        "\t\t(in_bom yes)",
        "\t\t(on_board yes)",
        "\t\t(in_pos_files yes)",
        "\t\t(duplicate_pin_numbers_are_jumpers no)",
        f'\t\t(property "Reference" "U"',
        f"\t\t\t(at {ref_pos[0]:.2f} {ref_pos[1]:.2f} 0)",
        "\t\t\t(show_name no)",
        "\t\t\t(do_not_autoplace no)",
        "\t\t\t(effects (font (size 1.27 1.27)))",
        "\t\t)",
        f'\t\t(property "Value" {q(name)}',
        f"\t\t\t(at {val_pos[0]:.2f} {val_pos[1]:.2f} 0)",
        "\t\t\t(show_name no)",
        "\t\t\t(do_not_autoplace no)",
        "\t\t\t(effects (font (size 1.27 1.27)))",
        "\t\t)",
        '\t\t(property "Footprint" ""',
        "\t\t\t(at 0 0 0)",
        "\t\t\t(show_name no)",
        "\t\t\t(do_not_autoplace no)",
        "\t\t\t(hide yes)",
        "\t\t\t(effects (font (size 1.27 1.27)))",
        "\t\t)",
        '\t\t(property "Datasheet" ""',
        "\t\t\t(at 0 0 0)",
        "\t\t\t(show_name no)",
        "\t\t\t(do_not_autoplace no)",
        "\t\t\t(hide yes)",
        "\t\t\t(effects (font (size 1.27 1.27)))",
        "\t\t)",
        f'\t\t(property "Description" {q(desc)}',
        "\t\t\t(at 0 0 0)",
        "\t\t\t(show_name no)",
        "\t\t\t(do_not_autoplace no)",
        "\t\t\t(hide yes)",
        "\t\t\t(effects (font (size 1.27 1.27)))",
        "\t\t)",
        f'\t\t(symbol {q(name + "_0_1")}',
        "\t\t\t(rectangle",
        f"\t\t\t\t(start {x_min:.2f} {y_max:.2f})",
        f"\t\t\t\t(end {x_max:.2f} {y_min:.2f})",
        "\t\t\t\t(stroke (width 0.254) (type default))",
        "\t\t\t\t(fill (type background))",
        "\t\t\t)",
        "\t\t)",
        f'\t\t(symbol {q(name + "_1_1")}',
    ]
    for num, pname, x, y, rot, etype in pins:
        lines.append(_pin(num, pname, x, y, rot, etype))
    lines += ["\t\t)", "\t)"]
    return "\n".join(lines)


PIN_LENGTH = 5.08


def _assert_block_geometry(
    name: str,
    pins: List[Tuple[int, str, float, float, int, str]],
    body: Tuple[float, float, float, float],
    ref_pos: Tuple[float, float],
    val_pos: Tuple[float, float],
    control_pins: Sequence[int] = (),
) -> None:
    """Fail the build if the block drawing is not geometrically consistent.

    Checks:
      * every left/right pin line ends exactly on the rectangle edge;
      * the rectangle encloses the full y range of the left/right pins;
      * every top/bottom pin connection point sits 5.08 mm outside the body;
      * Reference/Value are outside the body rectangle;
      * vertical pin names do not share an x position (control pins are
        additionally required to be at least 15.24 mm apart).
    """
    x_min, x_max, y_min, y_max = body
    side_ys: List[float] = []
    top: List[Tuple[float, float]] = []
    bottom: List[Tuple[float, float]] = []
    for num, pname, x, y, rot, _etype in pins:
        if rot == 0:
            assert abs(x + PIN_LENGTH - x_min) < 1e-6, (
                f"{name} pin {num} ({pname}): left pin end {x + PIN_LENGTH} "
                f"does not meet body edge {x_min}")
            side_ys.append(y)
        elif rot == 180:
            assert abs(x - PIN_LENGTH - x_max) < 1e-6, (
                f"{name} pin {num} ({pname}): right pin end {x - PIN_LENGTH} "
                f"does not meet body edge {x_max}")
            side_ys.append(y)
        elif rot == 270:
            assert abs(y - (y_max + PIN_LENGTH)) < 1e-6, (
                f"{name} pin {num} ({pname}): top pin connection {y} is not "
                f"5.08 mm above body top {y_max}")
            assert x_min <= x <= x_max, f"{name} pin {num} outside body width"
            top.append((num, x))
        elif rot == 90:
            assert abs(y - (y_min - PIN_LENGTH)) < 1e-6, (
                f"{name} pin {num} ({pname}): bottom pin connection {y} is not "
                f"5.08 mm below body bottom {y_min}")
            assert x_min <= x <= x_max, f"{name} pin {num} outside body width"
            bottom.append((num, x))
        else:
            raise AssertionError(f"{name} pin {num}: unsupported rotation {rot}")

    assert side_ys, f"{name}: no left/right pins"
    assert y_min <= min(side_ys) and max(side_ys) <= y_max, (
        f"{name}: body y-range ({y_min}, {y_max}) does not enclose side pins "
        f"({min(side_ys)}, {max(side_ys)})")

    def outside(pt: Tuple[float, float]) -> bool:
        px, py = pt
        return px < x_min or px > x_max or py < y_min or py > y_max

    assert outside(ref_pos), f"{name}: Reference at {ref_pos} is inside the body"
    assert outside(val_pos), f"{name}: Value at {val_pos} is inside the body"

    control = set(control_pins)
    for label, group in (("top", top), ("bottom", bottom)):
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                n1, x1 = group[i]
                n2, x2 = group[j]
                gap = abs(x1 - x2)
                if control and n1 in control and n2 in control:
                    assert gap >= 15.24 - 1e-6, (
                        f"{name}: control pins {n1}/{n2} vertical names only "
                        f"{gap:.2f} mm apart")
                else:
                    assert gap >= 2.54 - 1e-6, (
                        f"{name}: {label} pins {n1}/{n2} share x={x1}")


def write_block_library(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # --- 8x8 LUT multiplier unit: exactly the S_LUT_Mult_1 interface ------
    lut_pins: List[Tuple[int, str, float, float, int, str]] = []
    n = 1
    for i in range(8):
        lut_pins.append((n, f"A{i}", -38.1, 17.78 - i * 5.08, 0, "input")); n += 1
    for i in range(8):
        lut_pins.append((n, f"B{i}", -38.1, -20.32 - i * 5.08, 0, "input")); n += 1
    for i in range(16):
        lut_pins.append((n, f"PROD{i}", 38.1, 20.32 - i * 2.54, 180, "output")); n += 1
    lut_pins.append((n, "LUT_AB_LATCH", -10.16, 30.48, 270, "input")); n += 1
    lut_pins.append((n, "LUT_PROD_LATCH", 10.16, 30.48, 270, "input")); n += 1
    lut_pins.append((n, "LUT_CE_N", -10.16, -66.04, 90, "input")); n += 1
    lut_pins.append((n, "LUT_OE_N", 10.16, -66.04, 90, "input")); n += 1
    lut_body = (-33.02, 33.02, -60.96, 25.4)
    lut_ref = (-35.56, 29.21)
    lut_val = (-35.56, -64.77)

    # --- requant / zero-point correction block ---------------------------
    rq_left = [("MAC_STB", "input"), ("MODE0", "input"), ("MODE1", "input"),
               ("RELU_EN", "input"), ("START", "input"), ("CLK", "input"),
               ("RESET_N", "input")]
    rq_top = [("ACC[31:0]", "passive"), ("BIAS[31:0]", "passive"),
              ("M[31:0]", "passive"), ("SHIFT[5:0]", "passive"),
              ("ZP_X[15:0]", "passive"), ("ZP_W[15:0]", "passive"),
              ("ZP_OUT[15:0]", "passive"), ("N_MACS[15:0]", "passive")]
    rq_right = [
        ("Q0", "output"), ("Q1", "output"), ("Q2", "output"), ("Q3", "output"),
        ("Q4", "output"), ("Q5", "output"), ("Q6", "output"), ("Q7", "output"),
        ("QSTB", "output"), ("SAT_FLAG", "output"), ("BUSY", "output"),
        ("DONE", "output"),
    ]
    rq_pins: List[Tuple[int, str, float, float, int, str]] = []
    n = 1
    for i, (pname, et) in enumerate(rq_left):
        rq_pins.append((n, pname, -78.74, 19.05 - i * 6.35, 0, et)); n += 1
    for i, (pname, et) in enumerate(rq_top):
        rq_pins.append((n, pname, -69.85 + i * 20.32, 55.88, 270, et)); n += 1
    for i in range(8):
        rq_pins.append((n, f"PIX{i}", -30.48 + i * 6.35, -58.42, 90, "input")); n += 1
    for i in range(8):
        rq_pins.append((n, f"WGT{i}", 20.32 + i * 6.35, -58.42, 90, "input")); n += 1
    for i, (pname, et) in enumerate(rq_right):
        rq_pins.append((n, pname, 78.74, 40.64 - i * 7.62, 180, et)); n += 1

    # --- S02 timing-controller instance ----------------------------------
    s02_left = [("CLK", "input"), ("RESET_N", "input"), ("REQ", "input"),
                ("WE", "input"), ("WAIT_READ[3:0]", "passive"),
                ("WAIT_WRITE[3:0]", "passive")]
    s02_right = [("MEM_nCE", "output"), ("MEM_nOE", "output"),
                 ("MEM_nWE", "output"), ("MEM_ACK", "output"),
                 ("MEM_DONE", "output"), ("MEM_BUSY", "output")]
    s02_pins: List[Tuple[int, str, float, float, int, str]] = []
    n = 1
    for i, (pname, et) in enumerate(s02_left):
        s02_pins.append((n, pname, -45.72, 17.78 - i * 7.62, 0, et)); n += 1
    for i, (pname, et) in enumerate(s02_right):
        s02_pins.append((n, pname, 45.72, 17.78 - i * 7.62, 180, et)); n += 1

    rq_body = (-73.66, 73.66, -53.34, 50.8)
    rq_ref = (-76.2, 60.96)
    rq_val = (-76.2, -60.96)
    s02_body = (-40.64, 40.64, -25.4, 22.86)
    s02_ref = (-43.18, 26.67)
    s02_val = (-43.18, -29.21)

    _assert_block_geometry("LUT_Mult_Unit", lut_pins, lut_body, lut_ref, lut_val,
                           control_pins=(33, 34, 35, 36))
    _assert_block_geometry("Requant_Block", rq_pins, rq_body, rq_ref, rq_val)
    _assert_block_geometry("S02_MEM_IF", s02_pins, s02_body, s02_ref, s02_val)

    text = "\n".join([
        "(kicad_symbol_lib",
        "\t(version 20241209)",
        '\t(generator "kicad_symbol_editor")',
        '\t(generator_version "10.0")',
        _block_symbol("LUT_Mult_Unit", lut_pins, lut_body,
                      "8x8 LUT multiplier unit, interface identical to S_LUT_Mult_1",
                      lut_ref, lut_val),
        _block_symbol("Requant_Block", rq_pins, rq_body,
                      "Zero-point correction and requantization macro: serial 32x16 multiplier, 64-bit intermediate product, shift/round/saturate",
                      rq_ref, rq_val),
        _block_symbol("S02_MEM_IF", s02_pins, s02_body,
                      "S02_Timing memory controller instance (one per engine); signal names identical to S02",
                      s02_ref, s02_val),
        ")",
    ]) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def block_registry():
    reg = default_registry()
    reg.add_library("CNN_Blocks", BLOCK_LIB)
    return reg


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------
class GatePool:
    """Allocates all gates of a package so no unit is left unplaced."""

    CONFIG = {
        "74xx:74HC08": {
            "units": {1: (1, 2, 3), 2: (4, 5, 6), 3: (9, 10, 8), 4: (12, 13, 11)},
            "power": 5, "pins": (7, 14), "width": 34.0, "height": 30.0,
        },
        "74xx:74HC32": {
            "units": {1: (1, 2, 3), 2: (4, 5, 6), 3: (9, 10, 8), 4: (12, 13, 11)},
            "power": 5, "pins": (7, 14), "width": 34.0, "height": 30.0,
        },
        "74xx:74HC00": {
            "units": {1: (1, 2, 3), 2: (4, 5, 6), 3: (9, 10, 8), 4: (12, 13, 11)},
            "power": 5, "pins": (7, 14), "width": 34.0, "height": 30.0,
        },
        "74xx:74HC02": {
            # units are (input A, input B, output); 74HC02 has Y on 1/4/10/13
            "units": {1: (2, 3, 1), 2: (5, 6, 4), 3: (8, 9, 10), 4: (11, 12, 13)},
            "power": 5, "pins": (7, 14), "width": 34.0, "height": 30.0,
        },
        "74xx:74HC04": {
            "units": {1: (1, 2), 2: (3, 4), 3: (5, 6), 4: (9, 8), 5: (11, 10), 6: (13, 12)},
            "power": 7, "pins": (7, 14), "width": 30.0, "height": 26.0,
        },
    }

    def __init__(self, eng: "EngineBuilder", x0: float, y0: float, cols: int = 6,
                 dx: float = 42.0, dy: float = 34.0, ref_fn=None):
        self.eng = eng
        self.x0 = x0
        self.y0 = y0
        self.cols = cols
        self.dx = dx
        self.dy = dy
        self.ref_fn = ref_fn
        self.pos = 0
        self.chips: Dict[str, Tuple[str, int]] = {}   # lib -> (ref, next unit)
        self._placements: Dict[str, List[Tuple[int, int, float, float]]] = {}

    def _pos(self) -> Tuple[float, float]:
        c = self.pos % self.cols
        r = self.pos // self.cols
        self.pos += 1
        return self.x0 + c * self.dx, self.y0 + r * self.dy

    def _new_chip(self, lib: str) -> Tuple[str, int]:
        ref = self.ref_fn() if self.ref_fn is not None else self.eng.next_ref()
        cfg = self.CONFIG[lib]
        pu = cfg["power"]
        px, py = self.eng.next_power_slot()
        s = self.eng.add_ic(lib, px, py, unit=pu, ref=ref, value=None)
        p1, p2 = cfg["pins"]
        self.eng.connect(s, {str(p1): "GND", str(p2): "+5V"})
        return ref, 1

    def gate(self, lib: str, a: str, b: str, out: str) -> None:
        cfg = self.CONFIG[lib]
        if lib not in self.chips or self.chips[lib][1] > max(cfg["units"]):
            self.chips[lib] = self._new_chip(lib)
        ref, unit = self.chips[lib]
        pins = cfg["units"][unit]
        self.chips[lib] = (ref, unit + 1)
        x, y = self._pos()
        s = self.eng.add_ic(lib, x, y, unit=unit, ref=ref)
        self.eng.connect(s, {str(pins[0]): a, str(pins[1]): b, str(pins[2]): out})

    def inv(self, a: str, out: str) -> None:
        cfg = self.CONFIG["74xx:74HC04"]
        lib = "74xx:74HC04"
        if lib not in self.chips or self.chips[lib][1] > 6:
            self.chips[lib] = self._new_chip(lib)
        ref, unit = self.chips[lib]
        pins = cfg["units"][unit]
        self.chips[lib] = (ref, unit + 1)
        x, y = self._pos()
        s = self.eng.add_ic(lib, x, y, unit=unit, ref=ref)
        self.eng.connect(s, {str(pins[0]): a, str(pins[1]): out})

    def and2(self, a: str, b: str, out: str) -> None:
        self.gate("74xx:74HC08", a, b, out)

    def or2(self, a: str, b: str, out: str) -> None:
        self.gate("74xx:74HC32", a, b, out)

    def nand2(self, a: str, b: str, out: str) -> None:
        self.gate("74xx:74HC00", a, b, out)

    def nor2(self, a: str, b: str, out: str) -> None:
        self.gate("74xx:74HC02", a, b, out)


class Grid:
    """Simple left-to-right, top-to-bottom placement grid."""

    def __init__(self, x0: float, y0: float, dx: float, dy: float, cols: int):
        self.x0, self.y0, self.dx, self.dy, self.cols = x0, y0, dx, dy, cols
        self.i = 0

    def next(self) -> Tuple[float, float]:
        x = self.x0 + (self.i % self.cols) * self.dx
        y = self.y0 + (self.i // self.cols) * self.dy
        self.i += 1
        return x, y


class EngineBuilder:
    def __init__(self, prefix: str, title: str, paper: str = "A0",
                 global_nets: Sequence[str] = ()):
        self.prefix = prefix
        self.refn = 0
        self.pwrn = 0
        self.global_nets = set(global_nets)
        self.power_slots = [(430 + i * 30, 575) for i in range(8)]
        self.power_slot_idx = 0
        self.sh = Schematic(
            block_registry(), project=PROJECT, instance_path="/__ROOT_UUID__",
            title=title, paper=paper,
        )
        # Six columns at 50 mm keep neighbouring gate labels apart without
        # running into the OUTHOLD mux / output register group at x ~= 330.
        self.gates = GatePool(self, 20, 284, cols=5, dx=55.0, dy=20.0)
        # Comparator fix parts are emitted after the whole sheet is built so
        # they take the next free references instead of shifting any existing
        # designator.  Each entry is executed by flush_pending().
        self.pending_gates: List[tuple] = []
        # The S00 root sheet owns the single hierarchy PWR_FLAG pair.  Child
        # sheets must not add their own power-output flags (that produced
        # duplicate power output errors when S13 was added).

    # ---------------------------------------------------------------- basics
    def next_ref(self) -> str:
        self.refn += 1
        return f"U{self.refn}"

    def flush_pending(self) -> None:
        """Emit deferred comparator fix parts using the next free refs."""
        for fn in self.pending_gates:
            fn()
        self.pending_gates.clear()

    def pwr_ref(self) -> str:
        self.pwrn += 1
        return f"#PWR{self.pwrn:03d}"

    def net(self, base: str) -> str:
        if base in ("+5V", "GND"):
            return base
        return f"{self.prefix}_{base}"

    def add_ic(self, lib: str, x: float, y: float, unit: int = 1,
               ref: Optional[str] = None, value: Optional[str] = None):
        if ref is None:
            ref = self.next_ref()
        return self.sh.add_symbol(
            lib, ref, value, x, y, unit=unit,
            footprint=footprint_for(lib) if not lib.startswith("CNN_Blocks:") else "",
        )

    def connect(self, sym, nmap: Dict[str, str], local: bool = True,
                length: float = 5.08,
                skip: Optional[Sequence[str]] = None) -> None:
        skip_set = set(skip or ())
        for num, p in sym.pin_objs.items():
            if num in skip_set:
                continue
            net = nmap.get(num)
            if net is None:
                net = nmap.get(p.name)
            if net is None:
                if p.name == "VCC":
                    net = "+5V"
                elif p.name == "GND":
                    net = "GND"
                else:
                    raise KeyError(f"{sym.ref} pin {num} ({p.name}) has no net")
            if net == "NC":
                self.sh.stub_nc(sym, num)
            elif net in ("+5V", "GND"):
                # Global power labels are electrically identical to power
                # symbols; two PWR_FLAG anchors (see _anchor_logic_nets)
                # declare the rails as driven.  Horizontal stubs avoid the
                # vertical GND/VCC stub overlap between stacked ICs.
                self.power_label(sym, num, net)
            else:
                self.sh.stub_label(sym, num, net,
                                   length=length,
                                   local=local and net not in self.global_nets)

    def next_power_slot(self) -> Tuple[float, float]:
        x, y = self.power_slots[self.power_slot_idx % len(self.power_slots)]
        self.power_slot_idx += 1
        return x, y

    def power_label(self, sym, pin_number: str, net: str) -> None:
        """Connect a power pin with a horizontal stub/label.

        Vertical power stubs on stacked ICs overlap the VCC pin of the part
        below and short +5V to GND.  A horizontal stub keeps every power pin
        on its own point.
        """
        p = sym.pin_objs[pin_number]
        gx, gy = sym.pins[pin_number]
        if p.rot in (90, 270):
            ex, ey = gx + 5.08, gy
        else:
            dx, dy = outward(p)
            ex, ey = gx + dx * 5.08, gy + dy * 5.08
        self.sh.add_wire(gx, gy, ex, ey)
        self.sh.add_global_label(net, ex, ey, 0)

    def wire_label(self, net: str, x: float, y: float, local: bool = True) -> None:
        if local:
            self.sh.add_label(net, x, y, 0, "left")
        else:
            self.sh.add_global_label(net, x, y, 0)

    def _anchor_logic_nets(self) -> None:
        # PWR_FLAG declares the global +5V/GND rails as driven.  All IC power
        # pins use global labels instead of individual power symbols.
        for i, net in enumerate(("+5V", "GND")):
            x = 700 + i * 60
            y = 30
            self.sh.add_symbol("power:PWR_FLAG", f"#FLG{i+1}", value=net,
                               x=x, y=y)
            self.sh.add_wire(x, y, x + 12.7, y)
            self.sh.add_global_label(net, x + 12.7, y, 0)

    def text(self, s: str, x: float, y: float, size: float = 1.4,
             bold: bool = False, justify: str = "left top") -> None:
        self.sh.add_text(s, x, y, size=size, bold=bold, justify=justify)

    # --------------------------------------------------------------- counters
    def counter(self, name: str, x: float, y: float, nbits: int, last: int,
                enable: str, pe_net: Optional[str] = None,
                reset: Optional[str] = None, vertical: bool = False) -> List[str]:
        """74HC161 chain with synchronous zero-load at `last` (unless full range).

        Returns the Q nets (LSB first).  `pe_net` overrides ~PE (active low).
        """
        if reset is None:
            reset = self.net("CNT_RESET_N")
        stages = (nbits + 3) // 4
        qnets: List[str] = []
        chips = []
        carry = None
        full = (last == (1 << nbits) - 1)
        for i in range(stages):
            cx = x if vertical else x + i * 65.0
            cy = y + i * 55.0 if vertical else y
            u = self.add_ic("74xx:74HC161", cx, cy)
            chips.append(u)
            q = []
            for b in range(4):
                idx = 4 * i + b
                if idx < nbits:
                    q.append(self.net(f"{name}{idx}"))
                else:
                    q.append("NC")
            qnets.extend(q)
            tc = self.net(f"{name}_TC{i}") if i < stages - 1 else "TC_LAST"
            if i == 0:
                cen = enable
            else:
                cen = carry
            m = {
                "~{MR}": reset, "CP": "CLK", "CEP": cen, "CET": cen,
                "D0": self.net(L0), "D1": self.net(L0),
                "D2": self.net(L0), "D3": self.net(L0),
                "Q0": q[0], "Q1": q[1], "Q2": q[2], "Q3": q[3],
                "TC": tc if i < stages - 1 else "NC",
            }
            # ~PE: active low load.  Truncated counters load zero at `last`.
            if pe_net is not None:
                m["~{PE}"] = pe_net
            elif full:
                m["~{PE}"] = self.net(L1)
            else:
                m["~{PE}"] = self.net(f"{name}_NOT_LAST")
            self.connect(u, m)
            if i < stages - 1:
                carry = tc
        return qnets[:nbits]

    def comparator(self, x: float, y: float, value_nets: Sequence[str],
                   const: int, out: str) -> None:
        """Equality comparator with an active-high output.

        The 74HC688 /P=R output is active low, while every *_LAST consumer on
        these sheets (ROM A10, NAND pe stbes, AND chains) is active high.  The
        raw output therefore goes through an inverter.  Counters wider than
        8 bits use a second 688 for the upper bits; both halves are active low,
        so a 74HC02 NOR produces the final active-high equal signal.
        """
        width = len(value_nets)
        lo_n = f"{out}_LO_N"
        u = self.add_ic("74xx:74HC688", x, y)
        m = {"G": self.net(L0), "P=R": lo_n}
        for i in range(8):
            m[f"P{i}"] = self.net(L1) if (const >> i) & 1 else self.net(L0)
            m[f"R{i}"] = value_nets[i] if i < width else self.net(L0)
        self.connect(u, m)

        if width <= 8:
            self.pending_gates.append(lambda: self.gates.inv(lo_n, out))
            return

        hi_n = f"{out}_HI_N"

        def add_high_half() -> None:
            u2 = self.add_ic("74xx:74HC688", x + 45, y)
            m2 = {"G": self.net(L0), "P=R": hi_n}
            for i in range(8):
                bit = 8 + i
                m2[f"P{i}"] = self.net(L1) if (const >> bit) & 1 else self.net(L0)
                m2[f"R{i}"] = value_nets[bit] if bit < width else self.net(L0)
            self.connect(u2, m2)
            self.gates.nor2(lo_n, hi_n, out)

        self.pending_gates.append(add_high_half)

    def counter_last(self, name: str, x: float, y: float,
                     value_nets: Sequence[str], last: int) -> str:
        out = self.net(f"{name}_LAST")
        if last == (1 << len(value_nets)) - 1:
            # Full-range counter: the final TC pin is the last signal, wired
            # by counter() as NC, so use an equality comparator here instead.
            pass
        self.comparator(x, y, value_nets, last, out)
        return out

    # ---------------------------------------------------------------- adders
    def add283(self, x: float, y: float,
               a: Sequence[str], b: Sequence[str], cin: str,
               s: Sequence[Optional[str]], cout: Optional[str]) -> None:
        u = self.add_ic("74xx:74HC283", x, y)
        m = {}
        for i in range(4):
            m[f"A{i+1}"] = a[i]
            m[f"B{i+1}"] = b[i]
            m[f"S{i+1}"] = s[i] if s[i] is not None else "NC"
        m["C0"] = cin
        m["C4"] = cout if cout is not None else "NC"
        self.connect(u, m)

    def add_chain(self, name: str, x: float, y: float,
                  a_bits: Sequence[str], b_bits: Sequence[str],
                  cin: str, out_bits: Sequence[str],
                  cols: int = 4,
                  final_carry: Optional[str] = None) -> Optional[str]:
        """Ripple-carry adder chain; returns the final carry net or None."""
        n = max(len(a_bits), len(b_bits), len(out_bits))
        stages = (n + 3) // 4
        carry = cin
        for i in range(stages):
            a = list(a_bits[4*i:4*i+4]) + [self.net(L0)] * 4
            b = list(b_bits[4*i:4*i+4]) + [self.net(L0)] * 4
            s: List[Optional[str]] = []
            for j in range(4):
                idx = 4 * i + j
                s.append(out_bits[idx] if idx < len(out_bits) else None)
            if i < stages - 1:
                cout_n = self.net(f"{name}_C{i}")
            else:
                cout_n = final_carry
            self.add283(x + (i % cols) * 55.0,
                        y + (i // cols) * 55.0, a, b, carry, s, cout_n)
            carry = cout_n
        return carry

    def chain_grid(self, grid: Grid, name: str,
                   a_bits: Sequence[str], b_bits: Sequence[str],
                   cin: str, out_bits: Sequence[str],
                   final_carry: Optional[str] = None) -> None:
        n = max(len(a_bits), len(b_bits), len(out_bits))
        stages = (n + 3) // 4
        carry = cin
        for i in range(stages):
            a = list(a_bits[4*i:4*i+4]) + [self.net(L0)] * 4
            b = list(b_bits[4*i:4*i+4]) + [self.net(L0)] * 4
            s: List[Optional[str]] = []
            for j in range(4):
                idx = 4 * i + j
                s.append(out_bits[idx] if idx < len(out_bits) else None)
            if i < stages - 1:
                cout_n = self.net(f"{name}_C{i}")
            else:
                cout_n = final_carry
            x, y = grid.next()
            self.add283(x, y, a, b, carry, s, cout_n)
            carry = cout_n

    def inverter(self, a: str, out: str) -> None:
        self.gates.inv(a, out)

    def and2(self, a: str, b: str, out: str) -> None:
        self.gates.and2(a, b, out)

    def or2(self, a: str, b: str, out: str) -> None:
        self.gates.or2(a, b, out)

    def nand2(self, a: str, b: str, out: str) -> None:
        self.gates.nand2(a, b, out)

    # ------------------------------------------------------------------ muxes
    def mux_bank(self, name: str, x: float, y: float,
                 i0: Sequence[str], i1: Sequence[str], sel: str,
                 out: Sequence[str], dx: float = 55.0) -> None:
        n = len(out)
        chips = (n + 3) // 4
        names = ["a", "b", "c", "d"]
        for c in range(chips):
            u = self.add_ic("74xx:74HC157", x + c * dx, y)
            m = {"S": sel, "E": self.net(L0)}
            for j in range(4):
                idx = 4 * c + j
                if idx >= n:
                    m[f"I0{names[j]}"] = self.net(L0)
                    m[f"I1{names[j]}"] = self.net(L0)
                    m[f"Z{names[j]}"] = "NC"
                else:
                    m[f"I0{names[j]}"] = i0[idx]
                    m[f"I1{names[j]}"] = i1[idx]
                    m[f"Z{names[j]}"] = out[idx]
            self.connect(u, m)

    def mux4_bank(self, name: str, x: float, y: float,
                  sources: Sequence[Sequence[str]], sel0: str, sel1: str,
                  out: Sequence[str]) -> None:
        """4:1 mux built from two 74HC157 levels (4 sources)."""
        n = len(out)
        lo0 = [self.net(f"{name}_L0_{i}") for i in range(n)]
        lo1 = [self.net(f"{name}_L1_{i}") for i in range(n)]
        self.mux_bank(name + "_A", x, y, sources[0], sources[1], sel0, lo0)
        self.mux_bank(name + "_B", x, y + 45.0, sources[2], sources[3], sel0, lo1)
        self.mux_bank(name + "_C", x, y + 90.0, lo0, lo1, sel1, out)

    # ------------------------------------------------------------- registers
    @staticmethod
    def pin_number(sym, pin_name: str) -> str:
        for num, p in sym.pin_objs.items():
            if p.name == pin_name:
                return num
        raise KeyError(f"{sym.ref} has no pin named {pin_name}")

    def reg574(self, x: float, y: float, d: Sequence[str],
               q: Sequence[str], cp: str = "CLK", oe: str = "GND") -> None:
        u = self.add_ic("74xx:74HCT574", x, y)
        m = {"OE": oe, "Cp": cp}
        for i in range(8):
            m[f"D{i}"] = d[i] if i < len(d) else self.net(L0)
            m[f"Q{i}"] = q[i] if i < len(q) else "NC"
        self.connect(u, m)

    def reg574_pipeline(self, xs: Sequence[float], y: float,
                        d_nets: Sequence[str],
                        stage_nets: Sequence[Sequence[str]],
                        cp: str = "CLK", oe: str = "GND") -> None:
        """4-deep register pipeline with direct Q->D wires.

        The old layout put a label on every Q output and every D input, so the
        two label texts in a 50 mm gap drew on top of each other.  A straight
        wire from Q to the next D carries the same net; exactly one label is
        placed on that wire, and the same net name still connects to the LUT
        input.
        """
        assert len(xs) == len(stage_nets)
        last = len(xs) - 1
        syms = []
        for i, x in enumerate(xs):
            u = self.add_ic("74xx:74HCT574", x, y)
            m = {"OE": oe, "Cp": cp}
            skip: List[str] = []
            for j in range(8):
                dn = self.pin_number(u, f"D{j}")
                qn = self.pin_number(u, f"Q{j}")
                if i == 0:
                    m[dn] = d_nets[j]
                else:
                    skip.append(dn)
                if i == last:
                    m[qn] = stage_nets[i][j]
                else:
                    skip.append(qn)
            self.connect(u, m, skip=skip)
            syms.append(u)
        for i in range(last):
            for j in range(8):
                qn = self.pin_number(syms[i], f"Q{j}")
                dn = self.pin_number(syms[i + 1], f"D{j}")
                qx, qy = syms[i].pins[qn]
                dx, dy = syms[i + 1].pins[dn]
                assert abs(qy - dy) < 1e-6, "Q/D pins are not on the same row"
                self.sh.add_wire(qx, qy, dx, dy)
                if stage_nets[i][j] in self.global_nets:
                    self.sh.add_global_label(stage_nets[i][j], qx + 2.54, qy, 0)
                else:
                    self.sh.add_label(stage_nets[i][j], qx + 2.54, qy, 0, "left")

    def hold_mux8(self, x: float, y: float, hold: Sequence[str],
                  shift_in: Sequence[str], sel: str,
                  out: Sequence[str]) -> None:
        """8-bit 2:1 hold mux (2x74HC157).

        ``hold`` is the register's own Q (feedback), ``shift_in`` is the
        previous stage (or the input latch).  With ``sel`` low the register
        keeps its value; with ``sel`` high it shifts.  This is the enable
        that the free-running 74HCT574 pipeline was missing.
        """
        names = ["a", "b", "c", "d"]
        for c in range(2):
            u = self.add_ic("74xx:74HC157", x + c * 40, y)
            m = {"S": sel, "E": self.net(L0)}
            for j in range(4):
                idx = 4 * c + j
                m[f"I0{names[j]}"] = hold[idx]
                m[f"I1{names[j]}"] = shift_in[idx]
            zskip = [self.pin_number(u, f"Z{names[j]}") for j in range(4)]
            self.connect(u, m, skip=zskip)
            for j in range(4):
                idx = 4 * c + j
                self.sh.stub_label(u, self.pin_number(u, f"Z{names[j]}"),
                                   out[idx], length=2.54, local=True)

    def lut_rom_pair(self, x: float, y: float,
                     a_bits: Sequence[str], b_bits: Sequence[str],
                     prod: Sequence[str]) -> None:
        """One 8x8 multiplier lane: two 27C512 (low/high product byte).

        Address = {A[7:0], B[7:0]} (A is the high byte, matching
        model/lut/lut_lo.bin and lut_hi.bin).  The pipeline registers are the
        address registers, so no extra address latch is required.
        """
        for k in range(2):
            u = self.add_ic("Memory_EPROM:27C512", x, y + k * 70)
            m = {"~{CE}": self.net(L0), "~{OE}": self.net(L0)}
            for i in range(8):
                m[f"A{i}"] = b_bits[i]
                m[f"A{8+i}"] = a_bits[i]
                m[f"D{i}"] = prod[8 * k + i]
            self.connect(u, m)

    def ab_lut_path(self, x: float, y: float,
                    data: Sequence[str], a_load: str, b_load: str,
                    shift_en: str,
                    a_lat: Sequence[str], b_lat: Sequence[str],
                    a_st: Sequence[Sequence[str]],
                    b_st: Sequence[Sequence[str]],
                    lut_prod: Sequence[Sequence[str]],
                    b_zero: Optional[str] = None) -> None:
        """A/B input latches, four hold-enabled pipeline stages, four LUT lanes.

        Layout (all connections by label, so the block can be moved):
          row y      : A latch + A stage 0..3 (80 mm pitch)
          row y+35   : B latch + B stage 0..3
          row y+75   : A hold muxes (2x157 per stage, 40 mm apart)
          row y+110  : B hold muxes
          column x+400: LUT ROM pairs (2x27C512 per lane, 140 mm pitch)
        """
        self.reg574(x, y, data, a_lat, cp=a_load)
        if b_zero is None:
            self.reg574(x, y + 35, data, b_lat, cp=b_load)
        else:
            bd = [self.net(f"B_LAT_D{i}") for i in range(8)]
            self.mux_bank("BZERO", x - 140, y + 35, data,
                          [self.net(L0)] * 8, b_zero, bd, dx=65.0)
            self.reg574(x, y + 35, bd, b_lat, cp=b_load)

        for i in range(4):
            sx = x + 60 + i * 80
            ad = [self.net(f"A{i}_D{j}") for j in range(8)]
            bd = [self.net(f"B{i}_D{j}") for j in range(8)]
            self.reg574(sx, y, ad, a_st[i], cp="CLK")
            self.reg574(sx, y + 35, bd, b_st[i], cp="CLK")
            self.hold_mux8(sx, y + 75, a_st[i],
                           a_lat if i == 0 else a_st[i - 1], shift_en, ad)
            self.hold_mux8(sx, y + 110, b_st[i],
                           b_lat if i == 0 else b_st[i - 1], shift_en, bd)

        for lane in range(4):
            self.lut_rom_pair(x + 400, y + lane * 140,
                              a_st[lane], b_st[lane], lut_prod[lane])

    def dff(self, x: float, y: float, d: str, q: str,
            clk: str = "CLK", reset: str = "RESET_N") -> None:
        """One 74HC74 D flip-flop (async reset, set tied off).

        The package's second half is tied off and the unit-3 power pins are
        placed explicitly, matching the other 74HC74 uses in this project.
        """
        u = self.add_ic("74xx:74HC74", x, y, unit=1)
        self.connect(u, {"~{R}": reset, "D": d, "C": clk,
                         "~{S}": "+5V", "Q": q, "~{Q}": "NC"})
        up = self.add_ic("74xx:74HC74", x, y + 25, unit=2, ref=u.ref)
        self.connect(up, {"~{R}": reset, "D": self.net(L0), "C": clk,
                          "~{S}": "+5V", "Q": "NC", "~{Q}": "NC"})
        upw = self.add_ic("74xx:74HC74", x, y + 50, unit=3, ref=u.ref)
        self.connect(upw, {"VCC": "+5V", "GND": "GND"})

    def reg273(self, x: float, y: float, d: Sequence[str],
               q: Sequence[str], mr: str = "RESET_N") -> None:
        u = self.add_ic("74xx:74HCT273", x, y)
        m = {"~{Mr}": mr, "Cp": "CLK"}
        for i in range(8):
            m[f"D{i}"] = d[i] if i < len(d) else self.net(L0)
            m[f"Q{i}"] = q[i] if i < len(q) else "NC"
        self.connect(u, m)

    # ------------------------------------------------------------- buffers
    def buf541(self, x: float, y: float, a: Sequence[str], ynets: Sequence[str],
               oe: Optional[str] = None) -> None:
        u = self.add_ic("74xx:74HCT541", x, y)
        oe_net = oe if oe is not None else self.net(L0)
        m = {"G1": oe_net, "G2": oe_net}
        for i in range(8):
            m[f"A{i}"] = a[i] if i < len(a) else self.net(L0)
            m[f"Y{i}"] = ynets[i] if i < len(ynets) else "NC"
        self.connect(u, m)

    def transceiver245(self, x: float, y: float, a: Sequence[str],
                       b: Sequence[str], direction: str, ce: str) -> None:
        u = self.add_ic("74xx:74HC245", x, y)
        m = {"A->B": direction, "CE": ce}
        for i in range(8):
            m[f"A{i}"] = a[i]
            m[f"B{i}"] = b[i]
        self.connect(u, m)

    def decoder138(self, x: float, y: float, a: Sequence[str],
                   e0: str, e1: str, e2: str, ys: Sequence[str]) -> None:
        u = self.add_ic("74xx:74HC138", x, y)
        m = {"A0": a[0], "A1": a[1], "A2": a[2],
             "~{E0}": e0, "~{E1}": e1, "E2": e2}
        for i in range(8):
            m[f"~{{Y{i}}}"] = ys[i] if i < len(ys) else "NC"
        self.connect(u, m)

    def rom27c512(self, x: float, y: float, addr: Sequence[str],
                  data: Sequence[str]) -> None:
        u = self.add_ic("Memory_EPROM:27C512", x, y)
        m = {"~{CE}": self.net(L0), "~{OE}": self.net(L0)}
        for i in range(16):
            m[f"A{i}"] = addr[i] if i < len(addr) else self.net(L0)
        for i in range(8):
            m[f"D{i}"] = data[i]
        self.connect(u, m)

    def cap(self, x: float, y: float) -> None:
        c = self.add_ic("Device:C", x, y)
        self.sh.stub_label(c, "1", "+5V", local=False)
        self.sh.stub_label(c, "2", "GND", local=False)

    def testpoint(self, x: float, y: float, net: str, local: bool = True) -> None:
        tp = self.sh.add_symbol("Connector:TestPoint", self.next_ref(), "TP",
                                x, y, footprint=footprint_for("Connector:TestPoint"))
        gx, gy = tp.pins["1"]
        self.sh.add_wire(gx, gy, gx, gy + 5.08)
        self.sh.add_wire(gx, gy + 5.08, gx + 15.24, gy + 5.08)
        if local:
            self.sh.add_label(net, gx + 15.24, gy + 5.08, 0, "left")
        else:
            self.sh.add_global_label(net, gx + 15.24, gy + 5.08, 0)

    # --------------------------------------------------------------- output
    def write(self, path: str) -> None:
        self.sh.write(path)


# ---------------------------------------------------------------------------
# S07 CONV1
# ---------------------------------------------------------------------------
def build_conv1() -> str:
    p = lambda s: f"C1_{s}"
    globals_ = (["CLK", "RESET_N", "C1_START", "C1_DONE", "C1_BUSY",
                 "C1_BUSY_N", "MEM_nCE", "MEM_nOE", "MEM_nWE",
                 "MEM_ACK", "MEM_DONE", "MEM_BUSY",
                 "C1_MEM_REQ", "C1_MEM_WE"]
                + [f"DATA{i}" for i in range(8)]
                + [f"C1_ADDR{i}" for i in range(16)]
                + [f"C1_MEM_nCE_{x}" for x in ("IN", "W", "OUT", "B", "Q", "MC")]
                # Simple V2 Requant interface to S13_Requant_C1.  Only the
                # accumulator, start/strobe and status nets cross sheets.
                + [f"C1_ACC{i}" for i in range(32)]
                + [f"C1_REQ_Q{i}" for i in range(8)]
                + ["C1_REQ_START", "C1_REQ_QSTB",
                   "C1_SAT_FLAG", "C1_REQ_BUSY", "C1_REQ_DONE"])
    e = EngineBuilder("C1", "S07_Conv1 - CONV1 Engine (28x28x1 -> 24x24x8, K=5)",
                      paper="A0", global_nets=globals_)
    # Reference block 7xxx (the renumber tool then leaves this sheet alone, so
    # incremental rebuilds keep the S07 refs stable alongside S13 14xxx).
    e.refn = 7000
    e.text("S07  CONV1 ENGINE", 15, 10, size=3.0, bold=True)
    e.text(
        "H=28 W=28 Cin=1 Cout=8 K=5  ->  Hout=24 Wout=24\n"
        "Loop order: oc(0..7) -> oy(0..23) -> ox(0..23) -> ky(0..4) -> kx(0..4); ic=0 (Cin=1).\n"
        "MAC/point = 5x5 = 25; points = 8x24x24 = 4608; total MAC = 115200.\n"
        "Input layout HWC C=1:  IN_ADDR = (oy+ky)*28 + (ox+kx)            range 0..783\n"
        "Weight layout [oc][ky][kx]:  W_ADDR = oc*25 + ky*5 + kx          range 0..199\n"
        "Output layout HWC C=8:  OUT_ADDR = oc*576 + oy*24 + ox          range 0..4607\n"
        "Output order: for oc, for oy, for ox -> one uint8 per output point (little-endian byte 0 only).",
        15, 18, size=1.55,
    )
    e.text(
        "Local FSM: 2x27C512 16-bit microcode (ROM1: next state + flags, ROM2: control), "
        "74HCT273 state register, 2x74HCT574 output registers, 74HC138 state decoder.",
        430, 748, size=1.15,
    )
    e.text(
        "MAC datapath: 4x LUT_Mult_Unit (S_LUT_Mult_1 interface, qualified nets LUT1..4), "
        "4-deep input/weight pipeline (8x74HCT574), 4-product 18-bit adder tree, "
        "32-bit accumulator (8x74HC283 + 4x74HCT574), requant core on S13 "
        "(gate-level 32x16 serial multiplier, 49-bit correction, 64-bit requant).",
        430, 756, size=1.15,
    )

    # --- loop counters ----------------------------------------------------
    OC = e.counter("OC", 20, 62, 3, 7, enable=p("OC_EN"), pe_net=p("OC_PE_N"))
    e.comparator(20, 122, OC, 7, p("OC_LAST"))
    OY = e.counter("OY", 115, 62, 5, 23, enable=p("OY_EN"), pe_net=p("OY_PE_N"))
    e.comparator(115, 122, OY, 23, p("OY_LAST"))
    OX = e.counter("OX", 250, 62, 5, 23, enable=p("OX_EN"), pe_net=p("OX_PE_N"))
    e.comparator(240, 122, OX, 23, p("OX_LAST"))
    KY = e.counter("KY", 20, 188, 3, 4, enable=p("KY_EN"), pe_net=p("KY_PE_N"))
    e.comparator(20, 248, KY, 4, p("KY_LAST"))
    KX = e.counter("KX", 115, 188, 3, 4, enable=p("MAC_EN"), pe_net=p("KX_PE_N"))
    e.comparator(115, 248, KX, 4, p("KX_LAST"))
    SP = e.counter("SP", 370, 62, 10, 575, enable=p("OUT_STB"),
                   pe_net=p("SP_PE_N"), vertical=True)
    e.comparator(340, 230, SP, 575, p("SP_LAST"))

    # ic is fixed at zero (Cin=1); keep a real 74HC161 held cleared.
    u = e.add_ic("74xx:74HC161", 240, 188)
    e.connect(u, {
        "~{MR}": p("CNT_RESET_N"), "CP": "CLK", "CEP": "GND", "CET": "GND",
        "~{PE}": "+5V", "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
        "Q0": p("IC0"), "Q1": "NC", "Q2": "NC", "Q3": "NC", "TC": "NC",
    })
    e.testpoint(405, 245, p("IC0"))

    # --- loop enables and synchronous-load strobes -----------------------
    e.and2("RESET_N", p("LOOP_CLR_N"), p("CNT_RESET_N"))
    e.and2(p("KX_LAST"), p("MAC_EN"), p("KY_EN"))
    e.and2(p("KX_LAST"), p("KY_LAST"), p("KXKY"))
    e.and2(p("KXKY"), p("MAC_EN"), p("OX_EN"))
    e.and2(p("KXKY"), p("OX_LAST"), p("OXY"))
    e.and2(p("OXY"), p("MAC_EN"), p("OY_EN"))
    e.and2(p("OXY"), p("OY_LAST"), p("OXYO"))
    e.and2(p("OXYO"), p("MAC_EN"), p("OC_EN"))
    # Active-low synchronous load.  Each level loads only when every inner
    # loop is also at its last value, otherwise the outer counter is cleared
    # as soon as it reaches its own maximum (V7: masked while the 688 outputs
    # were still active-low).
    e.nand2(p("KX_LAST"), p("MAC_EN"), p("KX_PE_N"))
    e.nand2(p("KXKY"), p("MAC_EN"), p("KY_PE_N"))
    e.nand2(p("OXY"), p("MAC_EN"), p("OX_PE_N"))
    e.nand2(p("OXYO"), p("MAC_EN"), p("OY_PE_N"))
    e.nand2(p("OC_LAST"), p("OC_EN"), p("OC_PE_N"))
    e.nand2(p("SP_LAST"), p("OUT_STB"), p("SP_PE_N"))

    # --- address adders ---------------------------------------------------
    AG = Grid(15, 410, 62, 48, 4)
    SY = [p(f"SY{i}") for i in range(5)]
    SX = [p(f"SX{i}") for i in range(5)]
    NSY = [p(f"NSY{i}") for i in range(5)]
    for i in range(5):
        e.inverter(p(f"SY{i}"), p(f"NSY{i}"))
    e.chain_grid(AG, "SY", OY, KY, "GND", SY)
    e.chain_grid(AG, "SX", OX, KX, "GND", SX)

    SY28 = [p(f"SY28_{i}") for i in range(10)]
    a_sy28 = ["GND"] * 5 + SY
    b_sy28 = ["GND", "GND"] + NSY + ["GND", "GND", "GND"]
    e.chain_grid(AG, "SY28", a_sy28, b_sy28, "+5V", SY28)

    INA = [p(f"IN_ADDR{i}") for i in range(10)]
    e.chain_grid(AG, "INA", SY28, SX + ["GND"] * 5, "GND", INA)

    OC5 = [p(f"OC5_{i}") for i in range(5)]
    e.chain_grid(AG, "OC5", OC, ["GND", "GND"] + OC, "GND", OC5)
    OC25 = [p(f"OC25_{i}") for i in range(8)]
    e.chain_grid(AG, "OC25", OC5, ["GND", "GND"] + OC5, "GND", OC25)
    KY5 = [p(f"KY5_{i}") for i in range(5)]
    e.chain_grid(AG, "KY5", KY, ["GND", "GND"] + KY, "GND", KY5)
    W1 = [p(f"W1_{i}") for i in range(8)]
    e.chain_grid(AG, "W1", OC25, KY5 + ["GND"] * 3, "GND", W1)
    WA = [p(f"W_ADDR{i}") for i in range(8)]
    e.chain_grid(AG, "WA", W1, KX + ["GND"] * 5, "GND", WA)

    OC9 = [p(f"OC9_{i}") for i in range(6)]
    e.chain_grid(AG, "OC9", ["GND", "GND", "GND"] + OC, OC, "GND", OC9)
    OUTA = [p(f"OUT_ADDR{i}") for i in range(13)]
    e.chain_grid(AG, "OUTA", ["GND"] * 6 + OC9, SP + ["GND"] * 2,
                 "GND", OUTA[:12], final_carry=OUTA[12])

    # --- A/B operand path: latches, hold-enabled pipeline, 8x27C512 LUT ----
    # A_LOAD/B_LOAD capture the byte returned by the S02 read transaction;
    # SHIFT_EN moves both latches into the four-stage pipeline once per MAC.
    # The 2:1 hold muxes keep the pipeline frozen during S02 wait states.
    A_ST = [[p(f"A{lane}_{i}") for i in range(8)] for lane in range(4)]
    B_ST = [[p(f"B{lane}_{i}") for i in range(8)] for lane in range(4)]
    A_LAT = [p(f"A_LAT{i}") for i in range(8)]
    B_LAT = [p(f"B_LAT{i}") for i in range(8)]
    DATA = [f"DATA{i}" for i in range(8)]
    LUT_PROD = [[p(f"P{lane+1}_{i}") for i in range(16)] for lane in range(4)]
    e.ab_lut_path(700, 40, DATA, p("A_LOAD"), p("B_LOAD"),
                  p("SHIFT_EN"), A_LAT, B_LAT, A_ST, B_ST, LUT_PROD,
                  b_zero=p("PAD_ACTIVE"))

    # 4-product adder tree: two 17-bit sums, then one 18-bit sum.
    TG = Grid(270, 410, 65, 48, 2)
    S12 = [p(f"S12_{i}") for i in range(16)]
    e.chain_grid(TG, "S12", LUT_PROD[0], LUT_PROD[1], "GND", S12,
                 final_carry=p("S12_16"))
    S34 = [p(f"S34_{i}") for i in range(16)]
    e.chain_grid(TG, "S34", LUT_PROD[2], LUT_PROD[3], "GND", S34,
                 final_carry=p("S34_16"))
    PSUM = [p(f"PSUM{i}") for i in range(18)]
    e.chain_grid(TG, "PSUM", S12 + [p("S12_16")], S34 + [p("S34_16")],
                 "GND", PSUM[:17], final_carry=PSUM[17])

    # --- 32-bit accumulator (8x74HC283 + 4x74HC273) ----------------------
    # 74HC273 has an asynchronous master reset, so ACC_CLR_N clears the
    # register itself.  The old 574 + 32 pull-down tri-state trick left the
    # old value on the bus after ACC_CLR fell and could add it twice.
    BM = [p(f"BM{i}") for i in range(18)]
    e.mux_bank("BMSK", 610, 450, ["GND"] * 18, PSUM, p("ACC_LD"), BM, dx=65.0)
    ACC = [p(f"ACC{i}") for i in range(32)]
    SUM = [p(f"SUM{i}") for i in range(32)]
    ACCG = Grid(600, 310, 65, 45, 4)
    e.chain_grid(ACCG, "ACCSUM", ACC, BM + ["GND"] * 14, "GND", SUM)
    e.and2("RESET_N", p("ACC_CLR_N"), p("ACC_MR_N"))
    for i in range(4):
        e.reg273(610 + i * 65, 395,
                 SUM[8*i:8*i+8], ACC[8*i:8*i+8], mr=p("ACC_MR_N"))

    # --- simple V2 requant interface (S13) --------------------------------
    # S13 implements Q = clamp(ACC >> 8, 0, 255) with a two-cycle handshake.
    # There is no bias, zero-point, multiplier or parameter port.  The
    # testpoints anchor the four cross-sheet status nets on this sheet.
    for k, nm in enumerate(("REQ_QSTB", "SAT_FLAG", "REQ_BUSY", "REQ_DONE")):
        e.testpoint(980, 560 + k * 22, p(nm), local=False)

    # Output byte hold register and memory data transceiver.
    QBYTE = [p(f"REQ_Q{i}") for i in range(8)]
    OUTD = [p(f"OUT_D{i}") for i in range(8)]
    OUTQ = [p(f"OUT_DATA{i}") for i in range(8)]
    e.mux_bank("OUTHOLD", 330, 300, OUTQ, QBYTE, p("REQ_QSTB"), OUTD, dx=70.0)
    e.reg574(330, 350, OUTD, OUTQ)
    e.transceiver245(395, 350, OUTQ, DATA, "+5V", p("OUT_BUF_N"))
    e.nand2(p("MEM_REQ"), p("MEM_WE"), p("OUT_BUF_N"))

    # --- address source mux (74HC157) ------------------------------------
    def pad16(bits):
        return list(bits) + ["GND"] * (16 - len(bits))
    MX1 = [p(f"MX1_{i}") for i in range(16)]
    MX2 = [p(f"MX2_{i}") for i in range(16)]
    e.mux_bank("MX1", 430, 220, pad16(INA), pad16(WA), p("ADD_SEL0"), MX1, dx=65.0)
    e.mux_bank("MX2", 610, 265, MX1, pad16(OUTA), p("ADD_SEL1"), MX2, dx=65.0)

    # --- local FSM: microcode ROMs, state and output registers ------------
    # 13 states: 0 reset, 1 idle, 2 addr IN, 3 wait A, 4 addr W, 5 wait B,
    # 6 shift, 7 accumulate, 8 requant request, 9 addr OUT, 10 write,
    # 11 next point, 12 done.
    ST = [p(f"ST{i}") for i in range(5)]
    # C1_START is already synchronized by the supervisor FSM (S01).
    START_S = "C1_START"
    POINT_LAST = p("POINT_LAST")
    REQ_DONE = p("REQ_DONE")
    IMAGE_LAST = p("SP_LAST")
    ROMA = ST + [START_S, POINT_LAST, "MEM_ACK", "MEM_DONE",
                 REQ_DONE, IMAGE_LAST]
    MC1 = [p(f"MC1_{i}") for i in range(8)]
    MC2 = [p(f"MC2_{i}") for i in range(8)]
    e.rom27c512(445, 470, ROMA, MC1)
    e.rom27c512(515, 470, ROMA, MC2)
    e.reg273(425, 528, MC1[:5], ST, mr="RESET_N")
    # flags: BUSY, DONE, ACC_CLR_N (active low) in bits 5..7 of ROM1
    e.reg574(475, 528, ["GND"] * 5 + MC1[5:8],
             ["NC"] * 5 + ["C1_BUSY", "C1_DONE", p("ACC_CLR_N")])
    CTRL = [p("MAC_EN"), p("MEM_REQ"), p("MEM_WE"), p("OUT_STB"),
            p("ADD_SEL0"), p("ADD_SEL1"), "NC", "NC"]
    e.reg574(535, 528, MC2, CTRL)
    # State decode: Y0=reset, Y3=wait A, Y5=wait B, Y6=shift, Y7=acc.
    # V8: qualify the state decoder with ST3.  States 0..7 are the only ones
    # that use these outputs, but without the ST3 gate state 8 (requant, low
    # three bits = 000) also decodes as Y0 and clears every loop counter once
    # per output point, so the engine restarts from point 0 forever.
    e.decoder138(600, 528, ST[:3], "GND", p("ST3"), "+5V",
                 [p("LOOP_CLR_N"), "NC", "NC", p("WAIT_A_N"),
                  "NC", p("WAIT_B_N"), p("SHIFT_N"), p("ACC_N")])
    # Second decoder: states 8..15; Y0 = E_REQ (state 8).
    e.decoder138(670, 528, ST[:3], "GND", "GND", p("ST3"),
                 [p("REQ_START_N"), "NC", "NC", "NC", "NC", "NC", "NC", "NC"])
    e.inverter(p("WAIT_A_N"), p("WAIT_A"))
    e.inverter(p("WAIT_B_N"), p("WAIT_B"))
    e.inverter(p("SHIFT_N"), p("SHIFT_EN"))
    e.inverter(p("ACC_N"), p("ACC_EN"))
    e.inverter(p("REQ_START_N"), p("REQ_START"))
    e.and2(p("WAIT_A"), "MEM_ACK", p("A_LOAD"))
    e.and2(p("WAIT_B"), "MEM_ACK", p("B_LOAD"))

    # Lane counter counts accumulator groups of four MACs.  It loads zero on
    # the fourth ACC_EN, so ACC_LD is a clean one-cycle pulse every 4 MACs.
    e.counter("LANE", 960, 450, 2, 3, enable=p("ACC_EN"),
              pe_net=p("LANE_PE_N"))
    e.nand2(p("LANE0"), p("LANE1"), p("LANE_PE_N"))
    e.and2(p("LANE0"), p("LANE1"), p("LANE_LAST"))
    e.and2(p("ACC_EN"), p("LANE_LAST"), p("ACC_LD"))

    # CONV1 padding: 25 real MACs + 3 zero-weight MACs = 28 (7 groups of 4).
    # PAD_ACTIVE forces the B latch to zero for the three pad MACs; PAD_LAST
    # is captured one cycle before E_ACC so the FSM sees it after the counter
    # wraps.
    e.counter("PAD", 960, 520, 2, 3, enable=p("PAD_EN"), pe_net="+5V")
    e.or2(p("PAD0"), p("PAD1"), p("PAD_ACTIVE"))
    e.and2(p("PAD0"), p("PAD1"), p("PAD_LAST"))
    e.and2(p("KX_LAST"), p("KY_LAST"), p("KXKY_LAST"))
    e.or2(p("PAD_ACTIVE"), p("KXKY_LAST"), p("PAD_GO"))
    e.and2(p("MAC_EN"), p("PAD_GO"), p("PAD_EN"))
    e.dff(1060, 450, p("PAD_LAST"), POINT_LAST)

    # SP is at its last output point during E_NEXT; SP_LAST is therefore the
    # correct IMAGE_LAST (the OX/OY/OC counters have already advanced).

    # --- shared memory interface (S02 is the only timing controller) ------
    # C1 no longer contains an S02 instance.  MEM_nCE/nOE/nWE and the
    # MEM_ACK/DONE/BUSY handshake are shared global nets driven by S02; S11
    # consumes C1_MEM_REQ/WE and the region select.  The 74HC138 is qualified
    # by the (active-low) shared MEM_nCE, so exactly one region is low during a
    # transaction and all outputs are high when the array is idle.
    e.decoder138(460, 355, [p("ADD_SEL0"), p("ADD_SEL1"), "GND"],
                 "MEM_nCE", "GND", "+5V",
                 [p("MEM_nCE_IN"), p("MEM_nCE_W"), p("MEM_nCE_OUT"),
                  p("MEM_nCE_B"), p("MEM_nCE_Q"), p("MEM_nCE_MC"), "NC", "NC"])

    # Address bus isolation: only the running engine drives C1_ADDR.
    e.inverter("C1_BUSY", p("BUSY_N"))
    e.buf541(450, 400, MX2[:8], [f"C1_ADDR{i}" for i in range(8)],
             oe=p("BUSY_N"))
    e.buf541(510, 400, MX2[8:], [f"C1_ADDR{i}" for i in range(8, 16)],
             oe=p("BUSY_N"))

    # Passive monitor of the shared S02 handshake.  The real FSM consumer is
    # the ROM address input (MEM_ACK); this buffer makes nCE/nOE/nWE and
    # DONE/BUSY explicit loads and brings all six to test points so no
    # buffer output is left dangling.
    ust = e.add_ic("74xx:74HCT541", 950, 600)
    e.connect(ust, {
        "G1": "GND", "G2": "GND",
        "A0": "MEM_nCE", "A1": "MEM_nOE", "A2": "MEM_nWE",
        "A3": "MEM_ACK", "A4": "MEM_DONE", "A5": "MEM_BUSY",
        "A6": "GND", "A7": "GND",
        "Y0": p("MEM_STAT_nCE"), "Y1": p("MEM_STAT_nOE"),
        "Y2": p("MEM_STAT_nWE"), "Y3": p("MEM_STAT_ACK"),
        "Y4": p("MEM_STAT_DONE"), "Y5": p("MEM_STAT_BUSY"),
        "Y6": "NC", "Y7": "NC",
    })
    for k, st in enumerate(("nCE", "nOE", "nWE", "ACK", "DONE", "BUSY")):
        e.testpoint(1000, 620 + k * 22, p(f"MEM_STAT_{st}"))

    # --- status / notes ---------------------------------------------------
    e.text(
        "Microcode map (2 x 27C512):  A[4:0]=ST0..ST4; A5=START_S; A6=POINT_LAST; "
        "A7=MEM_ACK; A8=MEM_DONE; A9=REQ_DONE; A10=SP_LAST.\n"
        "ROM1 D[4:0]=next state, D5=BUSY, D6=DONE, D7=ACC_CLR_N (active low).  "
        "ROM2 D0=MAC_EN, D1=MEM_REQ, D2=MEM_WE, D3=OUT_STB, D4=ADD_SEL0, "
        "D5=ADD_SEL1, D6/D7=0.\n"
        "State sequence: 0 E_RESET -> 1 E_IDLE -> 2 E_ADDR_IN -> 3 E_WAIT_A -> "
        "4 E_ADDR_W -> 5 E_WAIT_B -> 6 E_SHIFT -> 7 E_ACC -> (loop or) 8 E_REQ -> "
        "9 E_ADDR_OUT -> 10 E_WRITE -> 11 E_NEXT -> 12 E_DONE.",
        430, 620, size=1.0,
    )
    e.text(
        "A/B path: A_LAT/B_LAT 74HCT574 capture the S02 read data on A_LOAD/"
        "B_LOAD; four 74HCT574 stages per operand with 2:1 74HC157 hold muxes "
        "(SHIFT_EN).  Eight 27C512 per engine (two per lane) form four "
        "independent 8x8 LUT multipliers; PROD=A*B, never x*x.\n"
        "CONV1 pads 25 MACs to 28 with three zero-B MACs (PAD_ACTIVE forces the "
        "B latch to zero) so the 4-MAC accumulator groups are complete.",
        430, 650, size=1.0,
    )
    e.text(
        "Memory interface is shared: S02 is the only timing controller and drives "
        "MEM_nCE/nOE/nWE plus MEM_ACK/DONE/BUSY globally.  S11 merges "
        "C1_MEM_REQ/WE and encodes C1_MEM_nCE_* into REGION/MEM_SEL.  "
        "C1_ADDR is driven only while C1_BUSY=1 (74HCT541 OE = C1_BUSY_N).  "
        "The 74HC138 region decoder is qualified by the active-low MEM_nCE.",
        430, 680, size=1.0,
    )
    e.text(
        "LUT ROMs: model/lut/lut_lo.bin and lut_hi.bin; address A[15:8]=A "
        "operand, A[7:0]=B operand; low ROM = product[7:0], high ROM = "
        "product[15:8].  All 24 ROMs (8 per engine) are independent.",
        430, 710, size=1.0,
    )

    e.text("Decoupling: one 100 nF per IC (banked at S10 power entry; see BOM).",
           430, 740, size=1.0)

    out = os.path.join(PROJECT_DIR, "S07_Conv1.kicad_sch")
    e.flush_pending()
    e.write(out)
    import json
    with open(os.path.join(PROJECT_DIR, "output", "s07_pins.json"), "w", encoding="utf-8") as f:
        json.dump([{"ref": sy.ref, "lib": sy.lib_id,
                    "pins": {n: list(xy) for n, xy in sy.pins.items()}}
                   for sy in e.sh.symbols], f, indent=1)
    return out


def main() -> int:
    write_block_library(BLOCK_LIB)
    print("wrote", build_conv1())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
