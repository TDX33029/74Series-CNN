"""Merge the manual, all schematic PDFs and module reports into one review PDF."""
from __future__ import annotations

import os
import subprocess
import sys

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PDF_DIR = os.path.join(PROJECT_DIR, "output", "pdf")
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")
OUT = os.path.join(PDF_DIR, "CNN_74xx_Review_Package.pdf")
PY = sys.executable

REPORTS = [
    ("Final status matrix", os.path.join(DOCS_DIR, "FINAL_STATUS.md")),
    ("Integration notes", os.path.join(DOCS_DIR, "INTEGRATION_NOTES.md")),
    ("Module connection matrix", os.path.join(DOCS_DIR, "CONNECTION_MATRIX.md")),
    ("Pool / Argmax report", os.path.join(DOCS_DIR, "REPORT_Pool_Argmax.md")),
    ("Memories / Top IO report", os.path.join(DOCS_DIR, "REPORT_Memories_TopIO.md")),
    ("Conv / FC report", os.path.join(DOCS_DIR, "REPORT_CONV_FC.md")),
    ("V2 simple requant", os.path.join(DOCS_DIR, "REQUANT_SIMPLE_V2.md")),
    ("Five-model joint review", os.path.join(PROJECT_DIR, "output", "model_reviews", "FINAL_JOINT_REVIEW.md")),
    ("F1/F5 repair report", os.path.join(PROJECT_DIR, "output", "model_reviews", "repair_f1f5", "REPAIR_REPORT.md")),
    ("M-12 repair report", os.path.join(PROJECT_DIR, "output", "model_reviews", "repair_m12", "REPAIR_REPORT.md")),
    ("S11 bus fabric repair report", os.path.join(PROJECT_DIR, "output", "model_reviews", "repair_bus", "REPAIR_REPORT.md")),
    ("S12 data assembly report", os.path.join(PROJECT_DIR, "output", "model_reviews", "repair_s12", "REPAIR_REPORT.md")),
    ("Argmax 4-byte transaction report", os.path.join(PROJECT_DIR, "output", "model_reviews", "repair_argmax4", "REPAIR_REPORT.md")),
    ("S11 bus fabric plan", os.path.join(DOCS_DIR, "BUS_FABRIC_REPAIR_PLAN.md")),
    ("Requant / LUT expansion plan", os.path.join(DOCS_DIR, "REQUANT_LUT_EXPANSION_PLAN.md")),
]

SHEETS = [
    ("S00 Top level", "CNN_74xx_System.pdf"),
    ("S01 Supervisor FSM", "S01_Supervisor.pdf"),
    ("S02 Memory timing", "S02_Timing.pdf"),
    ("S04 Memories", "S04_Memories.pdf"),
    ("S05 Pool", "S05_Pool.pdf"),
    ("S06 Argmax", "S06_Argmax.pdf"),
    ("S07 Conv1", "S07_Conv1.pdf"),
    ("S08 Conv2", "S08_Conv2.pdf"),
    ("S09 FC1/FC2", "S09_FC.pdf"),
    ("S10 Top IO", "S10_Top_IO.pdf"),
    ("S11 Bus fabric", "S11_BusFabric.pdf"),
    ("S12 Data assembly", "S12_DataAssembly.pdf"),
    ("S13 Conv1 simple requant", "S13_Requant_C1.pdf"),
    ("S15 Conv2 simple requant", "S15_Requant_C2.pdf"),
    ("S17 FC1 simple requant / FC2 raw signed32", "S17_Requant_FC.pdf"),
    ("LUT multiplier", "S_LUT_Mult_1.pdf"),
]


def ensure_report_pdf(title: str, md: str) -> str | None:
    if not os.path.exists(md):
        print("missing report:", md)
        return None
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)
    name = safe + ".pdf"
    out = os.path.join(PDF_DIR, name)
    if (not os.path.exists(out)
            or os.path.getmtime(out) < os.path.getmtime(md)):
        subprocess.run([
            PY, os.path.join(HERE, "md_to_pdf.py"), md, "-o", out,
            "--title", title, "--subtitle", "模块交付与仿真证据",
        ], check=True)
    return out


def main() -> int:
    entries: list[tuple[str, str]] = []
    manual = os.path.join(PDF_DIR, "HW_MANUAL.pdf")
    if not os.path.exists(manual):
        subprocess.run([
            PY, os.path.join(HERE, "md_to_pdf.py"),
            os.path.join(DOCS_DIR, "HW_MANUAL.md"), "-o", manual,
        ], check=True)
    entries.append(("Hardware manual (FSM, timing, evidence)", manual))
    for title, filename in SHEETS:
        path = os.path.join(PDF_DIR, filename)
        if os.path.exists(path):
            entries.append((title, path))
        else:
            print("missing schematic PDF:", path)
    for title, md in REPORTS:
        out = ensure_report_pdf(title, md)
        if out:
            entries.append((title, out))

    out_doc = pymupdf.open()
    toc = []
    for title, path in entries:
        doc = pymupdf.open(path)
        start = out_doc.page_count
        if os.path.basename(path) == "CNN_74xx_System.pdf":
            # Only the S00 index page; the standalone S01-S10 PDFs follow in
            # review order and avoid duplicating the whole hierarchy.
            out_doc.insert_pdf(doc, from_page=0, to_page=0)
        else:
            out_doc.insert_pdf(doc)
        toc.append([1, title, start + 1])
        print(f"  p{start + 1:2d}  {title:45s} {os.path.basename(path)}")
        doc.close()
    out_doc.set_toc(toc)
    out_doc.set_metadata({
        "title": "74-Series CNN Hardware Review Package",
        "author": "74Series-CNN Project",
        "subject": "28x28 MNIST CNN - schematics, FSM/timing manual, simulation reports",
        "keywords": "74HC, CNN, KiCad, ngspice, supervisor FSM, memory timing",
    })
    out_doc.save(OUT, garbage=4, deflate=True)
    print(f"\nwrote {OUT}: {out_doc.page_count} pages, {len(toc)} bookmarks")
    out_doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
