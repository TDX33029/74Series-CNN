"""Generate docs/BOARD_HANDOFF.md: the conversion brief for the 12 boards.

The next step is converting each board's KiCad sheets to JLC EDA.  This script
collects, per board:

  * the module sheets and the connector sheet;
  * the header references and pinout file;
  * the external net list (must appear on the connector);
  * the internal net list (must NOT appear on the connector).

It also writes a copy-paste instruction block for the conversion session.

Run after build_top.py (needs the final pinout CSV):
    python tools/gen_board_handoff.py
"""
from __future__ import annotations

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from backplane import POWER_NETS, natural_key  # noqa: E402
from build_boards import BOARDS, compute_external  # noqa: E402

DOC = os.path.join(PROJECT_DIR, "docs", "BOARD_HANDOFF.md")
PINOUT = os.path.join(PROJECT_DIR, "output", "backplane", "backplane_pinout.csv")
MANIFEST = os.path.join(PROJECT_DIR, "output", "boards", "BOARD_MANIFEST.csv")
NETS = os.path.join(PROJECT_DIR, "output", "boards", "backplane_nets.csv")


def sheet_nets(filename: str) -> set[str]:
    with open(os.path.join(PROJECT_DIR, filename), encoding="utf-8") as f:
        return set(re.findall(r'\(global_label "([^"]+)"', f.read()))


