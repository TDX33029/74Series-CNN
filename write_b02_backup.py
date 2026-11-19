import json

src = json.load(open(r'C:/Users/Lenovo/AppData/Local/Temp/b02_r17.json'))
r = json.loads(src['result'])
backup = {
    "board": "B02_TIMING",
    "pcb_uuid": "a8a7bb9eb952a5f7",
    "date": "2026-11-19",
    "note": "original chip positions before placement (rot=0 horizontal), units mil",
    "outline_polygon": r["outlines"][0]["polygon"],
    "chips": {},
    "pads_measured": r["uPads"],
}
for c in r["comps"]:
    if c["des"] and c["des"].startswith("U"):
        backup["chips"][c["des"]] = {"x": c["x"], "y": c["y"], "rot": c["rot"], "primId": c["primId"]}
out = r"D:\Document\tempPrj\74Series-CNN\B02_TIMING_chip_layout_backup_20261119.json"
with open(out, "w") as f:
    json.dump(backup, f, indent=1)
print("backup written:", out, "chips:", len(backup["chips"]))
