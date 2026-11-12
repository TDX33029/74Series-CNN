"""KiCad netlist -> structural-Verilog pre-analysis.

Reads  output/top.net  (read-only) and writes:
    parts.csv, pins.json, nets.csv, memories.csv, stats.json
into  D:/Document/tempPrj/74Series-CNN/Simulation/analysis
"""
from __future__ import annotations

import collections
import csv
import json
import os
import re
import sys

TOOLS = r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/tools"
sys.path.insert(0, TOOLS)
import kicad_sexpr as k  # noqa: E402

PROJ = r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System"
NETLIST = os.path.join(PROJ, "output", "top_20261112c.net")  # 2026-11-12: top.net (11-10) lost its components/nets sections; use the full kicad-cli export verified against the JLCEDA boards
SYMLIB = r"C:/Program Files/KiCad/10.0/share/kicad/symbols"
OUT = r"D:/Document/tempPrj/74Series-CNN/Simulation/analysis"

# --------------------------------------------------------------------------
# symbols
# --------------------------------------------------------------------------
LIB_FILES = {
    "74xx": "74xx.kicad_sym",
    "Memory_RAM": "Memory_RAM.kicad_sym",
    "Memory_EPROM": "Memory_EPROM.kicad_sym",
    "Memory_EEPROM": "Memory_EEPROM.kicad_sym",
    "Device": "Device.kicad_sym",
    "power": "power.kicad_sym",
    "Connector": "Connector.kicad_sym",
    "Connector_Generic": "Connector_Generic.kicad_sym",
    "Oscillator": "Oscillator.kicad_sym",
    "Switch": "Switch.kicad_sym",
}

# Parts used in the schematics that the installed KiCad 10.0.4 library does not
# ship; the project generator declares them as pin-compatible aliases of these
# base symbols (tools/kicad_gen.py: default_registry).
ALIAS = {
    ("74xx", "74HC08"): "74LS08",
    ("74xx", "74HC157"): "74LS157",
    ("74xx", "74HC161"): "74LS161",
    ("74xx", "74HC283"): "74LS283",
    ("74xx", "74HC32"): "74LS32",
    ("74xx", "74HCT245"): "74LS245",
}

_lib_text = {}
_lib_sym = {}


def _lazy_load(nick: str) -> str | None:
    if nick in _lib_text:
        return _lib_text[nick]
    fn = LIB_FILES.get(nick)
    text = None
    if fn:
        path = os.path.join(SYMLIB, fn)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
    _lib_text[nick] = text
    return text


def library_pins(nick: str, part: str):
    """Return list[k.Pin] for a library symbol (resolving ``extends``)."""
    key = (nick, part)
    if key in _lib_sym:
        return _lib_sym[key]
    text = _lazy_load(nick)
    if text is None:
        _lib_sym[key] = None
        return None
    blk = k.extract_block(text, '(symbol "%s"' % part)
    if blk is None:
        _lib_sym[key] = None
        return None
    root = k.parse(blk)[0]
    ext = k.first(root, "extends")
    if ext is not None:
        base = k.atoms(ext)[0]
        _lib_sym[key] = library_pins(nick, base)
        return _lib_sym[key]
    pins = k.find_pins(root)
    _lib_sym[key] = pins
    return pins


def library_units(nick: str, part: str):
    """Unit numbers present in the symbol body (0 = common to all units)."""
    text = _lazy_load(nick)
    if text is None:
        return None
    blk = k.extract_block(text, '(symbol "%s"' % part)
    if blk is None:
        return None
    root = k.parse(blk)[0]
    ext = k.first(root, "extends")
    if ext is not None:
        return library_units(nick, k.atoms(ext)[0])
    units = set()
    for node in k.walk(root):
        if node and node[0] == "symbol" and len(node) > 1 and isinstance(node[1], str):
            m = re.search(r"_(\d+)_(\d+)$", node[1])
            if m:
                units.add(int(m.group(1)))
    return sorted(units)


_pin_graphic = {}


def library_pin_graphics(nick: str, part: str):
    """pin number -> graphic style (line, inverted, clock, inverted_clock, ...).

    The netlist does not carry this information; it lives only in the symbol.
    """
    key = (nick, part)
    if key in _pin_graphic:
        return _pin_graphic[key]
    text = _lazy_load(nick)
    if text is None:
        _pin_graphic[key] = {}
        return {}
    blk = k.extract_block(text, '(symbol "%s"' % part)
    if blk is None:
        _pin_graphic[key] = {}
        return {}
    root = k.parse(blk)[0]
    ext = k.first(root, "extends")
    if ext is not None:
        _pin_graphic[key] = library_pin_graphics(nick, k.atoms(ext)[0])
        return _pin_graphic[key]
    out = {}

    def visit(node, style):
        for child in node[1:]:
            if not isinstance(child, list) or not child:
                continue
            if child[0] == "symbol":
                sub = child[1] if len(child) > 1 and isinstance(child[1], str) else ""
                m = re.search(r"_(\d+)_(\d+)$", sub)
                st = int(m.group(2)) if m else style
                if st in (0, 1):
                    visit(child, st)
            elif child[0] == "pin" and len(child) > 3:
                # body style 2 is the De Morgan alternative and must not be
                # mixed into style 1 (74LS00 draws inverted inputs there)
                graphic = child[2] if isinstance(child[2], str) else ""
                num = k.first(child, "number")
                if num and k.atoms(num):
                    out[k.atoms(num)[0]] = graphic

    visit(root, 1)
    _pin_graphic[key] = out
    return out


