"""Build the 12 board connector sheets and the board manifest.

Option A replaces the 14 reusable module sheets with 12 concrete boards.  Every
board owns the module sheets listed in BOARDS below; the two sheets of an
engine board are wired through their existing global labels, so the only new
artwork is the backplane connector sheet.

The external net list is *computed*, not hand-written:

  * collect every global label on the board's module sheets;
  * keep a net only if it also appears on a sheet belonging to another board;
  * drop power nets (the connector's fixed power pins handle +5V/+3V3/GND).

That rule keeps engine-internal nets such as FC1_ACC[31:0] (S09_FC1 + S17_FC1)
or IN_DATA1[7:0] (S05_Pool1 + S12A_PoolLatch1) off the backplane, while every
signal that really leaves the board gets a pin.

Outputs:
    B01_Conn.kicad_sch .. B12_Conn.kicad_sch
    output/boards/BOARD_MANIFEST.csv
    output/boards/backplane_nets.csv
    output/backplane/<board>_Conn_backplane.csv  (per-sheet pinout)
    output/backplane/backplane_pinout.csv        (all boards combined)
    docs/BOARD_PARTITION.md

Run after the module/variant builders and before build_top.py:
    python build_boards.py
"""
from __future__ import annotations

import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backplane import POWER_NETS, place_backplane
from kicad_gen import Schematic, default_registry, footprint_for

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"
OUT_DIR = os.path.join(PROJECT_DIR, "output", "boards")
BACKPLANE_DIR = os.path.join(PROJECT_DIR, "output", "backplane")
DOC_FILE = os.path.join(PROJECT_DIR, "docs", "BOARD_PARTITION.md")

# (id, slot title, function, [sheet files], stage note)
BOARDS = [
    ("01", "SUPERVISOR", "Global supervisor FSM, microcode ROM, watchdog",
     ["S01_Supervisor.kicad_sch"],
     "sequencer: START/BUSY/DONE, stage starts, FC_SEL/POOL_SEL"),
    ("02", "TIMING", "Memory timing controller SETUP/WAIT/CAPTURE/HOLD/RELEASE",
     ["S02_Timing.kicad_sch"],
     "single owner of MEM_nCE/nOE/nWE and the ACK handshake"),
    ("03", "MEMORY", "7x 6264 SRAM + 12x 28C256 + 8x 27C512 LUT/map storage",
     ["S04_Memories.kicad_sch"],
     "all feature maps, weights, biases, quant params and LUT/map ROMs"),
    ("04", "CONV1", "5x5x1 -> 8ch convolution engine + ACC>>8 requant",
     ["S07_Conv1.kicad_sch", "S13_Requant_C1.kicad_sch"],
     "C1 stage; requant is on-board, C1_ACC never leaves the board"),
    ("05", "POOL1", "2x2 stride-2 max pool 12x12x8 -> 6x6x8",
     ["S05_Pool1.kicad_sch", "S12A_PoolLatch1.kicad_sch"],
     "P1 stage; POOL_SEL tied 0, IN_DATA1 byte buffer on-board"),
    ("06", "CONV2", "3x3x8 -> 16ch convolution engine + ACC>>9 requant",
     ["S08_Conv2.kicad_sch", "S15_Requant_C2.kicad_sch"],
     "C2 stage; requant is on-board, C2_ACC never leaves the board"),
    ("07", "POOL2", "2x2 stride-2 max pool 10x10x16 -> 5x5x16",
     ["S05_Pool2.kicad_sch", "S12A_PoolLatch2.kicad_sch"],
     "P2 stage; POOL_SEL tied 1, IN_DATA2 byte buffer on-board"),
    ("08", "FC1", "400 -> 32 fully connected + FC1 uint8 requant",
     ["S09_FC1.kicad_sch", "S17_FC1.kicad_sch"],
     "FC1 stage; FC_SEL tied 0, FC1_ACC/FC1_REQ_* stay on-board"),
    ("09", "FC2", "32 -> 10 fully connected + FC2 raw signed32 requant",
     ["S09_FC2.kicad_sch", "S17_FC2.kicad_sch"],
     "FC2 stage; FC_SEL tied 1, FC2_ACC/FC2_REQ_* stay on-board"),
    ("10", "ARGMAX", "10-way signed-32 argmax + 32-bit score staging",
     ["S06_Argmax.kicad_sch", "S12B_ScoreLatch.kicad_sch"],
     "final stage; four score bytes assembled on-board"),
    ("11", "BUSFAB", "Master/region encode, map ROM, REQ/WE merge, engine merge",
     ["S11_BusFabric.kicad_sch", "S11A_EngineMerge.kicad_sch"],
     "arbitration only; FC1/FC2 and POOL1/POOL2 are muxed into the S11 slots"),
    ("12", "HOSTIO", "Host connector, clock/reset, image and weight load ports",
     ["S10_Top_IO.kicad_sch"],
     "the only board with the external host interface"),
]

