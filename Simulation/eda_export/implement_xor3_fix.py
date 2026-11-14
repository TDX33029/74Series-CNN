"""Implement the H1 XOR3 sign-bit fix in the EDA schematics (74HC86 per
adder board).  B04-2 was already done as the pilot; this script verifies it
and applies the remaining 7 boards:

  gate1: PA ^ PB -> X1      gate2: X1 ^ C4 -> S16
  adder pin9 stub rebound from S16-net to C4-net.

Per board the script: opens the functional page (the one containing the
adder), places SN74HC86N, sets the designator, wires stubs with net names,
rebinds the adder pin9 stub, saves, exports, and verifies the netlist
fragments.
"""
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = {"libraryUuid": "0819f05c4eef4c71ace90d822a990e87",
       "uuid": "0d0c8f2aa8a04af8ba13e444b486633f"}   # SN74HC86N DIP-14

BOARDS = [
    # board, newdes, adder, out-net, c4-net, x1-net, pa-net, pb-net
    ("B04-2_CONV1", "U7186", "U7088", "/B04_S07_CONV1/C1_S12_16",
     "/B04_S07_CONV1/C1_S12_C4", "/B04_S07_CONV1/C1_S12_X1",
     "/B04_S07_CONV1/C1_P1_15", "/B04_S07_CONV1/C1_P2_15"),
    ("B04-1_CONV1", "U7187", "U7092", "/B04_S07_CONV1/C1_S34_16",
     "/B04_S07_CONV1/C1_S34_C4", "/B04_S07_CONV1/C1_S34_X1",
     "/B04_S07_CONV1/C1_P3_15", "/B04_S07_CONV1/C1_P4_15"),
    ("B06-2_CONV2", "U8186", "U8089", "/B06_S08_CONV2/C2_S12_16",
     "/B06_S08_CONV2/C2_S12_C4", "/B06_S08_CONV2/C2_S12_X1",
     "/B06_S08_CONV2/C2_P1_15", "/B06_S08_CONV2/C2_P2_15"),
    ("B06-1_CONV2", "U8187", "U8093", "/B06_S08_CONV2/C2_S34_16",
     "/B06_S08_CONV2/C2_S34_C4", "/B06_S08_CONV2/C2_S34_X1",
     "/B06_S08_CONV2/C2_P3_15", "/B06_S08_CONV2/C2_P4_15"),
    ("B08-3_FC1", "U9186", "U9074", "/B08_S09_FC1/FC_S12_16",
     "/B08_S09_FC1/FC_S12_C4", "/B08_S09_FC1/FC_S12_X1",
     "/B08_S09_FC1/FC_P1_15", "/B08_S09_FC1/FC_P2_15"),
    ("B08-2_FC1", "U9187", "U9078", "/B08_S09_FC1/FC_S34_16",
     "/B08_S09_FC1/FC_S34_C4", "/B08_S09_FC1/FC_S34_X1",
     "/B08_S09_FC1/FC_P3_15", "/B08_S09_FC1/FC_P4_15"),
    ("B09-3_FC2", "U9288", "U9274", "/B09_S09_FC2/FC_S12_16",
     "/B09_S09_FC2/FC_S12_C4", "/B09_S09_FC2/FC_S12_X1",
     "/B09_S09_FC2/FC_P1_15", "/B09_S09_FC2/FC_P2_15"),
    ("B09-2_FC2", "U9289", "U9278", "/B09_S09_FC2/FC_S34_16",
     "/B09_S09_FC2/FC_S34_C4", "/B09_S09_FC2/FC_S34_X1",
     "/B09_S09_FC2/FC_P3_15", "/B09_S09_FC2/FC_P4_15"),
]