def strip_overbar(name: str) -> str:
    """KiCad ``~{OE}`` -> ``OE`` (for readable but faithful names)."""
    return name


# --------------------------------------------------------------------------
# netlist parse
# --------------------------------------------------------------------------
with open(NETLIST, encoding="utf-8") as f:
    TEXT = f.read()


def section(name: str, tag: str):
    blk = k.extract_block(TEXT, "\n\t(" + name)
    if blk is None:
        raise SystemExit("section %s not found" % name)
    root = k.parse(blk)[0]
    return [n for n in root[1:] if isinstance(n, list) and n and n[0] == tag]


comps = section("components", "comp")
libparts = section("libparts", "libpart")
nets = section("nets", "net")


def prop(c, name):
    for p in k.children(c, "property"):
        nm = k.first(p, "name")
        if nm and k.atoms(nm) and k.atoms(nm)[0] == name:
            v = k.first(p, "value")
            return k.atoms(v)[0] if v else None
    return None


def libsource(c):
    ls = k.first(c, "libsource")
    return k.atoms(k.first(ls, "lib"))[0], k.atoms(k.first(ls, "part"))[0]


def first_atom(node, tag):
    n = k.first(node, tag)
    return k.atoms(n)[0] if n and k.atoms(n) else None


# libparts: (lib,part) -> ordered pin dict
LIBPART = {}
for lp in libparts:
    lib = first_atom(lp, "lib")
    part = first_atom(lp, "part")
    pins = {}
    for p in k.children(k.first(lp, "pins"), "pin"):
        pins[first_atom(p, "num")] = {
            "name": first_atom(p, "name") or "",
            "etype": first_atom(p, "type") or "",
        }
    LIBPART[(lib, part)] = {
        "pins": pins,
        "description": first_atom(lp, "description") or "",
        "docs": first_atom(lp, "docs") or "",
    }

# components
COMP = {}
COMP_ORDER = []
for c in comps:
    ref = first_atom(c, "ref")
    lib, part = libsource(c)
    units = {}
    for u in k.children(k.first(c, "units"), "unit"):
        uname = first_atom(u, "name")
        pl = [first_atom(p, "num") for p in k.children(k.first(u, "pins"), "pin")]
        units[uname] = pl
    COMP[ref] = {
        "ref": ref,
        "value": first_atom(c, "value") or "",
        "lib": lib,
        "part": part,
        "sheet": prop(c, "Sheetname") or "",
        "sheetfile": prop(c, "Sheetfile") or "",
        "footprint": first_atom(c, "footprint") or prop(c, "Footprint") or "",
        "units": units,
        "props": {first_atom(p, "name"): first_atom(p, "value")
                  for p in k.children(c, "property")},
    }
    COMP_ORDER.append(ref)

# nets
NET = []           # in file order
NET_BY_CODE = {}
for n in nets:
    code = int(first_atom(n, "code"))
    name = first_atom(n, "name")
    nodes = []
    for x in k.children(n, "node"):
        pf = first_atom(x, "pinfunction")
        nodes.append({
            "ref": first_atom(x, "ref"),
            "pin": first_atom(x, "pin"),
            "pinfunction": pf,
            "pintype": first_atom(x, "pintype"),
        })
    NET.append({"code": code, "name": name, "nodes": nodes})
    NET_BY_CODE[code] = NET[-1]

PIN_NET = collections.defaultdict(dict)   # ref -> pin -> netname
for n in NET:
    for node in n["nodes"]:
        PIN_NET[node["ref"]][node["pin"]] = n["name"]

# --------------------------------------------------------------------------
# categorisation
# --------------------------------------------------------------------------
SKIP_PARTS = {
    "C": "capacitor (decoupling) - passive",
    "R": "resistor - passive",
    "LED": "indicator LED - passive/visual",
    "R_Network08": "8-resistor network - passive",
    "TestPoint": "test point - mechanical probe pad",
    "PWR_FLAG": "ERC power flag - not a physical part",
    "SW_Push": "push button - mechanical input, model as stimulus",
    "ASE-xxxMHz": "crystal oscillator can - model as clock source, not logic",
}
CONNECTOR_PARTS = {p for p in {COMP[r]["part"] for r in COMP}
                   if p.startswith("Conn_") or p.startswith("Connector")}

CATEGORY = {
    "74xx": "logic",
    "Memory_EPROM": "memory-rom",
    "Memory_EEPROM": "memory-eeprom",
    "Memory_RAM": "memory-sram",
    "Oscillator": "clock",
    "Switch": "input",
}


def is_skipped(part):
    """True for parts that are not modelled as logic/memory blocks."""
    if part in SKIP_PARTS:
        return True
    if part.startswith("Conn_") or part in CONNECTOR_PARTS:
        return True
    return False


