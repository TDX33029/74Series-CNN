"""Generate a flat structural Verilog DUT (cnn74_top_eda.v + models_eda.v)
from the merged EasyEDA 47-board system netlist (merged_system.json).

- logic parts instantiate the same behavioural models used by the KiCad
  flow (model_ports.json carries the pin lists, standard DIP numbering);
- X10001 (ACH-8.000MHZ-EK 8-pin can) uses a dedicated wrapper (EN=1,
  OUT=5, power pins skipped);
- memories get their INIT images from Simulation/analysis/memories.csv
  (ref -> model/... hex), copied into rtl/init_eda/;
- R/RP behave as pull/series like gen_rtl; LED/Q/C/connector parts are
  skipped;
- the Scheme-C XOR3 sign-bit ECO (apply_scheme_c_eco equivalent) is baked
  in, since the hardware adders still derive bit16 from the 283 C4 output.

Output: Simulation/rtl_eda/cnn74_top_eda.v (+ instance_map_eda.csv)
"""
import csv
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(HERE)
PROJ = r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System"
OUTDIR = os.path.join(SIM, "v1_verify_20261115", "rtl")
os.makedirs(OUTDIR, exist_ok=True)
INITDIR = os.path.join(OUTDIR, "init")
os.makedirs(INITDIR, exist_ok=True)

MERGED = os.path.join(HERE, "merged_system_v1.json")
PORTMAP = os.path.join(HERE, "tb_port_map.json")
# 11-14 net->KiCad-name map, reused because 7489/7494 nets have identical
# membership today (see structural_diff.log); new fall-back names are derived
# from the EDA net key for the few LED-block nets that changed.
NAMEMAP = os.path.join(SIM, "eda_export", "net_name_map.json")
MODEL_PORTS = json.load(open(os.path.join(SIM, "rtl", "model_ports.json"),
                             encoding="utf-8"))
# EDA-only models (see models_eda.v)
MODEL_PORTS["Memory_EEPROM:28C256"] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
                                       13, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                                       24, 25, 26, 27]
MODEL_PORTS["74xx:74HC86"] = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13]

# The XOR3 sign-bit fix is now implemented in the EDA schematics (H1 fix,
# 74x86 U7186/U7187/U8186/U8187/U9186/U9187/U9288/U9289); the simulation-side
# ECO is therefore DISABLED by default.  Pass --eco to re-enable it (e.g. to
# simulate a netlist exported before the hardware fix).
APPLY_ECO = "--eco" in sys.argv

# class token -> KiCad model full name (models.v module set)
CLASS2MODEL = {
    "74HC00": "74xx:74HC00", "74HC02": "74xx:74HC02", "74HC04": "74xx:74HC04",
    "74HC08": "74xx:74HC08", "74HC32": "74xx:74HC32", "74HC74": "74xx:74HC74",
    "74HCT273": "74xx:74HCT273", "74HCT574": "74xx:74HCT574",
    "74HC161": "74xx:74HC161", "74HC157": "74xx:74HC157",
    "74HCT541": "74xx:74HCT541", "74HC245": "74xx:74HC245",
    "74HCT245": "74xx:74HCT245", "74HC138": "74xx:74HC138",
    "74HC238": "74xx:74HC238", "74HC148": "74xx:74LS148",
    "74HC283": "74xx:74HC283", "74HC85": "74xx:74HC85",
    "74HC688": "74xx:74HC688",
    "27C512": "Memory_EPROM:27C512", "62256": "Memory_RAM:CY62256-70PC",
    "6264": "Memory_RAM:HY6264AxP", "28C256": "Memory_EEPROM:28C256",
    "74HC86": "74xx:74HC86",
}

# Scheme-C ECO targets: ref -> (stage, msb A pin, msb B pin)
ECO_REFS = {
    "U7088": ("S12", "12", "11"), "U7092": ("S34", "12", "11"),
    "U8089": ("S12", "12", "11"), "U8093": ("S34", "12", "11"),
    "U9074": ("S12", "12", "11"), "U9078": ("S34", "12", "11"),
    "U9274": ("S12", "12", "11"), "U9278": ("S34", "12", "11"),
}


def logic_class(parttype):
    up = parttype.upper()
    for tok in sorted(CLASS2MODEL, key=len, reverse=True):
        if tok in up:
            return tok
    if "ACH-8" in up or "ASE" in up:
        return "OSC"
    return None