def ex(code, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(
                "http://localhost:49620/execute",
                data=json.dumps({"code": code}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            return json.load(urllib.request.urlopen(req, timeout=600)).get("result")
        except Exception as e:
            print(f"    retry{i+1}: {str(e)[:60]}")
            time.sleep(4)
    return None


def verify_export(boards, pages, board, out_net, c4_net, x1_net, chip):
    t = None
    b = [x for x in boards if x.get("name") == board][0]
    ps = [p for p in pages if p.get("parentSchematicUuid") == b["schematic"]["uuid"]]
    for p in ps:
        ex(f'await eda.dmt_EditorControl.openDocument("{p["uuid"]}"); '
           'await new Promise(r2 => setTimeout(r2, 1200));')
        rr = ex('const file = await eda.sch_ManufactureData.getNetlistFile("v", "Protel2");'
                'return {text: await file.text()};')
        if rr and rr.get("text") and (not t or len(rr["text"]) > len(t)):
            t = rr["text"]
    if not t:
        return None, ps
    open(os.path.join(HERE, "boards", board + ".txt"), "w",
         encoding="utf-8", newline="").write(t)
    lines = t.replace("\r\n", "\n").split("\n")
    cur = None
    nets = {}
    for ln in lines:
        s = ln.strip()
        if s == "(":
            cur = None
        elif s == ")":
            cur = None
        elif cur is None and s:
            cur = s.rstrip()
            nets.setdefault(cur, [])
        elif cur is not None and s:
            nets[cur].append(s.split()[0])
    ok = (nets.get(c4_net) and f"{chip}-9" in nets[c4_net]
          and f"{chip}-2" in nets[c4_net] and f"{chip}-5" in nets[c4_net]
          and nets.get(x1_net) and f"{chip}-3" in nets[x1_net]
          and f"{chip}-4" in nets[x1_net]
          and nets.get(out_net) and f"{chip}-6" in nets[out_net]
          and f"{chip}-9" not in nets.get(out_net, []))
    return ok, ps


def main():
    boards = ex("return await eda.dmt_Board.getAllBoardsInfo();")
    pages = ex("return await eda.dmt_Schematic.getAllSchematicPagesInfo();")
    results = {}
    todo = list(BOARDS)
    # skip the pilot if already verified
    ok, _ = verify_export(boards, pages, *BOARDS[0][:1], *BOARDS[0][3:], BOARDS[0][1])
    if ok:
        print("B04-2 pilot already saved & verified")
        todo = BOARDS[1:]
    else:
        print("B04-2 pilot needs (re)doing")

    for board, des, adder, out_net, c4_net, x1_net, pa_net, pb_net in todo:
        print(f"\n=== {board}: {des} + {adder} ===")
        b = [x for x in boards if x.get("name") == board][0]
        ps = [p for p in pages if p.get("parentSchematicUuid") == b["schematic"]["uuid"]]
        # find the functional page: the one containing the adder
        func = None
        for p in ps:
            r = ex(f'''
await eda.dmt_EditorControl.openDocument("{p["uuid"]}");
await new Promise(r2 => setTimeout(r2, 1200));
const comps = await eda.sch_PrimitiveComponent.getAll();
let hit = false;
for (const c of comps) {{ try {{ if (String(c.designator||"") === "{adder}") {{ hit = true; }} }} catch(e) {{}} }}
return hit;
''')
            if r:
                func = p["uuid"]
                break
        if not func:
            print(f"  !! adder {adder} not found on any page")
            results[board] = "NO_PAGE"
            continue
        # bbox + place + designator
        r = ex(f'''
await eda.dmt_EditorControl.openDocument("{func}");
await new Promise(r2 => setTimeout(r2, 1500));
const all = await eda.sch_PrimitiveWire.getAll();
let maxX = 0;
for (const w of all) {{
  const ln = w.line || [];
  for (let i = 0; i + 1 < ln.length; i += 2) if (ln[i] > maxX) maxX = ln[i];
}}
const placed = await eda.sch_PrimitiveComponent.create({json.dumps(LIB)}, maxX + 200, 700, "", 0, false, true, true);
if (!placed) return {{err: "place failed"}};
const comp = await eda.sch_PrimitiveComponent.get(String(placed.primitiveId));
const aw = comp.toAsync();
await aw.setState_Designator("{des}");
await aw.done();
const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(String(placed.primitiveId));
return {{id: String(placed.primitiveId), pins: (pins||[]).map(q => [String(q.pinNumber), q.x, q.y])}};
''')
        if not r or "pins" not in (r or {}):
            print(f"  !! place failed: {r}")
            results[board] = "PLACE_FAIL"
            continue
        pinpos = {pn: [x, y] for pn, x, y in r["pins"]}
        chip_id = r["id"]
        NETS = {"1": pa_net, "2": c4_net, "3": x1_net, "4": x1_net,
                "5": c4_net, "6": out_net, "7": "GND", "14": "+5V",
                "9": "+5V", "10": "+5V", "12": "+5V", "13": "+5V"}
        js_nets = json.dumps(NETS)
        js_pins = json.dumps(pinpos)
        r = ex(f'''
const NETS = {js_nets};
const PINS = {js_pins};
const results = [];
for (const pn of Object.keys(NETS)) {{
  const [x, y] = PINS[pn];
  const x2 = Number(pn) <= 7 ? x - 15 : x + 15;
  const w = await eda.sch_PrimitiveWire.create([x2, y, x, y], NETS[pn]);
  results.push([pn, w ? "ok" : "fail"]);
}}
return results;
''')
        bad = [x for x in (r or []) if x[1] != "ok"]
        if bad:
            print(f"  !! wire failures: {bad}")
            results[board] = "WIRE_FAIL"
            continue
        # rebind the adder pin9 stub: the wire with net==out_net touching pin9
        px, py = pinpos["9"]
        r = ex(f'''
const all = await eda.sch_PrimitiveWire.getAll();
const out = [];
for (const w of all) {{
  try {{
    if (String(w.net) !== "{out_net}") continue;
    const ln = w.line || [];
    for (let i = 0; i + 1 < ln.length; i += 2) {{
      if (Math.abs(ln[i] - ({px})) <= 2 && Math.abs(ln[i+1] - ({py})) <= 2) {{ out.push(String(w.primitiveId)); }}
    }}
  }} catch(e) {{}}
}}
if (out.length !== 1) return {{err: "adder stub cands=" + out.length}};
const w = await eda.sch_PrimitiveWire.get(out[0]);
const aw = w.toAsync();
await aw.setState_Net("{c4_net}");
await aw.done();
return {{ok: true, id: out[0]}};
''')
        if not (r and r.get("ok")):
            print(f"  !! adder stub rebind failed: {r}")
            results[board] = "REBIND_FAIL"
            continue
        ex('await eda.sch_Document.save(); await new Promise(r2 => setTimeout(r2, 1500));')
        ok, _ = verify_export(boards, pages, board, out_net, c4_net, x1_net, des)
        print(f"  verify: {'OK' if ok else 'FAIL'}")
        results[board] = "OK" if ok else "VERIFY_FAIL"
        boards = ex("return await eda.dmt_Board.getAllBoardsInfo();") or boards
        pages = ex("return await eda.dmt_Schematic.getAllSchematicPagesInfo();") or pages

    print("\n=== summary ===")
    for k, v in results.items():
        print(f"  {k:14} {v}")


if __name__ == "__main__":
    main()