# Switch and oscillator are not logic either, but they are kept in parts.csv /
# pins.json because the Verilog testbench needs a model for them (a switch and
# a clock source).
SIMPLE_MODEL = {"SW_Push", "ASE-xxxMHz"}


def is_excluded(part):
    """True for parts that are dropped entirely (passives, connectors, power)."""
    return is_skipped(part) and part not in SIMPLE_MODEL


# --------------------------------------------------------------------------
# pins.json
# --------------------------------------------------------------------------
PIN_UNIT_ORDER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def collect_parts():
    seen = collections.OrderedDict()
    for ref in COMP_ORDER:
        c = COMP[ref]
        key = (c["lib"], c["part"])
        if key not in seen:
            seen[key] = []
        seen[key].append(ref)
    return seen


def pin_sort_key(num):
    m = re.match(r"^(\d+)(.*)$", num)
    if m:
        return (0, int(m.group(1)), m.group(2))
    return (1, 0, num)


PINS_JSON = {}
PARTS_ROWS = []
STATS = {}

parts_map = collect_parts()

for (lib, part), refs in parts_map.items():
    lp = LIBPART[(lib, part)]
    ref0 = refs[0]
    comp0 = COMP[ref0]

    # unit assignment as instantiated in the schematic
    pin_unit_name = {}
    unit_pins = {}
    for uname, plist in comp0["units"].items():
        unit_pins[uname] = list(plist)
        for pn in plist:
            pin_unit_name[pn] = uname
    # consistency over all instances
    unit_conflicts = []
    for r in refs[1:]:
        other = {}
        for uname, plist in COMP[r]["units"].items():
            for pn in plist:
                other[pn] = uname
        if other != pin_unit_name:
            unit_conflicts.append(r)

    # library symbol (with alias / extends resolution)
    alias = ALIAS.get((lib, part))
    lib_pins = library_pins(lib, alias or part)
    lib_units = library_units(lib, alias or part)
    lib_note = ""
    if alias:
        lib_note = ("symbol absent from installed %s.kicad_sym; modelled on the "
                    "pin-compatible %s" % (lib, alias))
    elif lib_pins is None:
        lib_note = "symbol not found in installed library"

    lib_by_num = {}
    if lib_pins:
        for p in lib_pins:
            lib_by_num.setdefault(p.number, p)
    graphics = library_pin_graphics(lib, alias or part)

    pins_out = {}
    name_mismatch = []
    type_mismatch = []
    implied = []
    for num in sorted(lp["pins"], key=pin_sort_key):
        rec = lp["pins"][num]
        unit_name = pin_unit_name.get(num)
        unit_no = PIN_UNIT_ORDER.index(unit_name) + 1 if unit_name in PIN_UNIT_ORDER else 0
        lpin = lib_by_num.get(num)
        lib_unit = lpin.unit if lpin else None
        entry = {
            "name": rec["name"],
            "etype": rec["etype"],
            "unit": unit_no,
            "unit_name": unit_name or "?",
        }
        g = graphics.get(num)
        if g and g != "line":
            entry["graphic"] = g
            base_name = rec["name"].strip()
            has_overbar = base_name.startswith("~{") or base_name.startswith("~")
            if g in ("inverted", "inverted_clock", "input_low", "clock_low") \
                    and not has_overbar:
                implied.append((num, base_name, g))
        if lpin is not None:
            entry["lib_unit"] = lib_unit
            if lpin.name != rec["name"]:
                name_mismatch.append((num, rec["name"], lpin.name))
            if lpin.etype != rec["etype"]:
                type_mismatch.append((num, rec["etype"], lpin.etype))
            if lib_unit not in (None, 0, unit_no):
                entry["unit_mismatch"] = True
        # sanity: pin in netlist units?
        if unit_name is None:
            entry["unit_name"] = "?"
            entry["warning"] = "pin not listed in component units block"
        pins_out[num] = entry

    pkg = ""
    m = re.search(r"DIP-(\d+)", comp0["footprint"] or "")
    if m:
        pkg = "DIP-%s" % m.group(1)
    elif comp0["footprint"]:
        pkg = comp0["footprint"]
    pkg_pins = int(m.group(1)) if m else None

    n_pins = len(lp["pins"])
    if pkg_pins is None:
        check = "n/a (no DIP footprint)"
    elif pkg_pins == n_pins:
        check = "ok"
    else:
        check = "MISMATCH (%d pins, package %d)" % (n_pins, pkg_pins)

    # power pins
    power_pins = [num for num, r in lp["pins"].items()
                  if r["etype"] in ("power_in", "power_out")]

    # names that are empty or repeated inside one unit
    empty_names = [num for num, r in lp["pins"].items() if not r["name"].strip()]
    per_unit_names = collections.defaultdict(list)
    for num, rec in pins_out.items():
        per_unit_names[rec["unit_name"]].append(rec["name"])
    dup_in_unit = {}
    for un, names in per_unit_names.items():
        cnt = collections.Counter(n for n in names if n)
        d = {n: v for n, v in cnt.items() if v > 1}
        if d:
            dup_in_unit[un] = d

    sheets = sorted({COMP[r]["sheet"] for r in refs})
    PINS_JSON["%s:%s" % (lib, part)] = {
        "lib": lib,
        "part": part,
        "description": lp["description"],
        "category": CATEGORY.get(lib, "other"),
        "instances": len(refs),
        "sheets": sheets,
        "footprint": comp0["footprint"],
        "package": pkg,
        "pin_count": n_pins,
        "package_pin_count": pkg_pins,
        "pin_count_check": check,
        "library_symbol": (alias or part),
        "library_note": lib_note,
        "symbol_units": lib_units,
        "units_used": sorted(comp0["units"].keys()),
        "unit_conflicts": unit_conflicts,
        "name_mismatches_vs_library": [list(x) for x in name_mismatch],
        "type_mismatches_vs_library": [list(x) for x in type_mismatch],
        "pins": pins_out,
        "power_pins": power_pins,
        "active_low_by_graphic_only": [list(x) for x in implied],
        "pins_without_name": empty_names,
        "duplicate_pin_names_within_unit": dup_in_unit,
    }

    PARTS_ROWS.append({
        "part": part,
        "lib": lib,
        "count": len(refs),
        "category": CATEGORY.get(lib, "other"),
        "behavioral_model_needed": "yes",
        "model_kind": {
            "logic": "synthesizable behavioral RTL (combinational/sequential)",
            "memory-rom": "ROM with init image",
            "memory-eeprom": "EEPROM/RAM array (writable)",
            "memory-sram": "SRAM array (writable)",
            "clock": "clock source (toggle)",
            "input": "switch/stimulus",
        }.get(CATEGORY.get(lib, "other"), ""),
        "package": pkg,
        "package_pins": pkg_pins or "",
        "pin_count": n_pins,
        "pin_check": check,
        "sheets": ";".join(sheets),
        "notes": lib_note,
    })