def ident(net_key, name_map=None):
    if net_key in ("G::+5V", "G::+3V3"):
        return None
    # prefer the matched KiCad net name so the testbenches' hierarchical
    # probes (dut._B01_S01_Supervisor_ST0, dut.MEM_nCE, ...) resolve
    if name_map:
        kn = name_map.get(net_key)
        if kn:
            name = re.sub(r"[^A-Za-z0-9_]", "_", kn)
            if name[0].isdigit():
                name = "N" + name
            return name
    if net_key.startswith("G::"):
        name = net_key[3:]
    else:
        # board-local ($-auto) net: qualify with the board name
        board, name = net_key.split("::", 1)
        board = re.sub(r"[^A-Za-z0-9_]", "_", board)
        name = board + "__" + name
    name = name.lstrip("/")
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if name[0].isdigit():
        name = "N" + name
    return name


def main():
    merged = json.load(open(MERGED, encoding="utf-8"))
    portmap = json.load(open(PORTMAP, encoding="utf-8"))
    comps = merged["comps"]
    nets = merged["nets"]
    pin2net = merged["pins"]          # "board|ref.pin" -> net key

    # build ref -> {pin: netkey} index (logic + R classes only, unique refs)
    ref_pins = {}
    for bp, key in pin2net.items():
        b, rp = bp.split("|", 1)
        ref, pin = rp.rsplit(".", 1)
        ref_pins.setdefault(ref, {})[pin] = key

    # memory init map
    mem_init = {}
    with open(os.path.join(SIM, "analysis", "memories.csv"), encoding="utf-8-sig",
              newline="") as f:
        for row in csv.DictReader(f):
            mem_init[row["ref"]] = row["init_file"]

    used_idents = {}
    name_map = {}
    if os.path.exists(NAMEMAP):
        name_map = json.load(open(NAMEMAP, encoding="utf-8"))
    seen_idents = set()
    for k in nets:
        i = ident(k, name_map)
        if not i:
            continue
        base = i
        n = 2
        while i in seen_idents:
            i = f"{base}_{n}"
            n += 1
        seen_idents.add(i)
        used_idents[k] = i

    # TB port override
    port_override = {}
    for port, netkey in portmap.items():
        port_override[netkey] = port

    def expr(netkey):
        if netkey in ("G::+5V", "G::+3V3"):
            return "1'b1"
        if netkey == "G::GND":
            return "1'b0"
        if netkey in port_override:
            return port_override[netkey]
        return used_idents[netkey]

    PORT_IN = sorted({port for net, port in port_override.items()
                      if port.startswith(("H_A", "H_MEM_SEL", "H_LOAD", "START", "RESET", "LOAD_EN"))
                      or port in ("IMAGE_DONE_N", "MODEL_DONE_N")})
    PORT_INOUT = sorted({port for net, port in port_override.items()
                         if port.startswith("H_D")})
    PORT_OUT = sorted({port for net, port in port_override.items()
                       if port in ("BUSY", "DONE", "RESULT_VALID", "ERROR",
                                   "IMAGE_READY", "MODEL_READY")
                       or port.startswith(("RESULT", "ERROR_CODE"))})

    lines = []
    map_rows = []
    used = set()

    def use(netkey):
        if netkey not in ("G::+5V", "G::+3V3", "G::GND"):
            used.add(netkey)

    skip_counts = {"led": 0, "q": 0, "c": 0, "conn": 0, "other": 0}
    inst_lines = []
    pull_lines = []
    eco_wires = []
    eco_assigns = []

    for ref in sorted(comps, key=lambda r: (comps[r]["board"], len(r), r)):
        c = comps[ref]
        pt = c["parttype"]
        pins = ref_pins.get(ref, {})
        cls = logic_class(pt)

        if cls is None:
            up = pt.upper()
            if up.startswith("LED") or "HLMP" in up:
                skip_counts["led"] += 1
            elif ref.startswith("Q"):
                skip_counts["q"] += 1
            elif ref.startswith("C"):
                skip_counts["c"] += 0          # EDA has no caps; keep counter 0
            elif "X6522" in up or ref.startswith("J") or "CONN" in up:
                skip_counts["conn"] += 1
            else:
                skip_counts["other"] += 1
                print(f"  skip {ref} ({pt[:30]})")
            continue

        if cls == "OSC":
            # X10001: EN=1 OUT=5, power 4/8 skipped
            en = pins.get("1")
            out = pins.get("5")
            if not en or not out:
                print(f"  !! {ref}: osc pins missing")
                continue
            use(en)
            use(out)
            inst_lines.append(f"  m_Osc_ACH {ref} (.p1({expr(en)}), .p5({expr(out)}));")
            map_rows.append([ref, "OSC", pt, c["board"]])
            continue

        full = CLASS2MODEL[cls]
        ports = MODEL_PORTS.get(full)
        if ports is None:
            print(f"  !! {ref}: no model for {full}")
            continue
        conns = []
        for pn in ports:
            net = pins.get(str(pn))
            if net is None or net.endswith("UNCONNECTED-") or "UNCONNECTED" in net:
                continue
            use(net)
            conns.append(f".p{pn}({expr(net)})")
        param = ""
        if cls in ("27C512", "62256", "6264"):
            src = mem_init.get(ref, "")
            if ref == "U2001":
                s = os.path.join(SIM, "rtl", "init", "timing.hex")
                shutil.copyfile(s, os.path.join(INITDIR, "timing.hex"))
                init = "init/timing.hex"
            elif src and src.startswith("model/"):
                base = os.path.splitext(os.path.basename(src))[0] + ".hex"
                s = os.path.join(PROJ, os.path.dirname(src), base)
                d = os.path.join(INITDIR, base)
                if os.path.exists(s):
                    shutil.copyfile(s, d)
                    init = f"init/{base}"
                else:
                    print(f"  !! {ref}: init image missing {s}")
                    init = None
            else:
                init = None
            if init:
                param = f' #(.INIT("{init}"))'
            else:
                print(f"  !! {ref}: no INIT (mem zeros)")
        mod = "m_" + full.replace(":", "_").replace("-", "_")
        inst_lines.append(f"  {mod}{param} {ref} (" + ", ".join(conns) + ");")
        map_rows.append([ref, full, pt, c["board"]])

        # Scheme-C ECO bookkeeping (only when simulating pre-fix hardware)
        if APPLY_ECO and ref in ECO_REFS:
            stage, a4, b4 = ECO_REFS[ref]
            p9 = pins.get("9")
            pa = pins.get(a4)
            pb = pins.get(b4)
            if p9 and pa and pb:
                eco_wires.append((ref, stage, expr(p9), expr(pa), expr(pb)))

    # resistors: pull or series (skip LED-chain resistors touching +VLED).
    # NOTE: R/RP refs are NOT globally unique (same designator reused on many
    # boards), so iterate (board, ref) pairs from the board-qualified pins.
    bp_pins = {}
    for bp, key in pin2net.items():
        b, rp = bp.split("|", 1)
        ref, pin = rp.rsplit(".", 1)
        bp_pins.setdefault((b, ref), {})[pin] = key
    for (board, ref) in sorted(bp_pins, key=lambda x: (x[0], len(x[1]), x[1])):
        c = comps.get(ref)
        if not c:
            continue
        pt = c["parttype"].upper()
        if not (ref.startswith("R") and ("0402" in pt or "RES" in pt or pt.startswith("R"))):
            continue
        pins = bp_pins[(board, ref)]
        a, b = pins.get("1"), pins.get("2")
        if not a or not b:
            continue
        if "+VLED" in (a, b):
            skip_counts["led"] += 1
            continue
        ra, rb = a in ("G::+5V", "G::+3V3", "G::GND"), b in ("G::+5V", "G::+3V3", "G::GND")
        if ra and rb:
            continue
        if ra or rb:
            rail, sig = (a, b) if ra else (b, a)
            use(sig)
            prim = "pullup" if rail in ("G::+5V", "G::+3V3") else "pulldown"
            pull_lines.append(f"  {prim} ({expr(sig)});   // {ref} {c['parttype']}")
            map_rows.append([ref, "pull", f"{rail}->{sig}", c["board"]])
        else:
            # series resistor between a global net and a board-local $-net =
            # LED/status tap (transistor base etc.): no logic role.  The base
            # $-net is undriven once the (skipped) transistor is removed, and
            # the assign forms an X-loop that poisons shared buses.
            def is_local_dollar(key):
                return "::" in key and key.split("::", 1)[1].startswith("$")
            if is_local_dollar(a) or is_local_dollar(b):
                skip_counts["led"] += 1
                continue
            use(a)
            use(b)
            pull_lines.append(f"  assign {expr(b)} = {expr(a)};   // {ref} {c['parttype']} series")
            map_rows.append([ref, "series", f"{a}->{b}", c["board"]])

    # ECO: rename the S12_16/S34_16 net driven by each adder's C4, then XOR3
    eco_header = ["  // SCHEME_C_ECO: bit16 = sign(XOR3) instead of C4 (hardware gap H1)"]
    for ref, stage, s_net, pa, pb in eco_wires:
        base = s_net
        c4 = base + "_C4_eco"
        # rename usage: replace the net ident in the whole instance section
        old_ident = expr_from_ident(base)
        eco_header.append(f"  wire {c4};")
        eco_header.append(f"  assign {base} = {pa} ^ {pb} ^ {c4};")
        eco_renames.append((old_ident, c4))
    # (applied textually after assembly)

    header = [
        "// Generated by gen_eda_dut.py - do not edit by hand.",
        "// Flat structural model of the 47-board 74CNN-BRD EasyEDA system.",
        "// Source: Simulation/eda_export/merged_system.json (47 board Protel2 exports)",
        "// merged by global net name (backplane = same-name join).",
        "`timescale 1ns/1ps",
        "",
        "module cnn74_top(",
    ]
    pl = []
    for p in PORT_IN:
        pl.append(f"  input  {p},")
    for p in PORT_INOUT:
        pl.append(f"  inout  {p},")
    for p in PORT_OUT:
        pl.append(f"  output {p},")
    header[-1] = header[-1].rstrip(",") if False else header[-1]
    # fix trailing comma on last port
    pl[-1] = pl[-1].rstrip(",")
    header += pl + [");", ""]

    body = []
    body += ["  // ---- power rails ----",
             "  // +5V/+3V3/GND are folded into 1'b1/1'b0 at the use sites.", ""]
    body += ["  // ---- pull/series resistors ----"] + pull_lines + [""]
    if APPLY_ECO:
        body += ["  // ---- Scheme-C ECO ----"] + eco_header + [""]
    # fitted JP10001 1-2 shunt: the EDA boards dropped the jumper part, the
    # KiCad flow models it as fitted; bridge OSC_OUT -> CLK accordingly
    osc_net = next((k for k in used_idents if k.endswith("OSC_OUT")), None)
    clk_net = "G::CLK"
    jumper = []
    if osc_net and clk_net in nets:
        use(clk_net)
        jumper = [f"  assign {expr(clk_net)} = {expr(osc_net)};   // JP10001 fitted 1-2 shunt (internal osc)"]
    body += ["  // ---- JP10001 osc shunt ----"] + jumper + [""]
    body += ["  // ---- instances ----"] + inst_lines + [""]

    # wires: every used net minus ports/rails
    wire_names = {}
    for k in sorted(used):
        if k in port_override or k in ("G::+5V", "G::+3V3", "G::GND"):
            continue
        wire_names[k] = used_idents[k]
    # ensure ECO source nets are present even if only referenced by ECO
    for ref, stage, s_net, pa, pb in eco_wires:
        for k, i in used_idents.items():
            if i == s_net and k not in wire_names and k not in port_override:
                wire_names[k] = i

    wlines = []
    for k, name in sorted(wire_names.items(), key=lambda x: x[1]):
        wlines.append(f"  wire {name};")
    body = ["  // ---- nets ----"] + wlines + [""] + body

    text = "\n".join(header + body + ["endmodule", ""]) + "\n"
    # textual ECO rename: inside the target adder instance line, .p9(<old>) -> .p9(<c4>)
    out_lines = []
    eco_todo = {ref: (s_net, s_net + "_C4_eco") for ref, stage, s_net, pa, pb in eco_wires}
    for ln in text.split("\n"):
        done = set()
        for ref, (s_net, c4) in eco_todo.items():
            if ref in done or f" {ref} (" not in ln or f".p9({s_net})" not in ln:
                continue
            ln = ln.replace(f".p9({s_net})", f".p9({c4})")
            done.add(ref)
        out_lines.append(ln)
    text = "\n".join(out_lines)
    for ref, (s_net, c4) in eco_todo.items():
        if f".p9({c4})" not in text:
            print(f"  !! ECO rename for {ref} not applied")

    with open(os.path.join(OUTDIR, "cnn74_top_eda.v"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(text)
    with open(os.path.join(OUTDIR, "instance_map_eda.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ref", "model", "parttype", "board"])
        w.writerows(map_rows)

    print(f"instances: {len(inst_lines)}  pulls/series: {len(pull_lines)}  "
          f"nets: {len(wire_names)}  skipped: {skip_counts}")
    print(f"wrote {os.path.join(OUTDIR, 'cnn74_top_eda.v')}")


eco_renames = []


def expr_from_ident(base):
    return base


if __name__ == "__main__":
    main()