GLOBAL_RE = re.compile(r'\(global_label "([^"]+)"')


def sheet_nets(filename: str) -> set[str]:
    with open(os.path.join(PROJECT_DIR, filename), encoding="utf-8") as f:
        text = f.read()
    return set(GLOBAL_RE.findall(text))


def compute_external(boards) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    """Return {board_id: sorted external nets} and {net: {board_id}}."""
    per_board: dict[str, set[str]] = {}
    for bid, _name, _func, sheets, _stage in boards:
        nets: set[str] = set()
        for s in sheets:
            nets |= sheet_nets(s)
        per_board[bid] = {n for n in nets if n not in POWER_NETS}

    net_boards: dict[str, set[str]] = {}
    for bid, nets in per_board.items():
        for n in nets:
            net_boards.setdefault(n, set()).add(bid)

    external = {}
    for bid, nets in per_board.items():
        external[bid] = sorted(n for n in nets if len(net_boards[n]) >= 2)
    return external, net_boards


def board_label(bid: str) -> str:
    return f"B{bid}_Conn"


def build_connector(bid: str, name: str, func: str, sheets: list[str],
                    nets: list[str]) -> tuple[int, int]:
    reg = default_registry()
    sh = Schematic(
        reg, project=PROJECT, instance_path="/__ROOT_UUID__",
        title=f"B{bid}_Conn - {name} board backplane connector",
        paper="A4",
    )
    sh.add_text(f"B{bid} {name}  -  BACKPLANE CONNECTOR", 15, 12,
                size=2.6, justify="left top", bold=True)
    sh.add_text(
        f"Board function: {func}\n"
        f"Module sheets on this board: {', '.join(sheets)}\n"
        f"External signals: {len(nets)} (power pins are fixed on every header).",
        15, 20, size=1.15, justify="left top",
    )
    sh.add_text(
        "Pinout: 1-4 +5V, 5-8 +3V3 (reserved), 9-14 GND, 15-40 signals.\n"
        "Signal order follows the net grouping in tools/backplane.py; the "
        "machine-readable map is output/backplane/.\n"
        "Internal board nets (engine ACC/REQ pairs, IN_DATA byte buses) are "
        "deliberately absent: they never leave the board.",
        15, 28, size=1.15, justify="left top",
    )
    headers = place_backplane(sh, board_label(bid), nets=nets,
                              y=70.0, pitch=60.0, note=False)
    sh.add_text(
        f"Backplane headers on this board: {headers} x 2x20P "
        "(J refs are assigned by renumber_refs.py).\n"
        "2x20P pinout: 1-4 +5V, 5-8 +3V3 (reserved), 9-14 GND, 15-40 signals.\n"
        "Signal positions are per board; see output/backplane/ for the pinout.",
        15, 39, size=1.0, justify="left top",
    )
    sh.write(os.path.join(PROJECT_DIR, f"{board_label(bid)}.kicad_sch"))
    return headers, len(nets)


