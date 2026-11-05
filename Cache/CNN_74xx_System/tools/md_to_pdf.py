"""Render a Markdown document to PDF through headless Edge/Chrome."""
from __future__ import annotations

import argparse
import base64
import datetime
import os
import re
import subprocess
import sys
import tempfile

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
html { -webkit-print-color-adjust: exact; }
body {
  font-family: "Segoe UI", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
  font-size: 10pt; line-height: 1.5; color: #1a1a1a; margin: 0;
}
.cover { page-break-after: always; padding-top: 55mm; text-align: left; }
.cover .kicker { font-size: 11pt; letter-spacing: 2px; color: #555; }
.cover h1 { font-size: 30pt; border: none; margin: 8mm 0 4mm 0; color: #0b2e59;
            page-break-before: avoid; }
.cover .sub { font-size: 13pt; color: #333; margin-bottom: 18mm; }
.cover .meta { font-size: 10pt; color: #444; line-height: 1.8; }
h1 { font-size: 19pt; color: #0b2e59; border-bottom: 2px solid #0b2e59;
     padding-bottom: 2mm; margin-top: 10mm; page-break-before: auto;
     page-break-after: avoid; }
h1.first { page-break-before: auto; }
h2 { font-size: 13.5pt; color: #123f73; margin-top: 7mm; page-break-after: avoid; }
h3 { font-size: 11.5pt; color: #123f73; margin-top: 5mm; page-break-after: avoid; }
p { margin: 2.2mm 0; text-align: justify; }
ul, ol { margin: 2mm 0 2mm 6mm; padding-left: 4mm; }
li { margin: 1mm 0; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 8.5pt; }
th { background: #e8eef7; color: #0b2e59; font-weight: 600; }
th, td { border: 1px solid #9aa7b8; padding: 1.6mm 2mm; vertical-align: top; }
tr { page-break-inside: avoid; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 8.8pt;
       background: #f2f4f7; padding: 0 1mm; border-radius: 2px; }
pre { background: #f6f8fa; border: 1px solid #d6dde6; border-left: 3px solid #2f5d8a;
      padding: 3mm; overflow-wrap: break-word; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.3pt; }
blockquote { border-left: 3px solid #c9a227; margin: 3mm 0; padding: 1mm 4mm;
             background: #fdf8e8; color: #3a3a3a; }
hr { border: none; border-top: 1px solid #ccc; margin: 6mm 0; }
.footer-note { margin-top: 12mm; font-size: 8.5pt; color: #666; }
img { display: block; max-width: 100%; height: auto; margin: 3mm auto;
      border: 1px solid #d6dde6; page-break-inside: avoid; }
p > img { text-align: center; }
p.caption, p > em:only-child { display: block; text-align: center;
      font-size: 8.5pt; color: #555; margin-top: -1mm; }
figure { margin: 3mm 0; page-break-inside: avoid; }
"""


def pick_browser() -> str:
    for b in BROWSERS:
        if os.path.exists(b):
            return b
    raise FileNotFoundError("No Edge/Chrome browser found")


def _embed_images(text: str, md_path: str) -> str:
    """Embed local images as data URIs so headless Chrome can render them."""
    base = os.path.dirname(os.path.abspath(md_path))

    def repl(m):
        alt, src = m.group(1), m.group(2).strip()
        if src.startswith(("data:", "http://", "https://")):
            return m.group(0)
        path = src
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(base, path))
        if not os.path.exists(path):
            print("WARN: image not found:", path, file=sys.stderr)
            return m.group(0)
        ext = os.path.splitext(path)[1].lower()
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".svg": "image/svg+xml"}.get(ext, "application/octet-stream")
        data = base64.b64encode(open(path, "rb").read()).decode("ascii")
        return f"![{alt}](data:{mime};base64,{data})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, text)


def convert(md_path: str, pdf_path: str, title: str, subtitle: str) -> None:
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    text = _embed_images(text, md_path)
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
        output_format="html5",
    )
    # The first h1 is the document title; drop it because the cover has it.
    body = body.replace("<h1", '<h1 class="first"', 1)
    now = datetime.date.today().isoformat()
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title><style>{CSS}</style></head><body>
<section class="cover">
  <div class="kicker">74-SERIES CNN HARDWARE PROJECT</div>
  <h1>{title}</h1>
  <div class="sub">{subtitle}</div>
  <div class="meta">
    Revision: V1.1<br>
    Date: {now}<br>
    Project: CNN_74xx_System<br>
    Scope: architecture, supervisor FSM, memory timing, simulation evidence, review checklist
  </div>
</section>
{body}
<div class="footer-note">Generated from {os.path.basename(md_path)}. Schematic PDFs and
ERC reports are in output/pdf and output/erc.</div>
</body></html>"""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8", newline="\n") as f:
        f.write(html)
        tmp = f.name
    try:
        browser = pick_browser()
        url = "file:///" + tmp.replace("\\", "/")
        out = os.path.abspath(pdf_path)
        cmd = [
            browser, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
            "--print-to-pdf=" + out, "--print-to-pdf-no-header",
            "--no-pdf-header-footer", url,
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        if p.returncode != 0 or not os.path.exists(out):
            raise RuntimeError(p.stderr or p.stdout or "browser print failed")
    finally:
        os.unlink(tmp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--title", default="74 系列 CNN 硬件说明手册")
    ap.add_argument("--subtitle", default="状态机、时序控制与模块验证（评审版）")
    args = ap.parse_args()
    convert(args.markdown, args.output, args.title, args.subtitle)
    import pymupdf
    doc = pymupdf.open(args.output)
    print(f"wrote {args.output}: {doc.page_count} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
