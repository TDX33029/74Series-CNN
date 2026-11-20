#!/usr/bin/env python3
"""Generate backup JSONs for B03-2_MEMORY from s1 inventory output."""
import json, io, os

SRC = r"D:\Document\tempPrj\74Series-CNN\tools\b03_2_work\s1_out.json"
OUT1 = r"D:\Document\tempPrj\74Series-CNN\B03-2_MEMORY_chip_layout_backup_v2_20261120.json"
OUT2 = r"D:\Document\tempPrj\74Series-CNN\B03-2_MEMORY_passives_backup_20261120.json"

with io.open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

comps = {c["des"]: {k: c[k] for k in ("x", "y", "rot", "layer")} for c in data["comps"]}

chips = {d: comps[d] for d in ["U4009","U4010","U4011","U4014","U4016","U4017","U4018","U4031","U4049"] if d in comps}
pass_pref = ("LED", "Q", "R", "RP")
passives = {d: comps[d] for d in comps if d.startswith(pass_pref)}

hdr = {"board": "B03-2_MEMORY", "pcb_uuid": "7f08bbdec72478d8", "date": "2026-11-20", "unit": "mil"}

with io.open(OUT1, "w", encoding="utf-8") as f:
    json.dump(dict(hdr, type="chip_layout_backup_v2", count=len(chips), components=chips), f, ensure_ascii=False, indent=1)
with io.open(OUT2, "w", encoding="utf-8") as f:
    json.dump(dict(hdr, type="passives_backup", count=len(passives), components=passives), f, ensure_ascii=False, indent=1)
print("chips:", len(chips), "->", OUT1)
print("passives:", len(passives), "->", OUT2)
missing = [d for d in ["U4009","U4010","U4011","U4014","U4016","U4017","U4018","U4031","U4049"] if d not in comps]
print("missing chips:", missing)