def write_manifests(rows, external, net_boards) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(os.path.join(OUT_DIR, "BOARD_MANIFEST.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["board", "name", "function", "sheets", "stage",
                    "external_nets", "headers", "signal_pins"])
        w.writerows(rows)

    with open(os.path.join(OUT_DIR, "backplane_nets.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["net", "boards", "board_count"])
        for net in sorted(net_boards, key=lambda n: (n.lower(), n)):
            bs = sorted(net_boards[net])
            if len(bs) < 2:
                continue
            w.writerow([net, ";".join(f"B{b}" for b in bs), len(bs)])

    # Combined pinout: concatenate the per-sheet CSVs place_backplane wrote.
    os.makedirs(BACKPLANE_DIR, exist_ok=True)
    combined = os.path.join(BACKPLANE_DIR, "backplane_pinout.csv")
    with open(combined, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["sheet", "connector", "pin", "net", "role"])
        for bid, *_rest in BOARDS:
            src = os.path.join(BACKPLANE_DIR,
                               f"{board_label(bid)}_backplane.csv")
            with open(src, encoding="utf-8-sig", newline="") as g:
                r = csv.reader(g)
                next(r, None)
                w.writerows(r)


def write_doc(rows) -> None:
    os.makedirs(os.path.dirname(DOC_FILE), exist_ok=True)
    lines = [
        "# 12 板卡划分（方案 A）",
        "",
        "每块板卡是独立的物理板；引擎不再跨阶段复用，层与层之间的差异用板上"
        "固定连线和独立网络前缀实现。底板只做无源互连，引脚定义见 "
        "`output/backplane/backplane_pinout.csv`。",
        "",
        "| 板卡 | 名称 | 功能 | 图页 | 对外网络 | 排针 |",
        "|---|---|---|---|---|---|",
    ]
    for bid, name, func, sheets, stage, nets, headers, pins in rows:
        lines.append(
            f"| B{bid} | {name} | {func} | {', '.join(sheets)} | {nets} | "
            f"{headers} x 2x20P ({pins} pins) |"
        )
    lines.extend([
        "",
        "## 电源引脚（所有排针一致）",
        "",
        "| 引脚 | 网络 |",
        "|---|---|",
        "| 1-4 | +5V |",
        "| 5-8 | +3V3（预留） |",
        "| 9-14 | GND |",
        "| 15-40 | 信号（每排针 26 根） |",
        "",
        "## 板内网络（不上底板）",
        "",
        "- `C1_ACC*` / `C1_REQ_*`：B04（S07+S13）",
        "- `C2_ACC*` / `C2_REQ_*`：B06（S08+S15）",
        "- `FC1_ACC*` / `FC1_REQ_*`：B08（S09_FC1+S17_FC1）",
        "- `FC2_ACC*` / `FC2_REQ_*`：B09（S09_FC2+S17_FC2）",
        "- `IN_DATA1*`：B05（S05_Pool1+S12A_PoolLatch1）",
        "- `IN_DATA2*`：B07（S05_Pool2+S12A_PoolLatch2）",
        "- `SCORE_DATA*`：B10（S06+S12B_ScoreLatch）",
        "",
        "## 复用消除后的固定选择",
        "",
        "- POOL1 板 `POOL_SEL` 固定 0；POOL2 板 `POOL_SEL` 固定 1。",
        "- FC1 板 `FC_SEL` 固定 0；FC2 板 `FC_SEL` 固定 1。",
        "- `FC_SEL` / `POOL_SEL` 仍由 S01 送 B11 的 map ROM，用于选择"
        "权重/输出窗口；它们不再进入引擎板。",
        "- B11 的 S11A 用 `FC2_BUSY` / `POOL2_BUSY` 把两套引擎信号二选一"
        "送回 S11 的单一 FC/POOL 槽位。",
        "",
        "## 工程文件",
        "",
        "- 交接说明（转嘉立创 EDA）：`docs/BOARD_HANDOFF.md`",
        "- 板卡清单：`output/boards/BOARD_MANIFEST.csv`",
        "- 网络-板卡矩阵：`output/boards/backplane_nets.csv`",
        "- 逐引脚定义：`output/backplane/backplane_pinout.csv`",
    ])
    with open(DOC_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    missing = [s for _b in BOARDS for s in _b[3]
               if not os.path.exists(os.path.join(PROJECT_DIR, s))]
    if missing:
        print("missing module sheets:")
        for s in missing:
            print("  ", s)
        print("run the module builders first")
        return 1

    external, net_boards = compute_external(BOARDS)
    rows = []
    for bid, name, func, sheets, stage in BOARDS:
        headers, count = build_connector(bid, name, func, sheets,
                                         external[bid])
        rows.append([f"B{bid}", name, func, ";".join(sheets), stage,
                     count, headers, headers * 26])
        print(f"B{bid} {name:10s} {len(sheets)} sheet(s) "
              f"{count:3d} nets -> {headers} header(s)")

    write_manifests(rows, external, net_boards)
    write_doc(rows)
    print("wrote output/boards/BOARD_MANIFEST.csv")
    print("wrote output/boards/backplane_nets.csv")
    print("wrote output/backplane/backplane_pinout.csv")
    print("wrote docs/BOARD_PARTITION.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
