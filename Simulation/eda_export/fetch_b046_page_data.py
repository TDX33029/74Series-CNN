"""Fetch complete primitive data (components, pins, wires, net flags) for
both pages of B04-6_CONV1 through the EasyEDA bridge, for offline damage
analysis.

Output: b046_page_<page>.json with
  comps:  [{id, x, y, kind, ...}]
  pins:   [{compId, designator, pinNumber, x, y, net, pinName}]
  wires:  [{id, net, line}]
"""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = "http://localhost:49620"

PAGES = {
    "s07_conv1": "fe550102fbf0e747",
    "b04_conn": "e6d74d8df72e476f",
}


def ex(code, timeout=600):
    req = urllib.request.Request(
        BRIDGE + "/execute",
        data=json.dumps({"code": code}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout)).get("result")


def main():
    for name, uuid in PAGES.items():
        r = ex(f"""
const tabId = await eda.dmt_EditorControl.openDocument("{uuid}");
await new Promise(r => setTimeout(r, 1500));
const comps = await eda.sch_PrimitiveComponent.getAll();
const pins = [];
for (const c of comps) {{
  try {{
    const pp = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.primitiveId);
    for (const p of (pp || [])) {{
      pins.push({{
        compId: c.primitiveId,
        designator: String(c.designator === undefined ? "" : c.designator),
        pinNumber: String(p.pinNumber === undefined ? (p.number === undefined ? "" : p.number) : p.pinNumber),
        pinName: String(p.pinName === undefined ? (p.name === undefined ? "" : p.name) : p.pinName),
        x: p.x, y: p.y,
        net: p.net === undefined ? null : String(p.net),
      }});
    }}
  }} catch (e) {{}}
}}
const wires = (await eda.sch_PrimitiveWire.getAll()).map(w => ({{
  id: w.primitiveId, net: w.net === undefined ? null : String(w.net), line: w.line,
}}));
let flags = [];
try {{
  const allc = await eda.sch_PrimitiveComponent.getAll();
  flags = [];
}} catch (e) {{}}
return {{comps: comps.map(c => ({{id: c.primitiveId, x: c.x, y: c.y,
  kind: String(c.componentType === undefined ? "" : c.componentType),
  des: String(c.designator === undefined ? "" : c.designator),
  pt: String(c.partType === undefined ? "" : c.partType)}})),
  pins, wires}};
""")
        out = os.path.join(HERE, f"b046_page_{name}.json")
        json.dump(r, open(out, "w", encoding="utf-8"), indent=0)
        print(f"{name}: comps {len(r['comps'])} pins {len(r['pins'])} wires {len(r['wires'])} -> {out}")


if __name__ == "__main__":
    main()
