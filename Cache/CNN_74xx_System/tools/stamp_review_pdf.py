"""Stamp page numbers and metadata on the review-guide PDF."""
from __future__ import annotations

import os
import sys

import pymupdf as fitz


def main(path: str) -> int:
    doc = fitz.open(path)
    n = doc.page_count
    for i, page in enumerate(doc):
        if i == 0:
            continue
        text = f"{i + 1} / {n}"
        w = fitz.get_text_length(text, fontname="helv", fontsize=8)
        x = (page.rect.width - w) / 2
        y = page.rect.height - 28
        page.insert_text((x, y), text, fontname="helv", fontsize=8,
                         color=(0.38, 0.38, 0.38))
    doc.set_metadata({
        "title": "74 系列 CNN 系统评审指南",
        "subject": "拓扑、端到端推理流程、S01 微码与引擎流水线（V2）",
        "author": "CNN_74xx_System project",
        "keywords": "74 series, CNN, KiCad, supervisor, microcode, requant, review",
        "creator": "tools/md_to_pdf.py + tools/stamp_review_pdf.py",
    })
    tmp = path + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, path)
    print(f"stamped {n} pages: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