# --------------------------------------------------------------------------
# parts.csv  (logic / memory / clock / switch only - passives, connectors and
# power symbols are listed in report.md instead)
# --------------------------------------------------------------------------
with open(os.path.join(OUT, "parts.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "part", "lib", "count", "category", "behavioral_model_needed",
        "model_kind", "package", "package_pins", "pin_count", "pin_check",
        "sheets", "notes"])
    w.writeheader()
    for row in sorted(PARTS_ROWS, key=lambda r: (-r["count"], r["part"])):
        if is_excluded(row["part"]):
            continue
        w.writerow(row)

with open(os.path.join(OUT, "pins.json"), "w", encoding="utf-8") as f:
    json.dump({
        "source": NETLIST,
        "netlist_export": "KiCad 10.0.4, 2026-11-07T23:23:23",
        "key": "lib:part -> pin number -> {name, etype, unit, unit_name}",
        "notes": [
            "Covers every part that needs a simulation model (logic, memory, "
            "clock, switch); passives/connectors/power symbols are excluded and "
            "listed in report.md.",
            "unit/unit_name come from the component 'units' blocks in the netlist "
            "(authoritative for how the part is instantiated).",
            "lib_unit is the unit number inside the KiCad symbol; 0 means the pin "
            "belongs to the common body shared by all units.",
            "~{NAME} is KiCad's overbar notation for an active-low pin.",
            "pins always include the power pins.",
        ],
        "parts": {k: v for k, v in PINS_JSON.items()
                  if not is_excluded(k.split(":", 1)[1])},
    }, f, indent=1, ensure_ascii=False)
    f.write("\n")

# --------------------------------------------------------------------------
# nets.csv
# --------------------------------------------------------------------------
VERILOG_KEYWORDS = {
    "always", "and", "assign", "begin", "buf", "bufif0", "bufif1", "case",
    "casex", "casez", "deassign", "default", "defparam", "disable", "edge",
    "else", "end", "endcase", "endfunction", "endmodule", "endprimitive",
    "endspecify", "endtable", "endtask", "event", "for", "force", "forever",
    "fork", "function", "highz0", "highz1", "if", "ifnone", "initial", "inout",
    "input", "integer", "join", "large", "macromodule", "medium", "module",
    "nand", "negedge", "nmos", "nor", "not", "notif0", "notif1", "or",
    "output", "parameter", "pmos", "posedge", "primitive", "pull0", "pull1",
    "pulldown", "pullup", "rcmos", "real", "realtime", "reg", "release",
    "repeat", "rnmos", "rpmos", "rtran", "rtranif0", "rtranif1", "scalared",
    "signed", "small", "specify", "specparam", "strong0", "strong1", "supply0",
    "supply1", "table", "task", "time", "tran", "tranif0", "tranif1", "tri",
    "tri0", "tri1", "triand", "trior", "trireg", "unsigned", "use", "vectored",
    "wait", "wand", "weak0", "weak1", "while", "wire", "wor", "xnor", "xor",
}
RAILS = {"+5V", "+3V3", "+12V", "-12V", "VCC", "VDD"}
GROUNDS = {"GND", "AGND", "DGND", "VSS"}