def read_pinout() -> dict[str, list[str]]:
    """{board sheet: [header refs in natural order]}"""
    refs: dict[str, set[str]] = {}
    with open(PINOUT, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            refs.setdefault(row["sheet"], set()).add(row["connector"])
    return {k: sorted(v, key=natural_key) for k, v in refs.items()}


def read_manifest() -> dict[str, dict[str, str]]:
    with open(MANIFEST, encoding="utf-8-sig", newline="") as f:
        return {row["board"]: row for row in csv.DictReader(f)}


def fmt_nets(nets: list[str], per_line: int = 6) -> str:
    if not nets:
        return "（无）"
    out = []
    for i in range(0, len(nets), per_line):
        out.append("、".join(f"`{n}`" for n in nets[i:i + per_line]))
    return "  \n".join(out)


def main() -> int:
    if not os.path.exists(PINOUT):
        print("missing", PINOUT, "- run tools/gen_backplane_csv.py first")
        return 1
    manifest = read_manifest()
    headers = read_pinout()
    external, net_boards = compute_external(BOARDS)

    lines = [
        "# 12 板卡交接说明（Convert to JLC EDA）",
        "",
        "本文件给下一个负责把 KiCad 图页转成嘉立创 EDA 的对话使用。",
        "设计已经完成板卡化；转换时**只重画、不改网络名、不改连接关系**。",
        "",
        "## 0. 可直接复制的指令",
        "",
        "```text",
        "把 Cache/CNN_74xx_System 里的 12 张板卡逐张转成嘉立创 EDA 工程。",
        "板卡清单见 output/boards/BOARD_MANIFEST.csv，每板的图页、排针号、",
        "对外网络和板内网络见 docs/BOARD_HANDOFF.md。",
        "要求：",
        "1. 每张板卡一个独立工程，图页按清单原样保留；不要合并板卡。",
        "2. 全局标签按原网络名改成 EDA 网络标签，禁止重命名，尤其是",
        "   FC1_*/FC2_*/POOL1_*/POOL2_*/C1_*/C2_* 前缀。",
        "3. 每板的 Bxx_Conn 页只放 2x20P 排针，引脚按",
        "   output/backplane/<board>_Conn_backplane.csv 逐个连接；",
        "   电源脚固定 1-4=+5V、5-8=+3V3(预留)、9-14=GND、15-40=信号。",
        "4. 板内网络（各引擎 ACC/REQ 对、IN_DATA1/2、SCORE_DATA）",
        "   不要引到排针；它们只在同一块板的两张图之间连接。",
        "5. 元件位号保持 KiCad 重新编号后的值（U5001…、J20401…），",
        "   不要重新从 U1 开始编号，否则 BOM 与底板表对不上。",
        "6. 转换完成后按 output/boards/backplane_nets.csv 逐网核对：",
        "   每个网络出现的板卡集合必须与表中一致。",
        "```",
        "",
        "## 1. 板卡总表",
        "",
        "| 板卡 | 名称 | 图页 | 排针 | 对外网络 |",
        "|---|---|---|---|---|",
    ]
    for bid, name, func, sheets, stage in BOARDS:
        hdr = headers.get(f"B{bid}_Conn", [])
        hdr_s = f"{hdr[0]}..{hdr[-1]}（{len(hdr)} 片）" if len(hdr) > 1 else (
            hdr[0] if hdr else "-")
        lines.append(
            f"| B{bid} | {name} | {', '.join('`'+s+'`' for s in sheets)} | "
            f"{hdr_s} | {len(external[bid])} |"
        )

    lines.extend([
        "",
        "## 2. 逐板说明",
        "",
    ])

    for bid, name, func, sheets, stage in BOARDS:
        ext = external[bid]
        own: set[str] = set()
        for s in sheets:
            own |= sheet_nets(s)
        internal = sorted(own - set(ext) - POWER_NETS,
                          key=lambda n: (n.lower(), n))
        hdr = headers.get(f"B{bid}_Conn", [])
        lines.extend([
            f"### B{bid} {name}",
            "",
            f"- 功能：{func}",
            f"- 阶段：{stage}",
            f"- 图页：{', '.join('`'+s+'`' for s in sheets)}、"
            f"`B{bid}_Conn.kicad_sch`",
            f"- 排针：{', '.join(hdr)}（2x20P，电源脚固定）",
            f"- 引脚表：`output/backplane/B{bid}_Conn_backplane.csv`",
            f"- 对外网络（{len(ext)}）：",
            "",
            fmt_nets(ext),
            "",
            f"- 板内网络（{len(internal)}，不上排针）：",
            "",
            fmt_nets(internal),
            "",
        ])

    lines.extend([
        "## 3. 转换时的固定约定",
        "",
        "- 电源脚：1–4 `+5V`、5–8 `+3V3`（预留，当前无负载）、9–14 `GND`。",
        "- 排针型号：`Connector_Generic:Conn_02x20_Odd_Even`，"
        "封装 `PinHeader_2x20_P2.54mm_Vertical`。",
        "- `FC_SEL`/`POOL_SEL` 只出现在 B01 与 B11，不再进引擎板；"
        "引擎变体已把选择脚固定为 0/1。",
        "- B11 的 `S11A_EngineMerge` 是板上 5 片 74HC157，不是跨板连接；"
        "转换时不要把它拆到别的板。",
        "- B03 的 FC2/POOL2 缓冲组（U58–U65）是板上三方态合并，"
        "不要误当成跨板直连。",
        "",
        "## 4. 核对清单",
        "",
        "- [ ] 12 个工程，共 32 张图页（模块图 + Bxx_Conn）。",
        "- [ ] 每板排针数与 `BOARD_MANIFEST.csv` 一致（合计 32 片）。",
        "- [ ] 每个排针 1–14 脚电源定义一致。",
        "- [ ] `backplane_nets.csv` 中 282 个网络的板卡集合逐一对上。",
        "- [ ] 板内网络没有出现在任何排针上。",
        "- [ ] 位号未重新编号。",
        "",
        "机器可读文件：",
        "",
        "- `output/boards/BOARD_MANIFEST.csv`：板卡 → 图页 → 网络数/排针数。",
        "- `output/boards/backplane_nets.csv`：网络 → 板卡集合。",
        "- `output/backplane/backplane_pinout.csv`：逐脚 net/role。",
        "- `output/bom/CNN_74xx_System_BOM.csv`：整机 BOM（1329 件）。",
    ])

    with open(DOC, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", DOC)
    print(f"  {len(BOARDS)} boards, "
          f"{sum(len(headers.get(f'B{b}_Conn', [])) for b, *_ in BOARDS)} headers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
