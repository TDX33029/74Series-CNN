"""Export the Protel2 netlist of every current 74CNN-BRD board schematic
through the EasyEDA bridge and save one file per board.

Skips the leftover A000 board (not part of the 47-board system).
"""
import json
import os
import re
import sys
import urllib.request

BRIDGE = "http://localhost:49620"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boards")
os.makedirs(OUT, exist_ok=True)


def ex(code, timeout=300):
    req = urllib.request.Request(
        BRIDGE + "/execute",
        data=json.dumps({"code": code}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout)).get("result")


def main():
    boards = ex("return await eda.dmt_Board.getAllBoardsInfo();")
    pages = ex("return await eda.dmt_Schematic.getAllSchematicPagesInfo();")
    by_sch = {}
    for p in pages:
        by_sch.setdefault(p.get("parentSchematicUuid"), []).append(p)

    results = []
    for b in boards:
        name = b.get("name") or "?"
        if name == "A000":
            print(f"skip A000 (leftover)")
            continue
        sch = (b.get("schematic") or {})
        sch_uuid = sch.get("uuid")
        blist = by_sch.get(sch_uuid, [])
        if not blist:
            print(f"!! {name}: no pages for schematic {sch_uuid}")
            results.append((name, "NO_PAGES"))
            continue
        page = sorted(blist, key=lambda p: p.get("name") or "")[0]
        page_uuid = page["uuid"]
        r = ex(f"""
const tabId = await eda.dmt_EditorControl.openDocument("{page_uuid}");
await new Promise(r => setTimeout(r, 1200));
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.documentType !== 1) {{
  return {{err: "not schematic page after open: " + (doc && doc.documentType)}};
}}
let file = null, err = null;
try {{ file = await eda.sch_ManufactureData.getNetlistFile("nl", "Protel2"); }}
catch (e) {{ err = String(e); }}
if (!file) return {{err: err || "netlist file undefined"}};
const text = await file.text();
try {{ await eda.dmt_EditorControl.closeDocument(tabId); }} catch (e) {{}}
return {{text: text}};
""")
        if not isinstance(r, dict) or "text" not in r:
            print(f"!! {name}: export failed: {str(r)[:200]}")
            results.append((name, "FAIL"))
            continue
        text = r["text"]
        fn = re.sub(r"[^A-Za-z0-9_.-]", "_", name) + ".txt"
        with open(os.path.join(OUT, fn), "w", encoding="utf-8", newline="") as f:
            f.write(text)
        ncomp = text.count("\n[")
        nnet = text.count("\n(")
        print(f"ok {name:18} comps~{ncomp:4} nets~{nnet:4} -> {fn}")
        results.append((name, "OK"))

    print("\n=== summary ===")
    ok = sum(1 for _, s in results if s == "OK")
    print(f"{ok}/{len(results)} boards exported")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