def verilog_ident(name: str) -> tuple[str, str]:
    """Deterministic KiCad -> Verilog identifier mapping.

    Rules (in order):
      1. every character outside [A-Za-z0-9_] becomes '_'
      2. runs of '_' collapse to one
      3. an identifier starting with a digit gets the 'n_' prefix
      4. an empty result becomes 'n_unnamed'
      5. Verilog keywords get the 'n_' prefix
    """
    base = re.sub(r"[^A-Za-z0-9_]", "_", name)
    base = re.sub(r"_+", "_", base)
    if not base:
        base = "n_unnamed"
    if base[0].isdigit():
        base = "n_" + base
    note = ""
    if base in VERILOG_KEYWORDS:
        base = "n_" + base
        note = "keyword-prefixed"
    return base, note


net_rows = []
base_count = collections.defaultdict(list)
for n in NET:
    base, note = verilog_ident(n["name"])
    base_count[base].append(n["code"])
    net_rows.append((n, base, note))

colliding = {b: codes for b, codes in base_count.items() if len(codes) > 1}
final_ident = {}
for n, base, note in net_rows:
    if base in colliding:
        ident = "%s_c%d" % (base, n["code"])
        note = (note + "; " if note else "") + "collision(%d names)" % len(colliding[base])
    else:
        ident = base
    final_ident[n["code"]] = (ident, base, note)

rows = []
DRIVER_TYPES = {"output", "tri_state", "bidirectional", "open_collector",
                "open_emitter", "power_out"}
LOAD_TYPES = {"input", "power_in"}
for n in NET:
    ident, base, note = final_ident[n["code"]]
    nm = n["name"]
    specials = "".join(sorted({c for c in nm if not (c.isalnum() or c == "_")}))
    is_unconn = nm.startswith("unconnected-")
    is_gnd = nm in GROUNDS
    is_pwr = nm in RAILS
    if is_unconn:
        note = (note + "; " if note else "") + "unconnected pin (single node)"
    elif len(n["nodes"]) == 1:
        note = (note + "; " if note else "") + "single-node net"
    drivers = loads = bidir = ncs = 0
    for node in n["nodes"]:
        parts = set((node["pintype"] or "").split("+"))
        if "no_connect" in parts:
            ncs += 1
        parts.discard("no_connect")
        if parts & DRIVER_TYPES:
            drivers += 1
        if parts & {"tri_state", "bidirectional"}:
            bidir += 1
        if parts & LOAD_TYPES:
            loads += 1
    if drivers == 0 and not is_unconn and not (is_pwr or is_gnd):
        note = (note + "; " if note else "") + "no driver"
    rows.append({
        "code": n["code"],
        "kicad_name": nm,
        "verilog_ident": ident,
        "verilog_base": base,
        "node_count": len(n["nodes"]),
        "drivers": drivers,
        "loads": loads,
        "bidir_drivers": bidir,
        "no_connect_nodes": ncs,
        "is_power": "yes" if is_pwr else "no",
        "is_ground": "yes" if is_gnd else "no",
        "rail_class": "power" if is_pwr else ("ground" if is_gnd else ""),
        "has_special_chars": "yes" if specials else "no",
        "special_chars": specials,
        "single_node": "yes" if len(n["nodes"]) == 1 else "no",
        "note": note,
    })

