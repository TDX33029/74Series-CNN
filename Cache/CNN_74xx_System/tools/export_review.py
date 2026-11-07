"""Export ERC reports, per-sheet PDFs, BOM and preview PNGs for review."""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"
KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"

sys.path.insert(0, HERE)
from build_boards import BOARDS  # noqa: E402

SHEETS = [("CNN_74xx_System", "CNN_74xx_System.kicad_sch")]
for _bid, _name, _func, _mods, _stage in BOARDS:
    for _f in _mods:
        SHEETS.append((os.path.splitext(_f)[0], _f))
    SHEETS.append((f"B{_bid}_Conn", f"B{_bid}_Conn.kicad_sch"))
SHEETS.append(("S_LUT_Mult_1", "S_LUT_Mult_1.kicad_sch"))

OUT_ERC = os.path.join(PROJECT_DIR, "output", "erc")
OUT_PDF = os.path.join(PROJECT_DIR, "output", "pdf")
OUT_BOM = os.path.join(PROJECT_DIR, "output", "bom")
OUT_PNG = os.path.join(PROJECT_DIR, "output", "preview")


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=PROJECT_DIR, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def erc_summary(report: str) -> str:
    if not os.path.exists(report):
        return "ERC report missing"
    with open(report, encoding="utf-8", errors="replace") as f:
        text = f.read()
    m = re.search(r"ERC messages:\s*(\d+)\s+Errors\s+(\d+)\s+Warnings\s+(\d+)", text)
    if m:
        return f"{m.group(1)} violation(s), {m.group(2)} error(s), {m.group(3)} warning(s)"
    m = re.search(r"(\d+)\s+violations? found", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)} violation(s)"
    return "summary not found"


def main() -> int:
    for d in (OUT_ERC, OUT_PDF, OUT_BOM, OUT_PNG):
        os.makedirs(d, exist_ok=True)

    have = [(n, f) for n, f in SHEETS if os.path.exists(os.path.join(PROJECT_DIR, f))]
    missing = [n for n, f in SHEETS if not os.path.exists(os.path.join(PROJECT_DIR, f))]
    if missing:
        print("pending sheets:", ", ".join(missing))

    failures = 0
    for name, filename in have:
        src = os.path.join(PROJECT_DIR, filename)
        rpt = os.path.join(OUT_ERC, name + ".rpt")
        print(f"== {name} ==")
        p = run([KICAD_CLI, "sch", "erc", "--severity-all", "--exit-code-violations",
                 "-o", rpt, src])
        if p.returncode not in (0, 5):  # 5 = ERC violations found
            print("  ERC command failed:", p.stderr.strip() or p.stdout.strip())
            failures += 1
        print("  ERC:", erc_summary(rpt))

        pdf = os.path.join(OUT_PDF, name + ".pdf")
        p = run([KICAD_CLI, "sch", "export", "pdf", "-o", pdf, src])
        if p.returncode != 0:
            print("  PDF export failed:", p.stderr.strip() or p.stdout.strip())
            failures += 1
        else:
            print("  PDF:", os.path.relpath(pdf, PROJECT_DIR))

    root = os.path.join(PROJECT_DIR, "CNN_74xx_System.kicad_sch")
    if os.path.exists(root):
        top_rpt = os.path.join(PROJECT_DIR, "output", "top-erc-simple.rpt")
        p = run([KICAD_CLI, "sch", "erc", "--severity-all",
                 "-o", top_rpt, root])
        if p.returncode not in (0, 5):
            print("top ERC command failed:", p.stderr.strip() or p.stdout.strip())
            failures += 1
        print("top ERC:", erc_summary(top_rpt))
        bom = os.path.join(OUT_BOM, "CNN_74xx_System_BOM.csv")
        p = run([
            KICAD_CLI, "sch", "export", "bom", "-o", bom,
            "--fields", "Reference,Value,Footprint,QUANTITY",
            "--labels", "Refs,Value,Footprint,Qty",
            "--group-by", "Value,Footprint",
            "--sort-field", "Reference",
            root,
        ])
        if p.returncode != 0:
            print("BOM export failed:", p.stderr.strip() or p.stdout.strip())
            failures += 1
        else:
            print("BOM:", os.path.relpath(bom, PROJECT_DIR))

    # PNG previews for quick visual review (optional dependency).
    if "--no-preview" in sys.argv:
        return 0 if failures == 0 else 1
    try:
        import pymupdf
        for name, _ in have:
            pdf = os.path.join(OUT_PDF, name + ".pdf")
            if not os.path.exists(pdf):
                continue
            doc = pymupdf.open(pdf)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=100)
                pix.save(os.path.join(OUT_PNG, f"{name}_p{i + 1}.png"))
            doc.close()
        print("preview PNGs written to output/preview")
    except Exception as exc:  # noqa: BLE001
        print("preview skipped:", exc)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
