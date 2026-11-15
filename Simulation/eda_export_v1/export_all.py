"""2026-11-15 insurance run: export Protel2 netlists for every board of 74CNN-BRD.

Writes one file per board into ./boards, plus an index JSON with page UUIDs
and export statistics. Resumable: existing non-empty files are skipped unless
--force is given.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eda_rpc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "boards")
SKIP = {"A000"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    proj = eda_rpc.rpc("const c=await eda.dmt_Project.getCurrentProjectInfo(); return c;")
    if not proj or proj.get("uuid") != "86c1d8c59be2462ebb49fab075a5c297":
        raise SystemExit("wrong project: %r" % (proj,))

    boards = eda_rpc.rpc(
        "const b=await eda.dmt_Board.getAllBoardsInfo();"
        "return b.map(x=>({name:x.name,uuid:x.uuid,"
        "schematic:(x.schematic&&x.schematic.uuid)||x.schematic||''"
        "}));",
        timeout=120,
    )
    pages = eda_rpc.rpc("return await eda.dmt_Schematic.getAllSchematicPagesInfo();", timeout=120)
    by_sch = {}
    for p in pages:
        by_sch.setdefault(p.get("parentSchematicUuid"), []).append(p)

    index = []
    ok = fail = skip = 0
    for b in sorted(boards, key=lambda x: x["name"] or ""):
        name = b.get("name") or "?"
        if name in SKIP:
            print("skip %s (leftover)" % name)
            skip += 1
            continue
        if args.only and name != args.only:
            continue
        fn = re.sub(r"[^A-Za-z0-9_.-]", "_", name) + ".txt"
        path = os.path.join(OUT, fn)
        if not args.force and os.path.exists(path) and os.path.getsize(path) > 200:
            print("have %-22s %8d bytes" % (name, os.path.getsize(path)))
            ok += 1
            index.append({"board": name, "file": fn, "status": "existing",
                          "page": None, "pages": []})
            continue
        sch_uuid = b.get("schematic") or ""
        plist = by_sch.get(sch_uuid) or []
        if not plist:
            print("!! %s: no pages" % name)
            fail += 1
            index.append({"board": name, "status": "NO_PAGES"})
            continue
        page = sorted(plist, key=lambda p: p.get("name") or "")[0]
        page_uuid = page["uuid"]
        text = None
        for attempt in range(3):
            try:
                r = eda_rpc.rpc(f"""
const tabId = await eda.dmt_EditorControl.openDocument("{page_uuid}");
await new Promise(r => setTimeout(r, 1500));
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.documentType !== 1) {{
  try {{ await eda.dmt_EditorControl.closeDocument(tabId); }} catch (e) {{}}
  return {{err: "not schematic page after open: " + (doc && doc.documentType)}};
}}
let file = null, err = null;
try {{ file = await eda.sch_ManufactureData.getNetlistFile("nl", "Protel2"); }}
catch (e) {{ err = String(e); }}
if (!file) {{
  try {{ await eda.dmt_EditorControl.closeDocument(tabId); }} catch (e) {{}}
  return {{err: err || "netlist file undefined"}};
}}
const text = await file.text();
try {{ await eda.dmt_EditorControl.closeDocument(tabId); }} catch (e) {{}}
return {{text: text}};
""", timeout=600)
            except Exception as e:
                print("   attempt %d exception: %s" % (attempt + 1, e))
                time.sleep(2)
                continue
            if isinstance(r, dict) and "text" in r and len(r["text"]) > 200:
                text = r["text"]
                break
            print("   attempt %d failed: %s" % (attempt + 1, str(r)[:200]))
            time.sleep(2)
        if text is None:
            print("!! %s: export failed" % name)
            fail += 1
            index.append({"board": name, "status": "FAIL"})
            continue
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        ncomp = text.count("\n[")
        npins = text.count("|")
        print("ok  %-22s %8d bytes comps~%4d -> %s" % (name, len(text), ncomp, fn))
        ok += 1
        index.append({"board": name, "file": fn, "status": "OK",
                      "page": page_uuid, "pages": [p.get("name") for p in plist],
                      "bytes": len(text), "pagelist": plist})

    with open(os.path.join(HERE, "export_index.json"), "w", encoding="utf-8") as f:
        json.dump({"project": proj, "boards": index}, f, ensure_ascii=False, indent=2)
    print("\n=== %d ok, %d fail, %d skipped; boards in project=%d ===" % (ok, fail, skip, len(boards)))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