with open(os.path.join(OUT, "nets.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "code", "kicad_name", "verilog_ident", "verilog_base", "node_count",
        "drivers", "loads", "bidir_drivers", "no_connect_nodes",
        "is_power", "is_ground", "rail_class", "has_special_chars",
        "special_chars", "single_node", "note"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

# --------------------------------------------------------------------------
# memories.csv
# --------------------------------------------------------------------------
MEM_SPECS = {
    "27C512": {
        "addr": ["A%d" % i for i in range(16)],
        "data": ["D%d" % i for i in range(8)],
        "ctrl": {"~{CE}": "CE", "~{OE}": "OE"},
        "addr_width": 16,
    },
    "28C256": {
        "addr": ["A%d" % i for i in range(15)],
        "data": ["D%d" % i for i in range(8)],
        "ctrl": {"~{CS}": "CS", "~{OE}": "OE", "~{WE}": "WE"},
        "addr_width": 15,
    },
    "HY6264AxP": {
        "addr": ["A%d" % i for i in range(13)],
        "data": ["I/O%d" % i for i in range(8)],
        "ctrl": {"~{CS1}": "CS1", "CS2": "CS2", "~{OE}": "OE", "~{WE}": "WE"},
        "addr_width": 13,
    },
}


def name_to_num(lib, part, want_name):
    for num, rec in LIBPART[(lib, part)]["pins"].items():
        if rec["name"] == want_name:
            return num
    return None


# init-file rules keyed on (sheet, control-pin net basename) or data-bus stem
def guess_init(comp, netmap, part):
    sheet = comp["sheet"]
    base = comp["part"]
    ctrl_ce = ""
    for pname in ("~{CE}", "~{CS}", "~{CS1}"):
        pn = name_to_num(comp["lib"], comp["part"], pname)
        if pn:
            ctrl_ce = netmap.get(pn, "")
            break
    ce_short = ctrl_ce.split("/")[-1]
    d0 = netmap.get(name_to_num(comp["lib"], comp["part"], "D0")
                    or name_to_num(comp["lib"], comp["part"], "I/O0") or "", "")
    d0_short = d0.split("/")[-1]

    if base == "HY6264AxP":
        return ("none", "SRAM is volatile - no init image in model/",
                "high")

    if base == "28C256":
        kind = ""
        if "W_" in ce_short:
            kind = "weights"
        elif "B_" in ce_short:
            kind = "bias"
        elif "Q_" in ce_short:
            kind = "qparam/requant"
        return ("unknown",
                "no EEPROM image in model/; nibble is %s (loaded at runtime)" % (kind or "?"),
                "high")

    # 27C512
    m = re.match(r"nCS_LUT(\d)_(LO|HI)$", ce_short)
    if m:
        return ("model/lut/lut_%s.bin" % m.group(2).lower(),
                "LUT multiplier ROM, pair %s %s byte" % (m.group(1), m.group(2)),
                "high")

    if sheet == "B01_S01_Supervisor":
        if d0_short.endswith("MC0"):
            return ("model/microcode/supervisor_lo.bin",
                    "supervisor FSM microcode, low byte (MC0..MC7)", "high")
        if "MC8" in d0_short:
            return ("model/microcode/supervisor_hi.bin",
                    "supervisor FSM microcode, high byte (MC8..MC15)", "high")

    if sheet == "B02_S02_Timing":
        return ("unknown",
                "timing FSM microcode ROM; no matching file in model/microcode", "low")

    if sheet == "B04_S07_Conv1" and d0_short.startswith("C1_MC"):
        idx = "1" if d0_short.startswith("C1_MC1") else "2"
        return ("model/microcode/c1_rom%s.bin" % idx,
                "conv1 microcode ROM%s (data bus C1_MC%s_*)" % (idx, idx), "high")

    if sheet == "B06_S08_Conv2" and d0_short.startswith("C2_MC"):
        idx = "1" if d0_short.startswith("C2_MC1") else "2"
        return ("model/microcode/c2_rom%s.bin" % idx,
                "conv2 microcode ROM%s (data bus C2_MC%s_*)" % (idx, idx), "high")

    if sheet in ("B08_S09_FC1", "B09_S09_FC2") and d0_short.startswith("FC_MC"):
        idx = "1" if d0_short.startswith("FC_MC1") else "2"
        return ("model/microcode/fc_rom%s.bin" % idx,
                "FC microcode ROM%s (data bus FC_MC%s_*); both FC halves share the "
                "single fc_rom pair in model/" % (idx, idx), "medium")

    if sheet == "B11_S11_BusFabric" and d0_short.startswith("MAP_SEL"):
        return ("model/busmap/bus_map.bin",
                "bus map ROM (data pins drive MEM_SEL[4:0])", "high")

    if d0_short.startswith("C1_P") or d0_short.startswith("C2_P") or d0_short.startswith("FC_P"):
        hi = d0_short.endswith("_8")
        return ("model/lut/lut_%s.bin" % ("hi" if hi else "lo"),
                "LUT multiplier ROM (%s)" % ("high" if hi else "low") + " byte",
                "high")

    return ("unknown", "no rule matched sheet/wiring", "low")


mem_rows = []
for ref in COMP_ORDER:
    c = COMP[ref]
    if c["part"] not in MEM_SPECS:
        continue
    spec = MEM_SPECS[c["part"]]
    netmap = PIN_NET[ref]
    addr_bits = []
    for i, an in enumerate(spec["addr"]):
        pn = name_to_num(c["lib"], c["part"], an)
        addr_bits.append((i, pn, netmap.get(pn, "<NC>")))
    data_bits = []
    for i, dn in enumerate(spec["data"]):
        pn = name_to_num(c["lib"], c["part"], dn)
        data_bits.append((i, pn, netmap.get(pn, "<NC>")))
    ctrl = []
    for pname, label in spec["ctrl"].items():
        pn = name_to_num(c["lib"], c["part"], pname)
        ctrl.append((label, pname, pn, netmap.get(pn, "<NC>")))
    # effective address width = number of address pins driven by a real signal
    tied = {nm for _, _, nm in addr_bits if nm in ("GND", "+5V")}
    eff = len({i for i, _, nm in addr_bits if nm not in ("GND", "+5V")})
    init, why, conf = guess_init(c, netmap, c["part"])
    missing_data = [str(i) for i, _, nm in data_bits if nm.startswith("unconnected")]
    mem_rows.append({
        "ref": ref,
        "lib": c["lib"],
        "part": c["part"],
        "value": c["value"],
        "sheet": c["sheet"],
        "sheetfile": c["sheetfile"],
        "footprint": c["footprint"],
        "addr_width": spec["addr_width"],
        "addr_pins_used": eff,
        "addr_pins": ";".join("A%d=p%s(%s)" % (i, pn, nm) for i, pn, nm in addr_bits),
        "data_pins": ";".join("D%d=p%s(%s)" % (i, pn, nm) for i, pn, nm in data_bits),
        "control_pins": ";".join("%s=p%s(%s)" % (lab, pn, nm) for lab, pname, pn, nm in ctrl),
        "data_pins_unconnected": ",".join(missing_data),
        "init_file": init,
        "init_confidence": conf,
        "rationale": why,
    })

with open(os.path.join(OUT, "memories.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "ref", "lib", "part", "value", "sheet", "sheetfile", "footprint",
        "addr_width", "addr_pins_used", "addr_pins", "data_pins",
        "control_pins", "data_pins_unconnected", "init_file",
        "init_confidence", "rationale"])
    w.writeheader()
    for r in mem_rows:
        w.writerow(r)

# --------------------------------------------------------------------------
# statistics for report.md
# --------------------------------------------------------------------------
stats = {}
stats["netlist"] = NETLIST
stats["counts"] = {
    "components": len(COMP),
    "distinct_parts": len(parts_map),
    "nets": len(NET),
    "nodes": sum(len(n["nodes"]) for n in NET),
    "memory_parts": len(mem_rows),
}
stats["by_sheet"] = dict(collections.Counter(COMP[r]["sheet"] for r in COMP_ORDER))
stats["by_part"] = dict(collections.Counter(
    "%s:%s" % (COMP[r]["lib"], COMP[r]["part"]) for r in COMP_ORDER))
stats["skipped"] = {}
for p in sorted({COMP[r]["part"] for r in COMP_ORDER}):
    if not is_skipped(p):
        continue
    refs = [r for r in COMP_ORDER if COMP[r]["part"] == p]
    netc = collections.Counter()
    for r in refs:
        for pin, nm in PIN_NET[r].items():
            netc[nm] += 1
    stats["skipped"][p] = {
        "count": len(refs),
        "reason": SKIP_PARTS.get(p, "connector - mechanical"),
        "refs": refs if len(refs) <= 12 else refs[:12] + ["..."],
        "nets": dict(netc.most_common(400)),
        "distinct_nets": len(netc),
    }

# model/ inventory and which memory uses which file
model_dir = os.path.join(PROJ, "model")
inventory = {}
for root, dirs, files in os.walk(model_dir):
    for fn in sorted(files):
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, PROJ).replace("\\", "/")
        if fn.endswith(".bin"):
            inventory[rel] = os.path.getsize(full)
stats["model_files"] = inventory
used = collections.Counter(r["init_file"] for r in mem_rows)
stats["init_files_used"] = dict(used)
stats["model_files_unused"] = sorted(
    f for f in inventory if f not in used and f.startswith("model/"))

# pin-count / library checks
stats["pin_checks"] = {}
for key, info in PINS_JSON.items():
    stats["pin_checks"][key] = {
        "pins": info["pin_count"],
        "package": info["package"],
        "check": info["pin_count_check"],
        "lib_symbol": info["library_symbol"],
        "name_mismatches": len(info["name_mismatches_vs_library"]),
        "type_mismatches": len(info["type_mismatches_vs_library"]),
        "unit_conflicts": len(info["unit_conflicts"]),
        "units_used": info["units_used"],
        "unnamed_pins": len(info["pins_without_name"]),
        "dup_names_in_unit": info["duplicate_pin_names_within_unit"],
    }

# net statistics
single = [n for n in NET if len(n["nodes"]) == 1]
stats["single_node"] = {
    "total": len(single),
    "unconnected_named": sum(1 for n in single if n["name"].startswith("unconnected-")),
    "other": [
        {"name": n["name"], "ref": n["nodes"][0]["ref"], "pin": n["nodes"][0]["pin"],
         "part": COMP[n["nodes"][0]["ref"]]["part"]}
        for n in single if not n["name"].startswith("unconnected-")
    ],
}
stats["chars"] = {}
for ch in ["/", "+", "-", "(", ")", "[", "]", "{", "}", "~", "<", "="]:
    stats["chars"][ch] = sum(1 for n in NET if ch in n["name"])
stats["collisions"] = {b: c for b, c in colliding.items()}
stats["net_name_shapes"] = {
    "hierarchical": sum(1 for n in NET if n["name"].startswith("/")),
    "plain": sum(1 for n in NET if re.fullmatch(r"[A-Za-z0-9_]+", n["name"])),
    "unconnected": sum(1 for n in NET if n["name"].startswith("unconnected-")),
    "rails": [n["name"] for n in NET if n["name"] in RAILS or n["name"] in GROUNDS],
}
stats["power"] = {}
for rail in ("+5V", "+3V3", "GND"):
    st = collections.Counter()
    for n in NET:
        if n["name"] == rail:
            for node in n["nodes"]:
                st[COMP[node["ref"]]["part"]] += 1
    stats["power"][rail] = {
        "nodes": sum(st.values()),
        "pintypes": dict(collections.Counter(
            node["pintype"] for n in NET if n["name"] == rail for node in n["nodes"])),
        "top_parts": dict(st.most_common(8)),
    }

# unconnected pins by part
unc = collections.Counter()
unc_pin_names = collections.Counter()
for n in NET:
    if not n["name"].startswith("unconnected-"):
        continue
    node = n["nodes"][0]
    part = COMP[node["ref"]]["part"]
    unc[part] += 1
    unc_pin_names[(part, node["pin"])] += 1
stats["unconnected_by_part"] = dict(unc.most_common())

# components with unused units (pins never connected)
unused_units = []
for ref in COMP_ORDER:
    c = COMP[ref]
    lp = LIBPART[(c["lib"], c["part"])]["pins"]
    got = set(PIN_NET[ref])
    missing = [p for p in lp if p not in got]
    if missing:
        units = sorted({PINS_JSON["%s:%s" % (c["lib"], c["part"])]["pins"][p]["unit_name"]
                        for p in missing})
        unused_units.append({"ref": ref, "part": c["part"],
                             "missing_pins": sorted(missing, key=pin_sort_key),
                             "units": units})
stats["incomplete_components"] = unused_units

# power-pin sanity
pp = []
for ref in COMP_ORDER:
    c = COMP[ref]
    lp = LIBPART[(c["lib"], c["part"])]["pins"]
    for num, rec in lp.items():
        if rec["etype"] not in ("power_in", "power_out"):
            continue
        nm = PIN_NET[ref].get(num, "<NONE>")
        if nm == "<NONE>":
            pp.append({"ref": ref, "part": c["part"], "pin": num,
                       "name": rec["name"], "net": nm})
        elif rec["name"] in ("VCC", "VDD") and nm not in ("+5V", "+3V3"):
            pp.append({"ref": ref, "part": c["part"], "pin": num,
                       "name": rec["name"], "net": nm})
        elif rec["name"] in ("GND", "VSS") and nm != "GND":
            pp.append({"ref": ref, "part": c["part"], "pin": num,
                       "name": rec["name"], "net": nm})
stats["power_pin_anomalies"] = pp

# logic parts driving power rails (tie-offs) and bus contention statistics
tie = collections.Counter()
by_part_rail = collections.Counter()
for n in NET:
    if n["name"] not in ("GND", "+5V", "+3V3"):
        continue
    for node in n["nodes"]:
        c = COMP[node["ref"]]
        if is_excluded(c["part"]):
            continue
        if node["pintype"].split("+")[0] in ("input", "tri_state", "output"):
            by_part_rail[c["part"]] += 1
            tie[(c["part"], n["name"])] += 1
stats["signal_pins_on_rails"] = {
    "total": sum(by_part_rail.values()),
    "by_part": dict(by_part_rail.most_common()),
    "by_part_and_rail": {"%s on %s" % k: v for k, v in tie.most_common()},
}

# driver statistics
multi = [r for r in rows if r["drivers"] > 1]
nodrv = [r for r in rows if r["drivers"] == 0 and r["rail_class"] == ""
         and not r["kicad_name"].startswith("unconnected-")]
stats["fanin_fanout"] = {
    "nets_with_multiple_drivers": len(multi),
    "multiple_driver_examples": [
        {"net": r["kicad_name"], "drivers": r["drivers"], "nodes": r["node_count"]}
        for r in sorted(multi, key=lambda x: -x["drivers"])[:10]],
    "nets_without_driver": len(nodrv),
    "no_driver_examples": [{"net": r["kicad_name"], "nodes": r["node_count"]}
                           for r in nodrv[:15]],
}

# net fanout histogram
hist = collections.Counter(len(n["nodes"]) for n in NET)
stats["node_histogram"] = {str(k): v for k, v in sorted(hist.items())}
stats["longest_net_names"] = [
    {"name": n["name"], "len": len(n["name"])}
    for n in sorted(NET, key=lambda x: -len(x["name"]))[:5]]

# external interface nets: every node sits on a skipped (mechanical) part
ext_only = []
ext_mixed = []
for n in NET:
    kinds = []
    for node in n["nodes"]:
        c = COMP[node["ref"]]
        kinds.append("skip" if is_excluded(c["part"]) else "logic")
    if "logic" not in kinds:
        ext_only.append(n["name"])
    elif "skip" in kinds and not n["name"].startswith("/"):
        ext_mixed.append(n["name"])
stats["external_nets"] = {
    "only_on_mechanical_parts": len(ext_only),
    "only_on_mechanical_parts_names": ext_only,
    "logic_and_mechanical_parts": len(ext_mixed),
    "logic_and_mechanical_examples": ext_mixed[:60],
}

# pins whose graphic is a clock (edge triggered)
clk = {}
for key, info in PINS_JSON.items():
    pins = [num for num, rec in info["pins"].items() if rec.get("graphic") == "clock"]
    if pins:
        clk[key] = pins
stats["clock_pins"] = clk

# memory summary by sheet
stats["memories"] = {}
for r in mem_rows:
    stats["memories"].setdefault(r["sheet"], collections.Counter())[r["part"]] += 1
stats["memories"] = {s: dict(c) for s, c in stats["memories"].items()}

with open(os.path.join(OUT, "stats.json"), "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=1, ensure_ascii=False)

print("wrote parts.csv pins.json nets.csv memories.csv stats.json")
print(json.dumps(stats["counts"], indent=1))
print("pin check failures:",
      [k for k, v in stats["pin_checks"].items() if not v["check"].startswith("ok")])
print("lib mismatches:",
      {k: (v["name_mismatches"], v["type_mismatches"])
       for k, v in stats["pin_checks"].items()
       if v["name_mismatches"] or v["type_mismatches"]})
print("single node:", stats["single_node"]["total"], "other:", len(stats["single_node"]["other"]))
print("collisions:", stats["collisions"])
