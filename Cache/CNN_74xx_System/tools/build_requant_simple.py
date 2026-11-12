"""Build the V2 simple requant cores S13/S15/S17.

V2 contract (deliberately small and readable):

  * symmetric quantization: ZP_X = ZP_W = ZP_OUT = 0
  * zero bias: the trained model must export bias = 0
  * one fixed power-of-two scale per layer: q = clamp(ACC >> SHIFT, 0, 255)
  * FC2 is not requantized: the raw signed 32-bit ACC is emitted little-endian
    (4 bytes) and Argmax compares the same scale for every class.

There is no M multiplier, no 49-bit zero-point correction, no PSEL/PDATA/PLOAD
port and therefore no parameter-loader sheets.  The arithmetic is only:

    QRAW[i] = ACC[SHIFT+i]              if SHIFT+i < 32
              ACC[31]                   otherwise (arithmetic sign extension)
    NEG     = ACC[31]
    HIGH    = OR(ACC[SHIFT+8 .. 31])
    SAT_POS = HIGH & ~NEG
    QVAL    = NEG ? 0 : (SAT_POS ? 255 : QRAW)
    Q       = QVAL registered on START
    QSTB    = one CLK after START
    DONE    = two CLKs after START
    BUSY    = START | QSTB | DONE

FC1 uses the same uint8 path.  FC2 uses a 4:1 byte mux over ACC[31:0],
selected by BC[1:0]; QSTB falls on BC=0..3 and DONE on BC=3.  The S09
byte counter and OUTHOLD are driven directly by QSTB.

The generated sheets are intentionally stand-alone: global labels carry
C1_*/C2_*/FC_* nets between the engine sheet and these cores.

Run:
    python tools/build_requant_simple.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import default_registry, footprint_for, Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"
REG = default_registry()

# Fixed per-layer right shift.  These are build-time constants, not host
# parameters.  Re-run this script to change them.
SHIFT = {"C1": 9, "C2": 10, "FC1": 9}

SECTION = ("a", "b", "c", "d")
GATE_PINS = {
    "74xx:74HC08": {1: ("1", "2", "3"), 2: ("4", "5", "6"),
                    3: ("9", "10", "8"), 4: ("12", "13", "11")},
    "74xx:74HC32": {1: ("1", "2", "3"), 2: ("4", "5", "6"),
                    3: ("9", "10", "8"), 4: ("12", "13", "11")},
    "74xx:74HC04": {1: ("1", "2"), 2: ("3", "4"), 3: ("5", "6"),
                    4: ("9", "8"), 5: ("11", "10"), 6: ("13", "12")},
}
GATE_POWER = {"74xx:74HC08": 5, "74xx:74HC32": 5, "74xx:74HC04": 7}


class Refs:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> str:
        self.n += 1
        return f"U{self.n}"


class Sheet:
    def __init__(self, title: str, prefix: str, globals_: set[str]) -> None:
        self.prefix = prefix
        self.globals = globals_
        self.refs = Refs()
        self.sh = Schematic(
            REG, project=PROJECT, instance_path="/__ROOT_UUID__",
            title=title, paper="A1",
        )
        self.ics: list = []
        self._gate_free: dict[str, list[tuple[str, int]]] = {}
        self._gate_power: set[str] = set()
        self._pwr = 0
        self._place = 0

    def _next_pos(self) -> tuple[float, float]:
        n = self._place
        self._place += 1
        return 45 + (n % 8) * 95, 120 + (n // 8) * 85

    def is_global(self, net: str) -> bool:
        return net in self.globals

    def add(self, lib: str, x: float, y: float, unit: int = 1, value=None):
        ref = self.refs.next()
        x, y = self._next_pos()
        sym = self.sh.add_symbol(
            lib, ref, value, x, y, unit=unit,
            footprint=footprint_for(lib),
        )
        self.ics.append(sym)
        return sym

    def add_unit(self, lib: str, ref: str, x: float, y: float, unit: int):
        x, y = self._next_pos()
        sym = self.sh.add_symbol(
            lib, ref, lib.split(":")[-1], x, y, unit=unit,
            footprint=footprint_for(lib),
        )
        self.ics.append(sym)
        return sym

    def connect(self, sym, nmap) -> None:
        for num, p in sym.pin_objs.items():
            net = nmap.get(num, nmap.get(p.name))
            if net is None:
                if p.name in ("VCC", "Vdd"):
                    net = "+5V"
                elif p.name == "GND":
                    net = "GND"
                elif p.etype == "no_connect":
                    continue
                else:
                    net = "NC"
            if net == "NC":
                self.sh.stub_nc(sym, num)
            elif net in ("+5V", "GND"):
                self.sh.stub_power(sym, num, net, self.pwr_ref())
            else:
                self.sh.stub_label(sym, num, net, local=not self.is_global(net))

    def pwr_ref(self) -> str:
        self._pwr += 1
        return f"#PWR{self._pwr:03d}"

    def gate_pkg(self, lib: str) -> tuple[str, int]:
        free = self._gate_free.setdefault(lib, [])
        if not free:
            ref = self.refs.next()
            free.extend((ref, u) for u in sorted(GATE_PINS[lib]))
            self._gate_power.add(ref)
            psym = self.add_unit(lib, ref, 20, 20, GATE_POWER[lib])
            self.connect(psym, {"VCC": "+5V", "GND": "GND"})
        return free.pop(0)

    def gate2(self, lib: str, a: str, b: str, out: str) -> None:
        ref, unit = self.gate_pkg(lib)
        p1, p2, p3 = GATE_PINS[lib][unit]
        sym = self.add_unit(lib, ref, 20, 20, unit)
        self.connect(sym, {p1: a, p2: b, p3: out})

    def inv(self, a: str, out: str) -> None:
        ref, unit = self.gate_pkg("74xx:74HC04")
        p1, p2 = GATE_PINS["74xx:74HC04"][unit]
        sym = self.add_unit("74xx:74HC04", ref, 20, 20, unit)
        self.connect(sym, {p1: a, p2: out})

    def or_tree(self, terms: list[str], out: str, tag: str) -> None:
        terms = list(terms)
        if len(terms) == 1:
            raise ValueError(f"{tag}: one-term OR would need an alias")
        level = 0
        while len(terms) > 2:
            nxt = []
            for i in range(0, len(terms) - 1, 2):
                n = f"{self.prefix}_RQ_{tag}_L{level}_{i // 2}"
                self.gate2("74xx:74HC32", terms[i], terms[i + 1], n)
                nxt.append(n)
            if len(terms) % 2:
                nxt.append(terms[-1])
            terms = nxt
            level += 1
        self.gate2("74xx:74HC32", terms[0], terms[1], out)

    def mux8(self, in0: list[str], in1: list[str], sel: str, out: list[str]) -> None:
        for pkg in range(2):
            sym = self.add("74xx:74HC157", 100, 100)
            m = {"S": sel, "E": "GND"}
            for k in range(4):
                bit = pkg * 4 + k
                sec = SECTION[k]
                m[f"I0{sec}"] = in0[bit]
                m[f"I1{sec}"] = in1[bit]
                m[f"Z{sec}"] = out[bit]
            self.connect(sym, m)

    def reg574(self, d: list[str], q: list[str], cp: str,
               oe: str = "GND") -> None:
        sym = self.add("74xx:74HCT574", 100, 100)
        m = {"OE": oe, "Cp": cp}
        for i in range(8):
            m[f"D{i}"] = d[i]
            m[f"Q{i}"] = q[i]
        self.connect(sym, m)

    def write(self, filename: str) -> None:
        stem = os.path.splitext(os.path.basename(filename))[0]
        self.sh.write(os.path.join(PROJECT_DIR, filename))


def acc(prefix: str) -> list[str]:
    return [f"{prefix}_ACC{i}" for i in range(32)]


def qbits(prefix: str) -> list[str]:
    return [f"{prefix}_REQ_Q{i}" for i in range(8)]


def base_globals(prefix: str) -> set[str]:
    g = {"CLK", "RESET_N", f"{prefix}_REQ_START", f"{prefix}_REQ_QSTB",
         f"{prefix}_SAT_FLAG", f"{prefix}_REQ_BUSY", f"{prefix}_REQ_DONE"}
    g |= set(acc(prefix))
    g |= set(qbits(prefix))
    return g


def qraw(bits: list[str], shift: int) -> list[str]:
    """Arithmetic-shift bit selection with sign extension past bit 31."""
    return [bits[shift + i] if shift + i < 32 else bits[31] for i in range(8)]


def high_terms(bits: list[str], shift: int) -> list[str]:
    """ACC bits above the 8-bit result field; sign bit is handled separately."""
    terms = [bits[i] for i in range(shift + 8, 32)]
    if not terms:
        raise ValueError("shift leaves no overflow bits")
    return terms


def add_uint8_clamp(s: Sheet, prefix: str, bits: list[str], shift: int) -> str:
    """Add the QRAW -> SAT -> QVAL clamp; return the SAT_POS net."""
    raw = qraw(bits, shift)
    high = f"{prefix}_RQ_HIGH"
    s.or_tree(high_terms(bits, shift), high, "HIGH")
    neg_n = f"{prefix}_RQ_NEG_N"
    s.inv(bits[31], neg_n)
    sat_pos = f"{prefix}_RQ_SAT_POS"
    s.gate2("74xx:74HC08", high, neg_n, sat_pos)
    satv = [f"{prefix}_RQ_SAT{i}" for i in range(8)]
    s.mux8(raw, ["+5V"] * 8, sat_pos, satv)
    qval = [f"{prefix}_RQ_QVAL{i}" for i in range(8)]
    s.mux8(satv, ["GND"] * 8, bits[31], qval)
    return sat_pos


def build_conv(prefix: str, shift: int, filename: str, title: str) -> None:
    g = base_globals(prefix)
    s = Sheet(title, prefix, g)
    s.sh.add_text(
        f"{prefix} SIMPLE REQUANT - NO BIAS / NO ZERO POINT / FIXED >>{shift}",
        18, 12, size=2.5, bold=True, justify="left top")
    s.sh.add_text(
        "Q = clamp(ACC >>> SHIFT, 0, 255); SAT_FLAG flags any negative or\n"
        "positive overflow.  The model contract is symmetric quantization with\n"
        "bias trained to zero.  There is no parameter port and no multiplier.\n"
        "START -> Q loaded; QSTB one CLK later; DONE two CLKs later.",
        18, 19, size=1.25, justify="left top")

    a = acc(prefix)
    sat_pos = add_uint8_clamp(s, prefix, a, shift)
    s.reg574([f"{prefix}_RQ_QVAL{i}" for i in range(8)],
             qbits(prefix), f"{prefix}_REQ_START")

    # SAT_FLAG = SAT_POS | NEG (negative results clamp to zero).
    s.gate2("74xx:74HC32", sat_pos, a[31], f"{prefix}_SAT_FLAG")

    # Two-cycle sequencer: QSTB=S1, DONE=S2.
    seq = s.add("74xx:74HC74", 100, 100, unit=1)
    s.connect(seq, {"~{R}": "RESET_N", "D": f"{prefix}_REQ_START", "C": "CLK",
                    "~{S}": "+5V", "Q": f"{prefix}_REQ_QSTB", "~{Q}": "NC"})
    seq2 = s.add_unit("74xx:74HC74", seq.ref, 100, 100, 2)
    s.connect(seq2, {"~{R}": "RESET_N", "D": f"{prefix}_REQ_QSTB", "C": "CLK",
                     "~{S}": "+5V", "Q": f"{prefix}_REQ_DONE", "~{Q}": "NC"})
    seqp = s.add_unit("74xx:74HC74", seq.ref, 100, 100, 3)
    s.connect(seqp, {"VCC": "+5V", "GND": "GND"})

    # BUSY = START | QSTB | DONE.
    b1 = f"{prefix}_RQ_BUSY1"
    s.gate2("74xx:74HC32", f"{prefix}_REQ_START",
            f"{prefix}_REQ_QSTB", b1)
    s.gate2("74xx:74HC32", b1, f"{prefix}_REQ_DONE",
            f"{prefix}_REQ_BUSY")

    s.sh.add_text(
        "Implementation notes:\n"
        f"- QRAW[i] = ACC[{shift} + i] if < 32 else ACC[31].\n"
        f"- HIGH = OR(ACC[{shift + 8}..31]); SAT_POS = HIGH & ~ACC[31].\n"
        "- First 74HC157 stage selects 0xFF on SAT_POS; second selects 0x00\n"
        "  when ACC[31]=1, so negative results clamp to 0 and set SAT_FLAG.\n"
        "- Q is a 74HCT574 clocked by START (a one-CLK supervisor pulse).\n"
        "- QSTB/DONE are the two 74HC74 stages; BUSY is their OR with START.\n"
        "- No bias adder: retrain/export with zero bias, or fold bias into an\n"
        "  extra constant input before quantization (documented model contract).",
        18, 70, size=1.05, justify="left top")
    s.write(filename)


def build_fc() -> None:
    prefix = "FC"
    g = base_globals(prefix)
    # FC_SEL selects the layer; FC_BYTE[1:0] is the S09 write-byte counter
    # that picks which ACC byte the S17 mux drives onto REQ_Q.
    g.update({"FC_SEL", "FC_BYTE0", "FC_BYTE1"})
    shift = SHIFT["FC1"]
    s = Sheet("S17_Requant_FC - Simple FC1 Requant + FC2 Raw Signed32",
              prefix, g)
    s.sh.add_text(
        f"FC SIMPLE REQUANT - FC1 >>{shift} UINT8, FC2 RAW SIGNED32 (4 BYTES LE)",
        18, 12, size=2.5, bold=True, justify="left top")
    s.sh.add_text(
        "FC_SEL=0: FC1 Q = clamp(ACC >>> SHIFT, 0, 255), one QSTB at BC=0.\n"
        "FC_SEL=1: FC2 Q = raw ACC byte selected by BC[1:0], QSTB at BC=0..3,\n"
        "DONE at BC=3.  No bias, no zero point, no M multiplier, no parameter port.",
        18, 19, size=1.2, justify="left top")

    a = acc(prefix)
    sat_pos = add_uint8_clamp(s, prefix, a, shift)

    # FC1 byte register; FC2 leaves it unchanged (the output mux bypasses it).
    q8 = [f"{prefix}_RQ_Q8_{i}" for i in range(8)]
    fc_sel_n = f"{prefix}_RQ_FC_SEL_N"
    s.inv("FC_SEL", fc_sel_n)
    q_load = f"{prefix}_RQ_Q_LOAD"
    s.gate2("74xx:74HC08", f"{prefix}_REQ_START", fc_sel_n, q_load)
    s.reg574([f"{prefix}_RQ_QVAL{i}" for i in range(8)], q8, q_load)

    # FC2 raw byte mux: 4:1 over ACC bytes, selected by the S09 write-byte
    # counter FC_BYTE[1:0].  The byte is stable for the whole write state.
    b0, b1 = a[0:8], a[8:16]
    b2, b3 = a[16:24], a[24:32]
    m01 = [f"{prefix}_RQ_B01_{i}" for i in range(8)]
    m23 = [f"{prefix}_RQ_B23_{i}" for i in range(8)]
    s.mux8(b0, b1, f"{prefix}_BYTE0", m01)
    s.mux8(b2, b3, f"{prefix}_BYTE0", m23)
    byte = [f"{prefix}_RQ_BYTE{i}" for i in range(8)]
    s.mux8(m01, m23, f"{prefix}_BYTE1", byte)

    # Final output mux: FC1 registered byte or FC2 raw byte.
    s.mux8(q8, byte, "FC_SEL", qbits(prefix))

    # SAT_FLAG is only meaningful for FC1: (SAT_POS | ACC31) & ~FC_SEL.
    sat_any = f"{prefix}_RQ_SAT_ANY"
    s.gate2("74xx:74HC32", sat_pos, a[31], sat_any)
    s.gate2("74xx:74HC08", sat_any, fc_sel_n, f"{prefix}_SAT_FLAG")

    # Requant handshake: START -> QSTB (one CLK later) -> DONE (two CLKs).
    # The FSM holds START for the whole E_REQ state, so a two-stage shift
    # chain is enough; the byte index is not counted here any more.  S09's
    # write counter FC_BYTE[1:0] selects which ACC byte the mux presents, so
    # each E_REQ visit writes exactly one byte and FC2 visits E_REQ four
    # times per neuron (ROM A12 = BYTE_LAST).
    seq = s.add("74xx:74HC74", 100, 100, unit=1)
    s.connect(seq, {"~{R}": "RESET_N", "D": f"{prefix}_REQ_START", "C": "CLK",
                    "~{S}": "+5V", "Q": f"{prefix}_REQ_QSTB", "~{Q}": "NC"})
    seq2 = s.add_unit("74xx:74HC74", seq.ref, 100, 100, 2)
    s.connect(seq2, {"~{R}": "RESET_N", "D": f"{prefix}_REQ_QSTB", "C": "CLK",
                     "~{S}": "+5V", "Q": f"{prefix}_REQ_DONE", "~{Q}": "NC"})
    seqp = s.add_unit("74xx:74HC74", seq.ref, 100, 100, 3)
    s.connect(seqp, {"VCC": "+5V", "GND": "GND"})

    # BUSY = START | QSTB | DONE.
    b1 = f"{prefix}_RQ_BUSY1"
    s.gate2("74xx:74HC32", f"{prefix}_REQ_START",
            f"{prefix}_REQ_QSTB", b1)
    s.gate2("74xx:74HC32", b1, f"{prefix}_REQ_DONE",
            f"{prefix}_REQ_BUSY")

    s.sh.add_text(
        "Byte timing: S09's write counter FC_BYTE[1:0] selects ACC byte 0..3\n"
        "on the 4:1 mux; each E_REQ visit writes one byte, and FC2 loops\n"
        "E_REQ/E_ADDR_OUT/E_WRITE four times (ROM A12 = BYTE_LAST).  FC1\n"
        "writes one byte and ignores BYTE_LAST (FC_SEL=0).\n"
        "QSTB and DONE are a two-stage shift of START, so the same handshake\n"
        "serves both layers.  No bias adder; FC2 raw ACC is the signed score.",
        18, 75, size=1.0, justify="left top")
    os.makedirs(os.path.join(PROJECT_DIR, "templates"), exist_ok=True)
    s.write("templates/S17_Requant_FC.kicad_sch")


def main() -> int:
    build_conv("C1", SHIFT["C1"], "S13_Requant_C1.kicad_sch",
               "S13_Requant_C1 - Simple CONV1 Requant")
    build_conv("C2", SHIFT["C2"], "S15_Requant_C2.kicad_sch",
               "S15_Requant_C2 - Simple CONV2 Requant")
    build_fc()
    for name in ("S13_Requant_C1.kicad_sch", "S15_Requant_C2.kicad_sch",
                 "templates/S17_Requant_FC.kicad_sch"):
        print("wrote", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
